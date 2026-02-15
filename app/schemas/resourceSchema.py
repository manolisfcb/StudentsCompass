from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ResourceRead(BaseModel):
    id: UUID
    title: str
    description: str
    icon: Optional[str] = None
    category: str
    tags: Optional[list[str]] = None
    level: Optional[str] = None
    estimated_duration_minutes: Optional[int] = None
    external_url: Optional[str] = None
    created_at: datetime
    is_published: bool

    model_config = ConfigDict(from_attributes=True)


class ResourceLessonRead(BaseModel):
    id: UUID
    module_id: UUID
    title: str
    position: int
    content_type: str
    content: str
    reading_time_minutes: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ResourceModuleRead(BaseModel):
    id: UUID
    resource_id: UUID
    title: str
    position: int
    description: Optional[str] = None
    lessons: list[ResourceLessonRead] = []

    model_config = ConfigDict(from_attributes=True)


class ResourceDetailRead(ResourceRead):
    modules: list[ResourceModuleRead] = []
