"""Interview confirmation under real concurrency, and the migration's cleanup.

Two candidate sessions confirming different times is the case the whole task
exists for. SQLite cannot stage it — one connection, writes serialised for free
— so the claim only means anything here.

The migration half checks the promise made about existing data: conflicts are
found and resolved, never discarded.
"""
from __future__ import annotations

import asyncio
import importlib.util
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select, text

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


def _migration():
    path = Path("alembic/versions/f4c9a17be205_one_booked_interview_slot_per_application.py")
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def _seed(session):
    from app.models.applicationModel import ApplicationModel, ApplicationStatus
    from app.models.companyModel import Company
    from app.models.companyRecruiterModel import CompanyRecruiter
    from app.models.interviewAvailabilityModel import (
        InterviewAvailabilityModel,
        InterviewAvailabilityStatus,
    )
    from app.models.userModel import User

    user = User(
        id=uuid.uuid4(),
        email=f"cand-{uuid.uuid4().hex[:8]}@example.invalid",
        hashed_password="x",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    company = Company(id=uuid.uuid4(), company_name="Interview Co")
    session.add_all([user, company])
    await session.flush()

    recruiter = CompanyRecruiter(
        id=uuid.uuid4(),
        company_id=company.id,
        email=f"rec-{uuid.uuid4().hex[:8]}@example.invalid",
        hashed_password="x",
        is_active=True,
        is_superuser=False,
        is_verified=True,
        role="owner",
    )
    application = ApplicationModel(
        id=uuid.uuid4(),
        user_id=user.id,
        company_id=company.id,
        job_title="Backend Intern",
        status=ApplicationStatus.INTERVIEW,
        application_date=datetime.utcnow(),
    )
    session.add_all([recruiter, application])
    await session.flush()

    starts_at = datetime.utcnow() + timedelta(days=4)
    slots = [
        InterviewAvailabilityModel(
            id=uuid.uuid4(),
            application_id=application.id,
            company_id=company.id,
            recruiter_id=recruiter.id,
            candidate_id=user.id,
            starts_at=starts_at + timedelta(hours=offset),
            ends_at=starts_at + timedelta(hours=offset + 1),
            timezone="America/Toronto",
            status=InterviewAvailabilityStatus.AVAILABLE,
        )
        for offset in (0, 24)
    ]
    session.add_all(slots)
    await session.commit()
    return user, application, slots


async def _booked_count(session, application_id) -> int:
    from app.models.interviewAvailabilityModel import (
        InterviewAvailabilityModel,
        InterviewAvailabilityStatus,
    )

    return int(
        await session.scalar(
            select(func.count(InterviewAvailabilityModel.id)).where(
                InterviewAvailabilityModel.application_id == application_id,
                InterviewAvailabilityModel.status == InterviewAvailabilityStatus.BOOKED,
            )
        )
    )


@pytest.mark.asyncio
async def test_two_sessions_choosing_different_times_leave_one_booking(
    schema, pg_sessionmaker, pg_two_sessions
):
    from app.models.emailNotificationLogModel import EmailNotificationLogModel
    from app.models.userModel import User
    from app.services.jobs.interviewService import InterviewService

    async with pg_sessionmaker() as setup:
        user, application, slots = await _seed(setup)

    first, second = pg_two_sessions

    async def choose(session, slot_id):
        candidate = await session.get(User, user.id)
        try:
            await InterviewService(session).select_user_availability(
                application_id=application.id, slot_id=slot_id, user=candidate
            )
            return "confirmed"
        except HTTPException as exc:
            await session.rollback()
            return exc.status_code

    outcomes = await asyncio.gather(
        choose(first, slots[0].id),
        choose(second, slots[1].id),
    )

    # One caller wins; the other is told the interview is already confirmed.
    assert sorted(str(outcome) for outcome in outcomes) == ["409", "confirmed"]

    async with pg_sessionmaker() as reader:
        assert await _booked_count(reader, application.id) == 1
        confirmations = await reader.scalar(
            select(func.count(EmailNotificationLogModel.id)).where(
                EmailNotificationLogModel.application_id == application.id,
                EmailNotificationLogModel.template_key == "candidate_interview_confirmed",
            )
        )
    # And the candidate is told about one interview, not two.
    assert confirmations == 1


@pytest.mark.asyncio
async def test_the_index_is_the_backstop_when_the_service_is_bypassed(schema, pg_sessionmaker):
    from sqlalchemy.exc import IntegrityError

    async with pg_sessionmaker() as session:
        _, application, slots = await _seed(session)
        await session.execute(
            text("UPDATE interview_availabilities SET status = 'booked' WHERE id = :id"),
            {"id": slots[0].id},
        )
        await session.commit()

        with pytest.raises(IntegrityError):
            await session.execute(
                text("UPDATE interview_availabilities SET status = 'booked' WHERE id = :id"),
                {"id": slots[1].id},
            )
            await session.commit()
        await session.rollback()


@pytest.mark.asyncio
async def test_the_migration_finds_and_resolves_conflicts_without_deleting(
    schema, pg_engine, pg_sessionmaker
):
    """Existing double bookings: reported, resolved, and still in the table."""
    from app.models.interviewAvailabilityModel import (
        InterviewAvailabilityModel,
        InterviewAvailabilityStatus,
    )

    migration = _migration()

    async with pg_sessionmaker() as session:
        _, application, slots = await _seed(session)

    # The conflict can only be created with the index gone — which is exactly
    # the state a database upgrading through this revision is in.
    async with pg_engine.begin() as conn:
        await conn.execute(text("DROP INDEX uq_interview_availabilities_booked_per_application"))
        await conn.execute(
            text(
                "UPDATE interview_availabilities SET status = 'booked', booked_at = :booked "
                "WHERE id = :id"
            ),
            {"id": slots[0].id, "booked": datetime.utcnow() - timedelta(minutes=5)},
        )
        await conn.execute(
            text(
                "UPDATE interview_availabilities SET status = 'booked', booked_at = :booked "
                "WHERE id = :id"
            ),
            {"id": slots[1].id, "booked": datetime.utcnow()},
        )

    async with pg_engine.begin() as conn:
        conflicts = await conn.run_sync(migration._inventory_duplicates)
        assert [row[1] for row in conflicts] == [2], "the conflict must be visible before any write"
        resolved = await conn.run_sync(migration._resolve_duplicates)
    assert resolved == 1

    async with pg_sessionmaker() as reader:
        rows = (
            await reader.execute(
                select(InterviewAvailabilityModel.id, InterviewAvailabilityModel.status).where(
                    InterviewAvailabilityModel.application_id == application.id
                )
            )
        ).all()
    statuses = dict(rows)

    # The earliest confirmation — the one both sides were told about — survives.
    assert statuses[slots[0].id] == InterviewAvailabilityStatus.BOOKED
    # The later one is cancelled, not deleted: the record of it still exists.
    assert statuses[slots[1].id] == InterviewAvailabilityStatus.CANCELLED
    assert len(rows) == 2

    # And the index can now be created over the resolved data.
    async with pg_engine.begin() as conn:
        await conn.execute(
            text(
                "CREATE UNIQUE INDEX uq_interview_availabilities_booked_per_application "
                "ON interview_availabilities (application_id) WHERE status = 'booked'"
            )
        )
