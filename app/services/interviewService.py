from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.applicationModel import ApplicationModel, ApplicationStatus
from app.models.companyRecruiterModel import CompanyRecruiter
from app.models.interviewAvailabilityModel import (
    InterviewAvailabilityModel,
    InterviewAvailabilityStatus,
)
from app.models.userModel import User
from app.schemas.interviewSchema import InterviewAvailabilityPublishRequest
from app.services.emailNotificationService import EmailNotificationService


class InterviewService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.email_service = EmailNotificationService(session)

    async def publish_company_availabilities(
        self,
        *,
        application_id: UUID,
        recruiter: CompanyRecruiter,
        payload: InterviewAvailabilityPublishRequest,
    ) -> ApplicationModel:
        application = await self._get_company_application(
            application_id=application_id,
            company_id=recruiter.company_id,
        )
        if application is None:
            raise HTTPException(status_code=404, detail="Application not found")

        if application.status not in {ApplicationStatus.IN_REVIEW, ApplicationStatus.INTERVIEW}:
            raise HTTPException(status_code=400, detail="Interview availability can only be shared for selected candidates")

        await self._cancel_existing_open_slots(application_id=application.id)

        now = datetime.utcnow()
        created_slots: list[InterviewAvailabilityModel] = []
        for slot in payload.slots:
            if slot.ends_at <= slot.starts_at:
                raise HTTPException(status_code=400, detail="Interview slot end time must be after start time")
            interview_slot = InterviewAvailabilityModel(
                application_id=application.id,
                company_id=application.company_id,
                recruiter_id=recruiter.id,
                candidate_id=application.user_id,
                starts_at=slot.starts_at,
                ends_at=slot.ends_at,
                timezone=slot.timezone,
                notes=slot.notes,
                status=InterviewAvailabilityStatus.AVAILABLE,
                created_at=now,
                updated_at=now,
            )
            self.session.add(interview_slot)
            created_slots.append(interview_slot)

        application.status = ApplicationStatus.INTERVIEW
        application.assigned_recruiter_id = recruiter.id
        application.notes = payload.notes or "Interview availabilities shared by recruiter."
        await self.session.flush()

        candidate = await self._get_user(application.user_id)
        recruiter_name = self._display_name(recruiter.first_name, recruiter.last_name, recruiter.email)
        await self.email_service.queue_mock_email(
            recipient_email=candidate.email,
            recipient_name=self._display_name(candidate.first_name, candidate.last_name, candidate.email),
            template_key="candidate_interview_availability_shared",
            subject=f"Interview availability shared for {application.job_title}",
            body_preview=(
                f"{recruiter_name} shared {len(created_slots)} interview availability option(s) for {application.job_title}."
            ),
            payload={
                "application_id": str(application.id),
                "job_title": application.job_title,
                "slot_count": len(created_slots),
                "timezone": created_slots[0].timezone if created_slots else "America/Toronto",
            },
            application_id=application.id,
            company_id=application.company_id,
            recruiter_id=recruiter.id,
            user_id=candidate.id,
        )

        await self.session.commit()
        return await self._get_company_application(application_id=application.id, company_id=recruiter.company_id)

    async def list_user_availabilities(
        self,
        *,
        application_id: UUID,
        user_id: UUID,
    ) -> ApplicationModel:
        application = await self._get_user_application(application_id=application_id, user_id=user_id)
        if application is None:
            raise HTTPException(status_code=404, detail="Application not found")
        return application

    async def select_user_availability(
        self,
        *,
        application_id: UUID,
        slot_id: UUID,
        user: User,
    ) -> ApplicationModel:
        application = await self._get_user_application(application_id=application_id, user_id=user.id)
        if application is None:
            raise HTTPException(status_code=404, detail="Application not found")

        slot = await self.session.scalar(
            select(InterviewAvailabilityModel).where(
                InterviewAvailabilityModel.id == slot_id,
                InterviewAvailabilityModel.application_id == application.id,
            )
        )
        if slot is None:
            raise HTTPException(status_code=404, detail="Interview slot not found")
        if slot.status != InterviewAvailabilityStatus.AVAILABLE:
            raise HTTPException(status_code=400, detail="Interview slot is no longer available")

        now = datetime.utcnow()
        slot.status = InterviewAvailabilityStatus.BOOKED
        slot.booked_at = now
        slot.updated_at = now

        open_slots = await self.session.execute(
            select(InterviewAvailabilityModel).where(
                InterviewAvailabilityModel.application_id == application.id,
                InterviewAvailabilityModel.status == InterviewAvailabilityStatus.AVAILABLE,
                InterviewAvailabilityModel.id != slot.id,
            )
        )
        for pending_slot in open_slots.scalars().all():
            pending_slot.status = InterviewAvailabilityStatus.CANCELLED
            pending_slot.updated_at = now

        recruiter = await self._get_recruiter(slot.recruiter_id)
        recruiter_name = self._display_name(
            recruiter.first_name if recruiter else None,
            recruiter.last_name if recruiter else None,
            recruiter.email if recruiter else None,
        )
        candidate_name = self._display_name(user.first_name, user.last_name, user.email)

        await self.email_service.queue_mock_email(
            recipient_email=user.email,
            recipient_name=candidate_name,
            template_key="candidate_interview_confirmed",
            subject=f"Interview confirmed for {application.job_title}",
            body_preview=(
                f"Your interview for {application.job_title} is confirmed on {slot.starts_at.isoformat()} ({slot.timezone})."
            ),
            payload={
                "application_id": str(application.id),
                "slot_id": str(slot.id),
                "starts_at": slot.starts_at.isoformat(),
                "ends_at": slot.ends_at.isoformat(),
                "timezone": slot.timezone,
            },
            application_id=application.id,
            company_id=application.company_id,
            recruiter_id=slot.recruiter_id,
            user_id=user.id,
        )

        if recruiter is not None:
            await self.email_service.queue_mock_email(
                recipient_email=recruiter.email,
                recipient_name=recruiter_name,
                template_key="recruiter_interview_confirmed",
                subject=f"{candidate_name} confirmed an interview for {application.job_title}",
                body_preview=(
                    f"{candidate_name} selected the interview slot on {slot.starts_at.isoformat()} ({slot.timezone})."
                ),
                payload={
                    "application_id": str(application.id),
                    "slot_id": str(slot.id),
                    "candidate_name": candidate_name,
                    "starts_at": slot.starts_at.isoformat(),
                    "ends_at": slot.ends_at.isoformat(),
                    "timezone": slot.timezone,
                },
                application_id=application.id,
                company_id=application.company_id,
                recruiter_id=recruiter.id,
                user_id=user.id,
            )

        await self.session.commit()
        return await self._get_user_application(application_id=application.id, user_id=user.id)

    async def _cancel_existing_open_slots(self, *, application_id: UUID) -> None:
        result = await self.session.execute(
            select(InterviewAvailabilityModel).where(
                InterviewAvailabilityModel.application_id == application_id,
                InterviewAvailabilityModel.status == InterviewAvailabilityStatus.AVAILABLE,
            )
        )
        now = datetime.utcnow()
        for slot in result.scalars().all():
            slot.status = InterviewAvailabilityStatus.CANCELLED
            slot.updated_at = now

    async def _get_company_application(self, *, application_id: UUID, company_id: UUID) -> ApplicationModel | None:
        result = await self.session.execute(
            select(ApplicationModel)
            .execution_options(populate_existing=True)
            .options(selectinload(ApplicationModel.interview_availabilities))
            .where(
                ApplicationModel.id == application_id,
                ApplicationModel.company_id == company_id,
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _get_user_application(self, *, application_id: UUID, user_id: UUID) -> ApplicationModel | None:
        result = await self.session.execute(
            select(ApplicationModel)
            .execution_options(populate_existing=True)
            .options(selectinload(ApplicationModel.interview_availabilities), selectinload(ApplicationModel.company))
            .where(
                ApplicationModel.id == application_id,
                ApplicationModel.user_id == user_id,
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _get_user(self, user_id: UUID) -> User:
        user = await self.session.scalar(select(User).where(User.id == user_id))
        if user is None:
            raise HTTPException(status_code=404, detail="Candidate not found")
        return user

    async def _get_recruiter(self, recruiter_id: UUID | None) -> CompanyRecruiter | None:
        if recruiter_id is None:
            return None
        return await self.session.scalar(select(CompanyRecruiter).where(CompanyRecruiter.id == recruiter_id))

    @staticmethod
    def _display_name(first_name: str | None, last_name: str | None, fallback: str | None) -> str:
        full_name = " ".join(part for part in [first_name, last_name] if part).strip()
        return full_name or (fallback or "User")
