from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.userModel import User
from app.schemas.resourceSchema import (
    ResourceDetailRead,
    ResourceLessonProgressUpdate,
    ResourceProgressRead,
    ResourceRead,
)
from app.services.resourceService import ResourceService
from app.services.userService import current_active_user

router = APIRouter()


@router.get("/resources", response_model=list[ResourceRead])
async def get_resources(
    category: str | None = Query(default=None),
    search: str | None = Query(default=None),
    sort: str = Query(default="recent"),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),
):
    service = ResourceService(session)
    return await service.list_published_resources(category=category, search=search, sort=sort)


@router.get("/resources/{resource_id}", response_model=ResourceDetailRead)
async def get_resource(
    resource_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),
):
    service = ResourceService(session)
    resource = await service.get_resource_with_outline(resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    return resource


@router.get("/resources/{resource_id}/outline")
async def get_resource_outline(
    resource_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),
):
    service = ResourceService(session)
    resource = await service.get_resource_with_outline(resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    return service.to_detail_payload(resource)


@router.get("/resources/{resource_id}/progress", response_model=ResourceProgressRead)
async def get_resource_progress(
    resource_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),
):
    service = ResourceService(session)
    progress = await service.get_resource_progress(resource_id=resource_id, user_id=user.id)
    if not progress:
        raise HTTPException(status_code=404, detail="Resource not found")
    return progress


@router.patch("/resources/lessons/{lesson_id}/progress", response_model=ResourceProgressRead)
async def patch_lesson_progress(
    lesson_id: UUID,
    payload: ResourceLessonProgressUpdate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),
):
    service = ResourceService(session)
    progress = await service.set_lesson_progress(
        user_id=user.id,
        lesson_id=lesson_id,
        completed=payload.completed,
    )
    if not progress:
        raise HTTPException(status_code=404, detail="Lesson not found")
    return progress
