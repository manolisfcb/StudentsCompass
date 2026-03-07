from pydantic import BaseModel
import uuid
from fastapi_users import schemas
from typing import Optional



class CreateResumeSchema(BaseModel):
    view_url: str
    original_filename: str
    storage_file_id: str
    folder_id: str
    user_id: uuid.UUID



class ResumeReadSchema(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    view_url: str
    original_filename: str
    storage_file_id: str
    folder_id: str
    created_at: Optional[str] = None


class ResumeCourseAuditRead(BaseModel):
    resume_id: str
    file_url: str
    original_filename: str
    evaluation_id: str
    overall_score: float
    llm_confidence: float
    pass_status: bool
    report: str
    reason_for_score: str
    main_weaknesses: list[str]
    improvements: list[str]
    scores: dict[str, float]
    attempts_today: int
    daily_limit: int
    attempts_remaining: int


class ResumeCourseAuditAttemptsRead(BaseModel):
    attempts_today: int
    daily_limit: int
    attempts_remaining: int
