"""Every status change leaves the same trace, whoever makes it.

An application's status lived in three places that each wrote it their own way,
and one of them — sharing interview availability — wrote it silently. So the
application said INTERVIEW while the history said the candidate was still under
review and the company's daily counters had never heard of it.

These tests state the invariant instead: status, event and counters move
together, exactly once per real change.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.models.applicationAnalyticsModel import (
    ApplicationDailyAggregateModel,
    ApplicationEventType,
    ApplicationStatusEventModel,
)
from app.models.applicationModel import ApplicationModel, ApplicationStatus
from app.schemas.applicationSchema import ApplicationUpdate
from app.services.applications.applicationService import ApplicationService, TransitionActor


# The company and recruiter come from the shared fixtures in conftest; only the
# application is specific to these tests.
@pytest.fixture
def company(test_company):
    return test_company


@pytest.fixture
def recruiter(test_company_recruiter):
    return test_company_recruiter


@pytest.fixture
async def application(db_session, test_user, company):
    model = ApplicationModel(
        id=uuid.uuid4(),
        user_id=test_user.id,
        company_id=company.id,
        job_title="Backend Intern",
        status=ApplicationStatus.APPLIED,
        application_date=datetime.utcnow(),
    )
    db_session.add(model)
    await db_session.commit()
    return model


async def _events(session, application_id):
    result = await session.execute(
        select(ApplicationStatusEventModel)
        .where(ApplicationStatusEventModel.application_id == application_id)
        .order_by(ApplicationStatusEventModel.occurred_at)
        .execution_options(populate_existing=True)
    )
    return list(result.scalars())


async def _aggregate(session, company_id, metric_date=None):
    return await session.scalar(
        select(ApplicationDailyAggregateModel)
        .where(
            ApplicationDailyAggregateModel.company_id == company_id,
            ApplicationDailyAggregateModel.metric_date == (metric_date or datetime.utcnow().date()),
        )
        .execution_options(populate_existing=True)
    )


@pytest.mark.asyncio
async def test_a_transition_writes_status_event_and_counter_together(
    db_session, application, company, recruiter
):
    service = ApplicationService(db_session)

    changed = await service.transition_status(
        application,
        to_status=ApplicationStatus.IN_REVIEW,
        actor=TransitionActor(recruiter_id=recruiter.id),
    )
    await db_session.commit()

    assert changed is True
    assert application.status == ApplicationStatus.IN_REVIEW

    events = await _events(db_session, application.id)
    assert [event.event_type for event in events] == [ApplicationEventType.STATUS_CHANGED]
    assert events[0].from_status == ApplicationStatus.APPLIED
    assert events[0].to_status == ApplicationStatus.IN_REVIEW
    assert events[0].triggered_by_company_recruiter_id == recruiter.id

    aggregate = await _aggregate(db_session, company.id)
    assert aggregate.status_change_events_count == 1
    assert aggregate.entered_in_review_count == 1


@pytest.mark.asyncio
async def test_repeating_a_transition_records_nothing(db_session, application, company, recruiter):
    """A replayed command is not a second change."""
    service = ApplicationService(db_session)

    await service.transition_status(
        application,
        to_status=ApplicationStatus.IN_REVIEW,
        actor=TransitionActor(recruiter_id=recruiter.id),
    )
    await db_session.commit()
    repeated = await service.transition_status(
        application,
        to_status=ApplicationStatus.IN_REVIEW,
        actor=TransitionActor(recruiter_id=recruiter.id),
    )
    await db_session.commit()

    assert repeated is False
    assert len(await _events(db_session, application.id)) == 1
    aggregate = await _aggregate(db_session, company.id)
    assert aggregate.status_change_events_count == 1


@pytest.mark.asyncio
async def test_sharing_interview_availability_records_the_transition(
    db_session, application, company, recruiter, test_user
):
    """The transition that used to be invisible."""
    from app.schemas.interviewSchema import (
        InterviewAvailabilityPublishRequest,
        InterviewAvailabilityCreate,
    )
    from app.services.jobs.interviewService import InterviewService

    application.status = ApplicationStatus.IN_REVIEW
    application.assigned_recruiter_id = recruiter.id
    await db_session.commit()

    starts_at = datetime.utcnow() + timedelta(days=2)
    await InterviewService(db_session).publish_company_availabilities(
        application_id=application.id,
        recruiter=recruiter,
        payload=InterviewAvailabilityPublishRequest(
            slots=[
                InterviewAvailabilityCreate(
                    starts_at=starts_at,
                    ends_at=starts_at + timedelta(hours=1),
                    timezone="America/Toronto",
                )
            ],
            notes="Two options attached.",
        ),
    )

    refreshed = await db_session.scalar(
        select(ApplicationModel)
        .where(ApplicationModel.id == application.id)
        .execution_options(populate_existing=True)
    )
    assert refreshed.status == ApplicationStatus.INTERVIEW

    events = await _events(db_session, application.id)
    interview_events = [e for e in events if e.to_status == ApplicationStatus.INTERVIEW]
    assert len(interview_events) == 1, "publishing availability is one transition, with one event"
    assert interview_events[0].from_status == ApplicationStatus.IN_REVIEW
    assert interview_events[0].triggered_by_company_recruiter_id == recruiter.id

    aggregate = await _aggregate(db_session, company.id)
    assert aggregate.entered_interview_count == 1
    assert aggregate.status_change_events_count == 1


@pytest.mark.asyncio
async def test_publishing_availability_twice_does_not_double_count(
    db_session, application, recruiter, company
):
    from app.schemas.interviewSchema import (
        InterviewAvailabilityPublishRequest,
        InterviewAvailabilityCreate,
    )
    from app.services.jobs.interviewService import InterviewService

    application.status = ApplicationStatus.IN_REVIEW
    application.assigned_recruiter_id = recruiter.id
    await db_session.commit()

    service = InterviewService(db_session)
    starts_at = datetime.utcnow() + timedelta(days=2)
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

    for _ in range(2):
        await service.publish_company_availabilities(
            application_id=application.id, recruiter=recruiter, payload=payload
        )

    events = await _events(db_session, application.id)
    assert len([e for e in events if e.to_status == ApplicationStatus.INTERVIEW]) == 1
    aggregate = await _aggregate(db_session, company.id)
    assert aggregate.entered_interview_count == 1


@pytest.mark.asyncio
async def test_a_student_status_change_is_recorded_with_the_student_as_actor(
    db_session, application, company, test_user
):
    service = ApplicationService(db_session)

    await service.update_application(
        application_id=application.id,
        user_id=test_user.id,
        payload=ApplicationUpdate(status=ApplicationStatus.WITHDRAWN),
    )

    events = await _events(db_session, application.id)
    assert [event.to_status for event in events] == [ApplicationStatus.WITHDRAWN]
    assert events[0].triggered_by_user_id == test_user.id
    assert events[0].triggered_by_company_recruiter_id is None
    aggregate = await _aggregate(db_session, company.id)
    assert aggregate.entered_withdrawn_count == 1


@pytest.mark.asyncio
async def test_updating_other_fields_records_no_transition(db_session, application, test_user):
    service = ApplicationService(db_session)

    await service.update_application(
        application_id=application.id,
        user_id=test_user.id,
        payload=ApplicationUpdate(notes="Recruiter replied by email."),
    )

    assert await _events(db_session, application.id) == []


@pytest.mark.asyncio
async def test_counters_accumulate_across_many_transitions(db_session, application, company, recruiter):
    """Twenty changes, twenty counted — the read-modify-write lost some."""
    service = ApplicationService(db_session)
    ladder = [ApplicationStatus.IN_REVIEW, ApplicationStatus.INTERVIEW, ApplicationStatus.OFFER,
              ApplicationStatus.APPLIED]

    for index in range(20):
        await service.transition_status(
            application,
            to_status=ladder[index % len(ladder)],
            actor=TransitionActor(recruiter_id=recruiter.id),
        )
    await db_session.commit()

    aggregate = await _aggregate(db_session, company.id)
    assert aggregate.status_change_events_count == 20
    assert (
        aggregate.entered_in_review_count
        + aggregate.entered_interview_count
        + aggregate.entered_offer_count
        + aggregate.entered_applied_count
    ) == 20

    total_events = await db_session.scalar(
        select(func.count(ApplicationStatusEventModel.id)).where(
            ApplicationStatusEventModel.application_id == application.id
        )
    )
    assert total_events == 20


@pytest.mark.asyncio
async def test_the_schema_and_the_column_share_one_enum(db_session):
    """A value valid in the API but unknown to the table was possible before."""
    from app.models.applicationModel import ApplicationStatus as ColumnStatus
    from app.schemas.applicationSchema import ApplicationStatus as SchemaStatus

    assert SchemaStatus is ColumnStatus
    assert [status.value for status in SchemaStatus] == [
        "applied",
        "in_review",
        "interview",
        "offer",
        "rejected",
        "withdrawn",
    ]


@pytest.mark.asyncio
async def test_counters_can_be_rebuilt_from_the_event_log(
    db_session, application, company, recruiter, test_user
):
    """The counters are a projection: the events can always redraw them.

    Only from the cut-off onwards, which is why the rebuild takes a ``since``.
    """
    from app.models.applicationAnalyticsModel import ApplicationDailyAggregateModel

    service = ApplicationService(db_session)
    for status in (ApplicationStatus.IN_REVIEW, ApplicationStatus.INTERVIEW, ApplicationStatus.OFFER):
        await service.transition_status(
            application,
            to_status=status,
            actor=TransitionActor(recruiter_id=recruiter.id),
        )
    await db_session.commit()

    # Corrupt the projection the way a lost increment would.
    aggregate = await _aggregate(db_session, company.id)
    aggregate.status_change_events_count = 1
    aggregate.entered_interview_count = 0
    await db_session.commit()

    days = await service.rebuild_daily_aggregates(
        company_id=company.id, since=datetime.utcnow().date()
    )
    await db_session.commit()

    assert days == 1
    rebuilt = await _aggregate(db_session, company.id)
    assert rebuilt.status_change_events_count == 3
    assert rebuilt.entered_in_review_count == 1
    assert rebuilt.entered_interview_count == 1
    assert rebuilt.entered_offer_count == 1


@pytest.mark.asyncio
async def test_the_rebuild_ignores_days_before_the_cut_off(
    db_session, application, company, recruiter
):
    """History older than the cut-off is incomplete; it must be left alone."""
    from datetime import timedelta

    service = ApplicationService(db_session)
    yesterday = datetime.utcnow() - timedelta(days=1)
    await service.transition_status(
        application,
        to_status=ApplicationStatus.IN_REVIEW,
        actor=TransitionActor(recruiter_id=recruiter.id),
        occurred_at=yesterday,
    )
    await db_session.commit()

    days = await service.rebuild_daily_aggregates(
        company_id=company.id, since=datetime.utcnow().date()
    )
    await db_session.commit()

    assert days == 0
    untouched = await _aggregate(db_session, company.id, metric_date=yesterday.date())
    assert untouched.status_change_events_count == 1
