from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.userModel import User
from app.routers.dependencies import get_current_user_stub
from app.schemas.roadmapSchema import ProjectSubmissionRead, ProjectSubmissionRequest
from app.services.roadmapService import RoadmapService

router = APIRouter()


def _is_missing_roadmap_tables_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        ("does not exist" in message or "undefinedtableerror" in message)
        and any(table_name in message for table_name in ("stage_projects", "user_project_submissions", "roadmap_stages"))
    )


@router.post("/projects/{project_id}/submit", response_model=ProjectSubmissionRead)
async def submit_project(
    project_id: UUID,
    payload: ProjectSubmissionRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user_stub),
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
