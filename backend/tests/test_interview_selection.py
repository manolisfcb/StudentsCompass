"""Confirming an interview time: once per application, whatever the client does.

Choosing a slot read it as available, marked it booked and cancelled the others
in three separate statements. Two taps on a phone with a slow connection were
enough to confirm two different times, cancel each other's choice, and send two
"your interview is confirmed" emails for the same interview.

The slots belong to an application, not to a company calendar: nothing here says
anything about a recruiter's wider agenda.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.applicationModel import ApplicationModel, ApplicationStatus
from app.models.interviewAvailabilityModel import (
    InterviewAvailabilityModel,
    InterviewAvailabilityStatus,
)
from app.models.emailNotificationLogModel import EmailNotificationLogModel
from app.services.jobs.interviewService import InterviewService


@pytest.fixture
async def application(db_session, test_user, test_company):
    model = ApplicationModel(
        id=uuid.uuid4(),
        user_id=test_user.id,
        company_id=test_company.id,
        job_title="Backend Intern",
        status=ApplicationStatus.INTERVIEW,
        application_date=datetime.utcnow(),
    )
    db_session.add(model)
    await db_session.commit()
    return model


@pytest.fixture
async def slots(db_session, application, test_company, test_company_recruiter, test_user):
    starts_at = datetime.utcnow() + timedelta(days=3)
    created = [
        InterviewAvailabilityModel(
            id=uuid.uuid4(),
            application_id=application.id,
            company_id=test_company.id,
            recruiter_id=test_company_recruiter.id,
            candidate_id=test_user.id,
            starts_at=starts_at + timedelta(hours=offset),
            ends_at=starts_at + timedelta(hours=offset + 1),
            timezone="America/Toronto",
            status=InterviewAvailabilityStatus.AVAILABLE,
        )
        for offset in (0, 24, 48)
    ]
    db_session.add_all(created)
    await db_session.commit()
    return created


async def _slot_statuses(session, application_id):
    result = await session.execute(
        select(InterviewAvailabilityModel.id, InterviewAvailabilityModel.status)
        .where(InterviewAvailabilityModel.application_id == application_id)
        .execution_options(populate_existing=True)
    )
    return dict(result.all())


async def _confirmation_emails(session, application_id):
    result = await session.execute(
        select(EmailNotificationLogModel).where(
            EmailNotificationLogModel.application_id == application_id
        )
    )
    return [log for log in result.scalars() if "interview_confirmed" in (log.template_key or "")]


@pytest.mark.asyncio
async def test_confirming_a_slot_books_it_and_cancels_the_rest(
    db_session, application, slots, test_user
):
    service = InterviewService(db_session)

    await service.select_user_availability(
        application_id=application.id, slot_id=slots[1].id, user=test_user
    )

    statuses = await _slot_statuses(db_session, application.id)
    assert statuses[slots[1].id] == InterviewAvailabilityStatus.BOOKED
    assert statuses[slots[0].id] == InterviewAvailabilityStatus.CANCELLED
    assert statuses[slots[2].id] == InterviewAvailabilityStatus.CANCELLED


@pytest.mark.asyncio
async def test_confirming_the_same_slot_again_returns_the_existing_state(
    db_session, application, slots, test_user
):
    """A retry is not a second confirmation: no error, and no second email."""
    service = InterviewService(db_session)

    await service.select_user_availability(
        application_id=application.id, slot_id=slots[0].id, user=test_user
    )
    emails_after_first = len(await _confirmation_emails(db_session, application.id))

    result = await service.select_user_availability(
        application_id=application.id, slot_id=slots[0].id, user=test_user
    )

    assert result is not None
    assert result.id == application.id
    statuses = await _slot_statuses(db_session, application.id)
    assert statuses[slots[0].id] == InterviewAvailabilityStatus.BOOKED
    assert len(await _confirmation_emails(db_session, application.id)) == emails_after_first


@pytest.mark.asyncio
async def test_confirming_a_different_slot_afterwards_is_refused(
    db_session, application, slots, test_user
):
    """One confirmed time per application; changing it is not a silent overwrite."""
    service = InterviewService(db_session)

    await service.select_user_availability(
        application_id=application.id, slot_id=slots[0].id, user=test_user
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.select_user_availability(
            application_id=application.id, slot_id=slots[1].id, user=test_user
        )

    assert exc_info.value.status_code == 409
    statuses = await _slot_statuses(db_session, application.id)
    assert statuses[slots[0].id] == InterviewAvailabilityStatus.BOOKED
    assert list(statuses.values()).count(InterviewAvailabilityStatus.BOOKED) == 1


@pytest.mark.asyncio
async def test_a_cancelled_slot_cannot_be_confirmed(db_session, application, slots, test_user):
    service = InterviewService(db_session)
    slots[2].status = InterviewAvailabilityStatus.CANCELLED
    await db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        await service.select_user_availability(
            application_id=application.id, slot_id=slots[2].id, user=test_user
        )
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_the_database_refuses_a_second_booking_directly(db_session, application, slots):
    """The backstop, in case a future path skips the service."""
    from sqlalchemy.exc import IntegrityError

    slots[0].status = InterviewAvailabilityStatus.BOOKED
    slots[0].booked_at = datetime.utcnow()
    await db_session.commit()

    slots[1].status = InterviewAvailabilityStatus.BOOKED
    slots[1].booked_at = datetime.utcnow()
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_confirming_records_exactly_one_transition(db_session, application, slots, test_user):
    """The application is already at INTERVIEW, so confirming adds no event."""
    from app.models.applicationAnalyticsModel import ApplicationStatusEventModel

    service = InterviewService(db_session)
    await service.select_user_availability(
        application_id=application.id, slot_id=slots[0].id, user=test_user
    )

    events = (
        await db_session.execute(
            select(ApplicationStatusEventModel).where(
                ApplicationStatusEventModel.application_id == application.id
            )
        )
    ).scalars().all()
    assert list(events) == []
