from pydantic import BaseModel
import uuid
from fastapi_users import schemas
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.models.resumeModel import ResumeModel



class CreateResumeSchema(BaseModel):
    view_url: str
    original_filename: str
    storage_file_id: str
    folder_id: str
    user_id: uuid.UUID
    ai_summary: Optional[str] = None
    contact_phone: Optional[str] = None



class ResumeReadSchema(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    view_url: str
    original_filename: str
    storage_file_id: str
    folder_id: str
    ai_summary: Optional[str] = None
    contact_phone: Optional[str] = None
    created_at: Optional[str] = None

    @classmethod
    def from_model(cls, resume: "ResumeModel") -> "ResumeReadSchema":
        return cls(
            id=resume.id,
            user_id=resume.user_id,
            view_url=resume.view_url,
            original_filename=resume.original_filename,
            storage_file_id=resume.storage_file_id,
            folder_id=resume.folder_id,
            ai_summary=resume.ai_summary,
            contact_phone=resume.contact_phone,
            created_at=resume.created_at.isoformat() if resume.created_at else None,
        )


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
