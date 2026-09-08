from pydantic import BaseModel
from typing import Optional
import uuid


class UserStatsBase(BaseModel):
    resume_progress: int
    linkedin_progress: int
    interview_progress: int


class UserStatsCreate(UserStatsBase):
    user_id: uuid.UUID


class UserStatsUpdate(BaseModel):
    resume_progress: Optional[int] = None
    linkedin_progress: Optional[int] = None
    interview_progress: Optional[int] = None


class UserStatsRead(UserStatsBase):
    id: uuid.UUID
    user_id: uuid.UUID

    class Config:
        orm_mode = True
