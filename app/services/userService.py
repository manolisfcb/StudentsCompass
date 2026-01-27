from app.schemas.userSchema import UserCreate, UserRead, UserUpdate
from fastapi_users import FastAPIUsers, models, BaseUserManager, UUIDIDMixin
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
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

SECRET = os.getenv("SECRET_KEY", "SECRET_RANDOM_STRING_CHANGE_IN_PRODUCTION")

class UserManager(UUIDIDMixin, BaseUserManager[User,uuid.UUID]):
    reset_password_token_secret = SECRET
    verification_token_secret = SECRET
    
    async def on_after_register(self, user: User, request: Optional[Request] = None):
        logger.info(f"User {user.id} has registered.")
        await super().on_after_register(user, request)
        
    async def on_after_forgot_password(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        logger.info(f"User {user.id} has forgot their password. Reset token: {token}")
        await super().on_after_forgot_password(user, token, request)
        

async def get_user_manager(user_db: SQLAlchemyUserDatabase = Depends(get_user_db)):
    yield UserManager(user_db)
    

bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")
def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=SECRET, lifetime_seconds=3600)


auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager=get_user_manager, auth_backends=[auth_backend])
current_active_user = fastapi_users.current_user(active=True)