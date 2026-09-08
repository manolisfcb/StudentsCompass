from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.userModel import User
from app.schemas.userSchema import UserUpdate


class ProfileService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def update_user_profile(self, *, user: User, payload: UserUpdate) -> User:
        update_data = payload.model_dump(exclude_unset=True)
        if update_data.get("email") in {"", None}:
            update_data.pop("email", None)

        if "email" in update_data and update_data["email"] != user.email:
            result = await self.session.execute(
                select(User.id).where(
                    User.email == update_data["email"],
                    User.id != user.id,
                )
            )
            if result.scalar_one_or_none() is not None:
                raise HTTPException(status_code=400, detail="Email already in use")

        for field, value in update_data.items():
            setattr(user, field, value)

        await self.session.commit()
        await self.session.refresh(user)
        return user
