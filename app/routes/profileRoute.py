from fastapi import APIRouter, HTTPException, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.userModel import User
from app.services.profileService import ProfileService
from app.services.userService import current_active_user
from app.schemas.userSchema import UserRead, UserUpdate

router = APIRouter()

@router.get("/profile", response_model=UserRead)
async def read_profile(
    response: Response,
    user: UserRead = Depends(current_active_user),
):
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Pragma"] = "no-cache"
    return user


@router.patch("/profile", response_model=UserRead)
async def update_profile(
    payload: UserUpdate,
    response: Response,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    user = await ProfileService(session).update_user_profile(user=user, payload=payload)
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Pragma"] = "no-cache"
    return user
