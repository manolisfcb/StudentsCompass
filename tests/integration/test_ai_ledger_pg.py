"""The AI ledger under real concurrency and real constraints.

Three things SQLite cannot answer, all of them load-bearing for the accounting:

* the partial unique index over ``(reference_type, reference_id)`` — the thing
  that makes a charge idempotent — actually rejects a second committed row while
  leaving reservations and released history alone;
* two sessions committing the same result at the same time end with one charge,
  decided by the server rather than by a check that both passed;
* a reservation abandoned by a dead process is reclaimed exactly once, even when
  several sessions notice the expired lease together.

Each test builds and drops the mapped schema on the lane database.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

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


async def _make_user(session):
    from app.models.userModel import User

    user = User(
        id=uuid.uuid4(),
        email=f"ledger-{uuid.uuid4().hex[:8]}@example.invalid",
        hashed_password="x",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    session.add(user)
    await session.commit()
    return user


async def _committed_count(session, user_id, reference_id) -> int:
    from app.models.aiUsageModel import AIUsageEventModel, AIUsageStatus

    return int(
        await session.scalar(
            select(func.count(AIUsageEventModel.id)).where(
                AIUsageEventModel.user_id == user_id,
                AIUsageEventModel.reference_id == reference_id,
                AIUsageEventModel.status == AIUsageStatus.COMMITTED,
            )
        )
    )


@pytest.mark.asyncio
async def test_the_reference_index_rejects_a_second_charge(pg_sessionmaker, schema):
    from app.models.aiUsageModel import AIUsageEventModel, AIUsageStatus

    async with pg_sessionmaker() as session:
        user = await _make_user(session)
        reference_id = uuid.uuid4()

        session.add(
            AIUsageEventModel(
                user_id=user.id,
                feature="cv_job_search",
                reference_type="job_analysis",
                reference_id=reference_id,
                status=AIUsageStatus.COMMITTED,
            )
        )
        await session.commit()

        session.add(
            AIUsageEventModel(
                user_id=user.id,
                feature="cv_job_search",
                reference_type="job_analysis",
                reference_id=reference_id,
                status=AIUsageStatus.COMMITTED,
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()


@pytest.mark.asyncio
async def test_the_index_leaves_reservations_and_history_alone(pg_sessionmaker, schema):
    """Partial on purpose: only *committed* rows are unique per reference.

    A user may reserve repeatedly (no reference yet), and a superseded duplicate
    stays in the table as evidence — neither may trip the constraint.
    """
    from app.models.aiUsageModel import AIUsageEventModel, AIUsageStatus

    async with pg_sessionmaker() as session:
        user = await _make_user(session)
        reference_id = uuid.uuid4()

        session.add_all(
            [
                AIUsageEventModel(
                    user_id=user.id,
                    feature="cv_job_search",
                    status=AIUsageStatus.RESERVED,
                    expires_at=datetime.utcnow() + timedelta(minutes=15),
                )
                for _ in range(3)
            ]
            + [
                AIUsageEventModel(
                    user_id=user.id,
                    feature="cv_job_search",
                    reference_type="job_analysis",
                    reference_id=reference_id,
                    status=AIUsageStatus.COMMITTED,
                ),
                AIUsageEventModel(
                    user_id=user.id,
                    feature="cv_job_search",
                    reference_type="job_analysis",
                    reference_id=reference_id,
                    status=AIUsageStatus.SUPERSEDED,
                ),
                AIUsageEventModel(
                    user_id=user.id,
                    feature="cv_job_search",
                    reference_type="job_analysis",
                    reference_id=reference_id,
                    status=AIUsageStatus.RELEASED,
                ),
            ]
        )
        await session.commit()

        assert await _committed_count(session, user.id, reference_id) == 1


@pytest.mark.asyncio
async def test_two_sessions_committing_the_same_result_charge_once(
    pg_sessionmaker, pg_two_sessions, schema
):
    """The replay race: both callers believe they must record the same spend."""
    from app.services.ai.aiUsageService import AIFeature, AIUsageService
    from app.services.ratelimit.counterStore import reset_counter_store

    await reset_counter_store()
    async with pg_sessionmaker() as setup:
        user = await _make_user(setup)

    first, second = pg_two_sessions
    reference_id = uuid.uuid4()

    reservations = []
    for session in (first, second):
        service = AIUsageService(session)
        reservations.append(await service.reserve(user_id=user.id, feature=AIFeature.CV_JOB_SEARCH))
        await session.commit()

    async def settle(session, reservation):
        service = AIUsageService(session)
        await service.commit_usage(
            reservation, reference_type="job_analysis", reference_id=reference_id
        )
        await session.commit()

    await asyncio.gather(
        settle(first, reservations[0]),
        settle(second, reservations[1]),
        return_exceptions=False,
    )

    async with pg_sessionmaker() as reader:
        assert await _committed_count(reader, user.id, reference_id) == 1
        service = AIUsageService(reader)
        # One charge, and the loser's slot went back instead of being stranded.
        assert await service.get_used_today(user_id=user.id, feature=AIFeature.CV_JOB_SEARCH) == 1


@pytest.mark.asyncio
async def test_an_expired_reservation_is_reclaimed_once_by_concurrent_callers(
    pg_sessionmaker, pg_two_sessions, schema
):
    """Only the session whose UPDATE matched may hand the slot back.

    If both could, a counter that had one stale slot would be credited twice and
    the daily limit would quietly grow.
    """
    from app.models.aiUsageModel import AIUsageEventModel, AIUsageStatus
    from app.services.ai.aiUsageService import AIFeature, AIUsageService
    from app.services.ratelimit.counterStore import reset_counter_store

    await reset_counter_store()
    async with pg_sessionmaker() as setup:
        user = await _make_user(setup)
        setup.add(
            AIUsageEventModel(
                user_id=user.id,
                feature=AIFeature.CV_JOB_SEARCH,
                status=AIUsageStatus.RESERVED,
                expires_at=datetime.utcnow() - timedelta(seconds=1),
            )
        )
        await setup.commit()

    first, second = pg_two_sessions
    reclaimed = await asyncio.gather(
        AIUsageService(first)._reclaim_expired_reservations(
            user_id=user.id,
            feature=AIFeature.CV_JOB_SEARCH,
            store=(await _store()),
            key="ai:quota:test:reclaim",
        ),
        AIUsageService(second)._reclaim_expired_reservations(
            user_id=user.id,
            feature=AIFeature.CV_JOB_SEARCH,
            store=(await _store()),
            key="ai:quota:test:reclaim",
        ),
    )

    assert sorted(reclaimed) == [0, 1]
    async with pg_sessionmaker() as reader:
        statuses = (
            await reader.execute(
                select(AIUsageEventModel.status).where(AIUsageEventModel.user_id == user.id)
            )
        ).scalars().all()
    assert list(statuses) == [AIUsageStatus.EXPIRED]


async def _store():
    from app.services.ratelimit.counterStore import get_counter_store

    return get_counter_store()


# --------------------------------------------------------------------------
# The reconciliation migration, against real data
# --------------------------------------------------------------------------


def _migration():
    """Load the revision module by path — ``alembic/versions`` is not a package."""
    import importlib.util
    from pathlib import Path

    path = Path("alembic/versions/d1c7e3a95b48_reconcile_ai_usage_ledger_and_reservations.py")
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def _seed_legacy_history(session, user_id, *, analyses: int, evaluations: int):
    from app.models.jobAnalysisModel import JobAnalysisModel, JobStatus
    from app.models.resumeCourseEvaluationModel import (
        ResumeCourseEvaluationModel,
        ResumeCourseEvaluationStatus,
    )
    from app.models.resumeModel import ResumeModel

    resume = ResumeModel(
        id=uuid.uuid4(),
        user_id=user_id,
        view_url="https://example.invalid/cv",
        storage_file_id="legacy-file",
        original_filename="cv.pdf",
        folder_id="legacy-folder",
    )
    session.add(resume)
    await session.flush()

    session.add_all(
        [
            JobAnalysisModel(
                id=uuid.uuid4(),
                user_id=user_id,
                resume_id=resume.id,
                status=JobStatus.COMPLETED,
                keywords="python",
            )
            for _ in range(analyses)
        ]
        + [
            ResumeCourseEvaluationModel(
                id=uuid.uuid4(),
                user_id=user_id,
                resume_id=resume.id,
                status=ResumeCourseEvaluationStatus.COMPLETED,
                prompt_version="v1",
            )
            for _ in range(evaluations)
        ]
    )
    await session.commit()


@pytest.mark.asyncio
async def test_the_backfill_reconciles_history_by_identity_and_is_resumable(
    pg_engine, pg_sessionmaker, schema
):
    """Historical usage must survive the switch to a ledger-only read.

    Three analyses and two audits happened before the ledger existed. After the
    backfill the ledger reports exactly that — no more (double charging a user
    who did nothing wrong) and no less (handing back quota that was spent).
    """
    from app.services.ai.aiUsageService import AIFeature, AIUsageService

    migration = _migration()

    async with pg_sessionmaker() as session:
        user = await _make_user(session)
        await _seed_legacy_history(session, user.id, analyses=3, evaluations=2)

        service = AIUsageService(session)
        # Before: the ledger knows nothing about any of it.
        assert await service.get_used_today(user_id=user.id, feature=AIFeature.CV_JOB_SEARCH) == 0
        assert len(await service.legacy_parity_gaps(feature=AIFeature.CV_JOB_SEARCH)) == 3
        assert len(await service.legacy_parity_gaps(feature=AIFeature.RESUME_COURSE_AUDIT)) == 2

    def _run_backfill(sync_conn):
        for table, feature, reference_type in migration.LEGACY_SOURCES:
            migration._backfill_legacy(sync_conn, table, feature, reference_type)

    async with pg_engine.begin() as conn:
        await conn.run_sync(_run_backfill)

    async with pg_sessionmaker() as session:
        service = AIUsageService(session)
        assert await service.get_used_today(user_id=user.id, feature=AIFeature.CV_JOB_SEARCH) == 3
        assert (
            await service.get_used_today(user_id=user.id, feature=AIFeature.RESUME_COURSE_AUDIT) == 2
        )
        assert await service.legacy_parity_gaps(feature=AIFeature.CV_JOB_SEARCH) == []
        assert await service.legacy_parity_gaps(feature=AIFeature.RESUME_COURSE_AUDIT) == []

    # Resumable: an interrupted upgrade replays the same step without charging
    # anyone a second time.
    async with pg_engine.begin() as conn:
        await conn.run_sync(_run_backfill)

    async with pg_sessionmaker() as session:
        service = AIUsageService(session)
        assert await service.get_used_today(user_id=user.id, feature=AIFeature.CV_JOB_SEARCH) == 3
        assert (
            await service.get_used_today(user_id=user.id, feature=AIFeature.RESUME_COURSE_AUDIT) == 2
        )


@pytest.mark.asyncio
async def test_duplicate_charges_are_kept_as_history_not_deleted(pg_engine, pg_sessionmaker, schema):
    """The pre-index cleanup: a double charge stops counting but stays readable."""
    from sqlalchemy import text

    from app.models.aiUsageModel import AIUsageEventModel, AIUsageStatus
    from app.services.ai.aiUsageService import AIFeature, AIUsageService

    migration = _migration()
    reference_id = uuid.uuid4()

    async with pg_sessionmaker() as session:
        user = await _make_user(session)

    # The index cannot exist yet — duplicates are what it is created to prevent.
    async with pg_engine.begin() as conn:
        await conn.execute(text("DROP INDEX uq_ai_usage_events_reference"))

    async with pg_sessionmaker() as session:
        session.add_all(
            [
                AIUsageEventModel(
                    user_id=user.id,
                    feature=AIFeature.CV_JOB_SEARCH,
                    reference_type="job_analysis",
                    reference_id=reference_id,
                    status=AIUsageStatus.COMMITTED,
                )
                for _ in range(2)
            ]
        )
        await session.commit()
        service = AIUsageService(session)
        assert await service.get_used_today(user_id=user.id, feature=AIFeature.CV_JOB_SEARCH) == 2

    async with pg_engine.begin() as conn:
        marked = await conn.run_sync(migration._mark_duplicate_references)
    assert marked == 1

    async with pg_sessionmaker() as session:
        service = AIUsageService(session)
        # One charge counts; the other is still in the table as evidence.
        assert await service.get_used_today(user_id=user.id, feature=AIFeature.CV_JOB_SEARCH) == 1
        rows = (
            await session.execute(
                select(AIUsageEventModel.status).where(AIUsageEventModel.reference_id == reference_id)
            )
        ).scalars().all()
        assert sorted(rows) == [AIUsageStatus.COMMITTED, AIUsageStatus.SUPERSEDED]
