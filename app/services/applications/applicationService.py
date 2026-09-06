from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from hashlib import sha256
from typing import Dict, List
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.applicationAnalyticsModel import (
    ApplicationDailyAggregateModel,
    ApplicationEventType,
    ApplicationStatusEventModel,
)
from app.models.applicationModel import (
    ApplicationMatchStrength,
    ApplicationModel,
    ApplicationStatus,
)
from app.models.companyRecruiterModel import CompanyRecruiter
from app.models.userModel import User
from app.models.resumeCourseEvaluationModel import (
    ResumeCourseEvaluationModel,
    ResumeCourseEvaluationStatus,
)
from app.models.resumeModel import ResumeModel
from app.schemas.applicationSchema import ApplicationCreate, ApplicationUpdate
from app.services.companies.companyRecruiterService import (
    ASSIGNABLE_COMPANY_RECRUITER_ROLES,
    recruiter_role_rank,
)
from app.services.notifications.emailNotificationService import EmailNotificationService


@dataclass(frozen=True)
class TransitionActor:
    """Who caused a transition. Exactly one side is set in practice.

    Carried explicitly because the event row is the authoritative history: an
    event without an actor cannot be explained afterwards.
    """

    user_id: UUID | None = None
    recruiter_id: UUID | None = None


@dataclass
class ApprovedResumeOption:
    resume: ResumeModel
    overall_score: float
    approved_at: datetime


