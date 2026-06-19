from app.schemas.userSchema import UserCreate, UserRead, UserUpdate
from fastapi_users import FastAPIUsers, models, BaseUserManager, UUIDIDMixin
from fastapi_users.authentication import (
    AuthenticationBackend,
    CookieTransport,
    JWTStrategy,
)
from fastapi_users.db import SQLAlchemyUserDatabase
from fastapi import Depends, Request
from typing import Optional
from app.models.userModel import User
import uuid
import logging
from app.models.userModel import get_user_db
import os

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

class UserManager(UUIDIDMixin, BaseUserManager[User,uuid.UUID]):
    reset_password_token_secret = SECRET
    verification_token_secret = SECRET
    
    async def on_after_register(self, user: User, request: Optional[Request] = None):
        logger.info(f"User {user.id} has registered.")
        await super().on_after_register(user, request)
        
    async def on_after_forgot_password(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        logger.info(f"User {user.id} requested a password reset.")
        await super().on_after_forgot_password(user, token, request)
        

async def get_user_manager(user_db: SQLAlchemyUserDatabase = Depends(get_user_db)):
    yield UserManager(user_db)
    

# In local/dev we typically run over plain HTTP, so secure cookies won't be stored.
# In production, keep secure cookies enabled.
cookie_transport = CookieTransport(
    cookie_name="studentscompass_auth",
    cookie_max_age=3600,
    cookie_secure=IS_PRODUCTION,
    cookie_samesite="lax",
)

def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=SECRET, lifetime_seconds=3600)


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=cookie_transport,
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager=get_user_manager, auth_backends=[auth_backend])
current_active_user = fastapi_users.current_user(active=True)
current_active_user_optional = fastapi_users.current_user(active=True, optional=True)
