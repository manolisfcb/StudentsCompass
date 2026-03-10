from __future__ import annotations

from datetime import datetime
from typing import Sequence
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.companyModel import Company
from app.models.jobPostingModel import JobPosting
from app.schemas.jobPostingSchema import CompanyJobPostingCreate, JobPostingUpdate


class JobPostingService:
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _is_open_expression():
        now = datetime.utcnow()
        return (
            JobPosting.is_active.is_(True),
            or_(JobPosting.expires_at.is_(None), JobPosting.expires_at >= now),
        )

    @staticmethod
    def _keyword_filter_expression(keywords: str):
        tokens = [token.strip().lower() for token in keywords.replace("\n", " ").replace(",", " ").split() if token.strip()]
        if not tokens:
            return None

        token_filters = []
        for token in tokens[:10]:
            normalized = f"%{token}%"
            token_filters.append(
                or_(
                    func.lower(func.coalesce(JobPosting.title, "")).like(normalized),
                    func.lower(func.coalesce(JobPosting.description, "")).like(normalized),
                    func.lower(func.coalesce(JobPosting.requirements, "")).like(normalized),
                    func.lower(func.coalesce(JobPosting.responsibilities, "")).like(normalized),
                    func.lower(func.coalesce(JobPosting.location, "")).like(normalized),
                    func.lower(func.coalesce(JobPosting.job_type, "")).like(normalized),
                    func.lower(func.coalesce(JobPosting.workplace_type, "")).like(normalized),
                    func.lower(func.coalesce(JobPosting.seniority_level, "")).like(normalized),
                    func.lower(func.coalesce(JobPosting.benefits, "")).like(normalized),
                    func.lower(func.coalesce(JobPosting.listed_context, "")).like(normalized),
                    func.lower(func.coalesce(JobPosting.source_context, "")).like(normalized),
                    func.lower(func.coalesce(Company.company_name, "")).like(normalized),
                    func.lower(func.coalesce(Company.description, "")).like(normalized),
                )
            )
        return and_(*token_filters)

    @staticmethod
    def _location_filter_expression(location: str):
        normalized = f"%{location.strip().lower()}%"
        return or_(
            func.lower(func.coalesce(JobPosting.location, "")).like(normalized),
            func.lower(func.coalesce(Company.location, "")).like(normalized),
        )

    async def create_for_company(
        self,
        company_id: UUID,
        payload: CompanyJobPostingCreate,
    ) -> JobPosting:
        job_posting = JobPosting(
            company_id=company_id,
            title=payload.title.strip(),
            description=payload.description,
            requirements=payload.requirements,
            responsibilities=payload.responsibilities,
            location=payload.location,
            job_type=payload.job_type,
            workplace_type=payload.workplace_type,
            seniority_level=payload.seniority_level,
            salary_range=payload.salary_range,
            benefits=payload.benefits,
            listed_context=payload.listed_context,
            source_context=payload.source_context,
            application_url=payload.application_url,
            is_active=payload.is_active,
            expires_at=payload.expires_at,
        )
        self.session.add(job_posting)
        await self.session.commit()
        await self.session.refresh(job_posting)
        await self.session.refresh(job_posting, attribute_names=["company"])
        return job_posting

    async def list_company_job_postings(
        self,
        company_id: UUID,
        *,
        include_closed: bool = True,
        limit: int = 50,
    ) -> Sequence[JobPosting]:
        query = (
            select(JobPosting)
            .options(selectinload(JobPosting.company))
            .where(JobPosting.company_id == company_id)
            .order_by(JobPosting.created_at.desc())
            .limit(limit)
        )
        if not include_closed:
            query = query.where(*self._is_open_expression())

        result = await self.session.execute(query)
        return result.scalars().all()

    async def list_public_job_postings(
        self,
        *,
        keywords: str | None = None,
        location: str | None = None,
        limit: int = 50,
    ) -> Sequence[JobPosting]:
        query = (
            select(JobPosting)
            .join(Company, Company.id == JobPosting.company_id)
            .options(selectinload(JobPosting.company))
            .where(*self._is_open_expression())
            .order_by(JobPosting.created_at.desc())
            .limit(limit)
        )

        if keywords and keywords.strip():
            keyword_filter = self._keyword_filter_expression(keywords)
            if keyword_filter is not None:
                query = query.where(keyword_filter)

        if location and location.strip():
            query = query.where(self._location_filter_expression(location))

        result = await self.session.execute(query)
        return result.scalars().all()

    async def update_company_job_posting(
        self,
        company_id: UUID,
        job_posting_id: UUID,
        payload: JobPostingUpdate,
    ) -> JobPosting | None:
        result = await self.session.execute(
            select(JobPosting)
            .options(selectinload(JobPosting.company))
            .where(JobPosting.id == job_posting_id, JobPosting.company_id == company_id)
        )
        job_posting = result.scalar_one_or_none()
        if job_posting is None:
            return None

        updates = payload.model_dump(exclude_unset=True)
        if "title" in updates and updates["title"] is not None:
            updates["title"] = updates["title"].strip()

        for field, value in updates.items():
            setattr(job_posting, field, value)

        await self.session.commit()
        await self.session.refresh(job_posting)
        return job_posting

    async def delete_company_job_posting(
        self,
        company_id: UUID,
        job_posting_id: UUID,
    ) -> bool:
        result = await self.session.execute(
            select(JobPosting).where(
                JobPosting.id == job_posting_id,
                JobPosting.company_id == company_id,
            )
        )
        job_posting = result.scalar_one_or_none()
        if job_posting is None:
            return False

        await self.session.delete(job_posting)
        await self.session.commit()
        return True
