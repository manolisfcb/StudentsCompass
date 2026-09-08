"""The CV analysis queue under genuine concurrency.

SQLite serialises writes through one connection, so it can show that the rules
are written correctly but never that they hold when two connections race. These
run on separate PostgreSQL connections:

* two simultaneous "analyze my CV" requests end with **one** job, and both
  callers are told the same ``job_id``;
* two workers reaching for the same job — the request's background task and the
  durable runner — result in exactly one claim.
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
    import tests.conftest  # noqa: F401  (imports the full model set)
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


async def _seed_user_and_resume(session):
    from app.models.resumeModel import ResumeModel
    from app.models.userModel import User

    user = User(
        id=uuid.uuid4(),
        email=f"queue-{uuid.uuid4().hex[:8]}@example.invalid",
        hashed_password="x",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    session.add(user)
    await session.flush()
    resume = ResumeModel(
        id=uuid.uuid4(),
        user_id=user.id,
        view_url="https://example.invalid/cv",
        storage_file_id="resumes/user.pdf",
        original_filename="cv.pdf",
        folder_id="bucket",
    )
    session.add(resume)
    await session.commit()
    return user, resume


@pytest.mark.asyncio
async def test_simultaneous_requests_produce_one_job(schema, pg_sessionmaker, pg_two_sessions):
    from app.models.jobAnalysisModel import JobAnalysisModel
    from app.services.ai.cvAnalysisService import CVAnalysisService

    async with pg_sessionmaker() as setup:
        user, resume = await _seed_user_and_resume(setup)

    first, second = pg_two_sessions

    jobs = await asyncio.gather(
        CVAnalysisService(first).create_pending_analysis(user_id=user.id, resume_id=resume.id),
        CVAnalysisService(second).create_pending_analysis(user_id=user.id, resume_id=resume.id),
    )

    # Both callers poll the same job — the API's promise to the browser.
    assert jobs[0].id == jobs[1].id
    async with pg_sessionmaker() as reader:
        total = await reader.scalar(
            select(func.count(JobAnalysisModel.id)).where(JobAnalysisModel.user_id == user.id)
        )
    assert total == 1


@pytest.mark.asyncio
async def test_two_workers_racing_for_one_job_produce_one_claim(
    schema, pg_sessionmaker, pg_two_sessions
):
    from app.services.ai.cvAnalysisService import CVAnalysisService

    async with pg_sessionmaker() as setup:
        user, resume = await _seed_user_and_resume(setup)
        job = await CVAnalysisService(setup).create_pending_analysis(
            user_id=user.id, resume_id=resume.id
        )

    first, second = pg_two_sessions
    claims = await asyncio.gather(
        CVAnalysisService(first).claim_job(job.id),
        CVAnalysisService(second).claim_job(job.id),
    )

    assert sorted(claims) == [False, True]
    async with pg_sessionmaker() as reader:
        claimed = await CVAnalysisService(reader).get_job(job.id)
    assert claimed.attempts == 1, "a lost race must not consume an attempt"


@pytest.mark.asyncio
async def test_two_runners_recovering_the_same_stale_job_agree(
    schema, pg_sessionmaker, pg_two_sessions
):
    """Recovery is a decision about one row; two sweepers must not fight."""
    from app.models.jobAnalysisModel import JobStatus
    from app.services.ai.cvAnalysisService import CVAnalysisService

    async with pg_sessionmaker() as setup:
        user, resume = await _seed_user_and_resume(setup)
        service = CVAnalysisService(setup)
        job = await service.create_pending_analysis(user_id=user.id, resume_id=resume.id)
        await service.claim_job(job.id)
        stale = await service.get_job(job.id)
        stale.lease_expires_at = datetime.utcnow() - timedelta(seconds=1)
        await setup.commit()

    first, second = pg_two_sessions
    outcomes = await asyncio.gather(
        CVAnalysisService(first).recover_stale_jobs(),
        CVAnalysisService(second).recover_stale_jobs(),
    )

    assert sum(outcome["requeued"] for outcome in outcomes) == 1
    async with pg_sessionmaker() as reader:
        recovered = await CVAnalysisService(reader).get_job(job.id)
    assert recovered.status == JobStatus.PENDING
    assert recovered.lease_expires_at is None


@pytest.mark.asyncio
async def test_a_finished_job_frees_the_cv_for_the_next_one(schema, pg_sessionmaker):
    """The unique index constrains only *active* jobs, not the history."""
    from app.models.jobAnalysisModel import JobStatus
    from app.services.ai.cvAnalysisService import CVAnalysisService

    async with pg_sessionmaker() as session:
        user, resume = await _seed_user_and_resume(session)
        service = CVAnalysisService(session)

        for _ in range(3):
            job = await service.create_pending_analysis(user_id=user.id, resume_id=resume.id)
            await service.claim_job(job.id)
            finished = await service.get_job(job.id)
            finished.status = JobStatus.COMPLETED
            finished.keywords = "python"
            finished.lease_expires_at = None
            finished.completed_at = datetime.utcnow()
            await session.commit()

        from app.models.jobAnalysisModel import JobAnalysisModel

        total = await session.scalar(
            select(func.count(JobAnalysisModel.id)).where(JobAnalysisModel.user_id == user.id)
        )
    assert total == 3
