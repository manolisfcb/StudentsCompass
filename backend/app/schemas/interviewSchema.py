from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class InterviewAvailabilityCreate(BaseModel):
    starts_at: datetime
    ends_at: datetime
    timezone: str = "America/Toronto"
    notes: Optional[str] = None


class InterviewAvailabilityPublishRequest(BaseModel):
    slots: list[InterviewAvailabilityCreate]
    notes: Optional[str] = None


class InterviewAvailabilityRead(BaseModel):
    id: UUID
    application_id: UUID
    starts_at: datetime
    ends_at: datetime
    timezone: str
    status: str
    notes: Optional[str] = None
    booked_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class InterviewAvailabilitySelectionRequest(BaseModel):
    slot_id: UUID
