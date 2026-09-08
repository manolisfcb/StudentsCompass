from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.roadmapModel import ProjectSubmissionStatus, TaskProgressStatus, TaskType


class RoadmapListItemRead(BaseModel):
    id: UUID
    slug: str
    title: str
    description: str
    role_target: str
    difficulty: str
    duration_weeks_min: int
    duration_weeks_max: int
    popularity: int
    is_saved: bool = False
    total_tasks: int = 0
    completed_tasks: int = 0
    overall_progress_percent: int = 0

    model_config = ConfigDict(from_attributes=True)


class StageTaskRead(BaseModel):
    id: UUID
    order_index: int
    title: str
    description: str
    estimated_hours: int
    task_type: TaskType
    resource_url: str | None = None
    resource_title: str | None = None
    status: TaskProgressStatus = TaskProgressStatus.NOT_STARTED

    model_config = ConfigDict(from_attributes=True)


class ProjectSubmissionRead(BaseModel):
    id: UUID
    project_id: UUID
    repo_url: str | None = None
    live_url: str | None = None
    notes: str | None = None
    status: ProjectSubmissionStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StageProjectRead(BaseModel):
    id: UUID
    title: str
    brief: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    rubric: dict[str, Any] = Field(default_factory=dict)
    estimated_hours: int
    submission: ProjectSubmissionRead | None = None

    model_config = ConfigDict(from_attributes=True)


class StageDetailRead(BaseModel):
    id: UUID
    order_index: int
    title: str
    objective: str
    duration_weeks: int
    progress_percent: int
    tasks: list[StageTaskRead]
    projects: list[StageProjectRead]

    model_config = ConfigDict(from_attributes=True)


class RoadmapDetailRead(BaseModel):
    id: UUID
    slug: str
    title: str
    description: str
    role_target: str
    difficulty: str
    duration_weeks_min: int
    duration_weeks_max: int
    popularity: int
    is_saved: bool = False
    total_tasks: int = 0
    completed_tasks: int = 0
    overall_progress_percent: int = 0
    stages: list[StageDetailRead]

    model_config = ConfigDict(from_attributes=True)


class SavedRoadmapRead(BaseModel):
    saved_at: datetime
    roadmap: RoadmapListItemRead


class TaskProgressUpdateRequest(BaseModel):
    status: TaskProgressStatus = Field(..., description="Task status")


class TaskProgressUpdateResponse(BaseModel):
    task_id: UUID
    status: TaskProgressStatus
    stage_id: UUID
    stage_progress_percent: int
    roadmap_id: UUID
    roadmap_progress_percent: int
    completed_tasks: int
    total_tasks: int


class ProjectSubmissionRequest(BaseModel):
    repo_url: str | None = None
    live_url: str | None = None
    notes: str | None = None
    status: ProjectSubmissionStatus | None = None


class SaveRoadmapResponse(BaseModel):
    roadmap_slug: str
    saved: bool
    popularity: int
