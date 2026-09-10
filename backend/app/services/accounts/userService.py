from fastapi_users import FastAPIUsers, BaseUserManager, UUIDIDMixin
from fastapi_users.authentication import (
    AuthenticationBackend,
    CookieTransport,
    JWTStrategy,
)
from fastapi_users.db import SQLAlchemyUserDatabase
from fastapi import Depends, Request
from app.core.observability import stamp_actor
from typing import Optional
from app.models.userModel import User
import uuid
import logging
from app.models.userModel import get_user_db
from app.config import IS_PRODUCTION, load_secret_key

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# The two auth identities stay separate; the rule about when a missing
# SECRET_KEY is acceptable does not. This block used to be copied character for
# character into both services, so a fix to one would silently leave the other
# signing tokens with the development fallback.
SECRET = load_secret_key(logger)

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
_authenticated_user = fastapi_users.current_user(active=True)
_authenticated_user_optional = fastapi_users.current_user(active=True, optional=True)


async def current_active_user(
    request: Request, user: User = Depends(_authenticated_user)
) -> User:
    """The authenticated student, and the one place that records *which* one.

    Wrapped here rather than stamped in each route because this is the single
    dependency every student endpoint already goes through: an endpoint added
    later gets the log field without anybody remembering to add it. The value is
    a keyed pseudonym, never the user id — see ``anonymize_actor`` (TASK-045).
    """
    stamp_actor(request, "student", user.id)
    return user


async def current_active_user_optional(
    request: Request, user: Optional[User] = Depends(_authenticated_user_optional)
) -> Optional[User]:
    if user is not None:
        stamp_actor(request, "student", user.id)
    return user


async def current_ai_user(user: User = Depends(current_active_user)) -> User:
    """Auth dependency for endpoints that spend on the LLM.

    Verification-ready gate: when ``REQUIRE_VERIFIED_FOR_AI`` is enabled it
    requires a verified email (the main defense against account farming for free
    AI quota). Kept OFF by default until a real email provider is wired so no
    existing user is locked out; meanwhile the cost bleed is capped by the
    atomic per-user quota, the global budget guard and registration limits.
    """
    from app import config
    from fastapi import HTTPException, status

    if config.REQUIRE_VERIFIED_FOR_AI and not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email address to use AI features.",
        )
    return user
