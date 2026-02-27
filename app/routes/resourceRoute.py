from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.userModel import User
from app.schemas.resourceSchema import (
    LessonCompletionUpdate,
    ResourceDetailRead,
    ResourceEnrollmentProgressRead,
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


@router.get("/resources/file")
async def get_resource_file(
    key: str = Query(...),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),
):
    service = ResourceService(session)
    try:
        file_bytes, media_type, filename = await service.download_resource_file(key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch resource file: {str(e)}")

    return Response(
        content=file_bytes,
        media_type=media_type,
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.get("/resources/progress/me", response_model=list[ResourceEnrollmentProgressRead])
async def get_my_resource_progress(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),
):
    service = ResourceService(session)
    return await service.list_user_enrollment_progress(user.id)


@router.post("/resources/{resource_id}/enroll", response_model=ResourceEnrollmentProgressRead)
async def enroll_in_resource(
    resource_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),
):
    service = ResourceService(session)
    try:
        return await service.enroll_user_in_resource(user.id, resource_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/resources/{resource_id}/lessons/{lesson_id}/open",
    response_model=ResourceEnrollmentProgressRead,
)
async def mark_lesson_opened(
    resource_id: UUID,
    lesson_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),
):
    service = ResourceService(session)
    try:
        return await service.mark_lesson_opened(
            user_id=user.id,
            resource_id=resource_id,
            lesson_id=lesson_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/resources/{resource_id}/lessons/{lesson_id}/complete",
    response_model=ResourceEnrollmentProgressRead,
)
async def complete_lesson(
    resource_id: UUID,
    lesson_id: UUID,
    payload: LessonCompletionUpdate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),
):
    service = ResourceService(session)
    try:
        return await service.set_lesson_completion(
            user_id=user.id,
            resource_id=resource_id,
            lesson_id=lesson_id,
            completed=payload.completed,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/resources/{resource_id}/progress", response_model=ResourceEnrollmentProgressRead)
async def get_resource_progress(
    resource_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user),
):
    service = ResourceService(session)
    try:
        return await service.get_user_resource_progress(user_id=user.id, resource_id=resource_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


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
    return await service.to_detail_payload(resource)
