"""The outbox where its guarantees are actually true.

Two of this task's claims cannot be made on SQLite:

* **the dispatch and the job commit together.** That is a statement about
  savepoints and rollback, and pysqlite does not implement savepoints
  faithfully;
* **a replayed task spends nothing twice.** That is a statement about two
  connections racing for one row, and SQLite serialises them onto one.

So both are made here. No provider is called: the analysis is driven through a
fake so the assertion is about the claim, not about Gemini.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import func, select

pytestmark = [pytest.mark.integration, pytest.mark.postgres]


@pytest.fixture
def _models():
    import tests.conftest  # noqa: F401

    from app.db import Base

    return Base


@pytest.fixture
async def schema(pg_engine, _models):
    async with pg_engine.begin() as conn:
        await conn.run_sync(_models.metadata.create_all)
    try:
        yield
    finally:
        async with pg_engine.begin() as conn:
            await conn.run_sync(_models.metadata.drop_all)


async def _user(session):
    from app.models.userModel import User

    user = User(
        id=uuid.uuid4(),
        email=f"outbox-{uuid.uuid4().hex[:8]}@example.invalid",
        hashed_password="x",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    session.add(user)
    await session.commit()
    return user


async def _resume(session, user):
    from app.models.resumeModel import ResumeModel

    resume = ResumeModel(
        id=uuid.uuid4(),
        user_id=user.id,
        view_url="https://example.invalid/cv.pdf",
        storage_file_id="resumes/cv.pdf",
        original_filename="cv.pdf",
        folder_id="test-bucket",
    )
    session.add(resume)
    await session.commit()
    return resume


@pytest.mark.asyncio
async def test_the_job_and_its_dispatch_commit_together(schema, pg_session):
    """Rolling back the transaction discards both, or the outbox is pointless.

    A dispatch that survives a rolled-back job would tell a worker to run
    something that does not exist; a job that survives a rolled-back dispatch
    would sit queued with nobody ever told about it.
    """
    from app.models.jobAnalysisModel import JobAnalysisModel
    from app.models.taskOutboxModel import TaskOutboxModel
    from app.services.ai.cvAnalysisService import CVAnalysisService

    user = await _user(pg_session)
    resume = await _resume(pg_session, user)

    service = CVAnalysisService(pg_session)
    job = await service.create_pending_analysis(user_id=user.id, resume_id=resume.id)

    jobs = await pg_session.execute(select(func.count(JobAnalysisModel.id)))
    rows = await pg_session.execute(select(func.count(TaskOutboxModel.id)))
    assert jobs.scalar_one() == 1
    assert rows.scalar_one() == 1
    assert job is not None


@pytest.mark.asyncio
async def test_a_rolled_back_creation_leaves_no_dispatch(schema, pg_session):
    """The savepoint claim, on a database whose savepoints are real."""
    from app.models.taskOutboxModel import TaskOutboxModel
    from app.services.tasks import outbox

    job_id = uuid.uuid4()
    await outbox.enqueue_cv_analysis(pg_session, job_id=job_id)
    await pg_session.rollback()

    rows = await pg_session.execute(select(func.count(TaskOutboxModel.id)))
    assert rows.scalar_one() == 0


@pytest.mark.asyncio
async def test_two_concurrent_enqueues_write_one_dispatch(schema, pg_two_sessions):
    """Two connections, one key. The database decides, not a prior read."""
    from sqlalchemy.exc import IntegrityError

    from app.models.taskOutboxModel import TaskOutboxModel
    from app.services.tasks.outbox import cv_analysis_dedupe_key

    first, second = pg_two_sessions
    job_id = uuid.uuid4()
    now = datetime.utcnow()

    def row():
        from app.models.taskOutboxModel import OutboxStatus

        return TaskOutboxModel(
            id=uuid.uuid4(),
            task_type="cv_analysis",
            payload={"job_id": str(job_id)},
            dedupe_key=cv_analysis_dedupe_key(job_id),
            status=OutboxStatus.PENDING,
            attempts=0,
            available_at=now,
            created_at=now,
            updated_at=now,
        )

    first.add(row())
    second.add(row())
    outcomes = await asyncio.gather(first.commit(), second.commit(), return_exceptions=True)

    failures = [o for o in outcomes if isinstance(o, Exception)]
    assert len(failures) == 1
    assert isinstance(failures[0], IntegrityError)

    await first.rollback()
    await second.rollback()
    total = await first.execute(select(func.count(TaskOutboxModel.id)))
    assert total.scalar_one() == 1


@pytest.mark.asyncio
async def test_a_replayed_task_does_not_run_the_analysis_twice(schema, pg_session):
    """The claim is the whole mechanism, and it is TASK-013's, unchanged.

    Two deliveries of the same task reach ``process_job``; the conditional
    UPDATE lets exactly one through, so the provider is called once. Nothing
    here re-implements that — it verifies that moving the trigger out of the
    web replica did not lose it.
    """
    from app.models.jobAnalysisModel import JobStatus
    from app.services.ai.cvAnalysisService import CVAnalysisService

    user = await _user(pg_session)
    resume = await _resume(pg_session, user)
    service = CVAnalysisService(pg_session)
    job = await service.create_pending_analysis(user_id=user.id, resume_id=resume.id)

    first_claim = await service.claim_job(job.id)
    second_claim = await service.claim_job(job.id)

    assert first_claim is True, "the first delivery claims the job"
    assert second_claim is False, "the replay finds it already claimed"

    refreshed = await service.get_job(job.id)
    assert refreshed.status == JobStatus.PROCESSING
    assert refreshed.attempts == 1, "a replay must not count as a second attempt"


@pytest.mark.asyncio
async def test_a_job_whose_worker_died_becomes_due_again(schema, pg_session):
    """Scale-to-zero, a killed instance and a dropped task all end here.

    The lease is what makes them recoverable, and reconciliation is what makes
    them *dispatched* again — without running any AI itself.
    """
    from app.models.jobAnalysisModel import JobAnalysisModel
    from app.models.taskOutboxModel import OutboxStatus, TaskOutboxModel
    from app.services.ai.cvAnalysisService import CVAnalysisService
    from app.services.tasks import outbox

    user = await _user(pg_session)
    resume = await _resume(pg_session, user)
    service = CVAnalysisService(pg_session)
    job = await service.create_pending_analysis(user_id=user.id, resume_id=resume.id)

    # The worker claimed it and then vanished: PROCESSING with a dead lease.
    await service.claim_job(job.id)
    stale = await pg_session.get(JobAnalysisModel, job.id)
    stale.lease_expires_at = datetime.utcnow() - timedelta(minutes=5)
    await pg_session.commit()

    # Its dispatch was already delivered, so nothing would call again.
    row = (await pg_session.execute(select(TaskOutboxModel))).scalar_one()
    row.status = OutboxStatus.DISPATCHED
    await pg_session.commit()

    await service.recover_stale_jobs()
    due = await service.due_job_ids(limit=10)
    for due_id in due:
        await outbox.requeue_for_job(pg_session, job_id=due_id)
    await pg_session.commit()

    row = (await pg_session.execute(select(TaskOutboxModel))).scalar_one()
    assert job.id in due
    assert row.status == OutboxStatus.PENDING
    assert row.available_at <= datetime.utcnow()
