"""The reservation cycle: every claimed slot reaches exactly one end state.

A reservation used to live only in a counter, so the accounting could not answer
two questions after the fact: *was this slot ever settled?* and *has this result
already been charged?* Both are asked here, plus the failure paths that used to
run outside the block that hands a slot back.

Fast lane (SQLite). The concurrency and constraint behaviour these rules rest on
is checked against a real server in ``tests/integration/test_ai_ledger_pg.py``.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.aiUsageModel import AIUsageEventModel, AIUsageStatus
from app.models.jobAnalysisModel import JobAnalysisModel, JobStatus
from app.services.ai.aiUsageService import (
    RELEASE_AFTER_ATTEMPT,
    RELEASE_DUPLICATE,
    RELEASE_NO_SPEND,
    AIFeature,
    AIUsageService,
)
from app.services.ratelimit.counterStore import reset_counter_store


async def _events(session, user_id) -> list[AIUsageEventModel]:
    # populate_existing: rows settled from another session (a lease reclaim, a
    # background release) must be read as the database has them, not as this
    # session last saw them.
    result = await session.execute(
        select(AIUsageEventModel)
        .where(AIUsageEventModel.user_id == user_id)
        .execution_options(populate_existing=True)
    )
    return list(result.scalars())


@pytest.mark.asyncio
async def test_a_reservation_is_written_to_the_ledger(db_session, test_user):
    await reset_counter_store()
    service = AIUsageService(db_session)

    reservation = await service.reserve(user_id=test_user.id, feature=AIFeature.CV_JOB_SEARCH)
    await db_session.commit()

    events = await _events(db_session, test_user.id)
    assert [event.status for event in events] == [AIUsageStatus.RESERVED]
    assert events[0].id == reservation.event_id
    assert events[0].expires_at is not None, "a reservation without a lease can never be reclaimed"
    # A claimed slot counts immediately: nothing else may hand it out again.
    assert await service.get_used_today(user_id=test_user.id, feature=AIFeature.CV_JOB_SEARCH) == 1


@pytest.mark.asyncio
async def test_release_returns_the_slot_and_says_why(db_session, test_user):
    await reset_counter_store()
    service = AIUsageService(db_session)

    reservation = await service.reserve(user_id=test_user.id, feature=AIFeature.CV_JOB_SEARCH)
    await db_session.commit()
    await reservation.release(reason=RELEASE_AFTER_ATTEMPT)
    await db_session.commit()

    events = await _events(db_session, test_user.id)
    assert [event.status for event in events] == [AIUsageStatus.RELEASED]
    # Provider spend and user entitlement are different facts: the attempt was
    # made (and counted by the global budget guard), the user was not charged.
    assert events[0].source == RELEASE_AFTER_ATTEMPT
    assert await service.get_used_today(user_id=test_user.id, feature=AIFeature.CV_JOB_SEARCH) == 0


@pytest.mark.asyncio
async def test_commit_settles_the_reserved_row_instead_of_adding_one(db_session, test_user):
    await reset_counter_store()
    service = AIUsageService(db_session)
    job_id = uuid4()

    reservation = await service.reserve(user_id=test_user.id, feature=AIFeature.CV_JOB_SEARCH)
    await db_session.commit()
    await service.commit_usage(reservation, reference_type="job_analysis", reference_id=job_id)
    await db_session.commit()

    events = await _events(db_session, test_user.id)
    assert len(events) == 1, "a settled reservation must not leave a second row behind"
    assert events[0].status == AIUsageStatus.COMMITTED
    assert events[0].reference_id == job_id
    assert events[0].expires_at is None
    assert await service.get_used_today(user_id=test_user.id, feature=AIFeature.CV_JOB_SEARCH) == 1


@pytest.mark.asyncio
async def test_replaying_a_commit_charges_once(db_session, test_user):
    """A re-delivered background task must not bill the same result twice."""
    await reset_counter_store()
    service = AIUsageService(db_session)
    job_id = uuid4()

    first = await service.reserve(user_id=test_user.id, feature=AIFeature.CV_JOB_SEARCH)
    await db_session.commit()
    charged = await service.commit_usage(first, reference_type="job_analysis", reference_id=job_id)
    await db_session.commit()

    replay = await service.reserve(user_id=test_user.id, feature=AIFeature.CV_JOB_SEARCH)
    await db_session.commit()
    again = await service.commit_usage(replay, reference_type="job_analysis", reference_id=job_id)
    await db_session.commit()

    assert again.id == charged.id
    committed = [event for event in await _events(db_session, test_user.id) if event.status == AIUsageStatus.COMMITTED]
    assert len(committed) == 1
    # The duplicate reservation gives its slot back rather than sitting on it.
    released = [event for event in await _events(db_session, test_user.id) if event.status == AIUsageStatus.RELEASED]
    assert [event.source for event in released] == [RELEASE_DUPLICATE]
    assert await service.get_used_today(user_id=test_user.id, feature=AIFeature.CV_JOB_SEARCH) == 1


@pytest.mark.asyncio
async def test_record_usage_is_idempotent_by_reference(db_session, test_user):
    await reset_counter_store()
    service = AIUsageService(db_session)
    evaluation_id = uuid4()

    first = await service.record_usage(
        user_id=test_user.id,
        feature=AIFeature.RESUME_COURSE_AUDIT,
        reference_type="resume_course_evaluation",
        reference_id=evaluation_id,
    )
    second = await service.record_usage(
        user_id=test_user.id,
        feature=AIFeature.RESUME_COURSE_AUDIT,
        reference_type="resume_course_evaluation",
        reference_id=evaluation_id,
    )
    await db_session.commit()

    assert first.id == second.id
    assert await service.get_used_today(user_id=test_user.id, feature=AIFeature.RESUME_COURSE_AUDIT) == 1


@pytest.mark.asyncio
async def test_an_abandoned_reservation_stops_counting_when_its_lease_ends(db_session, test_user):
    """The process died between reserve and settle: the slot comes back.

    Without a lease this is the "retained quota" case — a counter incremented by
    a request that no longer exists, holding a slot until midnight.
    """
    await reset_counter_store()
    service = AIUsageService(db_session)

    await service.reserve(user_id=test_user.id, feature=AIFeature.CV_JOB_SEARCH)
    await db_session.commit()
    assert await service.get_used_today(user_id=test_user.id, feature=AIFeature.CV_JOB_SEARCH) == 1

    abandoned = (await _events(db_session, test_user.id))[0]
    abandoned.expires_at = datetime.utcnow() - timedelta(seconds=1)
    await db_session.commit()

    # Expiry is a predicate, not a repair job: the read is correct with no write.
    assert await service.get_used_today(user_id=test_user.id, feature=AIFeature.CV_JOB_SEARCH) == 0


@pytest.mark.asyncio
async def test_reserving_again_reclaims_the_abandoned_slot(db_session, test_user):
    await reset_counter_store()
    service = AIUsageService(db_session)

    for _ in range(3):  # AI_BASE_DAILY_LIMIT
        await service.reserve(user_id=test_user.id, feature=AIFeature.CV_JOB_SEARCH)
    await db_session.commit()
    with pytest.raises(HTTPException):
        await service.reserve(user_id=test_user.id, feature=AIFeature.CV_JOB_SEARCH)

    stale = datetime.utcnow() - timedelta(seconds=1)
    for event in await _events(db_session, test_user.id):
        event.expires_at = stale
    await db_session.commit()

    # The counter is corrected as part of reserving, so the user is not locked
    # out for the rest of the day by requests that no longer exist.
    reservation = await service.reserve(user_id=test_user.id, feature=AIFeature.CV_JOB_SEARCH)
    await db_session.commit()
    assert reservation.event_id is not None

    expired = [e for e in await _events(db_session, test_user.id) if e.status == AIUsageStatus.EXPIRED]
    assert len(expired) == 3
    assert await service.get_used_today(user_id=test_user.id, feature=AIFeature.CV_JOB_SEARCH) == 1


@pytest.mark.asyncio
async def test_reserved_slots_hold_the_limit_against_the_ledger(db_session, test_user):
    """A restarted counter reseeds from live reservations, not only from spends."""
    await reset_counter_store()
    service = AIUsageService(db_session)

    for _ in range(3):
        await service.reserve(user_id=test_user.id, feature=AIFeature.CV_JOB_SEARCH)
    await db_session.commit()

    await reset_counter_store()  # fresh Redis / new process
    with pytest.raises(HTTPException) as exc_info:
        await service.reserve(user_id=test_user.id, feature=AIFeature.CV_JOB_SEARCH)
    assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_a_released_reservation_does_not_block_the_next_one(db_session, test_user):
    await reset_counter_store()
    service = AIUsageService(db_session)

    reservations = [
        await service.reserve(user_id=test_user.id, feature=AIFeature.CV_JOB_SEARCH) for _ in range(3)
    ]
    await db_session.commit()
    await reservations[0].release()
    await db_session.commit()

    assert await service.get_used_today(user_id=test_user.id, feature=AIFeature.CV_JOB_SEARCH) == 2
    await service.reserve(user_id=test_user.id, feature=AIFeature.CV_JOB_SEARCH)
    await db_session.commit()
    with pytest.raises(HTTPException):
        await service.reserve(user_id=test_user.id, feature=AIFeature.CV_JOB_SEARCH)


@pytest.mark.asyncio
async def test_legacy_backfilled_rows_count_as_the_spends_they_record(db_session, test_user):
    """Historical quota must not move: two attempts before, two after."""
    await reset_counter_store()
    analyses = [
        JobAnalysisModel(user_id=test_user.id, status=JobStatus.COMPLETED, keywords="python"),
        JobAnalysisModel(user_id=test_user.id, status=JobStatus.FAILED, error_message="failed"),
    ]
    db_session.add_all(analyses)
    await db_session.commit()

    service = AIUsageService(db_session)
    for analysis in analyses:
        await service.record_usage(
            user_id=test_user.id,
            feature=AIFeature.CV_JOB_SEARCH,
            source="legacy_backfill",
            reference_type="job_analysis",
            reference_id=analysis.id,
        )
    await db_session.commit()

    assert await service.get_used_today(user_id=test_user.id, feature=AIFeature.CV_JOB_SEARCH) == 2
    assert await service.legacy_parity_gaps(feature=AIFeature.CV_JOB_SEARCH, user_id=test_user.id) == []
    # And a rerun of the same backfill adds nothing.
    for analysis in analyses:
        await service.record_usage(
            user_id=test_user.id,
            feature=AIFeature.CV_JOB_SEARCH,
            source="legacy_backfill",
            reference_type="job_analysis",
            reference_id=analysis.id,
        )
    await db_session.commit()
    assert await service.get_used_today(user_id=test_user.id, feature=AIFeature.CV_JOB_SEARCH) == 2


@pytest.mark.asyncio
async def test_release_after_the_owning_request_ended(db_session, test_user):
    """The CV analysis settles from a background task with its own session."""
    await reset_counter_store()
    service = AIUsageService(db_session)

    reservation = await service.reserve(user_id=test_user.id, feature=AIFeature.CV_JOB_SEARCH)
    await db_session.commit()

    reservation.session = None  # the request that reserved is gone
    await reservation.release(reason=RELEASE_NO_SPEND)

    await db_session.rollback()  # drop this session's identity map, read fresh
    events = await _events(db_session, test_user.id)
    assert [event.status for event in events] == [AIUsageStatus.RELEASED]
    assert await service.get_used_today(user_id=test_user.id, feature=AIFeature.CV_JOB_SEARCH) == 0
