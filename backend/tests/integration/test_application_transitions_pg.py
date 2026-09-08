"""Transitions and daily counters under real concurrency.

The two claims that only a real server can settle:

* the row lock actually serialises transitions, so a command that arrives twice
  at once produces one event, not two;
* the aggregate upsert adds in SQL, so simultaneous writers cannot lose each
  other's increments — and cannot collide on the unique constraint while
  creating the day's row.

SQLite funnels every write through one connection, so it would pass these by
construction and prove nothing.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import date, datetime

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


async def _seed(session):
    from app.models.applicationModel import ApplicationModel, ApplicationStatus
    from app.models.companyModel import Company
    from app.models.companyRecruiterModel import CompanyRecruiter
    from app.models.userModel import User

    user = User(
        id=uuid.uuid4(),
        email=f"cand-{uuid.uuid4().hex[:8]}@example.invalid",
        hashed_password="x",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    company = Company(id=uuid.uuid4(), company_name="Transition Co")
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
        status=ApplicationStatus.APPLIED,
        application_date=datetime.utcnow(),
    )
    session.add_all([recruiter, application])
    await session.commit()
    return user, company, recruiter, application


@pytest.mark.asyncio
async def test_concurrent_increments_are_all_counted(schema, pg_sessionmaker):
    """Twenty writers, twenty increments — none overwritten by another's read."""
    from app.models.applicationAnalyticsModel import ApplicationDailyAggregateModel
    from app.services.applications.applicationService import ApplicationService

    async with pg_sessionmaker() as setup:
        _, company, _, _ = await _seed(setup)

    async def bump():
        async with pg_sessionmaker() as session:
            await ApplicationService(session)._apply_daily_aggregate_delta(
                company_id=company.id,
                occurred_at=datetime.utcnow(),
                delta={"status_change_events_count": 1, "entered_in_review_count": 1},
            )
            await session.commit()

    await asyncio.gather(*(bump() for _ in range(20)))

    async with pg_sessionmaker() as reader:
        aggregate = await reader.scalar(
            select(ApplicationDailyAggregateModel).where(
                ApplicationDailyAggregateModel.company_id == company.id,
                ApplicationDailyAggregateModel.metric_date == date.today(),
            )
        )
        rows = await reader.scalar(
            select(func.count(ApplicationDailyAggregateModel.id)).where(
                ApplicationDailyAggregateModel.company_id == company.id
            )
        )

    assert aggregate.status_change_events_count == 20
    assert aggregate.entered_in_review_count == 20
    # And the day's row was created once, not raced into a constraint violation.
    assert rows == 1


@pytest.mark.asyncio
async def test_the_same_command_arriving_twice_at_once_transitions_once(schema, pg_sessionmaker):
    """A double-clicked button is one change, and the lock is what decides."""
    from app.models.applicationAnalyticsModel import (
        ApplicationDailyAggregateModel,
        ApplicationStatusEventModel,
    )
    from app.models.applicationModel import ApplicationStatus
    from app.services.applications.applicationService import ApplicationService

    async with pg_sessionmaker() as setup:
        _, company, recruiter, application = await _seed(setup)

    async def move():
        async with pg_sessionmaker() as session:
            await ApplicationService(session).update_company_application(
                application_id=application.id,
                company_id=company.id,
                recruiter_id=recruiter.id,
                status=ApplicationStatus.IN_REVIEW,
                notes="Moving to review",
            )

    await asyncio.gather(move(), move())

    async with pg_sessionmaker() as reader:
        events = await reader.scalar(
            select(func.count(ApplicationStatusEventModel.id)).where(
                ApplicationStatusEventModel.application_id == application.id,
                ApplicationStatusEventModel.to_status == ApplicationStatus.IN_REVIEW,
            )
        )
        aggregate = await reader.scalar(
            select(ApplicationDailyAggregateModel).where(
                ApplicationDailyAggregateModel.company_id == company.id
            )
        )

    assert events == 1
    assert aggregate.entered_in_review_count == 1
    assert aggregate.status_change_events_count == 1


@pytest.mark.asyncio
async def test_two_recruiters_publishing_availability_record_one_transition(
    schema, pg_sessionmaker
):
    from datetime import timedelta

    from app.models.applicationAnalyticsModel import ApplicationStatusEventModel
    from app.models.applicationModel import ApplicationModel, ApplicationStatus
    from app.schemas.interviewSchema import (
        InterviewAvailabilityCreate,
        InterviewAvailabilityPublishRequest,
    )
    from app.services.jobs.interviewService import InterviewService

    async with pg_sessionmaker() as setup:
        _, company, recruiter, application = await _seed(setup)
        moved = await setup.get(ApplicationModel, application.id)
        moved.status = ApplicationStatus.IN_REVIEW
        await setup.commit()

    starts_at = datetime.utcnow() + timedelta(days=3)
    payload = InterviewAvailabilityPublishRequest(
        slots=[
            InterviewAvailabilityCreate(
                starts_at=starts_at,
                ends_at=starts_at + timedelta(hours=1),
                timezone="America/Toronto",
            )
        ],
        notes=None,
    )

    async def publish():
        async with pg_sessionmaker() as session:
            recruiter_row = await session.get(type(recruiter), recruiter.id)
            await InterviewService(session).publish_company_availabilities(
                application_id=application.id, recruiter=recruiter_row, payload=payload
            )

    await asyncio.gather(publish(), publish())

    async with pg_sessionmaker() as reader:
        events = await reader.scalar(
            select(func.count(ApplicationStatusEventModel.id)).where(
                ApplicationStatusEventModel.application_id == application.id,
                ApplicationStatusEventModel.to_status == ApplicationStatus.INTERVIEW,
            )
        )
        final = await reader.get(ApplicationModel, application.id)

    assert events == 1
    assert final.status == ApplicationStatus.INTERVIEW
