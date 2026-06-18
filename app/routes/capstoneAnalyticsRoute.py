from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.userModel import User
from app.schemas.capstoneAnalyticsSchema import (
    CapstoneGapAnalysisRead,
    CapstoneSkillExtractionRead,
    CapstoneSkillExtractionRequest,
)
from app.services.capstoneAnalyticsService import CapstoneAnalyticsService
from app.services.userService import current_active_user


router = APIRouter()


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

    await service.extract_resume_skills_from_text(
        resume_id=resume_id,
        user_id=user.id,
        text=payload.text,
        extraction_method="manual_text_rules_v1",
        source_section=payload.source_section,
    )
    return CapstoneSkillExtractionRead(
        resume_id=str(resume_id),
        extracted_skills=await service.get_resume_skills(resume_id),
    )


@router.get("/capstone/gap-analysis", response_model=CapstoneGapAnalysisRead)
async def get_capstone_gap_analysis(
    resume_id: UUID,
    target_role: str = Query(..., min_length=2, max_length=120),
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    service = CapstoneAnalyticsService(session)
    payload = await service.analyze_gap(
        resume_id=resume_id,
        user_id=user.id,
        target_role=target_role,
    )
    if payload["status"] == "resume_not_found":
        raise HTTPException(status_code=404, detail="Resume not found")
    return payload
