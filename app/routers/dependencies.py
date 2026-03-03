from fastapi import Depends

from app.models.userModel import User
from app.services.userService import current_active_user


async def get_current_user_stub(user: User = Depends(current_active_user)) -> User:
    """Auth dependency stub used by roadmap domain routes."""
    return user
