"""
Admin service – guards, helpers, and data-fetching logic for the admin panel.

Admin access is gated on the `is_superuser` flag that FastAPI-Users already
provides on every User row.  The dependency `current_admin_user` can be
injected into any route that should be admin-only.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional, Sequence

from fastapi import Depends, HTTPException, status
from sqlalchemy import func, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session
from app.models.userModel import User
from app.models.communityModel import CommunityModel, CommunityMemberModel
from app.models.resourceModel import ResourceModel
from app.models.jobPostingModel import JobPosting
from app.models.companyModel import Company
from app.models.applicationModel import ApplicationModel
from app.models.questionnaireModel import UserQuestionnaire
from app.models.resumeModel import ResumeModel
from app.models.userStatsModel import UserStatsModel
from app.services.userService import current_active_user
from app.schemas.resourceSchema import ResourceCreate


# ---------------------------------------------------------------------------
# Dependency: require a logged-in superuser
# ---------------------------------------------------------------------------

async def current_admin_user(user: User = Depends(current_active_user)) -> User:
    """Dependency that raises 403 if the logged-in user is not a superuser."""
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required.",
        )
    return user


# ---------------------------------------------------------------------------
# Admin data service
# ---------------------------------------------------------------------------

class AdminService:
    """Encapsulates read/write operations the admin panel needs."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ── Dashboard stats ────────────────────────────────────────────────
    async def get_dashboard_stats(self) -> dict:
        total_users = (await self.session.execute(select(func.count(User.id)))).scalar() or 0
        total_companies = (await self.session.execute(select(func.count(Company.id)))).scalar() or 0
        total_communities = (await self.session.execute(select(func.count(CommunityModel.id)))).scalar() or 0
        total_resources = (await self.session.execute(select(func.count(ResourceModel.id)))).scalar() or 0
        total_jobs = (await self.session.execute(select(func.count(JobPosting.id)))).scalar() or 0
        total_applications = (await self.session.execute(select(func.count(ApplicationModel.id)))).scalar() or 0
        total_resumes = (await self.session.execute(select(func.count(ResumeModel.id)))).scalar() or 0
        total_questionnaires = (await self.session.execute(select(func.count(UserQuestionnaire.id)))).scalar() or 0

        recent_users_count = 0  # No created_at field natively in FastAPI-Users base model

        return {
            "total_users": total_users,
            "total_companies": total_companies,
            "total_communities": total_communities,
            "total_resources": total_resources,
            "total_jobs": total_jobs,
            "total_applications": total_applications,
            "total_resumes": total_resumes,
            "total_questionnaires": total_questionnaires,
            "recent_users": recent_users_count,
        }

    # ── Users ──────────────────────────────────────────────────────────
    async def list_users(self, skip: int = 0, limit: int = 50) -> Sequence[User]:
        result = await self.session.execute(
            select(User).order_by(User.email).offset(skip).limit(limit)
        )
        return result.scalars().all()

    async def get_user(self, user_id: uuid.UUID) -> Optional[User]:
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def toggle_user_active(self, user_id: uuid.UUID) -> Optional[User]:
        user = await self.get_user(user_id)
        if user is None:
            return None
        user.is_active = not user.is_active
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def toggle_user_superuser(self, user_id: uuid.UUID) -> Optional[User]:
        user = await self.get_user(user_id)
        if user is None:
            return None
        user.is_superuser = not user.is_superuser
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def delete_user(self, user_id: uuid.UUID) -> bool:
        user = await self.get_user(user_id)
        if user is None:
            return False
        await self.session.delete(user)
        await self.session.commit()
        return True

    async def count_users(self) -> int:
        return (await self.session.execute(select(func.count(User.id)))).scalar() or 0

    # ── Communities ────────────────────────────────────────────────────
    async def list_communities(self, skip: int = 0, limit: int = 50) -> Sequence[CommunityModel]:
        result = await self.session.execute(
            select(CommunityModel)
            .options(selectinload(CommunityModel.creator))
            .order_by(CommunityModel.created_at.desc())
            .offset(skip).limit(limit)
        )
        return result.scalars().all()

    async def delete_community(self, community_id: uuid.UUID) -> bool:
        community = await self.session.execute(
            select(CommunityModel).where(CommunityModel.id == community_id)
        )
        community = community.scalar_one_or_none()
        if community is None:
            return False
        await self.session.delete(community)
        await self.session.commit()
        return True

    # ── Resources ──────────────────────────────────────────────────────
    async def list_resources(self, skip: int = 0, limit: int = 50) -> Sequence[ResourceModel]:
        result = await self.session.execute(
            select(ResourceModel)
            .order_by(ResourceModel.created_at.desc())
            .offset(skip).limit(limit)
        )
        return result.scalars().all()

    async def create_resource(self, payload: ResourceCreate) -> ResourceModel:
        resource = ResourceModel(
            title=payload.title,
            description=payload.description,
            category=payload.category,
            icon=payload.icon,
            level=payload.level,
            tags=payload.tags,
            estimated_duration_minutes=payload.estimated_duration_minutes,
            external_url=payload.external_url,
            is_published=payload.is_published,
        )
        self.session.add(resource)
        await self.session.commit()
        await self.session.refresh(resource)
        return resource

    async def toggle_resource_published(self, resource_id: uuid.UUID) -> Optional[ResourceModel]:
        result = await self.session.execute(
            select(ResourceModel).where(ResourceModel.id == resource_id)
        )
        resource = result.scalar_one_or_none()
        if resource is None:
            return None
        resource.is_published = not resource.is_published
        await self.session.commit()
        await self.session.refresh(resource)
        return resource

    async def delete_resource(self, resource_id: uuid.UUID) -> bool:
        result = await self.session.execute(
            select(ResourceModel).where(ResourceModel.id == resource_id)
        )
        resource = result.scalar_one_or_none()
        if resource is None:
            return False
        await self.session.delete(resource)
        await self.session.commit()
        return True

    # ── Jobs ───────────────────────────────────────────────────────────
    async def list_jobs(self, skip: int = 0, limit: int = 50) -> Sequence[JobPosting]:
        result = await self.session.execute(
            select(JobPosting)
            .options(selectinload(JobPosting.company))
            .order_by(JobPosting.created_at.desc())
            .offset(skip).limit(limit)
        )
        return result.scalars().all()

    async def toggle_job_active(self, job_id: uuid.UUID) -> Optional[JobPosting]:
        result = await self.session.execute(
            select(JobPosting).where(JobPosting.id == job_id)
        )
        job = result.scalar_one_or_none()
        if job is None:
            return None
        job.is_active = not job.is_active
        await self.session.commit()
        await self.session.refresh(job)
        return job

    async def delete_job(self, job_id: uuid.UUID) -> bool:
        result = await self.session.execute(
            select(JobPosting).where(JobPosting.id == job_id)
        )
        job = result.scalar_one_or_none()
        if job is None:
            return False
        await self.session.delete(job)
        await self.session.commit()
        return True

    # ── Companies ──────────────────────────────────────────────────────
    async def list_companies(self, skip: int = 0, limit: int = 50) -> Sequence[Company]:
        result = await self.session.execute(
            select(Company).order_by(Company.company_name).offset(skip).limit(limit)
        )
        return result.scalars().all()

    async def delete_company(self, company_id: uuid.UUID) -> bool:
        result = await self.session.execute(
            select(Company).where(Company.id == company_id)
        )
        company = result.scalar_one_or_none()
        if company is None:
            return False
        await self.session.delete(company)
        await self.session.commit()
        return True

    # ── Applications ───────────────────────────────────────────────────
    async def list_applications(self, skip: int = 0, limit: int = 50) -> Sequence[ApplicationModel]:
        result = await self.session.execute(
            select(ApplicationModel)
            .options(
                selectinload(ApplicationModel.user),
                selectinload(ApplicationModel.company),
            )
            .order_by(ApplicationModel.created_at.desc())
            .offset(skip).limit(limit)
        )
        return result.scalars().all()
