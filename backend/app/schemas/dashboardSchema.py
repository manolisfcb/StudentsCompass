"""Typed response for `GET /dashboard/student` (TASK-048, plan 08 §5.2).

`DashboardService.get_student_dashboard` has always returned a plain `Dict`
(`response_model=Dict` on the legacy `/students_dashboard` route, so every
field showed as `unknown` in the generated contract). This is the same shape,
named, so the React dashboard can read `progress.resume` etc. without casting.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class DashboardUserRead(BaseModel):
    id: str
    email: Optional[str] = None
    nickname: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class DashboardStatsRead(BaseModel):
    overall_progress: float
    total_applications: int
    in_review: int
    interviews_scheduled: int
    offers_received: int
    applied: int


class DashboardProgressRead(BaseModel):
    """Percent complete per core course, projected by `CourseProgressProjector`
    (TASK-016) — never recomputed here or on the client (F-15)."""

    resume: float
    linkedin: float
    interview_prep: float
    portfolio: float


class DashboardApplicationBreakdownRead(BaseModel):
    applied: int
    in_review: int
    interviews: int
    offers: int


class DashboardRecentApplicationRead(BaseModel):
    id: str
    job_title: str
    company_id: str
    status: str
    application_date: Optional[str] = None
    notes: Optional[str] = None


class DashboardResourceLinkRead(BaseModel):
    title: str
    url: str
    icon: str


class StudentDashboardRead(BaseModel):
    user: DashboardUserRead
    stats: DashboardStatsRead
    progress: DashboardProgressRead
    application_breakdown: DashboardApplicationBreakdownRead
    #: Deep link to the next unfinished lesson of each core course, keyed the
    #: same as `progress` (`resume`, `linkedin`, `interview_prep`, `portfolio`).
    resource_navigation: dict[str, str]
    recent_applications: list[DashboardRecentApplicationRead]
    resources: list[DashboardResourceLinkRead]
