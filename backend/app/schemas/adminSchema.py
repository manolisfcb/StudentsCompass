"""Typed REST contract for the React administration console (TASK-053)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class AdminStatsRead(BaseModel):
    total_users: int
    total_companies: int
    total_communities: int
    total_resources: int
    total_jobs: int
    total_applications: int
    total_resumes: int
    total_questionnaires: int
    recent_users: int


class AdminUserRead(BaseModel):
    id: UUID
    email: str
    first_name: str | None = None
    last_name: str | None = None
    nickname: str | None = None
    is_active: bool
    is_superuser: bool
    is_verified: bool


class AdminUserPatch(BaseModel):
    is_active: bool | None = None
    is_superuser: bool | None = None

    @model_validator(mode="after")
    def require_change(self):
        if not self.model_fields_set:
            raise ValueError("At least one user field is required.")
        return self


class AdminUsersPage(BaseModel):
    items: list[AdminUserRead]
    page: int
    page_size: int
    total: int
    # Compatibility adapter for backend/app/static/js/admin.js. TASK-059
    # removes it only after the legacy consumer has observed zero traffic.
    users: list[AdminUserRead]


class AdminCommunityRead(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    icon: str | None = None
    member_count: int
    activity_status: str | None = None
    created_at: datetime | None = None
    creator_email: str | None = None


class AdminCommunitiesPage(BaseModel):
    items: list[AdminCommunityRead]
    page: int
    page_size: int
    total: int
    communities: list[AdminCommunityRead]


class AdminResourceRead(BaseModel):
    id: UUID
    title: str
    description: str
    category: str
    icon: str | None = None
    level: str | None = None
    tags: list[str] = Field(default_factory=list)
    estimated_duration_minutes: int | None = None
    external_url: str | None = None
    is_published: bool
    is_locked: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AdminResourceLessonRead(BaseModel):
    id: UUID
    title: str
    position: int
    content_type: str
    content: str | None = None
    content_payload: dict[str, Any] | None = None
    video_url: str | None = None
    resource_url: str | None = None
    notes: str | None = None
    reading_time_minutes: int | None = None


class AdminResourceModuleRead(BaseModel):
    id: UUID
    title: str
    position: int
    description: str | None = None
    lessons: list[AdminResourceLessonRead] = Field(default_factory=list)


class AdminResourceDetailRead(AdminResourceRead):
    modules: list[AdminResourceModuleRead] = Field(default_factory=list)


class AdminResourcesPage(BaseModel):
    items: list[AdminResourceRead]
    page: int
    page_size: int
    total: int
    resources: list[AdminResourceRead]


class AdminResourceStatePatch(BaseModel):
    is_published: bool | None = None
    is_locked: bool | None = None

    @model_validator(mode="after")
    def require_change(self):
        if not self.model_fields_set:
            raise ValueError("At least one resource field is required.")
        return self


class AdminResourceMutationRead(BaseModel):
    id: UUID
    title: str | None = None
    is_published: bool
    is_locked: bool


class AdminResourceFileRead(BaseModel):
    file_key: str
    file_url: str
    original_filename: str
    content_type: str


class AdminJobPostingRead(BaseModel):
    id: UUID
    title: str
    company_name: str
    location: str | None = None
    job_type: str | None = None
    is_active: bool
    created_at: datetime | None = None


class AdminJobPostingsPage(BaseModel):
    items: list[AdminJobPostingRead]
    page: int
    page_size: int
    total: int


class AdminJobPostingPatch(BaseModel):
    is_active: bool


class AdminCompanyRead(BaseModel):
    id: UUID
    company_name: str
    industry: str | None = None
    location: str | None = None
    website: str | None = None
    email: str | None = None


class AdminCompaniesPage(BaseModel):
    items: list[AdminCompanyRead]
    page: int
    page_size: int
    total: int
    companies: list[AdminCompanyRead]


class AdminApplicationRead(BaseModel):
    id: UUID
    job_title: str
    status: str | None = None
    user_email: str | None = None
    company_name: str | None = None
    application_date: datetime | None = None


class AdminApplicationsPage(BaseModel):
    items: list[AdminApplicationRead]
    page: int
    page_size: int
    total: int
    applications: list[AdminApplicationRead]


class AdminDeleteRead(BaseModel):
    ok: bool
