from pydantic import BaseModel, UUID4
from typing import Optional
from datetime import datetime
from enum import Enum


class ApplicationStatus(str, Enum):
    APPLIED = "applied"
    IN_REVIEW = "in_review"
    INTERVIEW = "interview"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class ApplicationBase(BaseModel):
    job_title: str
    status: ApplicationStatus = ApplicationStatus.APPLIED
    application_url: Optional[str] = None
    notes: Optional[str] = None


class ApplicationCreate(ApplicationBase):
    company_id: UUID4
    job_posting_id: Optional[UUID4] = None


class ApplicationUpdate(BaseModel):
    job_title: Optional[str] = None
    status: Optional[ApplicationStatus] = None
    application_url: Optional[str] = None
    notes: Optional[str] = None


class ApplicationRead(ApplicationBase):
    id: UUID4
    user_id: UUID4
    company_id: UUID4
    job_posting_id: Optional[UUID4] = None
    application_date: datetime
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
