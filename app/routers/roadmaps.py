from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import ProgrammingError

from app.db import get_session
from app.models.userModel import User
from app.routers.dependencies import get_current_user_stub
from app.schemas.roadmapSchema import (
    RoadmapDetailRead,
    RoadmapListItemRead,
    SaveRoadmapResponse,
    SavedRoadmapRead,
)
from app.services.roadmapService import RoadmapService
from app.services.userService import current_active_user_optional

api_router = APIRouter()
view_router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _is_missing_roadmap_tables_error(exc: Exception) -> bool:
    message = str(exc).lower()
    if "does not exist" not in message and "undefinedtableerror" not in message:
        return False
    return any(
        table_name in message
        for table_name in (
            "roadmaps",
            "user_roadmaps",
            "roadmap_stages",
            "stage_tasks",
            "stage_projects",
            "user_task_progress",
            "user_stage_progress",
            "user_project_submissions",
        )
    )


@api_router.get("/roadmaps", response_model=list[RoadmapListItemRead])
async def list_roadmaps(
    search: str | None = Query(default=None),
    sort: str = Query(default="most_saved"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user_stub),
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


@api_router.get("/roadmaps/{slug}", response_model=RoadmapDetailRead)
async def get_roadmap(
    slug: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user_stub),
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


@api_router.post("/roadmaps/{slug}/save", response_model=SaveRoadmapResponse)
async def save_roadmap(
    slug: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user_stub),
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


@api_router.delete("/roadmaps/{slug}/save", response_model=SaveRoadmapResponse)
async def unsave_roadmap(
    slug: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user_stub),
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


@api_router.get("/me/roadmaps", response_model=list[SavedRoadmapRead])
async def get_my_roadmaps(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user_stub),
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


@view_router.get("/roadmaps")
async def roadmaps_page(
    request: Request,
    search: str | None = Query(default=None),
    sort: str = Query(default="most_saved"),
    session: AsyncSession = Depends(get_session),
    current_user: User | None = Depends(current_active_user_optional),
):
    if current_user is None:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    service = RoadmapService(session)
    schema_not_ready = request.query_params.get("schema_not_ready") == "1"

    try:
        saved_roadmaps = await service.list_saved_roadmaps(user_id=current_user.id)
        roadmaps = await service.list_public_roadmaps(user_id=current_user.id, search=search, sort=sort)
    except ProgrammingError as exc:
        if not _is_missing_roadmap_tables_error(exc):
            raise
        saved_roadmaps = []
        roadmaps = []
        schema_not_ready = True

    return templates.TemplateResponse(
        "roadmaps_list.html",
        {
            "request": request,
            "saved_roadmaps": saved_roadmaps,
            "roadmaps": roadmaps,
            "search": search or "",
            "sort": sort,
            "schema_not_ready": schema_not_ready,
        },
    )


@view_router.get("/roadmaps/{slug}")
async def roadmap_detail_page(
    request: Request,
    slug: str,
    session: AsyncSession = Depends(get_session),
    current_user: User | None = Depends(current_active_user_optional),
):
    if current_user is None:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    service = RoadmapService(session)
    try:
        detail = await service.get_roadmap_detail(user_id=current_user.id, slug=slug)
    except ProgrammingError as exc:
        if _is_missing_roadmap_tables_error(exc):
            return RedirectResponse(url="/roadmaps?schema_not_ready=1", status_code=status.HTTP_307_TEMPORARY_REDIRECT)
        raise
    if not detail:
        raise HTTPException(status_code=404, detail="Roadmap not found")

    grouped_tasks = service.build_stage_grouped_tasks(detail)
    detail_items: dict[str, dict] = {}
    first_item_id: str | None = None

    for stage in detail.stages:
        for task in stage.tasks:
            key = str(task.id)
            detail_items[key] = {
                "kind": "task",
                "stage_title": stage.title,
                "title": task.title,
                "description": task.description,
                "estimated_hours": task.estimated_hours,
                "task_type": task.task_type.value,
                "resource_url": task.resource_url,
                "resource_title": task.resource_title,
            }
            if first_item_id is None:
                first_item_id = key

        for project in stage.projects:
            key = str(project.id)
            detail_items[key] = {
                "kind": "project",
                "stage_title": stage.title,
                "title": project.title,
                "description": project.brief,
                "estimated_hours": project.estimated_hours,
                "acceptance_criteria": project.acceptance_criteria,
                "rubric": project.rubric,
                "submission": project.submission.model_dump() if project.submission else None,
            }
            if first_item_id is None:
                first_item_id = key

    return templates.TemplateResponse(
        "roadmap_detail.html",
        {
            "request": request,
            "roadmap": detail,
            "grouped_tasks": grouped_tasks,
            "detail_items_json": json.dumps(detail_items, default=str),
            "first_item_id": first_item_id,
        },
    )
