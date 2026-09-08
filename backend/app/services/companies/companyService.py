import logging
import os
import uuid
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin
from fastapi_users.authentication import (
    AuthenticationBackend,
    CookieTransport,
    JWTStrategy,
)
from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.companyModel import Company
from app.models.companyRecruiterModel import CompanyRecruiter, get_company_recruiter_db

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

ENV = os.getenv("ENV", "development").lower()
IS_PRODUCTION = ENV in {"production", "prod"}
_DEFAULT_SECRET_FALLBACK = "SECRET_RANDOM_STRING_CHANGE_IN_PRODUCTION"


def _load_secret_key() -> str:
    configured_secret = os.getenv("SECRET_KEY", "").strip()
    if configured_secret:
        return configured_secret

    if IS_PRODUCTION:
        raise RuntimeError("SECRET_KEY must be configured in production.")

    logger.warning("SECRET_KEY is not set; using development fallback secret.")
    return _DEFAULT_SECRET_FALLBACK


SECRET = _load_secret_key()


class CompanyRecruiterManager(UUIDIDMixin, BaseUserManager[CompanyRecruiter, uuid.UUID]):
    reset_password_token_secret = SECRET
    verification_token_secret = SECRET
    
    async def on_after_register(self, user: CompanyRecruiter, request: Optional[Request] = None):
        logger.info(f"Company recruiter {user.id} has registered for company {user.company_id}.")
        await super().on_after_register(user, request)
        
    async def on_after_forgot_password(
        self, user: CompanyRecruiter, token: str, request: Optional[Request] = None
    ):
        logger.info(f"Company recruiter {user.id} requested a password reset.")
        await super().on_after_forgot_password(user, token, request)
        

async def get_company_recruiter_manager(
    company_recruiter_db: SQLAlchemyUserDatabase = Depends(get_company_recruiter_db),
):
    yield CompanyRecruiterManager(company_recruiter_db)
    

cookie_transport_company = CookieTransport(
    cookie_name="studentscompass_company_auth",
    cookie_max_age=3600,
    cookie_secure=IS_PRODUCTION,
    cookie_samesite="lax",
)

def get_jwt_strategy_company() -> JWTStrategy:
    return JWTStrategy(secret=SECRET, lifetime_seconds=3600)


auth_backend_company = AuthenticationBackend(
    name="jwt",
    transport=cookie_transport_company,
    get_strategy=get_jwt_strategy_company,
)

fastapi_company_recruiters = FastAPIUsers[CompanyRecruiter, uuid.UUID](
    get_user_manager=get_company_recruiter_manager,
    auth_backends=[auth_backend_company]
)
fastapi_companies = fastapi_company_recruiters

current_active_company_recruiter = fastapi_company_recruiters.current_user(active=True)
current_active_company_recruiter_optional = fastapi_company_recruiters.current_user(active=True, optional=True)


async def current_company_owner_recruiter(
    recruiter: CompanyRecruiter = Depends(current_active_company_recruiter),
) -> CompanyRecruiter:
    if recruiter.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only company owners can manage recruiters",
        )
    return recruiter


async def current_company_job_manager_recruiter(
    recruiter: CompanyRecruiter = Depends(current_active_company_recruiter),
) -> CompanyRecruiter:
    if recruiter.role not in {"owner", "admin", "recruiter"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only company recruiters can manage job postings",
        )
    return recruiter


async def current_active_company(
    recruiter: CompanyRecruiter = Depends(current_active_company_recruiter),
    session: AsyncSession = Depends(get_session),
) -> Company:
    result = await session.execute(select(Company).where(Company.id == recruiter.company_id))
    company = result.scalar_one_or_none()
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


async def current_active_company_optional(
    recruiter: Optional[CompanyRecruiter] = Depends(current_active_company_recruiter_optional),
    session: AsyncSession = Depends(get_session),
) -> Optional[Company]:
    if recruiter is None:
        return None
    result = await session.execute(select(Company).where(Company.id == recruiter.company_id))
    return result.scalar_one_or_none()
