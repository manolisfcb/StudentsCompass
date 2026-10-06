"""Career Lab: a vacancy the user pastes, analysed against their CV (plan 11, C1).

TASK-078 (paste a job description) and TASK-079 (the deterministic analysis).
No LLM is called on this path: C1 costs nothing per request beyond, at most,
one embedding of a posting no user has pasted before.
"""
from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ErrorCode
from app.core.idempotency import actor_key, begin_idempotent_request
from app.core.pagination import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, InvalidCursor
from app.db import get_session
from app.models.userModel import User
from app.schemas.careerLabSchema import (
    JobTargetCreate,
    JobTargetPageRead,
    JobTargetRead,
    JobTargetSummaryRead,
)
from app.services.accounts.userService import current_active_user
from app.services.analytics.resumeSkillReviewService import ResumeSkillReviewService
from app.services.careerLab.jobTargetAnalysisService import (
    JobTargetAnalysisError,
    JobTargetAnalysisService,
)
from app.services.careerLab.jobTargetService import JobTargetService

LOGGER = logging.getLogger(__name__)

router = APIRouter(prefix="/career-lab")


@router.post(
    "/job-targets",
    response_model=JobTargetRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_job_target(
    request: Request,
    payload: JobTargetCreate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    """Paste a job description and get its analysis against one of your CVs.

    The analysis runs in the request and the answer carries it: score, band,
    breakdown, strengths and prioritised gaps. A target whose analysis failed is
    still created, with ``status: failed`` and a reason, so nothing the user
    pasted is lost.

    Retry-safe under ``Idempotency-Key``: a lost response retried does not file
    the same vacancy twice.
    """
    guard = await begin_idempotent_request(
        session,
        request=request,
        actor=actor_key("user", user.id),
        endpoint="POST /career-lab/job-targets",
        payload=payload,
    )
    if guard.is_replay:
        return guard.replay

    try:
        resume = await ResumeSkillReviewService(session).get_user_resume(
            resume_id=payload.resume_id, user_id=user.id
        )
        if resume is None:
            raise AppError(ErrorCode.NOT_FOUND, "Resume not found.", status_code=404)

        target = await JobTargetService(session).create_target(
            user_id=user.id, raw_text=payload.text, resume_id=resume.id
        )
        target = await JobTargetAnalysisService(session).run(target=target, resume=resume)
    except JobTargetAnalysisError as exc:
        await guard.release()
        raise AppError(ErrorCode.CONFLICT, str(exc), status_code=409) from exc
    except Exception:
        await guard.release()
        raise
    return await guard.store(JobTargetRead.from_model(target), status_code=status.HTTP_201_CREATED)


@router.get("/job-targets", response_model=JobTargetPageRead)
async def list_job_targets(
    before: str | None = Query(
        default=None,
        description="Cursor from a previous page's next_cursor; returns older targets.",
    ),
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    """The caller's own job targets, newest first."""
    try:
        rows, next_cursor, has_more, page_size = await JobTargetService(
            session
        ).list_user_target_page(user_id=user.id, before=before, limit=limit)
    except InvalidCursor as exc:
        raise AppError(ErrorCode.INVALID_INPUT, "Invalid cursor.", status_code=400) from exc
    return JobTargetPageRead(
        items=[JobTargetSummaryRead.from_model(row) for row in rows],
        next_cursor=next_cursor,
        has_more=has_more,
        limit=page_size,
    )


@router.get("/job-targets/{target_id}", response_model=JobTargetRead)
async def get_job_target(
    target_id: UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    """One of the caller's job targets with its stored analysis. Reopening is free."""
    target = await JobTargetService(session).get_user_target(target_id=target_id, user_id=user.id)
    if target is None:
        raise AppError(ErrorCode.NOT_FOUND, "Job target not found.", status_code=404)
    return JobTargetRead.from_model(target)
