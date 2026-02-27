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
    modules: list["ResourceModuleCreate"] = Field(default_factory=list)


class ResourceLessonCreate(BaseModel):
    title: str
    content_type: str = "text"
    content: str
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
    modules: list[ResourceModuleRead] = Field(default_factory=list)


class ResourceEnrollmentProgressRead(BaseModel):
    resource_id: UUID
    title: str
    category: str
    level: Optional[str] = None
    icon: Optional[str] = None
    enrolled_at: datetime
    last_opened_lesson_id: Optional[UUID] = None
    total_lessons: int
    completed_lessons: int
    progress_percent: float
    is_completed: bool


class LessonCompletionUpdate(BaseModel):
    completed: bool = True
