from fastapi import APIRouter, HTTPException, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.userModel import User
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
    update_data = payload.model_dump(exclude_unset=True)
    if update_data.get("email") in {"", None}:
        update_data.pop("email", None)

    if "email" in update_data and update_data["email"] != user.email:
        result = await session.execute(
            select(User.id).where(
                User.email == update_data["email"],
                User.id != user.id,
            )
        )
        if result.scalar_one_or_none() is not None:
            raise HTTPException(status_code=400, detail="Email already in use")

    for field, value in update_data.items():
        setattr(user, field, value)

    await session.commit()
    await session.refresh(user)
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Pragma"] = "no-cache"
    return user
