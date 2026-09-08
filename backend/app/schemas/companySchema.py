from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr


class CompanyCreate(BaseModel):
    email: EmailStr
    password: str
    company_name: str
    industry: Optional[str] = None
    description: Optional[str] = None
    website: Optional[str] = None
    location: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    recruiter_first_name: Optional[str] = None
    recruiter_last_name: Optional[str] = None


class CompanyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_name: str
    industry: Optional[str] = None
    description: Optional[str] = None
    website: Optional[str] = None
    location: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class CompanyUpdate(BaseModel):
    company_name: Optional[str] = None
    industry: Optional[str] = None
    description: Optional[str] = None
    website: Optional[str] = None
    location: Optional[str] = None
    contact_person: Optional[str] = None
    phone: Optional[str] = None
