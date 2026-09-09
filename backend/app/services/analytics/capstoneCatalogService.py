"""Catalogue health, analytics counts and which roles the product can answer for.

Split out of ``CapstoneAnalyticsService`` by TASK-023. That class had grown to
1499 lines holding extraction, review, catalogue, metrics, embeddings,
recommendations, optimisation and persistence at once; length was the symptom,
those eight responsibilities in one place were the problem.

Everything here is read-only: it counts rows and grades the catalogue. Nothing
in this module writes.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skillModel import (
    CourseModel,
    CourseSkillModel,
    JobSkillModel,
    ResumeSkillModel,
    SkillAliasModel,
    SkillModel,
)
from app.services.analytics.capstoneAnalyticsSeedService import CAPSTONE_ROLE_SKILL_SEED_DATA
from app.services.analytics.embeddingService import (
    ResumeEmbeddingService,
    get_embedding_status,
)

RESUME_SKILL_STATUS_DETECTED = "detected"
RESUME_SKILL_STATUS_CONFIRMED = "confirmed"
RESUME_SKILL_STATUS_REJECTED = "rejected"
RESUME_SKILL_STATUS_MANUAL = "manual"


class CapstoneCatalogService:
    """How healthy the analytical catalogue is, and what it can support."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_analytics_status(self) -> dict:
        skills_count = await self._count(SkillModel)
        aliases_count = await self._count(SkillAliasModel)
        resume_skill_status_counts = await self._count_resume_skills_by_status()
        courses_count = await self._count(CourseModel)
        course_skills_count = await self._count(CourseSkillModel)

        role_seed_result = await self.session.execute(
            select(func.count(JobSkillModel.id)).where(
                JobSkillModel.job_posting_id.is_(None),
                JobSkillModel.extraction_method == "role_seed",
            )
        )
        role_seed_requirements_count = int(role_seed_result.scalar_one() or 0)

        real_job_skill_result = await self.session.execute(
            select(func.count(JobSkillModel.id)).where(JobSkillModel.job_posting_id.is_not(None))
        )
        real_job_skill_links_count = int(real_job_skill_result.scalar_one() or 0)

        synced_jobs_result = await self.session.execute(
            select(func.count(func.distinct(JobSkillModel.job_posting_id))).where(
                JobSkillModel.job_posting_id.is_not(None)
            )
        )
        synced_job_postings_count = int(synced_jobs_result.scalar_one() or 0)
        embedding_service = ResumeEmbeddingService(self.session)
        embedding_status = get_embedding_status()
        resume_embeddings_count = await embedding_service.count_resume_embeddings()

        catalog_ready = (
            skills_count > 0
            and courses_count > 0
            and course_skills_count > 0
            and role_seed_requirements_count > 0
        )

        next_action = None
        if not catalog_ready:
            next_action = "Run the capstone analytics seed to create the starter skill, course, and role catalog."
        elif real_job_skill_links_count == 0:
            next_action = "Sync open job postings to replace starter role requirements with market-backed requirements."

        return {
            "schema_ready": True,
            "catalog_ready": catalog_ready,
            "skills_count": skills_count,
            "aliases_count": aliases_count,
            "resume_skills_count": sum(resume_skill_status_counts.values()),
            "detected_resume_skills_count": resume_skill_status_counts.get(RESUME_SKILL_STATUS_DETECTED, 0),
            "confirmed_resume_skills_count": resume_skill_status_counts.get(RESUME_SKILL_STATUS_CONFIRMED, 0),
            "rejected_resume_skills_count": resume_skill_status_counts.get(RESUME_SKILL_STATUS_REJECTED, 0),
            "manual_resume_skills_count": resume_skill_status_counts.get(RESUME_SKILL_STATUS_MANUAL, 0),
            "courses_count": courses_count,
            "course_skills_count": course_skills_count,
            "role_seed_requirements_count": role_seed_requirements_count,
            "real_job_skill_links_count": real_job_skill_links_count,
            "synced_job_postings_count": synced_job_postings_count,
            "supported_seed_roles": sorted(CAPSTONE_ROLE_SKILL_SEED_DATA.keys()),
            "resume_embeddings_count": resume_embeddings_count,
            "embedding_provider": embedding_status["provider"],
            "embedding_model_name": embedding_status["model_name"],
            "semantic_matching_ready": embedding_status["semantic_matching_ready"],
            "local_embedding_provider_configured": embedding_status["local_provider_configured"],
            "local_embedding_package_available": embedding_status["local_package_available"],
            "embedding_fallback_provider": embedding_status["fallback_provider"],
            "embedding_model_cache_strategy": embedding_status["model_cache_strategy"],
            "embedding_local_failure_count": embedding_status["local_failure_count"],
            "embedding_fallback_to_hash_count": embedding_status["fallback_to_hash_count"],
            "embedding_production_recommendation": embedding_status["production_recommendation"],
            "next_action": next_action,
        }

    async def get_supported_roles(self) -> dict:
        seed_counts = await self._count_role_requirements(require_real_job_posting=False)
        market_counts = await self._count_role_requirements(require_real_job_posting=True)
        synced_jobs_by_role = await self._count_synced_jobs_by_role()

        role_names = set(CAPSTONE_ROLE_SKILL_SEED_DATA.keys())
        role_names.update(seed_counts)
        role_names.update(market_counts)

        roles = []
        for role_name in sorted(role for role in role_names if role):
            market_skill_count = market_counts.get(role_name, 0)
            seed_skill_count = seed_counts.get(role_name, 0)
            has_market_requirements = market_skill_count > 0
            requirement_source = "none"
            if has_market_requirements:
                requirement_source = "job_postings"
            elif seed_skill_count > 0:
                requirement_source = "role_seed"

            roles.append(
                {
                    "target_role": role_name,
                    "requirement_source": requirement_source,
                    "required_skills_count": market_skill_count if has_market_requirements else seed_skill_count,
                    "synced_job_postings_count": synced_jobs_by_role.get(role_name, 0),
                    "is_market_backed": has_market_requirements,
                }
            )

        return {"roles": roles}

    async def get_catalog_quality(self) -> dict:
        skills_count = await self._count(SkillModel)
        role_counts = await self._count_role_requirements(require_real_job_posting=False)
        market_role_counts = await self._count_role_requirements(require_real_job_posting=True)

        # Load courses once and derive the count metrics from the result set
        # instead of issuing separate COUNT queries for the same table.
        course_rows_result = await self.session.execute(select(CourseModel))
        courses = list(course_rows_result.scalars().all())
        courses_count = len(courses)
        active_courses_count = sum(1 for course in courses if course.is_active)
        completeness = self._calculate_course_metadata_completeness(courses)

        course_skill_result = await self.session.execute(
            select(
                CourseSkillModel.course_id,
                func.count(CourseSkillModel.skill_id),
            ).group_by(CourseSkillModel.course_id)
        )
        course_skill_counts = [int(count or 0) for _, count in course_skill_result.all()]
        average_skills_per_course = (
            sum(course_skill_counts) / len(course_skill_counts)
            if course_skill_counts
            else 0.0
        )
        courses_with_skill_mapping = sum(1 for count in course_skill_counts if count > 0)
        mapped_course_ratio = courses_with_skill_mapping / courses_count if courses_count else 0.0

        quality_score = self._calculate_catalog_quality_score(
            skills_count=skills_count,
            active_courses_count=active_courses_count,
            role_count=len(role_counts),
            mapped_course_ratio=mapped_course_ratio,
            metadata_completeness=completeness["overall"],
        )
        next_actions = self._build_catalog_quality_actions(
            skills_count=skills_count,
            active_courses_count=active_courses_count,
            role_count=len(role_counts),
            mapped_course_ratio=mapped_course_ratio,
            metadata_completeness=completeness["overall"],
            market_role_count=len(market_role_counts),
        )

        return {
            "quality_version": "catalog_quality_v1",
            "quality_score": quality_score,
            "skills_count": skills_count,
            "courses_count": courses_count,
            "active_courses_count": active_courses_count,
            "seed_role_count": len(role_counts),
            "market_backed_role_count": len(market_role_counts),
            "courses_with_skill_mapping": courses_with_skill_mapping,
            "mapped_course_ratio": round(mapped_course_ratio, 4),
            "average_skills_per_course": round(average_skills_per_course, 2),
            "metadata_completeness": completeness,
            "next_actions": next_actions,
        }

    @staticmethod
    def _calculate_course_metadata_completeness(courses: list[CourseModel]) -> dict:
        if not courses:
            return {
                "overall": 0.0,
                "url": 0.0,
                "cost": 0.0,
                "duration_hours": 0.0,
                "difficulty": 0.0,
                "rating": 0.0,
            }

        checks = {
            "url": sum(1 for course in courses if course.url),
            "cost": sum(1 for course in courses if course.cost is not None),
            "duration_hours": sum(1 for course in courses if course.duration_hours is not None),
            "difficulty": sum(1 for course in courses if course.difficulty),
            "rating": sum(1 for course in courses if course.rating is not None),
        }
        ratios = {
            key: round(value / len(courses), 4)
            for key, value in checks.items()
        }
        ratios["overall"] = round(sum(ratios.values()) / len(ratios), 4)
        return ratios

    @staticmethod
    def _calculate_catalog_quality_score(
        *,
        skills_count: int,
        active_courses_count: int,
        role_count: int,
        mapped_course_ratio: float,
        metadata_completeness: float,
    ) -> float:
        skill_score = min(skills_count / 75, 1.0)
        course_score = min(active_courses_count / 40, 1.0)
        role_score = min(role_count / 8, 1.0)
        quality_score = (
            skill_score * 0.25
            + course_score * 0.25
            + role_score * 0.2
            + mapped_course_ratio * 0.15
            + metadata_completeness * 0.15
        )
        return round(max(0.0, min(quality_score, 1.0)), 4)

    @staticmethod
    def _build_catalog_quality_actions(
        *,
        skills_count: int,
        active_courses_count: int,
        role_count: int,
        mapped_course_ratio: float,
        metadata_completeness: float,
        market_role_count: int,
    ) -> list[str]:
        actions = []
        if skills_count < 75:
            actions.append("Expand the skill catalog toward at least 75 canonical skills for the first production vertical.")
        if active_courses_count < 40:
            actions.append("Curate at least 40 active learning resources with reliable cost, duration, difficulty, and rating.")
        if role_count < 8:
            actions.append("Add more target role profiles before positioning the feature as a broad career planner.")
        if mapped_course_ratio < 0.95:
            actions.append("Ensure every active course maps to at least one canonical skill.")
        if metadata_completeness < 0.9:
            actions.append("Fill missing course metadata so optimization can compare cost, time, difficulty, and quality fairly.")
        if market_role_count == 0:
            actions.append("Sync real job postings so role requirements and demand signals are market-backed.")
        if not actions:
            actions.append("Catalog is ready for product validation; continue monitoring freshness and outcome quality.")
        return actions

    async def _count(self, model) -> int:
        result = await self.session.execute(select(func.count(model.id)))
        return int(result.scalar_one() or 0)

    async def _count_resume_skills_by_status(self) -> dict[str, int]:
        result = await self.session.execute(
            select(
                ResumeSkillModel.status,
                func.count(ResumeSkillModel.id),
            ).group_by(ResumeSkillModel.status)
        )
        return {str(status or RESUME_SKILL_STATUS_DETECTED): int(count or 0) for status, count in result.all()}

    async def _count_role_requirements(self, *, require_real_job_posting: bool) -> dict[str, int]:
        job_posting_filter = (
            JobSkillModel.job_posting_id.is_not(None)
            if require_real_job_posting
            else JobSkillModel.job_posting_id.is_(None)
        )
        result = await self.session.execute(
            select(
                JobSkillModel.target_role,
                func.count(func.distinct(JobSkillModel.skill_id)),
            )
            .where(JobSkillModel.target_role.is_not(None), job_posting_filter)
            .group_by(JobSkillModel.target_role)
        )
        return {str(role): int(count or 0) for role, count in result.all() if role}

    async def _count_synced_jobs_by_role(self) -> dict[str, int]:
        result = await self.session.execute(
            select(
                JobSkillModel.target_role,
                func.count(func.distinct(JobSkillModel.job_posting_id)),
            )
            .where(
                JobSkillModel.target_role.is_not(None),
                JobSkillModel.job_posting_id.is_not(None),
            )
            .group_by(JobSkillModel.target_role)
        )
        return {str(role): int(count or 0) for role, count in result.all() if role}
