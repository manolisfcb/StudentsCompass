from pydantic import BaseModel, Field, UUID4
from typing import TYPE_CHECKING, Optional
from datetime import datetime
from app.models.applicationModel import ApplicationMatchStrength, ApplicationStatus
from app.schemas.paginationSchema import CursorPage
from app.schemas.interviewSchema import InterviewAvailabilityRead

if TYPE_CHECKING:
    from app.services.applications.applicationService import ApprovedResumeOption


# Re-exported, not redeclared. Two identical enums meant a value could be valid
# in the schema and unknown to the column (or the reverse) with nothing failing
# until a request hit the database; there is now one definition, the one the
# table is built from. Both names stay importable from here.
__all__ = ["ApplicationStatus", "ApplicationMatchStrength"]


class ApplicationBase(BaseModel):
    job_title: str
    status: ApplicationStatus = ApplicationStatus.APPLIED
    application_url: Optional[str] = None
    notes: Optional[str] = None


class ApplicationCreate(ApplicationBase):
    company_id: UUID4
    job_posting_id: Optional[UUID4] = None
    resume_id: Optional[UUID4] = None


class ApplicationUpdate(BaseModel):
    job_title: Optional[str] = None
    status: Optional[ApplicationStatus] = None
    application_url: Optional[str] = None
    notes: Optional[str] = None


class ApplicationRead(ApplicationBase):
    id: UUID4
    user_id: UUID4
    company_id: UUID4
    assigned_recruiter_id: Optional[UUID4] = None
    match_strength: ApplicationMatchStrength
    company_name: Optional[str] = None
    company_location: Optional[str] = None
    job_posting_id: Optional[UUID4] = None
    resume_id: Optional[UUID4] = None
    selected_interview_slot: Optional[InterviewAvailabilityRead] = None
    available_interview_slots: list[InterviewAvailabilityRead] = Field(default_factory=list)
    application_date: datetime
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ApplicationPageRead(CursorPage[ApplicationRead]):
    """One bounded page of a student's applications, newest first.

    ``next_cursor`` addresses the application the following page starts from;
    ``None`` means the end of the history has been reached.
    """


class ApplicationEligibleResumeRead(BaseModel):
    id: UUID4
    original_filename: str
    created_at: datetime
    ai_summary: Optional[str] = None
    contact_phone: Optional[str] = None
    overall_score: float
    approved_at: datetime
    is_latest: bool = False

    @classmethod
    def from_option(
        cls,
        option: "ApprovedResumeOption",
        *,
        is_latest: bool = False,
    ) -> "ApplicationEligibleResumeRead":
        return cls(
            id=option.resume.id,
            original_filename=option.resume.original_filename,
            created_at=option.resume.created_at,
            ai_summary=option.resume.ai_summary,
            contact_phone=option.resume.contact_phone,
            overall_score=round(option.overall_score, 1),
            approved_at=option.approved_at,
            is_latest=is_latest,
        )
