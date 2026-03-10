from __future__ import annotations

from datetime import datetime
from typing import Dict, List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.applicationAnalyticsModel import (
    ApplicationDailyAggregateModel,
    ApplicationEventType,
    ApplicationStatusEventModel,
)
from app.models.applicationModel import ApplicationModel, ApplicationStatus
from app.schemas.applicationSchema import ApplicationCreate, ApplicationUpdate


class ApplicationService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_application(self, *, user_id: UUID, payload: ApplicationCreate) -> ApplicationModel:
        now = datetime.utcnow()
        application = ApplicationModel(
            user_id=user_id,
            company_id=payload.company_id,
            job_posting_id=payload.job_posting_id,
            job_title=payload.job_title,
            status=payload.status,
            application_url=payload.application_url,
            notes=payload.notes,
            application_date=now,
        )
        self.session.add(application)
        await self.session.flush()

        await self._record_status_event(
            application=application,
            event_type=ApplicationEventType.CREATED,
            from_status=None,
            to_status=application.status,
            triggered_by_user_id=user_id,
            occurred_at=now,
        )
        await self._apply_daily_aggregate_delta(
            company_id=application.company_id,
            occurred_at=now,
            delta={
                "applications_created_count": 1,
                self._entered_status_field(application.status): 1,
            },
        )

        await self.session.commit()
        await self.session.refresh(application)
        return application

    async def list_user_applications(self, *, user_id: UUID) -> List[ApplicationModel]:
        result = await self.session.execute(
            select(ApplicationModel)
            .where(ApplicationModel.user_id == user_id)
            .order_by(ApplicationModel.created_at.desc())
        )
        return list(result.scalars().all())

    async def update_application(
        self,
        *,
        application_id: UUID,
        user_id: UUID,
        payload: ApplicationUpdate,
    ) -> ApplicationModel | None:
        application = await self._get_user_application(application_id=application_id, user_id=user_id)
        if application is None:
            return None

        previous_status = application.status
        update_data = payload.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(application, field, value)

        if "status" in update_data and application.status != previous_status:
            now = datetime.utcnow()
            await self._record_status_event(
                application=application,
                event_type=ApplicationEventType.STATUS_CHANGED,
                from_status=previous_status,
                to_status=application.status,
                triggered_by_user_id=user_id,
                occurred_at=now,
            )
            await self._apply_daily_aggregate_delta(
                company_id=application.company_id,
                occurred_at=now,
                delta={
                    "status_change_events_count": 1,
                    self._entered_status_field(application.status): 1,
                },
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
            select(ApplicationModel).where(
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
        occurred_at: datetime,
    ) -> None:
        event = ApplicationStatusEventModel(
            application_id=application.id,
            company_id=application.company_id,
            user_id=application.user_id,
            job_posting_id=application.job_posting_id,
            triggered_by_user_id=triggered_by_user_id,
            event_type=event_type,
            from_status=from_status,
            to_status=to_status,
            occurred_at=occurred_at,
        )
        self.session.add(event)

    async def _apply_daily_aggregate_delta(
        self,
        *,
        company_id: UUID,
        occurred_at: datetime,
        delta: Dict[str, int],
    ) -> None:
        metric_date = occurred_at.date()
        result = await self.session.execute(
            select(ApplicationDailyAggregateModel).where(
                ApplicationDailyAggregateModel.company_id == company_id,
                ApplicationDailyAggregateModel.metric_date == metric_date,
            )
        )
        aggregate = result.scalar_one_or_none()
        if aggregate is None:
            aggregate = ApplicationDailyAggregateModel(
                company_id=company_id,
                metric_date=metric_date,
            )
            self.session.add(aggregate)
            await self.session.flush()

        for field, increment in delta.items():
            current = getattr(aggregate, field, 0) or 0
            setattr(aggregate, field, current + increment)
        aggregate.updated_at = occurred_at

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
