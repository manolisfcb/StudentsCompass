from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.resumeModel import ResumeModel
from app.models.skillModel import (
    JobSkillModel,
    ResumeSkillModel,
    SkillModel,
)
from app.services.analytics.capstoneCatalogService import CapstoneCatalogService
from app.services.analytics.jobSkillExtractionService import JobSkillExtractionService
from app.services.analytics.capstoneGapService import CapstoneGapService
from app.services.analytics.resumeSkillExtractionService import ResumeSkillExtractionService
from app.services.analytics.resumeSkillReviewService import ResumeSkillReviewService
from app.services.analytics.skillExtractionService import SkillExtractionMatch, SkillExtractionService
from app.services.analytics.skillNormalizer import SkillNormalizer


LOGGER = logging.getLogger(__name__)

SkillMatch = SkillExtractionMatch

RESUME_SKILL_STATUS_DETECTED = "detected"
RESUME_SKILL_STATUS_CONFIRMED = "confirmed"
RESUME_SKILL_STATUS_REJECTED = "rejected"
RESUME_SKILL_STATUS_MANUAL = "manual"
ACTIVE_RESUME_SKILL_STATUSES = {
    RESUME_SKILL_STATUS_DETECTED,
    RESUME_SKILL_STATUS_CONFIRMED,
    RESUME_SKILL_STATUS_MANUAL,
}


class CapstoneAnalyticsService:
    """The Capstone facade: one entry point, several focused services behind it.

    TASK-023 split this class up. It had reached 1499 lines holding extraction,
    review, catalogue, metrics, embeddings, recommendations, optimisation and
    persistence at once. The routes and the payloads did not change — the facade
    is what keeps that true — but each responsibility now lives in one place and
    the facade holds no implementation of its own for what it delegates.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.skill_extraction_service = SkillExtractionService(session)
        self.catalog = CapstoneCatalogService(session)
        self.review = ResumeSkillReviewService(session)
        self.extraction = ResumeSkillExtractionService(session, review=self.review)
        self.gap = CapstoneGapService(session, review=self.review, extraction=self.extraction)
        self.job_skills = JobSkillExtractionService(session)

    @staticmethod
    def normalize_skill_text(value: str) -> str:
        return SkillNormalizer.normalize_text(value)

    async def build_skill_lookup(self) -> dict[str, SkillModel]:
        return await self.skill_extraction_service.build_skill_lookup()

    async def extract_known_skills_from_text(
        self,
        text: str,
        *,
        lookup: dict[str, SkillModel] | None = None,
    ) -> list[SkillMatch]:
        return await self.skill_extraction_service.extract_known_skills_from_text(
            text,
            lookup=lookup,
        )

    async def extract_resume_skills_from_text(self, *, resume_id: UUID, user_id: UUID, text: str, extraction_method: str='rules_v1', source_section: str | None=None) -> list[ResumeSkillModel]:
        return await self.extraction.extract_resume_skills_from_text(resume_id=resume_id, user_id=user_id, text=text, extraction_method=extraction_method, source_section=source_section)


    async def extract_resume_skills_from_existing_resume(self, *, resume_id: UUID, user_id: UUID, extraction_method: str='resume_summary_rules_v1') -> list[ResumeSkillModel]:
        return await self.extraction.extract_resume_skills_from_existing_resume(resume_id=resume_id, user_id=user_id, extraction_method=extraction_method)






    async def extract_job_skills_from_job_posting(self, *, job_posting_id: UUID, extraction_method: str='job_posting_rules_v1', lookup: dict[str, SkillModel] | None=None) -> list[JobSkillModel]:
        return await self.job_skills.extract_job_skills_from_job_posting(job_posting_id=job_posting_id, extraction_method=extraction_method, lookup=lookup)


    async def extract_job_skills_for_open_postings(self, *, limit: int=100) -> dict[str, int]:
        return await self.job_skills.extract_job_skills_for_open_postings(limit=limit)


    async def get_user_resume(self, *, resume_id: UUID, user_id: UUID) -> ResumeModel | None:
        return await self.review.get_user_resume(resume_id=resume_id, user_id=user_id)


    async def get_job_skills(self, job_posting_id: UUID) -> list[dict]:
        return await self.job_skills.get_job_skills(job_posting_id)


    async def get_analytics_status(self) -> dict:
        return await self.catalog.get_analytics_status()


    async def get_supported_roles(self) -> dict:
        return await self.catalog.get_supported_roles()


    async def get_catalog_quality(self) -> dict:
        return await self.catalog.get_catalog_quality()


    async def analyze_gap(self, *, resume_id: UUID, user_id: UUID, target_role: str, include_course_recommendations: bool=True) -> dict:
        return await self.gap.analyze_gap(resume_id=resume_id, user_id=user_id, target_role=target_role, include_course_recommendations=include_course_recommendations)


    async def optimize_learning_route(self, *, resume_id: UUID, user_id: UUID, target_role: str, budget: float | None, available_hours: float | None, max_courses: int | None) -> dict:
        return await self.gap.optimize_learning_route(resume_id=resume_id, user_id=user_id, target_role=target_role, budget=budget, available_hours=available_hours, max_courses=max_courses)


    async def evaluate_learning_route_baselines(self, *, resume_id: UUID, user_id: UUID, target_role: str, budget: float | None, available_hours: float | None, max_courses: int | None) -> dict:
        return await self.gap.evaluate_learning_route_baselines(resume_id=resume_id, user_id=user_id, target_role=target_role, budget=budget, available_hours=available_hours, max_courses=max_courses)


    async def list_learning_route_runs(self, *, user_id: UUID, limit: int=20) -> dict:
        return await self.gap.list_learning_route_runs(user_id=user_id, limit=limit)










    async def get_resume_skills(self, resume_id: UUID, *, include_rejected: bool=False) -> list[dict]:
        return await self.review.get_resume_skills(resume_id, include_rejected=include_rejected)


    async def list_resume_skills_for_review(self, *, resume_id: UUID, user_id: UUID) -> dict | None:
        return await self.review.list_resume_skills_for_review(resume_id=resume_id, user_id=user_id)


    async def update_resume_skill_review_status(self, *, resume_id: UUID, user_id: UUID, resume_skill_id: UUID, status: str) -> dict | None:
        return await self.review.update_resume_skill_review_status(resume_id=resume_id, user_id=user_id, resume_skill_id=resume_skill_id, status=status)


    async def add_manual_resume_skill(self, *, resume_id: UUID, user_id: UUID, skill_id: UUID | None=None, normalized_name: str | None=None, evidence_text: str | None=None, source_section: str | None=None) -> dict | None:
        return await self.review.add_manual_resume_skill(resume_id=resume_id, user_id=user_id, skill_id=skill_id, normalized_name=normalized_name, evidence_text=evidence_text, source_section=source_section)


    async def delete_resume_skill(self, *, resume_id: UUID, user_id: UUID, resume_skill_id: UUID) -> dict | None:
        return await self.review.delete_resume_skill(resume_id=resume_id, user_id=user_id, resume_skill_id=resume_skill_id)




















