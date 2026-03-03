from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.userModel import User
from app.routers.dependencies import get_current_user_stub
from app.schemas.roadmapSchema import TaskProgressUpdateRequest, TaskProgressUpdateResponse
from app.services.roadmapService import RoadmapService

router = APIRouter()


def _is_missing_roadmap_tables_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        ("does not exist" in message or "undefinedtableerror" in message)
        and any(table_name in message for table_name in ("stage_tasks", "user_task_progress", "roadmap_stages"))
    )


@router.patch("/tasks/{task_id}/progress", response_model=TaskProgressUpdateResponse)
async def patch_task_progress(
    task_id: UUID,
    payload: TaskProgressUpdateRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user_stub),
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
