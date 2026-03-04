from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.userModel import User
from app.schemas.roadmapSchema import (
    ProjectSubmissionRead,
    ProjectSubmissionRequest,
    RoadmapDetailRead,
    RoadmapListItemRead,
    SaveRoadmapResponse,
    SavedRoadmapRead,
    TaskProgressUpdateRequest,
    TaskProgressUpdateResponse,
)
from app.services.roadmapService import RoadmapService
from app.services.userService import current_active_user

router = APIRouter()

_ROADMAP_TABLES = (
    "roadmaps",
    "user_roadmaps",
    "roadmap_stages",
    "stage_tasks",
    "stage_projects",
    "user_task_progress",
    "user_stage_progress",
    "user_project_submissions",
)


def _is_missing_roadmap_tables_error(exc: Exception) -> bool:
    """Returns True when the DB error is caused by missing roadmap tables (migrations not run)."""
    message = str(exc).lower()
    if "does not exist" not in message and "undefinedtableerror" not in message:
        return False
    return any(table_name in message for table_name in _ROADMAP_TABLES)


# ── Roadmaps ──────────────────────────────────────────────────────────────────

@router.get("/roadmaps", response_model=list[RoadmapListItemRead])
async def list_roadmaps(
    search: str | None = Query(default=None),
    sort: str = Query(default="most_saved"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(current_active_user),
):
    service = RoadmapService(session)
    try:
        return await service.list_public_roadmaps(user_id=current_user.id, search=search, sort=sort)
    except ProgrammingError as exc:
        if _is_missing_roadmap_tables_error(exc):
            raise HTTPException(
                status_code=503,
                detail="Roadmaps schema is not ready. Run: alembic upgrade head",
            ) from exc
        raise


@router.get("/me/roadmaps", response_model=list[SavedRoadmapRead])
async def get_my_roadmaps(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(current_active_user),
):
    service = RoadmapService(session)
    try:
        return await service.list_saved_roadmaps(user_id=current_user.id)
    except ProgrammingError as exc:
        if _is_missing_roadmap_tables_error(exc):
            raise HTTPException(
                status_code=503,
                detail="Roadmaps schema is not ready. Run: alembic upgrade head",
            ) from exc
        raise


@router.get("/roadmaps/{slug}", response_model=RoadmapDetailRead)
async def get_roadmap(
    slug: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(current_active_user),
):
    service = RoadmapService(session)
    try:
        roadmap = await service.get_roadmap_detail(user_id=current_user.id, slug=slug)
    except ProgrammingError as exc:
        if _is_missing_roadmap_tables_error(exc):
            raise HTTPException(
                status_code=503,
                detail="Roadmaps schema is not ready. Run: alembic upgrade head",
            ) from exc
        raise
    if not roadmap:
        raise HTTPException(status_code=404, detail="Roadmap not found")
    return roadmap


@router.post("/roadmaps/{slug}/save", response_model=SaveRoadmapResponse)
async def save_roadmap(
    slug: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(current_active_user),
):
    service = RoadmapService(session)
    try:
        result = await service.save_roadmap(user_id=current_user.id, slug=slug)
    except ProgrammingError as exc:
        if _is_missing_roadmap_tables_error(exc):
            raise HTTPException(
                status_code=503,
                detail="Roadmaps schema is not ready. Run: alembic upgrade head",
            ) from exc
        raise
    if not result:
        raise HTTPException(status_code=404, detail="Roadmap not found")
    return result


@router.delete("/roadmaps/{slug}/save", response_model=SaveRoadmapResponse)
async def unsave_roadmap(
    slug: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(current_active_user),
):
    service = RoadmapService(session)
    try:
        result = await service.unsave_roadmap(user_id=current_user.id, slug=slug)
    except ProgrammingError as exc:
        if _is_missing_roadmap_tables_error(exc):
            raise HTTPException(
                status_code=503,
                detail="Roadmaps schema is not ready. Run: alembic upgrade head",
            ) from exc
        raise
    if not result:
        raise HTTPException(status_code=404, detail="Roadmap not found")
    return result


# ── Task progress ─────────────────────────────────────────────────────────────

@router.patch("/tasks/{task_id}/progress", response_model=TaskProgressUpdateResponse)
async def patch_task_progress(
    task_id: UUID,
    payload: TaskProgressUpdateRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(current_active_user),
):
    service = RoadmapService(session)
    try:
        response = await service.update_task_progress(
            user_id=current_user.id,
            task_id=task_id,
            status=payload.status,
        )
    except ProgrammingError as exc:
        if _is_missing_roadmap_tables_error(exc):
            raise HTTPException(
                status_code=503,
                detail="Roadmaps schema is not ready. Run: alembic upgrade head",
            ) from exc
        raise
    if not response:
        raise HTTPException(status_code=404, detail="Task not found")
    return response


# ── Project submissions ───────────────────────────────────────────────────────

@router.post("/projects/{project_id}/submit", response_model=ProjectSubmissionRead)
async def submit_project(
    project_id: UUID,
    payload: ProjectSubmissionRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(current_active_user),
):
    service = RoadmapService(session)
    try:
        result = await service.submit_project(
            user_id=current_user.id,
            project_id=project_id,
            payload=payload,
        )
    except ProgrammingError as exc:
        if _is_missing_roadmap_tables_error(exc):
            raise HTTPException(
                status_code=503,
                detail="Roadmaps schema is not ready. Run: alembic upgrade head",
            ) from exc
        raise
    if not result:
        raise HTTPException(status_code=404, detail="Project not found")
    return result
