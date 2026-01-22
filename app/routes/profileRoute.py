from fastapi import APIRouter, HTTPException, Depends
from app.services.userService import current_active_user
from app.schemas.userSchema import UserRead
from pydantic import BaseModel, Field

router = APIRouter()

@router.get("/profile", response_model=UserRead)
async def read_profile(user: UserRead = Depends(current_active_user)):
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user