from app.schemas.companySchema import CompanyCreate, CompanyRead, CompanyUpdate
from fastapi_users import FastAPIUsers, models, BaseUserManager, UUIDIDMixin
from fastapi_users.authentication import (
    AuthenticationBackend,
    CookieTransport,
    JWTStrategy,
)
from fastapi_users.db import SQLAlchemyUserDatabase
from fastapi import Depends, Request
from typing import Optional
from app.models.companyModel import Company
import uuid
import logging
from app.models.companyModel import get_company_db
import os

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

SECRET = os.getenv("SECRET_KEY", "SECRET_RANDOM_STRING_CHANGE_IN_PRODUCTION")
ENV = os.getenv("ENV", "development").lower()

class CompanyManager(UUIDIDMixin, BaseUserManager[Company, uuid.UUID]):
    reset_password_token_secret = SECRET
    verification_token_secret = SECRET
    
    async def on_after_register(self, user: Company, request: Optional[Request] = None):
        logger.info(f"Company {user.id} has registered.")
        await super().on_after_register(user, request)
        
    async def on_after_forgot_password(
        self, user: Company, token: str, request: Optional[Request] = None
    ):
        logger.info(f"Company {user.id} has forgot their password. Reset token: {token}")
        await super().on_after_forgot_password(user, token, request)
        

async def get_company_manager(company_db: SQLAlchemyUserDatabase = Depends(get_company_db)):
    yield CompanyManager(company_db)
    

cookie_transport_company = CookieTransport(
    cookie_name="studentscompass_company_auth",
    cookie_max_age=3600,
    cookie_secure=(ENV == "production"),
    cookie_samesite="lax",
)

def get_jwt_strategy_company() -> JWTStrategy:
    return JWTStrategy(secret=SECRET, lifetime_seconds=3600)


auth_backend_company = AuthenticationBackend(
    name="jwt",
    transport=cookie_transport_company,
    get_strategy=get_jwt_strategy_company,
)

fastapi_companies = FastAPIUsers[Company, uuid.UUID](
    get_user_manager=get_company_manager, 
    auth_backends=[auth_backend_company]
)
current_active_company = fastapi_companies.current_user(active=True)
current_active_company_optional = fastapi_companies.current_user(active=True, optional=True)
