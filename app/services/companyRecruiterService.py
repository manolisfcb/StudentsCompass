from __future__ import annotations

from typing import Sequence
from uuid import UUID

from fastapi import HTTPException, status
from fastapi_users.password import PasswordHelper
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.companyRecruiterModel import CompanyRecruiter
from app.schemas.companyRecruiterSchema import (
    CompanyRecruiterCreate,
    CompanyRecruiterManagementUpdate,
)


ALLOWED_COMPANY_RECRUITER_ROLES = ("owner", "admin", "recruiter", "viewer")


class CompanyRecruiterService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.password_helper = PasswordHelper()

    async def list_company_recruiters(self, company_id: UUID) -> Sequence[CompanyRecruiter]:
        role_rank = case(
            (CompanyRecruiter.role == "owner", 0),
            (CompanyRecruiter.role == "admin", 1),
            (CompanyRecruiter.role == "recruiter", 2),
            else_=3,
        )
        result = await self.session.execute(
            select(CompanyRecruiter)
            .where(CompanyRecruiter.company_id == company_id)
            .order_by(role_rank, CompanyRecruiter.created_at.asc(), CompanyRecruiter.email.asc())
        )
        return result.scalars().all()

    async def create_company_recruiter(
        self,
        company_id: UUID,
        payload: CompanyRecruiterCreate,
    ) -> CompanyRecruiter:
        role = self._normalize_role(payload.role)
        email = payload.email.strip().lower()
        self._validate_password(payload.password)

        existing_recruiter = await self.session.execute(
            select(CompanyRecruiter).where(func.lower(CompanyRecruiter.email) == email)
        )
        if existing_recruiter.scalar_one_or_none() is not None:
            raise HTTPException(status_code=400, detail="REGISTER_USER_ALREADY_EXISTS")

        recruiter = CompanyRecruiter(
            company_id=company_id,
            email=email,
            hashed_password=self.password_helper.hash(payload.password),
            is_active=True,
            is_superuser=False,
            is_verified=True,
            first_name=payload.first_name,
            last_name=payload.last_name,
            role=role,
        )
        self.session.add(recruiter)
        await self.session.commit()
        await self.session.refresh(recruiter)
        return recruiter

    async def update_company_recruiter(
        self,
        company_id: UUID,
        recruiter_id: UUID,
        actor_recruiter_id: UUID,
        payload: CompanyRecruiterManagementUpdate,
    ) -> CompanyRecruiter:
        recruiter = await self._get_company_recruiter(company_id, recruiter_id)
        update_data = payload.model_dump(exclude_unset=True)

        if not update_data:
            return recruiter

        if update_data.get("email"):
            email = update_data["email"].strip().lower()
            existing_recruiter = await self.session.execute(
                select(CompanyRecruiter).where(
                    func.lower(CompanyRecruiter.email) == email,
                    CompanyRecruiter.id != recruiter.id,
                )
            )
            if existing_recruiter.scalar_one_or_none() is not None:
                raise HTTPException(status_code=400, detail="REGISTER_USER_ALREADY_EXISTS")
            recruiter.email = email

        if "password" in update_data and update_data["password"]:
            self._validate_password(update_data["password"])
            recruiter.hashed_password = self.password_helper.hash(update_data["password"])

        if "first_name" in update_data:
            recruiter.first_name = update_data["first_name"]

        if "last_name" in update_data:
            recruiter.last_name = update_data["last_name"]

        if "role" in update_data and update_data["role"] is not None:
            next_role = self._normalize_role(update_data["role"])
            if recruiter.role == "owner" and next_role != "owner":
                await self._ensure_multiple_owners(company_id)
            recruiter.role = next_role

        if "is_active" in update_data and update_data["is_active"] is not None:
            if recruiter.id == actor_recruiter_id and update_data["is_active"] is False:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="OWNERS_CANNOT_DEACTIVATE_THEMSELVES",
                )
            recruiter.is_active = update_data["is_active"]

        await self.session.commit()
        await self.session.refresh(recruiter)
        return recruiter

    async def delete_company_recruiter(
        self,
        company_id: UUID,
        recruiter_id: UUID,
        actor_recruiter_id: UUID,
    ) -> None:
        recruiter = await self._get_company_recruiter(company_id, recruiter_id)

        if recruiter.id == actor_recruiter_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OWNERS_CANNOT_DELETE_THEMSELVES",
            )

        if recruiter.role == "owner":
            await self._ensure_multiple_owners(company_id)

        await self.session.delete(recruiter)
        await self.session.commit()

    async def _get_company_recruiter(self, company_id: UUID, recruiter_id: UUID) -> CompanyRecruiter:
        result = await self.session.execute(
            select(CompanyRecruiter).where(
                CompanyRecruiter.company_id == company_id,
                CompanyRecruiter.id == recruiter_id,
            )
        )
        recruiter = result.scalar_one_or_none()
        if recruiter is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recruiter not found")
        return recruiter

    async def _ensure_multiple_owners(self, company_id: UUID) -> None:
        result = await self.session.execute(
            select(func.count(CompanyRecruiter.id)).where(
                CompanyRecruiter.company_id == company_id,
                CompanyRecruiter.role == "owner",
            )
        )
        owner_count = int(result.scalar_one() or 0)
        if owner_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="COMPANY_MUST_KEEP_AT_LEAST_ONE_OWNER",
            )

    def _normalize_role(self, role: str | None) -> str:
        normalized_role = (role or "").strip().lower()
        if normalized_role not in ALLOWED_COMPANY_RECRUITER_ROLES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"role must be one of: {', '.join(ALLOWED_COMPANY_RECRUITER_ROLES)}",
            )
        return normalized_role

    @staticmethod
    def _validate_password(password: str) -> None:
        if len(password) < 8:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="password must be at least 8 characters long",
            )
