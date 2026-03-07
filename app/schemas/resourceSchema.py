from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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
    is_locked: bool

    model_config = ConfigDict(from_attributes=True)


class ResourceCreate(BaseModel):
    title: str
    description: str
    category: str
    icon: Optional[str] = None
    level: Optional[str] = None
    tags: Optional[list[str]] = None
    estimated_duration_minutes: Optional[int] = None
    external_url: Optional[str] = None
    is_published: bool = True
    is_locked: bool = False
    modules: list["ResourceModuleCreate"] = Field(default_factory=list)


class ResourceLessonCreate(BaseModel):
    title: str
    content_type: str = "text"
    content: Optional[str] = None
    video_url: Optional[str] = None
    resource_url: Optional[str] = None
    notes: Optional[str] = None
    reading_time_minutes: Optional[int] = None


class ResourceModuleCreate(BaseModel):
    title: str
    description: Optional[str] = None
    lessons: list[ResourceLessonCreate] = Field(default_factory=list)


class ResourceLessonRead(BaseModel):
    id: UUID
    module_id: UUID
    title: str
    position: int
    content_type: str
    content: str
    content_payload: Optional[dict[str, str]] = None
    video_url: Optional[str] = None
    resource_url: Optional[str] = None
    notes: Optional[str] = None
    reading_time_minutes: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ResourceModuleRead(BaseModel):
    id: UUID
    resource_id: UUID
    title: str
    position: int
    description: Optional[str] = None
    lessons: list[ResourceLessonRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ResourceDetailRead(ResourceRead):
    modules: list[ResourceModuleRead] = []


class ResourceLessonProgressUpdate(BaseModel):
    completed: bool = True


class ResourceModuleProgressRead(BaseModel):
    module_id: UUID
    completed_lessons: int
    total_lessons: int
    progress_percent: int


class ResourceProgressRead(BaseModel):
    resource_id: UUID
    completed_lesson_ids: list[UUID]
    completed_lessons: int
    total_lessons: int
    progress_percent: int
    modules: list[ResourceModuleProgressRead]
