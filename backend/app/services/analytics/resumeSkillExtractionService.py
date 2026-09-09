"""Turning a stored CV into skill rows.

Split out of ``CapstoneAnalyticsService`` by TASK-023. Extraction decides what a
CV appears to say; ``ResumeSkillReviewService`` is where a person overrules it.
The two were in one class with catalogue metrics and route optimisation.

Nothing here calls an LLM: extraction is rule-based against the known skill
catalogue, so it costs no quota and needs no provider.
"""
from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.resumeModel import ResumeModel
from app.models.skillModel import ResumeSkillModel
from app.services.analytics.resumeSkillReviewService import (
    RESUME_SKILL_STATUS_DETECTED,
    ResumeSkillReviewService,
)
from app.services.analytics.skillExtractionService import SkillExtractionService

LOGGER = logging.getLogger(__name__)


class ResumeSkillExtractionService:
    """Read a CV — its summary or its file — and record the skills it shows."""

    def __init__(self, session: AsyncSession, *, review: ResumeSkillReviewService | None = None):
        self.session = session
        self.review = review or ResumeSkillReviewService(session)
        self.skill_extraction_service = SkillExtractionService(session)

    async def extract_resume_skills_from_text(
        self,
        *,
        resume_id: UUID,
        user_id: UUID,
        text: str,
        extraction_method: str = "rules_v1",
        source_section: str | None = None,
    ) -> list[ResumeSkillModel]:
        resume = await self.review.get_user_resume(resume_id=resume_id, user_id=user_id)
        if resume is None:
            return []

        matches = await self.skill_extraction_service.extract_known_skills_from_text(
            text,
            extraction_method=extraction_method,
            source_section=source_section,
        )
        created_or_existing: list[ResumeSkillModel] = []

        for match in matches:
            existing_result = await self.session.execute(
                select(ResumeSkillModel).where(
                    ResumeSkillModel.resume_id == resume.id,
                    ResumeSkillModel.skill_id == match.skill.id,
                    ResumeSkillModel.extraction_method == extraction_method,
                )
            )
            existing = existing_result.scalar_one_or_none()
            if existing:
                created_or_existing.append(existing)
                continue

            resume_skill = ResumeSkillModel(
                resume_id=resume.id,
                user_id=user_id,
                skill_id=match.skill.id,
                confidence_score=match.confidence_score,
                extraction_method=match.extraction_method,
                evidence_text=match.evidence_text,
                source_section=match.source_section,
                status=RESUME_SKILL_STATUS_DETECTED,
            )
            self.session.add(resume_skill)
            created_or_existing.append(resume_skill)

        await self.session.commit()
        return created_or_existing

    async def extract_resume_skills_from_existing_resume(
        self,
        *,
        resume_id: UUID,
        user_id: UUID,
        extraction_method: str = "resume_summary_rules_v1",
    ) -> list[ResumeSkillModel]:
        resume = await self.review.get_user_resume(resume_id=resume_id, user_id=user_id)
        if resume is None:
            return []
        if resume.ai_summary:
            return await self.extract_resume_skills_from_text(
                resume_id=resume.id,
                user_id=user_id,
                text=resume.ai_summary,
                extraction_method=extraction_method,
                source_section="ai_summary",
            )
        # No AI summary yet (e.g. the CV was uploaded without running the
        # quota-limited Jobs analysis). Fall back to rule-based extraction over
        # the raw resume text so the Career Lab still reads real skills.
        return await self._extract_resume_skills_from_file_text(resume=resume, user_id=user_id)

    async def _extract_resume_skills_from_file_text(
        self,
        *,
        resume: ResumeModel,
        user_id: UUID,
    ) -> list[ResumeSkillModel]:
        """Rule-based skill extraction straight from the stored CV file.

        Decouples the Career Lab from ``ai_summary`` (which is only populated by
        the separate, quota-limited Jobs CV analysis). No LLM call, no quota.
        """
        from app.core.resume_analyzer.resume_text_extractor import extract_resume_text_from_bytes
        from app.services.resumes.resumeService import ResumeService

        if not resume.storage_file_id:
            return []
        try:
            resume_service = ResumeService(self.session)
            file_content = await resume_service.download_resume_file(resume.storage_file_id)
            resume_text = await extract_resume_text_from_bytes(
                file_content,
                filename=resume.original_filename,
                content_type="",
            )
        except Exception:  # noqa: BLE001 — storage/extraction issues must not 500 the analysis
            LOGGER.exception("Could not read resume file for skill extraction (resume %s)", resume.id)
            return []

        if not resume_text or len(resume_text.strip()) < 30:
            return []

        return await self.extract_resume_skills_from_text(
            resume_id=resume.id,
            user_id=user_id,
            text=resume_text,
            extraction_method="resume_text_rules_v1",
            source_section="resume_text",
        )

    async def _extract_from_resume_summary_if_needed(self, *, resume: ResumeModel, user_id: UUID) -> None:
        existing_result = await self.session.execute(
            select(func.count(ResumeSkillModel.id)).where(ResumeSkillModel.resume_id == resume.id)
        )
        existing_count = int(existing_result.scalar_one() or 0)
        if existing_count:
            return
        if resume.ai_summary:
            await self.extract_resume_skills_from_text(
                resume_id=resume.id,
                user_id=user_id,
                text=resume.ai_summary,
                extraction_method="resume_summary_rules_v1",
                source_section="ai_summary",
            )
            return
        # No AI summary: extract straight from the CV text (no LLM / no quota).
        await self._extract_resume_skills_from_file_text(resume=resume, user_id=user_id)
