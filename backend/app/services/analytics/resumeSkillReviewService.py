"""Reviewing the skills extracted from a CV: reading them, and changing their status.

Split out of ``CapstoneAnalyticsService`` by TASK-023, which is the only part of
that class that *writes* skill rows on a user's behalf. Keeping it separate from
extraction matters: extraction decides what a CV appears to say, review is where
a person overrules it, and the two had been sharing a class with catalogue
metrics and route optimisation.

Ownership is part of every lookup here, never a check bolted on afterwards: a
resume that belongs to someone else is indistinguishable from one that does not
exist.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.resumeModel import ResumeModel
from app.models.skillModel import ResumeSkillModel, SkillModel
from app.services.analytics.skillNormalizer import SkillNormalizer

RESUME_SKILL_STATUS_DETECTED = "detected"
RESUME_SKILL_STATUS_CONFIRMED = "confirmed"
RESUME_SKILL_STATUS_REJECTED = "rejected"
RESUME_SKILL_STATUS_MANUAL = "manual"

#: What counts as still standing. A rejected skill is kept as a record of the
#: decision, not deleted, so every read has to say whether it wants them.
ACTIVE_RESUME_SKILL_STATUSES = {
    RESUME_SKILL_STATUS_DETECTED,
    RESUME_SKILL_STATUS_CONFIRMED,
    RESUME_SKILL_STATUS_MANUAL,
}


class ResumeSkillReviewService:
    """Read and adjudicate the skills extracted from a CV."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_resume(self, *, resume_id: UUID, user_id: UUID) -> ResumeModel | None:
        result = await self.session.execute(
            select(ResumeModel).where(
                ResumeModel.id == resume_id,
                ResumeModel.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_resume_skills(self, resume_id: UUID, *, include_rejected: bool = False) -> list[dict]:
        result = await self.session.execute(
            select(ResumeSkillModel)
            .options(selectinload(ResumeSkillModel.skill))
            .where(ResumeSkillModel.resume_id == resume_id)
        )
        resume_skills = [
            resume_skill
            for resume_skill in result.scalars().all()
            if include_rejected or resume_skill.status in ACTIVE_RESUME_SKILL_STATUSES
        ]
        best_by_skill_id: dict[UUID, ResumeSkillModel] = {}
        for resume_skill in resume_skills:
            existing = best_by_skill_id.get(resume_skill.skill_id)
            if existing is None or self._resume_skill_rank(resume_skill) > self._resume_skill_rank(existing):
                best_by_skill_id[resume_skill.skill_id] = resume_skill

        return [
            {
                "resume_skill_id": str(resume_skill.id),
                "skill_id": str(resume_skill.skill_id),
                "normalized_name": resume_skill.skill.normalized_name,
                "display_name": resume_skill.skill.display_name,
                "category": resume_skill.skill.category,
                "confidence_score": resume_skill.confidence_score,
                "evidence_text": resume_skill.evidence_text,
                "extraction_method": resume_skill.extraction_method,
                "source_section": resume_skill.source_section,
                "status": resume_skill.status,
                "reviewed_at": resume_skill.reviewed_at,
            }
            for resume_skill in sorted(best_by_skill_id.values(), key=lambda item: item.skill.display_name.lower())
        ]

    async def list_resume_skills_for_review(self, *, resume_id: UUID, user_id: UUID) -> dict | None:
        resume = await self.get_user_resume(resume_id=resume_id, user_id=user_id)
        if resume is None:
            return None
        return {
            "resume_id": str(resume.id),
            "skills": await self.get_resume_skills(resume.id, include_rejected=True),
        }

    async def update_resume_skill_review_status(
        self,
        *,
        resume_id: UUID,
        user_id: UUID,
        resume_skill_id: UUID,
        status: str,
    ) -> dict | None:
        if status not in {RESUME_SKILL_STATUS_CONFIRMED, RESUME_SKILL_STATUS_REJECTED}:
            return None
        resume_skill = await self._get_user_resume_skill(
            resume_id=resume_id,
            user_id=user_id,
            resume_skill_id=resume_skill_id,
        )
        if resume_skill is None:
            return None

        resume_skill.status = status
        resume_skill.reviewed_at = datetime.utcnow()
        resume_skill.reviewed_by_user_id = user_id
        if status == RESUME_SKILL_STATUS_CONFIRMED:
            resume_skill.confidence_score = max(float(resume_skill.confidence_score or 0), 0.95)
        self.session.add(resume_skill)
        await self.session.commit()
        return await self.list_resume_skills_for_review(resume_id=resume_id, user_id=user_id)

    async def add_manual_resume_skill(
        self,
        *,
        resume_id: UUID,
        user_id: UUID,
        skill_id: UUID | None = None,
        normalized_name: str | None = None,
        evidence_text: str | None = None,
        source_section: str | None = None,
    ) -> dict | None:
        resume = await self.get_user_resume(resume_id=resume_id, user_id=user_id)
        if resume is None:
            return None

        skill = await self._find_skill(skill_id=skill_id, normalized_name=normalized_name)
        if skill is None:
            return {"status": "skill_not_found", "resume_id": str(resume.id), "skills": []}

        existing_result = await self.session.execute(
            select(ResumeSkillModel).where(
                ResumeSkillModel.resume_id == resume.id,
                ResumeSkillModel.skill_id == skill.id,
            )
        )
        existing = existing_result.scalars().first()
        if existing:
            existing.status = RESUME_SKILL_STATUS_MANUAL
            existing.extraction_method = "manual_review_v1"
            existing.confidence_score = 1.0
            existing.evidence_text = evidence_text or existing.evidence_text or "Added manually by student."
            existing.source_section = source_section or existing.source_section or "student_review"
            existing.reviewed_at = datetime.utcnow()
            existing.reviewed_by_user_id = user_id
            self.session.add(existing)
        else:
            self.session.add(
                ResumeSkillModel(
                    resume_id=resume.id,
                    user_id=user_id,
                    skill_id=skill.id,
                    confidence_score=1.0,
                    extraction_method="manual_review_v1",
                    evidence_text=evidence_text or "Added manually by student.",
                    source_section=source_section or "student_review",
                    status=RESUME_SKILL_STATUS_MANUAL,
                    reviewed_at=datetime.utcnow(),
                    reviewed_by_user_id=user_id,
                )
            )

        await self.session.commit()
        return await self.list_resume_skills_for_review(resume_id=resume_id, user_id=user_id)

    async def delete_resume_skill(
        self,
        *,
        resume_id: UUID,
        user_id: UUID,
        resume_skill_id: UUID,
    ) -> dict | None:
        resume_skill = await self._get_user_resume_skill(
            resume_id=resume_id,
            user_id=user_id,
            resume_skill_id=resume_skill_id,
        )
        if resume_skill is None:
            return None
        await self.session.delete(resume_skill)
        await self.session.commit()
        return await self.list_resume_skills_for_review(resume_id=resume_id, user_id=user_id)

    async def _get_user_resume_skill(
        self,
        *,
        resume_id: UUID,
        user_id: UUID,
        resume_skill_id: UUID,
    ) -> ResumeSkillModel | None:
        result = await self.session.execute(
            select(ResumeSkillModel)
            .join(ResumeModel, ResumeModel.id == ResumeSkillModel.resume_id)
            .where(
                ResumeSkillModel.id == resume_skill_id,
                ResumeSkillModel.resume_id == resume_id,
                ResumeModel.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def _find_skill(
        self,
        *,
        skill_id: UUID | None,
        normalized_name: str | None,
    ) -> SkillModel | None:
        if skill_id:
            return await self.session.get(SkillModel, skill_id)
        if not normalized_name:
            return None
        normalized = SkillNormalizer.normalize_canonical_name(normalized_name)
        result = await self.session.execute(
            select(SkillModel).where(SkillModel.normalized_name == normalized)
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _resume_skill_rank(resume_skill: ResumeSkillModel) -> tuple[int, float]:
        status_rank = {
            RESUME_SKILL_STATUS_MANUAL: 4,
            RESUME_SKILL_STATUS_CONFIRMED: 3,
            RESUME_SKILL_STATUS_DETECTED: 2,
            RESUME_SKILL_STATUS_REJECTED: 1,
        }.get(resume_skill.status or RESUME_SKILL_STATUS_DETECTED, 0)
        return (status_rank, float(resume_skill.confidence_score or 0.0))
