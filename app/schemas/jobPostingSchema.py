from pydantic import BaseModel, UUID4, HttpUrl
from typing import Optional
from datetime import datetime


class JobPostingBase(BaseModel):
    title: str
    description: Optional[str] = None
    requirements: Optional[str] = None
    responsibilities: Optional[str] = None
    location: Optional[str] = None
    job_type: Optional[str] = None
    salary_range: Optional[str] = None
    application_url: Optional[str] = None
    is_active: bool = True
    expires_at: Optional[datetime] = None


class JobPostingCreate(JobPostingBase):
    company_id: UUID4


class JobPostingUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    requirements: Optional[str] = None
    responsibilities: Optional[str] = None
    location: Optional[str] = None
    job_type: Optional[str] = None
    salary_range: Optional[str] = None
    application_url: Optional[str] = None
    is_active: Optional[bool] = None
    expires_at: Optional[datetime] = None


class JobPostingRead(JobPostingBase):
    id: UUID4
    company_id: UUID4
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
