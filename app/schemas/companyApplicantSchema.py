from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class CompanyApplicantApplicationRead(BaseModel):
    id: UUID
    job_posting_id: Optional[UUID] = None
    job_title: str
    status: str
    application_date: datetime
    assigned_recruiter_id: Optional[UUID] = None
    notes: Optional[str] = None


class CompanyApplicantCandidateRead(BaseModel):
    id: UUID
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: str
    email: str
    phone: Optional[str] = None
    address: Optional[str] = None
    sex: Optional[str] = None
    age: Optional[int] = None


class CompanyApplicantResumeRead(BaseModel):
    id: UUID
    original_filename: str
    uploaded_at: datetime
    summary: Optional[str] = None
    phone: Optional[str] = None
    preview_url: str
    download_url: str


class CompanyApplicantCertificationRead(BaseModel):
    id: Optional[str] = None
    name: str
    issuer: Optional[str] = None
    issued_at: Optional[datetime] = None


class CompanyApplicantRead(BaseModel):
    application: CompanyApplicantApplicationRead
    candidate: CompanyApplicantCandidateRead
    resume: Optional[CompanyApplicantResumeRead] = None
    certifications: list[CompanyApplicantCertificationRead] = Field(default_factory=list)
