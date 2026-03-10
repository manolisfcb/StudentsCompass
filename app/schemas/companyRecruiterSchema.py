from fastapi_users import schemas
from datetime import datetime
from typing import Optional

from pydantic import UUID4, BaseModel, ConfigDict, EmailStr


class CompanyRecruiterRead(schemas.BaseUser):
    company_id: UUID4
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: str


class CompanyRecruiterUpdate(schemas.BaseUserUpdate):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: Optional[str] = None


class CompanyRecruiterManagementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID4
    company_id: UUID4
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime


class CompanyRecruiterCreate(BaseModel):
    email: EmailStr
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: str = "recruiter"


class CompanyRecruiterManagementUpdate(BaseModel):
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
