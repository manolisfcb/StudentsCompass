"""Pasted vacancies, their shared parse, and their lease (TASK-077)."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from app.models.jobTargetModel import JobDescriptionParseModel, JobTargetModel
from app.services.careerLab.jobTargetService import (
    EXHAUSTED_ATTEMPTS_MESSAGE,
    INTERRUPTED_AFTER_SPEND_MESSAGE,
    MAX_JOB_TARGET_ATTEMPTS,
    JobTargetService,
    job_text_hash,
    normalize_job_text,
)

POSTING = "Data Analyst\r\n\r\n\r\n\r\nWe need SQL and   Python.  \nTableau is a plus.\n"


# ---------------------------------------------------------------------------
# Normalization: what decides the shared cache's hit rate
# ---------------------------------------------------------------------------


def test_copy_noise_is_folded():
    assert normalize_job_text(POSTING) == "Data Analyst\n\nWe need SQL and Python.\nTableau is a plus."


def test_two_copies_of_one_posting_share_a_hash():
    other_browser = "  Data Analyst\n\nWe need SQL and Python.\nTableau is a plus.  "
    assert job_text_hash(POSTING) == job_text_hash(other_browser)


def test_wording_and_case_still_matter():
    assert job_text_hash("We need SQL") != job_text_hash("We need NoSQL")
    assert job_text_hash("We need SQL") != job_text_hash("we need sql")


# ---------------------------------------------------------------------------
# The shared parse
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_first_parse_wins_and_the_second_writer_gets_it(db_session):
    service = JobTargetService(db_session)
    text_hash = job_text_hash(POSTING)

    first = await service.store_parse(
        text_hash=text_hash, parsed={"skills": ["sql"]}, model_id="rules", prompt_version="jd_rules_v1"
    )
    second = await service.store_parse(
        text_hash=text_hash, parsed={"skills": ["other"]}, model_id="rules", prompt_version="jd_rules_v1"
    )

    assert second.parsed == first.parsed == {"skills": ["sql"]}
    count = await db_session.scalar(select(func.count()).select_from(JobDescriptionParseModel))
    assert count == 1


@pytest.mark.asyncio
async def test_a_vector_is_never_stored_without_its_model(db_session):
    with pytest.raises(ValueError):
        await JobTargetService(db_session).store_parse(
            text_hash="a" * 64,
            parsed={},
            model_id="rules",
            prompt_version="v1",
            embedding=[0.0] * 384,
        )


# ---------------------------------------------------------------------------
# Targets
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_new_target_is_pending_and_keyed_by_its_normalized_text(db_session, test_user):
    target = await JobTargetService(db_session).create_target(user_id=test_user.id, raw_text=POSTING)

    assert target.status == "pending"
    assert target.attempts == 0
    assert target.source == "pasted"
    assert target.text_hash == job_text_hash(POSTING)
    # The user's text is kept as pasted; only the key is normalized.
    assert target.raw_text == POSTING


@pytest.mark.asyncio
async def test_a_target_is_only_visible_to_its_owner(db_session, test_user):
    import uuid

    service = JobTargetService(db_session)
    target = await service.create_target(user_id=test_user.id, raw_text=POSTING)

    assert await service.get_user_target(target_id=target.id, user_id=test_user.id) is not None
    assert await service.get_user_target(target_id=target.id, user_id=uuid.uuid4()) is None


@pytest.mark.asyncio
async def test_an_unknown_status_is_refused_by_the_database(db_session, test_user):
    target = await JobTargetService(db_session).create_target(user_id=test_user.id, raw_text=POSTING)

    with pytest.raises(IntegrityError):
        await db_session.execute(
            update(JobTargetModel).where(JobTargetModel.id == target.id).values(status="done")
        )
        await db_session.commit()
    await db_session.rollback()


# ---------------------------------------------------------------------------
# The lease cycle
# ---------------------------------------------------------------------------


async def _reload(session, target_id) -> JobTargetModel:
    result = await session.execute(
        select(JobTargetModel)
        .where(JobTargetModel.id == target_id)
        .execution_options(populate_existing=True)
    )
    return result.scalar_one()


async def _expire_lease(session, target_id) -> None:
    await session.execute(
        update(JobTargetModel)
        .where(JobTargetModel.id == target_id)
        .values(lease_expires_at=datetime.utcnow() - timedelta(seconds=1))
    )
    await session.commit()


@pytest.mark.asyncio
async def test_a_held_lease_cannot_be_claimed_again(db_session, test_user):
    service = JobTargetService(db_session)
    target = await service.create_target(user_id=test_user.id, raw_text=POSTING)

    assert await service.claim(target.id) is True
    assert await service.claim(target.id) is False

    claimed = await _reload(db_session, target.id)
    assert (claimed.status, claimed.attempts) == ("parsing", 1)
    assert claimed.lease_expires_at > datetime.utcnow()


@pytest.mark.asyncio
async def test_an_expired_lease_can_be_reclaimed(db_session, test_user):
    service = JobTargetService(db_session)
    target = await service.create_target(user_id=test_user.id, raw_text=POSTING)
    await service.claim(target.id)
    await _expire_lease(db_session, target.id)

    assert await service.claim(target.id) is True
    assert (await _reload(db_session, target.id)).attempts == 2


@pytest.mark.asyncio
async def test_complete_needs_the_lease_and_keeps_the_snapshot(db_session, test_user):
    service = JobTargetService(db_session)
    target = await service.create_target(user_id=test_user.id, raw_text=POSTING)

    assert await service.complete(target.id, match_snapshot={"score": 0.7}) is False

    await service.claim(target.id)
    assert await service.complete(
        target.id, match_snapshot={"score": 0.7}, title="Data Analyst", workplace_type="remote"
    )
    done = await _reload(db_session, target.id)
    assert (done.status, done.lease_expires_at) == ("ready", None)
    assert done.match_snapshot == {"score": 0.7}
    assert (done.title, done.workplace_type) == ("Data Analyst", "remote")


@pytest.mark.asyncio
async def test_recovery_never_pays_twice(db_session, test_user):
    """The three outcomes, each on its own target, in one sweep."""
    service = JobTargetService(db_session)
    spent = await service.create_target(user_id=test_user.id, raw_text="spent")
    exhausted = await service.create_target(user_id=test_user.id, raw_text="exhausted")
    retry = await service.create_target(user_id=test_user.id, raw_text="retry")
    for target in (spent, exhausted, retry):
        await service.claim(target.id)
    await service.mark_provider_attempted(spent.id)
    await db_session.execute(
        update(JobTargetModel)
        .where(JobTargetModel.id == exhausted.id)
        .values(attempts=MAX_JOB_TARGET_ATTEMPTS)
    )
    for target in (spent, exhausted, retry):
        await _expire_lease(db_session, target.id)

    outcome = await service.recover_stale()

    assert outcome == {"failed_after_spend": 1, "failed_attempts_exhausted": 1, "requeued": 1}
    spent_row = await _reload(db_session, spent.id)
    assert (spent_row.status, spent_row.error_message) == ("failed", INTERRUPTED_AFTER_SPEND_MESSAGE)
    exhausted_row = await _reload(db_session, exhausted.id)
    assert (exhausted_row.status, exhausted_row.error_message) == ("failed", EXHAUSTED_ATTEMPTS_MESSAGE)
    assert (await _reload(db_session, retry.id)).status == "pending"
    assert await service.due_target_ids() == [retry.id]


@pytest.mark.asyncio
async def test_a_live_lease_is_left_alone_by_recovery(db_session, test_user):
    service = JobTargetService(db_session)
    target = await service.create_target(user_id=test_user.id, raw_text=POSTING)
    await service.claim(target.id)

    assert await service.recover_stale() == {
        "failed_after_spend": 0,
        "failed_attempts_exhausted": 0,
        "requeued": 0,
    }
    assert (await _reload(db_session, target.id)).status == "parsing"


@pytest.mark.asyncio
async def test_fail_records_the_reason(db_session, test_user):
    service = JobTargetService(db_session)
    target = await service.create_target(user_id=test_user.id, raw_text=POSTING)

    await service.fail(target.id, "The text does not look like a job description.")

    failed = await _reload(db_session, target.id)
    assert failed.status == "failed"
    assert failed.error_message == "The text does not look like a job description."
