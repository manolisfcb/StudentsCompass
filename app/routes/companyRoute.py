from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi_users.password import PasswordHelper
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.companyModel import Company
from app.models.companyRecruiterModel import CompanyRecruiter
from app.schemas.companyRecruiterSchema import (
    CompanyRecruiterCreate,
    CompanyRecruiterManagementRead,
    CompanyRecruiterManagementUpdate,
    CompanyRecruiterRead,
)
from app.schemas.companySchema import CompanyCreate, CompanyRead, CompanyUpdate
from app.services.companyRecruiterService import CompanyRecruiterService
from app.services.companyService import (
    auth_backend_company,
    current_active_company,
    current_active_company_recruiter,
    current_company_owner_recruiter,
    fastapi_company_recruiters,
)

router = APIRouter()


# Include company authentication routes
router.include_router(
    fastapi_company_recruiters.get_auth_router(auth_backend_company),
    prefix="/auth/company",
    tags=["company-auth"]
)

# Company registration (creates company + initial recruiter)
@router.post("/auth/company/register", response_model=CompanyRead, status_code=status.HTTP_201_CREATED)
async def register_company_with_initial_recruiter(
    payload: CompanyCreate,
    session: AsyncSession = Depends(get_session),
):
    existing_recruiter = await session.execute(
        select(CompanyRecruiter).where(CompanyRecruiter.email == payload.email)
    )
    if existing_recruiter.scalar_one_or_none() is not None:
        raise HTTPException(status_code=400, detail="REGISTER_USER_ALREADY_EXISTS")

    password_helper = PasswordHelper()
    hashed_password = password_helper.hash(payload.password)

    company = Company(
        company_name=payload.company_name,
        industry=payload.industry,
        description=payload.description,
        website=payload.website,
        location=payload.location,
        contact_person=payload.contact_person,
        phone=payload.phone,
    )
    session.add(company)
    await session.flush()

    recruiter = CompanyRecruiter(
        company_id=company.id,
        email=payload.email,
        hashed_password=hashed_password,
        is_active=True,
        is_superuser=False,
        is_verified=True,
        first_name=payload.recruiter_first_name or payload.contact_person,
        last_name=payload.recruiter_last_name,
        role="owner",
    )
    session.add(recruiter)

    await session.commit()
    await session.refresh(company)
    return company


# Include company recruiter reset password routes
router.include_router(
    fastapi_company_recruiters.get_reset_password_router(),
    prefix="/auth/company",
    tags=["company-auth"]
)

# Include company recruiter verification routes
router.include_router(
    fastapi_company_recruiters.get_verify_router(CompanyRecruiterRead),
    prefix="/auth/company",
    tags=["company-auth"]
)

@router.get("/companies/me", response_model=CompanyRead)
async def get_current_company_profile(
    company: Company = Depends(current_active_company),
):
    return company


@router.patch("/companies/me", response_model=CompanyRead)
async def update_current_company_profile(
    payload: CompanyUpdate,
    company: Company = Depends(current_active_company),
    session: AsyncSession = Depends(get_session),
):
    updatable_fields = (
        "company_name",
        "industry",
        "description",
        "website",
        "location",
        "contact_person",
        "phone",
    )
    update_data = payload.model_dump(exclude_unset=True)

    for field in updatable_fields:
        if field in update_data:
            setattr(company, field, update_data[field])

    await session.commit()
    await session.refresh(company)
    return company


@router.get("/companies/me/recruiters", response_model=List[CompanyRecruiterManagementRead])
async def list_company_recruiters(
    owner_recruiter: CompanyRecruiter = Depends(current_company_owner_recruiter),
    session: AsyncSession = Depends(get_session),
):
    recruiter_service = CompanyRecruiterService(session)
    return await recruiter_service.list_company_recruiters(owner_recruiter.company_id)


@router.post(
    "/companies/me/recruiters",
    response_model=CompanyRecruiterManagementRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_company_recruiter(
    payload: CompanyRecruiterCreate,
    owner_recruiter: CompanyRecruiter = Depends(current_company_owner_recruiter),
    session: AsyncSession = Depends(get_session),
):
    recruiter_service = CompanyRecruiterService(session)
    return await recruiter_service.create_company_recruiter(owner_recruiter.company_id, payload)


@router.patch("/companies/me/recruiters/{recruiter_id}", response_model=CompanyRecruiterManagementRead)
async def update_company_recruiter(
    recruiter_id: UUID,
    payload: CompanyRecruiterManagementUpdate,
    owner_recruiter: CompanyRecruiter = Depends(current_company_owner_recruiter),
    session: AsyncSession = Depends(get_session),
):
    recruiter_service = CompanyRecruiterService(session)
    return await recruiter_service.update_company_recruiter(
        company_id=owner_recruiter.company_id,
        recruiter_id=recruiter_id,
        actor_recruiter_id=owner_recruiter.id,
        payload=payload,
    )


@router.delete("/companies/me/recruiters/{recruiter_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company_recruiter(
    recruiter_id: UUID,
    owner_recruiter: CompanyRecruiter = Depends(current_company_owner_recruiter),
    session: AsyncSession = Depends(get_session),
):
    recruiter_service = CompanyRecruiterService(session)
    await recruiter_service.delete_company_recruiter(
        company_id=owner_recruiter.company_id,
        recruiter_id=recruiter_id,
        actor_recruiter_id=owner_recruiter.id,
    )


@router.get("/companies/me/recruiters/current", response_model=CompanyRecruiterManagementRead)
async def get_current_company_recruiter_profile(
    recruiter: CompanyRecruiter = Depends(current_active_company_recruiter),
):
    return recruiter
