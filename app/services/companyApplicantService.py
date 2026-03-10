from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.applicationModel import ApplicationModel
from app.models.userModel import User


class CompanyApplicantService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_company_applicants(
        self,
        *,
        company_id: UUID,
        job_posting_id: UUID | None = None,
    ) -> list[ApplicationModel]:
        query = (
            select(ApplicationModel)
            .options(
                selectinload(ApplicationModel.resume),
                selectinload(ApplicationModel.job_posting),
            )
            .where(ApplicationModel.company_id == company_id)
            .order_by(ApplicationModel.application_date.desc(), ApplicationModel.created_at.desc())
        )
        if job_posting_id is not None:
            query = query.where(ApplicationModel.job_posting_id == job_posting_id)

        result = await self.session.execute(query)
        applications = list(result.scalars().all())
        user_map = await self._get_users_for_applications(applications)
        for application in applications:
            application.user = user_map.get(application.user_id)
        return applications

    async def get_company_application(
        self,
        *,
        company_id: UUID,
        application_id: UUID,
    ) -> ApplicationModel | None:
        result = await self.session.execute(
            select(ApplicationModel)
            .options(
                selectinload(ApplicationModel.resume),
                selectinload(ApplicationModel.job_posting),
            )
            .where(
                ApplicationModel.id == application_id,
                ApplicationModel.company_id == company_id,
            )
            .limit(1)
        )
        application = result.scalar_one_or_none()
        if application is None:
            return None
        user_map = await self._get_users_for_applications([application])
        application.user = user_map.get(application.user_id)
        return application

    async def _get_users_for_applications(
        self,
        applications: list[ApplicationModel],
    ) -> dict[UUID, User]:
        user_ids = [application.user_id for application in applications if application.user_id is not None]
        if not user_ids:
            return {}

        result = await self.session.execute(
            select(User).where(User.id.in_(user_ids))
        )
        users = list(result.scalars().all())
        return {user.id: user for user in users}