class ApplicationService:
    MIN_APPROVED_RESUME_SCORE = 8.0
    APPROVED_RESUME_REQUIRED_MESSAGE = (
        "You need a Students Compass-approved resume with score 8+ before applying to this job."
    )

    def __init__(self, session: AsyncSession):
        self.session = session
        self.email_service = EmailNotificationService(session)

    async def record_application_created(
        self,
        application: ApplicationModel,
        *,
        actor: TransitionActor,
        occurred_at: datetime,
    ) -> None:
        """The opening move of an application's history."""
        await self._record_status_event(
            application=application,
            event_type=ApplicationEventType.CREATED,
            from_status=None,
            to_status=application.status,
            triggered_by_user_id=actor.user_id,
            triggered_by_company_recruiter_id=actor.recruiter_id,
            occurred_at=occurred_at,
        )
        await self._apply_daily_aggregate_delta(
            company_id=application.company_id,
            occurred_at=occurred_at,
            delta={
                "applications_created_count": 1,
                self._entered_status_field(application.status): 1,
            },
        )

    async def transition_status(
        self,
        application: ApplicationModel,
        *,
        to_status: ApplicationStatus,
        actor: TransitionActor,
        occurred_at: datetime | None = None,
    ) -> bool:
        """Move an application to ``to_status``: state, event and counters together.

        The single place a status may change. It used to be three places, and
        one of them — sharing interview availability — moved the application to
        INTERVIEW by assigning the attribute, so that transition left no event
        and no counter behind: the history and the dashboard disagreed with the
        application itself.

        Returns False when the application is already in that status. That makes
        a replayed command (a double-clicked button, a retried request) a no-op
        rather than a second event for a change that did not happen; callers
        holding the row lock are serialised, so the second one sees the result
        of the first.
        """
        if application.status == to_status:
            return False

        previous_status = application.status
        now = occurred_at or datetime.utcnow()
        application.status = to_status
        await self.session.flush()

        await self._record_status_event(
            application=application,
            event_type=ApplicationEventType.STATUS_CHANGED,
            from_status=previous_status,
            to_status=to_status,
            triggered_by_user_id=actor.user_id,
            triggered_by_company_recruiter_id=actor.recruiter_id,
            occurred_at=now,
        )
        await self._apply_daily_aggregate_delta(
            company_id=application.company_id,
            occurred_at=now,
            delta={
                "status_change_events_count": 1,
                self._entered_status_field(to_status): 1,
            },
        )
        return True

    async def lock_application(self, application_id: UUID) -> None:
        """Serialise transitions of one application against each other.

        Deliberately a bare id select: adding FOR UPDATE to the hydrating query
        would have PostgreSQL refuse the outer-joined relationships. SQLite has
        no row locks, which is why the concurrency claim is only proven in the
        PostgreSQL lane.
        """
        await self.session.execute(
            select(ApplicationModel.id)
            .where(ApplicationModel.id == application_id)
            .with_for_update()
        )

    async def create_application(self, *, user_id: UUID, payload: ApplicationCreate) -> ApplicationModel:
        if payload.job_posting_id is not None:
            existing_application = await self._get_existing_job_application(
                user_id=user_id,
                job_posting_id=payload.job_posting_id,
            )
            if existing_application is not None:
                return existing_application

        now = datetime.utcnow()
        application = ApplicationModel(
            user_id=user_id,
            company_id=payload.company_id,
            assigned_recruiter_id=await self._select_assigned_recruiter_id(company_id=payload.company_id),
            job_posting_id=payload.job_posting_id,
            resume_id=await self._select_resume_id(user_id=user_id, requested_resume_id=payload.resume_id),
            job_title=payload.job_title,
            status=payload.status,
            match_strength=self._generate_mock_match_strength(
                user_id=user_id,
                company_id=payload.company_id,
                job_posting_id=payload.job_posting_id,
                job_title=payload.job_title,
            ),
            application_url=payload.application_url,
            notes=payload.notes,
            application_date=now,
        )
        self.session.add(application)
        await self.session.flush()

        await self.record_application_created(
            application,
            actor=TransitionActor(user_id=user_id),
            occurred_at=now,
        )

        await self.session.commit()
        hydrated_application = await self._get_user_application(application_id=application.id, user_id=user_id)
        return hydrated_application or application

    async def _get_existing_job_application(
        self,
        *,
        user_id: UUID,
        job_posting_id: UUID,
    ) -> ApplicationModel | None:
        result = await self.session.execute(
            select(ApplicationModel)
            .options(
                selectinload(ApplicationModel.company),
                selectinload(ApplicationModel.interview_availabilities),
            )
            .where(
                ApplicationModel.user_id == user_id,
                ApplicationModel.job_posting_id == job_posting_id,
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_user_applications(self, *, user_id: UUID) -> List[ApplicationModel]:
        result = await self.session.execute(
            select(ApplicationModel)
            .options(
                selectinload(ApplicationModel.company),
                selectinload(ApplicationModel.interview_availabilities),
            )
            .where(ApplicationModel.user_id == user_id)
            .order_by(ApplicationModel.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_approved_resumes(self, *, user_id: UUID) -> list[ApprovedResumeOption]:
        result = await self.session.execute(
            select(ResumeModel, ResumeCourseEvaluationModel)
            .join(
                ResumeCourseEvaluationModel,
                ResumeCourseEvaluationModel.resume_id == ResumeModel.id,
            )
            .where(
                ResumeModel.user_id == user_id,
                ResumeCourseEvaluationModel.user_id == user_id,
                ResumeCourseEvaluationModel.status == ResumeCourseEvaluationStatus.COMPLETED,
                ResumeCourseEvaluationModel.pass_status.is_(True),
                ResumeCourseEvaluationModel.overall_score >= self.MIN_APPROVED_RESUME_SCORE,
            )
            .order_by(
                ResumeModel.created_at.desc(),
                ResumeCourseEvaluationModel.completed_at.desc(),
                ResumeCourseEvaluationModel.created_at.desc(),
            )
        )

        approved_options: list[ApprovedResumeOption] = []
        seen_resume_ids: set[UUID] = set()
        for resume, evaluation in result.all():
            if resume.id in seen_resume_ids:
                continue
            seen_resume_ids.add(resume.id)
            approved_options.append(
                ApprovedResumeOption(
                    resume=resume,
                    overall_score=float(evaluation.overall_score or 0.0),
                    approved_at=evaluation.completed_at or evaluation.created_at,
                )
            )
        return approved_options

    async def update_application(
        self,
        *,
        application_id: UUID,
        user_id: UUID,
        payload: ApplicationUpdate,
    ) -> ApplicationModel | None:
        # Lock before reading the current status: two requests that both read
        # "applied" would both write an event for the same single change.
        await self.lock_application(application_id)
        application = await self._get_user_application(application_id=application_id, user_id=user_id)
        if application is None:
            return None

        update_data = payload.dict(exclude_unset=True)
        requested_status = update_data.pop("status", None)
        for field, value in update_data.items():
            setattr(application, field, value)

        if requested_status is not None:
            await self.transition_status(
                application,
                to_status=requested_status,
                actor=TransitionActor(user_id=user_id),
            )

        await self.session.commit()
        hydrated_application = await self._get_user_application(application_id=application.id, user_id=user_id)
        return hydrated_application or application

    async def update_company_application(
        self,
        *,
        application_id: UUID,
        company_id: UUID,
        recruiter_id: UUID,
        status: ApplicationStatus,
        notes: str | None = None,
    ) -> ApplicationModel | None:
        await self.lock_application(application_id)
        result = await self.session.execute(
            select(ApplicationModel).where(
                ApplicationModel.id == application_id,
                ApplicationModel.company_id == company_id,
            )
        )
        application = result.scalar_one_or_none()
        if application is None:
            return None

        previous_status = application.status
        application.notes = notes
        application.assigned_recruiter_id = recruiter_id

        if await self.transition_status(
            application,
            to_status=status,
            actor=TransitionActor(recruiter_id=recruiter_id),
        ):
            await self._queue_company_status_change_email(
                application=application,
                recruiter_id=recruiter_id,
                previous_status=previous_status,
            )

        await self.session.commit()
        await self.session.refresh(application)
        return application

    async def delete_application(self, *, application_id: UUID, user_id: UUID) -> bool:
        application = await self._get_user_application(application_id=application_id, user_id=user_id)
        if application is None:
            return False

        now = datetime.utcnow()
        await self._record_status_event(
            application=application,
            event_type=ApplicationEventType.DELETED,
            from_status=application.status,
            to_status=None,
            triggered_by_user_id=user_id,
            occurred_at=now,
        )
        await self._apply_daily_aggregate_delta(
            company_id=application.company_id,
            occurred_at=now,
            delta={"applications_deleted_count": 1},
        )
        await self.session.flush()
        await self.session.delete(application)
        await self.session.commit()
        return True

    async def _get_user_application(self, *, application_id: UUID, user_id: UUID) -> ApplicationModel | None:
        result = await self.session.execute(
            select(ApplicationModel)
            .options(
                selectinload(ApplicationModel.company),
                selectinload(ApplicationModel.interview_availabilities),
            )
            .where(
                ApplicationModel.id == application_id,
                ApplicationModel.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def _record_status_event(
        self,
        *,
        application: ApplicationModel,
        event_type: ApplicationEventType,
        from_status: ApplicationStatus | None,
        to_status: ApplicationStatus | None,
        triggered_by_user_id: UUID | None,
        triggered_by_company_recruiter_id: UUID | None = None,
        occurred_at: datetime,
    ) -> None:
        event = ApplicationStatusEventModel(
            application_id=application.id,
            company_id=application.company_id,
            user_id=application.user_id,
            job_posting_id=application.job_posting_id,
            triggered_by_user_id=triggered_by_user_id,
            triggered_by_company_recruiter_id=triggered_by_company_recruiter_id,
            event_type=event_type,
            from_status=from_status,
            to_status=to_status,
            occurred_at=occurred_at,
        )
        self.session.add(event)

    async def _select_assigned_recruiter_id(self, *, company_id: UUID) -> UUID | None:
        result = await self.session.execute(
            select(CompanyRecruiter)
            .where(
                CompanyRecruiter.company_id == company_id,
                CompanyRecruiter.is_active.is_(True),
                CompanyRecruiter.role.in_(ASSIGNABLE_COMPANY_RECRUITER_ROLES),
            )
            .order_by(CompanyRecruiter.created_at.asc())
        )
        recruiters = list(result.scalars().all())
        if not recruiters:
            return None

        # Same seniority order the recruiter list uses; shared, not copied.
        recruiters.sort(key=lambda recruiter: (recruiter_role_rank(recruiter.role), recruiter.created_at))
        return recruiters[0].id

    async def _select_resume_id(
        self,
        *,
        user_id: UUID,
        requested_resume_id: UUID | None,
    ) -> UUID | None:
        approved_resumes = await self.list_approved_resumes(user_id=user_id)

        if requested_resume_id is not None:
            for option in approved_resumes:
                if option.resume.id == requested_resume_id:
                    return option.resume.id
            raise HTTPException(
                status_code=400,
                detail=self.APPROVED_RESUME_REQUIRED_MESSAGE,
            )

        if approved_resumes:
            return approved_resumes[0].resume.id

        raise HTTPException(
            status_code=400,
            detail=self.APPROVED_RESUME_REQUIRED_MESSAGE,
        )

    # Every counter column, so the upsert below can insert a complete row.
    _AGGREGATE_COUNTERS = (
        "applications_created_count",
        "applications_deleted_count",
        "status_change_events_count",
        "entered_applied_count",
        "entered_in_review_count",
        "entered_interview_count",
        "entered_offer_count",
        "entered_rejected_count",
        "entered_withdrawn_count",
    )

    async def _apply_daily_aggregate_delta(
        self,
        *,
        company_id: UUID,
        occurred_at: datetime,
        delta: Dict[str, int],
    ) -> None:
        """Add to a company's daily counters without reading them first.

        Read-modify-write lost increments: two transitions in the same second
        both read 4, both wrote 5. Worse, both could find no row and both try to
        create one, and the unique constraint turned an analytics update into a
        failed request. One upsert with SQL-side addition does neither — the
        database resolves the collision and the increment is applied to whatever
        the row holds at that moment.
        """
        table = ApplicationDailyAggregateModel.__table__
        metric_date = occurred_at.date()

        values = {
            "id": uuid4(),
            "company_id": company_id,
            "metric_date": metric_date,
            "created_at": occurred_at,
            "updated_at": occurred_at,
        }
        for counter in self._AGGREGATE_COUNTERS:
            values[counter] = int(delta.get(counter, 0))

        insert_statement = self._dialect_insert()(table).values(**values)
        statement = insert_statement.on_conflict_do_update(
            index_elements=["company_id", "metric_date"],
            set_={
                **{
                    counter: table.c[counter] + int(increment)
                    for counter, increment in delta.items()
                },
                "updated_at": occurred_at,
            },
        )
        await self.session.execute(statement)

    async def rebuild_daily_aggregates(self, *, company_id: UUID, since: date) -> int:
        """Recompute a company's daily counters from the event log.

        The events are the authoritative history and the counters are a
        projection of them, so the projection can always be rebuilt — **from the
        cut-off onwards**. Before it, the log is incomplete by construction:
        moving a candidate to INTERVIEW by sharing availability wrote no event
        at all, so rebuilding across that period would replace correct counters
        with an undercount. That is why this is an explicit operation with a
        ``since`` and never runs on its own.

        Returns the number of day rows written.
        """
        counter_by_status = {
            status: self._entered_status_field(status) for status in ApplicationStatus
        }
        events = (
            await self.session.execute(
                select(
                    func.date(ApplicationStatusEventModel.occurred_at).label("metric_date"),
                    ApplicationStatusEventModel.event_type,
                    ApplicationStatusEventModel.to_status,
                    func.count(ApplicationStatusEventModel.id),
                )
                .where(
                    ApplicationStatusEventModel.company_id == company_id,
                    ApplicationStatusEventModel.occurred_at >= datetime.combine(since, time.min),
                )
                .group_by(
                    func.date(ApplicationStatusEventModel.occurred_at),
                    ApplicationStatusEventModel.event_type,
                    ApplicationStatusEventModel.to_status,
                )
            )
        ).all()

        by_day: Dict[date, Dict[str, int]] = {}
        for metric_date, event_type, to_status, count in events:
            if isinstance(metric_date, str):  # SQLite returns dates as text
                metric_date = date.fromisoformat(metric_date)
            day = by_day.setdefault(metric_date, {counter: 0 for counter in self._AGGREGATE_COUNTERS})
            if event_type == ApplicationEventType.CREATED:
                day["applications_created_count"] += count
            elif event_type == ApplicationEventType.STATUS_CHANGED:
                day["status_change_events_count"] += count
            elif event_type == ApplicationEventType.DELETED:
                day["applications_deleted_count"] += count
            if to_status is not None:
                day[counter_by_status[to_status]] += count

        for metric_date, counters in by_day.items():
            table = ApplicationDailyAggregateModel.__table__
            now = datetime.utcnow()
            statement = self._dialect_insert()(table).values(
                id=uuid4(),
                company_id=company_id,
                metric_date=metric_date,
                created_at=now,
                updated_at=now,
                **counters,
            )
            # A rebuild *replaces* the day, unlike the incremental delta, which
            # adds to it: the event log is the whole truth for that day.
            await self.session.execute(
                statement.on_conflict_do_update(
                    index_elements=["company_id", "metric_date"],
                    set_={**counters, "updated_at": now},
                )
            )
        return len(by_day)

    def _dialect_insert(self):
        """``INSERT ... ON CONFLICT DO UPDATE`` exists on both lanes, separately."""
        if self.session.get_bind().dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as dialect_insert
        else:
            from sqlalchemy.dialects.sqlite import insert as dialect_insert
        return dialect_insert

    @staticmethod
    def _entered_status_field(status: ApplicationStatus) -> str:
        return {
            ApplicationStatus.APPLIED: "entered_applied_count",
            ApplicationStatus.IN_REVIEW: "entered_in_review_count",
            ApplicationStatus.INTERVIEW: "entered_interview_count",
            ApplicationStatus.OFFER: "entered_offer_count",
            ApplicationStatus.REJECTED: "entered_rejected_count",
            ApplicationStatus.WITHDRAWN: "entered_withdrawn_count",
        }[status]

    @staticmethod
    def _generate_mock_match_strength(
        *,
        user_id: UUID,
        company_id: UUID,
        job_posting_id: UUID | None,
        job_title: str,
    ) -> ApplicationMatchStrength:
        fingerprint = "|".join(
            [
                str(user_id),
                str(company_id),
                str(job_posting_id or ""),
                job_title.strip().lower(),
            ]
        )
        bucket = int(sha256(fingerprint.encode("utf-8")).hexdigest(), 16) % 3
        return (
            ApplicationMatchStrength.STRONG_MATCH
            if bucket == 0
            else ApplicationMatchStrength.MATCH
            if bucket == 1
            else ApplicationMatchStrength.WEAK_MATCH
        )

    async def _queue_company_status_change_email(
        self,
        *,
        application: ApplicationModel,
        recruiter_id: UUID,
        previous_status: ApplicationStatus,
    ) -> None:
        if application.status != ApplicationStatus.IN_REVIEW or previous_status == ApplicationStatus.IN_REVIEW:
            return

        candidate = await self.session.scalar(select(User).where(User.id == application.user_id))
        recruiter = await self.session.scalar(select(CompanyRecruiter).where(CompanyRecruiter.id == recruiter_id))
        if candidate is None:
            return

        recruiter_name = " ".join(
            part for part in [
                recruiter.first_name if recruiter else None,
                recruiter.last_name if recruiter else None,
            ] if part
        ).strip() or (recruiter.email if recruiter else "Students Compass")

        await self.email_service.queue_mock_email(
            recipient_email=candidate.email,
            recipient_name=" ".join(
                part for part in [candidate.first_name, candidate.last_name] if part
            ).strip() or candidate.email,
            template_key="candidate_selected_for_review",
            subject=f"Your application for {application.job_title} is now in review",
            body_preview=f"{recruiter_name} moved your application for {application.job_title} to the next phase.",
            payload={
                "application_id": str(application.id),
                "job_title": application.job_title,
                "status": application.status.value,
            },
            application_id=application.id,
            company_id=application.company_id,
            recruiter_id=recruiter_id,
            user_id=candidate.id,
        )
