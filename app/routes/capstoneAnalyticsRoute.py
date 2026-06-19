from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.userModel import User
from app.schemas.capstoneAnalyticsSchema import (
    CapstoneAnalyticsRolesRead,
    CapstoneAnalyticsSeedSummaryRead,
    CapstoneAnalyticsStatusRead,
    CapstoneGapAnalysisRead,
    CapstoneJobSkillBatchExtractionRead,
    CapstoneJobSkillExtractionRead,
    CapstoneSkillExtractionRead,
    CapstoneSkillExtractionRequest,
)
from app.services.analytics.capstoneAnalyticsService import CapstoneAnalyticsService
from app.services.analytics.capstoneAnalyticsSeedService import seed_capstone_analytics_minimum
from app.services.accounts.userService import current_active_user


router = APIRouter()

_CAPSTONE_ANALYTICS_TABLES = (
    "skills",
    "skill_aliases",
    "job_skills",
    "resume_skills",
    "courses",
    "course_skills",
    "optimization_runs",
)


def _is_missing_capstone_analytics_schema_error(exc: Exception) -> bool:
    message = str(exc).lower()
    if "does not exist" not in message and "undefinedtableerror" not in message:
        return False
    return any(table in message for table in _CAPSTONE_ANALYTICS_TABLES)


async def _run_capstone_operation(operation):
    try:
        return await operation()
    except ProgrammingError as exc:
        if not _is_missing_capstone_analytics_schema_error(exc):
            raise
        raise HTTPException(
            status_code=503,
            detail="Career analytics schema is not ready. Run: uv run alembic upgrade head, then seed the capstone analytics catalog.",
        ) from exc


def _require_capstone_admin(user: User) -> None:
    if not user.is_superuser:
        raise HTTPException(status_code=403, detail="Only admins can manage the career analytics catalog")


@router.post("/capstone/resumes/{resume_id}/skills/extract", response_model=CapstoneSkillExtractionRead)
async def extract_resume_skills(
    resume_id: UUID,
    payload: CapstoneSkillExtractionRequest,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    service = CapstoneAnalyticsService(session)
    resume = await service.get_user_resume(resume_id=resume_id, user_id=user.id)
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found")

    await _run_capstone_operation(
        lambda: service.extract_resume_skills_from_text(
            resume_id=resume_id,
            user_id=user.id,
            text=payload.text,
            extraction_method="manual_text_rules_v1",
            source_section=payload.source_section,
        )
    )
    extracted_skills = await _run_capstone_operation(
        lambda: service.get_resume_skills(resume_id)
    )
    return CapstoneSkillExtractionRead(
        resume_id=str(resume_id),
        extracted_skills=extracted_skills,
    )


@router.post("/capstone/resumes/{resume_id}/skills/sync", response_model=CapstoneSkillExtractionRead)
async def sync_resume_skills_from_summary(
    resume_id: UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    service = CapstoneAnalyticsService(session)
    resume = await service.get_user_resume(resume_id=resume_id, user_id=user.id)
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found")

    await _run_capstone_operation(
        lambda: service.extract_resume_skills_from_existing_resume(
            resume_id=resume_id,
            user_id=user.id,
        )
    )
    extracted_skills = await _run_capstone_operation(
        lambda: service.get_resume_skills(resume_id)
    )
    return CapstoneSkillExtractionRead(
        resume_id=str(resume_id),
        extracted_skills=extracted_skills,
    )


@router.get("/capstone/analytics/status", response_model=CapstoneAnalyticsStatusRead)
async def get_capstone_analytics_status(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    del user
    service = CapstoneAnalyticsService(session)
    return await _run_capstone_operation(lambda: service.get_analytics_status())


@router.get("/capstone/analytics/roles", response_model=CapstoneAnalyticsRolesRead)
async def get_capstone_analytics_roles(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    del user
    service = CapstoneAnalyticsService(session)
    return await _run_capstone_operation(lambda: service.get_supported_roles())


@router.post("/capstone/analytics/seed", response_model=CapstoneAnalyticsSeedSummaryRead)
async def seed_capstone_analytics_catalog(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    _require_capstone_admin(user)
    return await _run_capstone_operation(lambda: seed_capstone_analytics_minimum(session))


@router.post("/capstone/job-postings/{job_posting_id}/skills/sync", response_model=CapstoneJobSkillExtractionRead)
async def sync_job_posting_skills(
    job_posting_id: UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    _require_capstone_admin(user)
    service = CapstoneAnalyticsService(session)
    await _run_capstone_operation(
        lambda: service.extract_job_skills_from_job_posting(job_posting_id=job_posting_id)
    )
    extracted_skills = await _run_capstone_operation(
        lambda: service.get_job_skills(job_posting_id)
    )
    if not extracted_skills:
        # Keep this endpoint diagnostic: a valid job can return an empty extraction.
        return CapstoneJobSkillExtractionRead(job_posting_id=str(job_posting_id), extracted_skills=[])
    return CapstoneJobSkillExtractionRead(
        job_posting_id=str(job_posting_id),
        extracted_skills=extracted_skills,
    )


@router.post("/capstone/job-postings/skills/sync-open", response_model=CapstoneJobSkillBatchExtractionRead)
async def sync_open_job_posting_skills(
    limit: int = Query(100, ge=1, le=500),
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    _require_capstone_admin(user)
    service = CapstoneAnalyticsService(session)
    return await _run_capstone_operation(
        lambda: service.extract_job_skills_for_open_postings(limit=limit)
    )


@router.get("/capstone/gap-analysis", response_model=CapstoneGapAnalysisRead)
async def get_capstone_gap_analysis(
    resume_id: UUID,
    target_role: str = Query(..., min_length=2, max_length=120),
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    service = CapstoneAnalyticsService(session)
    payload = await _run_capstone_operation(
        lambda: service.analyze_gap(
            resume_id=resume_id,
            user_id=user.id,
            target_role=target_role,
        )
    )
    if payload["status"] == "resume_not_found":
        raise HTTPException(status_code=404, detail="Resume not found")
    return payload
