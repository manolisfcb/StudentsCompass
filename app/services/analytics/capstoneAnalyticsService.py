from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.resumeModel import ResumeModel
from app.models.jobPostingModel import JobPosting
from app.models.skillModel import (
    CourseModel,
    CourseSkillModel,
    JobSkillModel,
    OptimizationRunModel,
    ResumeSkillModel,
    SkillAliasModel,
    SkillModel,
)
from app.services.analytics.embeddingService import ResumeEmbeddingService, get_embedding_status
from app.services.analytics.capstoneAnalyticsSeedService import CAPSTONE_ROLE_SKILL_SEED_DATA
from app.services.analytics.courseCatalogQueries import load_active_course_links
from app.services.analytics.learningRouteOptimizerService import (
    LearningRouteConstraints,
    get_learning_route_optimizer,
)
from app.services.analytics.learningRouteBaselineEvaluationService import (
    LearningRouteBaselineEvaluationService,
)
from app.services.analytics.semanticMatchingService import SemanticMatchingService
from app.services.analytics.skillGapScoringService import SkillGapScoringService
from app.services.analytics.skillExtractionService import SkillExtractionMatch, SkillExtractionService
from app.services.analytics.skillNormalizer import SkillNormalizer


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
    def __init__(self, session: AsyncSession):
        self.session = session
        self.skill_extraction_service = SkillExtractionService(session)

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

    async def extract_resume_skills_from_text(
        self,
        *,
        resume_id: UUID,
        user_id: UUID,
        text: str,
        extraction_method: str = "rules_v1",
        source_section: str | None = None,
    ) -> list[ResumeSkillModel]:
        resume = await self.get_user_resume(resume_id=resume_id, user_id=user_id)
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
        resume = await self.get_user_resume(resume_id=resume_id, user_id=user_id)
        if resume is None or not resume.ai_summary:
            return []
        return await self.extract_resume_skills_from_text(
            resume_id=resume.id,
            user_id=user_id,
            text=resume.ai_summary,
            extraction_method=extraction_method,
            source_section="ai_summary",
        )

    async def extract_job_skills_from_job_posting(
        self,
        *,
        job_posting_id: UUID,
        extraction_method: str = "job_posting_rules_v1",
        lookup: dict[str, SkillModel] | None = None,
    ) -> list[JobSkillModel]:
        job_posting = await self.session.get(JobPosting, job_posting_id)
        if job_posting is None:
            return []

        text = self._job_posting_text(job_posting)
        if not text.strip():
            return []

        matches = await self.skill_extraction_service.extract_known_skills_from_text(
            text,
            lookup=lookup,
            extraction_method=extraction_method,
        )
        created_or_existing: list[JobSkillModel] = []
        target_role = self._infer_target_role(job_posting.title)

        existing_result = await self.session.execute(
            select(JobSkillModel).where(
                JobSkillModel.job_posting_id == job_posting.id,
                JobSkillModel.extraction_method == extraction_method,
            )
        )
        existing_by_skill_id = {
            existing.skill_id: existing for existing in existing_result.scalars().all()
        }

        for match in matches:
            existing = existing_by_skill_id.get(match.skill.id)
            if existing:
                created_or_existing.append(existing)
                continue

            job_skill = JobSkillModel(
                job_posting_id=job_posting.id,
                skill_id=match.skill.id,
                target_role=target_role,
                importance_score=0.75,
                extraction_method=match.extraction_method,
                evidence_text=match.evidence_text,
            )
            self.session.add(job_skill)
            created_or_existing.append(job_skill)

        await self.session.commit()
        return created_or_existing

    async def extract_job_skills_for_open_postings(self, *, limit: int = 100) -> dict[str, int]:
        result = await self.session.execute(
            select(JobPosting)
            .where(JobPosting.is_active.is_(True))
            .order_by(JobPosting.created_at.desc())
            .limit(max(1, min(limit, 500)))
        )
        jobs = list(result.scalars().all())

        # Build the skill lookup once for the whole batch instead of reloading
        # the full skills + aliases tables for every job.
        lookup = await self.build_skill_lookup()

        total_links = 0
        jobs_with_matches = 0
        for job in jobs:
            links = await self.extract_job_skills_from_job_posting(
                job_posting_id=job.id,
                lookup=lookup,
            )
            total_links += len(links)
            if links:
                jobs_with_matches += 1

        return {
            "jobs_scanned": len(jobs),
            "jobs_with_matches": jobs_with_matches,
            "job_skill_links": total_links,
        }

    async def get_user_resume(self, *, resume_id: UUID, user_id: UUID) -> ResumeModel | None:
        result = await self.session.execute(
            select(ResumeModel).where(
                ResumeModel.id == resume_id,
                ResumeModel.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_job_skills(self, job_posting_id: UUID) -> list[dict]:
        result = await self.session.execute(
            select(JobSkillModel)
            .options(selectinload(JobSkillModel.skill))
            .where(JobSkillModel.job_posting_id == job_posting_id)
        )
        job_skills = result.scalars().all()
        return [
            {
                "skill_id": str(job_skill.skill_id),
                "normalized_name": job_skill.skill.normalized_name,
                "display_name": job_skill.skill.display_name,
                "category": job_skill.skill.category,
                "importance_score": job_skill.importance_score,
                "evidence_text": job_skill.evidence_text,
                "extraction_method": job_skill.extraction_method,
            }
            for job_skill in sorted(job_skills, key=lambda item: item.skill.display_name.lower())
        ]

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

    async def analyze_gap(
        self,
        *,
        resume_id: UUID,
        user_id: UUID,
        target_role: str,
        include_course_recommendations: bool = True,
    ) -> dict:
        resume = await self.get_user_resume(resume_id=resume_id, user_id=user_id)
        if resume is None:
            return {"status": "resume_not_found", "resume_id": str(resume_id)}

        await self._extract_from_resume_summary_if_needed(resume=resume, user_id=user_id)
        await self._sync_resume_embedding_if_possible(resume)

        current_skills = await self.get_resume_skills(resume.id)
        required_skills = await self._get_role_required_skills(target_role)
        market_signals = await self._get_role_market_signals(
            target_role=target_role,
            required_skills=required_skills,
        )
        required_skills = self._attach_market_signals(
            required_skills=required_skills,
            market_signals=market_signals,
        )
        requirements_source = required_skills[0]["source_type"] if required_skills else "none"

        semantic_service = SemanticMatchingService()
        match_summary = await semantic_service.analyze_required_skill_matches(
            current_skills=current_skills,
            required_skills=required_skills,
        )
        role_context = await self._build_role_context(target_role=target_role, required_skills=required_skills)
        resume_context_text = self._build_resume_context_text(resume=resume, current_skills=current_skills)
        context_summary = await semantic_service.analyze_context_similarity(
            resume_text=resume_context_text,
            role_text=role_context["text"],
            evidence_sources=role_context["evidence_sources"],
        )
        overall_readiness_score = self._calculate_overall_readiness_score(
            skill_match_score=match_summary.match_score,
            context_similarity_score=context_summary.context_similarity_score,
            semantic_context_ready=context_summary.semantic_context_ready,
        )

        priority_missing_skills = self._prioritize_missing_skills(match_summary.missing_skills)
        # The optimize flow runs its own course selection, so it skips this load
        # to avoid querying the course catalog twice in one request.
        recommendations = (
            await self._recommend_courses_for_missing_skills(priority_missing_skills)
            if include_course_recommendations
            else []
        )
        gap_insights = self._build_gap_insights(
            match_summary=match_summary,
            priority_missing_skills=priority_missing_skills,
            market_signals=market_signals,
            context_summary=context_summary,
        )

        return {
            "status": "ok",
            "resume_id": str(resume.id),
            "target_role": target_role,
            "requirements_source": requirements_source,
            "coverage_ratio": match_summary.coverage_ratio,
            "analysis_version": match_summary.analysis_version,
            "match_score": match_summary.match_score,
            "overall_readiness_score": overall_readiness_score,
            "semantic_score": match_summary.semantic_score,
            "context_similarity_score": context_summary.context_similarity_score,
            "context_match_level": context_summary.context_match_level,
            "semantic_context_ready": context_summary.semantic_context_ready,
            "context_evidence_sources": context_summary.evidence_sources,
            "exact_match_count": match_summary.exact_match_count,
            "semantic_match_count": match_summary.semantic_match_count,
            "weak_match_count": match_summary.weak_match_count,
            "priority_gap_score": match_summary.priority_gap_score,
            "current_skills": current_skills,
            "required_skills": required_skills,
            "matched_required_skills": match_summary.matched_required_skills,
            "semantic_matched_skills": match_summary.semantic_matched_skills,
            "weak_matched_skills": match_summary.weak_matched_skills,
            "missing_skills": match_summary.missing_skills,
            "priority_missing_skills": priority_missing_skills,
            "recommended_courses": recommendations,
            "gap_insights": gap_insights,
            "market_signals": market_signals,
        }

    async def optimize_learning_route(
        self,
        *,
        resume_id: UUID,
        user_id: UUID,
        target_role: str,
        budget: float | None,
        available_hours: float | None,
        max_courses: int | None,
    ) -> dict:
        gap_payload = await self.analyze_gap(
            resume_id=resume_id,
            user_id=user_id,
            target_role=target_role,
            include_course_recommendations=False,
        )
        if gap_payload["status"] != "ok":
            return gap_payload

        constraints = LearningRouteConstraints(
            budget=budget,
            available_hours=available_hours,
            max_courses=max_courses,
        )
        optimizer = get_learning_route_optimizer(self.session)
        route_payload = await optimizer.optimize(
            missing_skills=gap_payload["priority_missing_skills"],
            match_score_before=gap_payload["overall_readiness_score"],
            constraints=constraints,
        )

        optimization_run = OptimizationRunModel(
            user_id=user_id,
            resume_id=resume_id,
            target_role=target_role,
            budget=budget,
            available_hours=available_hours,
            max_courses=max_courses,
            objective_version=route_payload["objective_version"],
            status="completed",
            total_score=route_payload["projected_match_score_after"],
            total_cost=route_payload["total_cost"],
            total_hours=route_payload["total_hours"],
            skill_coverage={
                "match_score_before": route_payload["match_score_before"],
                "skill_match_score_before": gap_payload["match_score"],
                "context_similarity_score": gap_payload["context_similarity_score"],
                "projected_match_score_after": route_payload["projected_match_score_after"],
                "covered_skills": route_payload["covered_skills"],
                "remaining_gaps": route_payload["remaining_gaps"],
                "selected_courses": route_payload["selected_courses"],
                "route_summary": route_payload["route_summary"],
                "solver_status": route_payload.get("solver_status"),
                "objective_value": route_payload.get("objective_value"),
                "model_explanation": route_payload.get("model_explanation"),
            },
            constraints={
                "budget": budget,
                "available_hours": available_hours,
                "max_courses": max_courses,
            },
        )
        self.session.add(optimization_run)
        await self.session.commit()
        await self.session.refresh(optimization_run)

        return {
            "status": "ok",
            "optimization_run_id": str(optimization_run.id),
            "target_role": target_role,
            **route_payload,
        }

    async def evaluate_learning_route_baselines(
        self,
        *,
        resume_id: UUID,
        user_id: UUID,
        target_role: str,
        budget: float | None,
        available_hours: float | None,
        max_courses: int | None,
    ) -> dict:
        gap_payload = await self.analyze_gap(
            resume_id=resume_id,
            user_id=user_id,
            target_role=target_role,
            include_course_recommendations=False,
        )
        if gap_payload["status"] != "ok":
            return gap_payload

        constraints = LearningRouteConstraints(
            budget=budget,
            available_hours=available_hours,
            max_courses=max_courses,
        )
        evaluator = LearningRouteBaselineEvaluationService(self.session)
        evaluation_payload = await evaluator.evaluate(
            missing_skills=gap_payload["priority_missing_skills"],
            match_score_before=gap_payload["overall_readiness_score"],
            constraints=constraints,
        )

        return {
            "status": "ok",
            "resume_id": str(resume_id),
            "target_role": target_role,
            "match_score_before": gap_payload["overall_readiness_score"],
            **evaluation_payload,
        }

    async def list_learning_route_runs(self, *, user_id: UUID, limit: int = 20) -> dict:
        result = await self.session.execute(
            select(OptimizationRunModel)
            .where(OptimizationRunModel.user_id == user_id)
            .order_by(OptimizationRunModel.created_at.desc())
            .limit(max(1, min(limit, 50)))
        )
        runs = result.scalars().all()
        return {"runs": [self._serialize_optimization_run(run) for run in runs]}

    async def _extract_from_resume_summary_if_needed(self, *, resume: ResumeModel, user_id: UUID) -> None:
        existing_result = await self.session.execute(
            select(func.count(ResumeSkillModel.id)).where(ResumeSkillModel.resume_id == resume.id)
        )
        existing_count = int(existing_result.scalar_one() or 0)
        if existing_count or not resume.ai_summary:
            return
        await self.extract_resume_skills_from_text(
            resume_id=resume.id,
            user_id=user_id,
            text=resume.ai_summary,
            extraction_method="resume_summary_rules_v1",
            source_section="ai_summary",
        )

    async def _sync_resume_embedding_if_possible(self, resume: ResumeModel) -> None:
        if not resume.ai_summary:
            return
        embedding_service = ResumeEmbeddingService(self.session)
        await embedding_service.upsert_resume_embedding_from_text(
            resume_id=resume.id,
            text=resume.ai_summary,
        )

    def _build_resume_context_text(self, *, resume: ResumeModel, current_skills: list[dict]) -> str:
        skill_lines = [
            f"{skill['display_name']}: {skill.get('evidence_text') or skill['normalized_name']}"
            for skill in current_skills
        ]
        fields = [
            resume.ai_summary,
            "Extracted resume skills:",
            "\n".join(skill_lines),
        ]
        return "\n".join(field for field in fields if field and field.strip())

    async def _build_role_context(self, *, target_role: str, required_skills: list[dict]) -> dict:
        required_skill_lines = [
            (
                f"{skill['display_name']} "
                f"(importance {float(skill.get('importance_score') or 0.75):.2f}): "
                f"{skill.get('evidence_text') or skill['normalized_name']}"
            )
            for skill in required_skills
        ]
        evidence_sources = ["role_required_skills"]

        job_texts = await self._get_role_job_posting_context(target_role=target_role, limit=5)
        if job_texts:
            evidence_sources.append("job_postings")
        else:
            evidence_sources.append("role_seed")

        fields = [
            f"Target role: {target_role}",
            "Required skills:",
            "\n".join(required_skill_lines),
            "Market job posting context:",
            "\n\n".join(job_texts),
        ]
        return {
            "text": "\n".join(field for field in fields if field and field.strip()),
            "evidence_sources": evidence_sources,
        }

    async def _get_role_job_posting_context(self, *, target_role: str, limit: int = 5) -> list[str]:
        result = await self.session.execute(
            select(JobPosting)
            .join(JobSkillModel, JobSkillModel.job_posting_id == JobPosting.id)
            .where(
                func.lower(JobSkillModel.target_role) == target_role.lower(),
                JobPosting.is_active.is_(True),
            )
            .order_by(JobPosting.created_at.desc())
            .limit(max(1, min(limit, 20)))
        )
        job_postings = result.scalars().unique().all()
        return [
            self._job_posting_text(job_posting)
            for job_posting in job_postings
            if self._job_posting_text(job_posting).strip()
        ]

    @staticmethod
    def _calculate_overall_readiness_score(
        *,
        skill_match_score: float,
        context_similarity_score: float,
        semantic_context_ready: bool,
    ) -> float:
        if not semantic_context_ready:
            return round(skill_match_score, 4)
        return round(max(0.0, min(skill_match_score * 0.8 + context_similarity_score * 0.2, 1.0)), 4)

    @staticmethod
    def _job_posting_text(job_posting: JobPosting) -> str:
        fields = [
            job_posting.title,
            job_posting.description,
            job_posting.requirements,
            job_posting.responsibilities,
            job_posting.benefits,
            job_posting.listed_context,
            job_posting.source_context,
        ]
        return "\n".join(field for field in fields if field)

    @staticmethod
    def _infer_target_role(title: str | None) -> str | None:
        normalized_title = (title or "").lower()
        if "business analyst" in normalized_title:
            return "Business Analyst"
        if "data scientist" in normalized_title:
            return "Junior Data Scientist"
        if "data analyst" in normalized_title:
            return "Data Analyst"
        return None

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

    async def _get_role_market_signals(self, *, target_role: str, required_skills: list[dict]) -> dict:
        required_by_id = {skill["skill_id"]: skill for skill in required_skills}
        if not required_by_id:
            return {
                "target_role": target_role,
                "source": "none",
                "synced_job_postings_count": 0,
                "skills": [],
            }

        total_jobs_result = await self.session.execute(
            select(func.count(func.distinct(JobSkillModel.job_posting_id))).where(
                func.lower(JobSkillModel.target_role) == target_role.lower(),
                JobSkillModel.job_posting_id.is_not(None),
            )
        )
        synced_job_postings_count = int(total_jobs_result.scalar_one() or 0)

        skill_counts_result = await self.session.execute(
            select(
                JobSkillModel.skill_id,
                func.count(func.distinct(JobSkillModel.job_posting_id)),
            )
            .where(
                func.lower(JobSkillModel.target_role) == target_role.lower(),
                JobSkillModel.job_posting_id.is_not(None),
            )
            .group_by(JobSkillModel.skill_id)
        )
        demand_counts = {
            str(skill_id): int(count or 0)
            for skill_id, count in skill_counts_result.all()
        }

        skills = []
        for skill_id, skill in required_by_id.items():
            demand_count = demand_counts.get(skill_id, 0)
            demand_score = demand_count / synced_job_postings_count if synced_job_postings_count else 0.0
            skills.append(
                {
                    "skill_id": skill_id,
                    "normalized_name": skill["normalized_name"],
                    "display_name": skill["display_name"],
                    "job_posting_count": demand_count,
                    "demand_score": round(demand_score, 4),
                }
            )

        return {
            "target_role": target_role,
            "source": "job_postings" if synced_job_postings_count else "role_seed",
            "synced_job_postings_count": synced_job_postings_count,
            "skills": sorted(skills, key=lambda item: (-item["demand_score"], item["display_name"].lower())),
        }

    @staticmethod
    def _attach_market_signals(*, required_skills: list[dict], market_signals: dict) -> list[dict]:
        market_by_skill_id = {
            skill["skill_id"]: skill
            for skill in market_signals.get("skills", [])
        }
        enriched = []
        for skill in required_skills:
            market_skill = market_by_skill_id.get(skill["skill_id"], {})
            enriched.append(
                {
                    **skill,
                    "market_demand_count": int(market_skill.get("job_posting_count") or 0),
                    "market_demand_score": float(market_skill.get("demand_score") or 0.0),
                }
            )
        return enriched

    @staticmethod
    def _prioritize_missing_skills(missing_skills: list[dict]) -> list[dict]:
        return SkillGapScoringService.prioritize_missing_skills(missing_skills)

    @staticmethod
    def _build_gap_insights(
        *,
        match_summary,
        priority_missing_skills: list[dict],
        market_signals: dict,
        context_summary,
    ) -> list[dict]:
        insights = []
        match_score = match_summary.match_score
        if match_score >= 0.75:
            insights.append(
                {
                    "insight_type": "readiness",
                    "severity": "positive",
                    "message": "The resume is close to the target role; focus on the highest-priority remaining gaps.",
                }
            )
        elif match_score >= 0.45:
            insights.append(
                {
                    "insight_type": "readiness",
                    "severity": "medium",
                    "message": "The resume has a partial fit; a focused learning route can materially improve readiness.",
                }
            )
        else:
            insights.append(
                {
                    "insight_type": "readiness",
                    "severity": "high",
                    "message": "The resume is early for this target role; prioritize foundational missing skills first.",
                }
            )

        if priority_missing_skills:
            top_gap = priority_missing_skills[0]
            insights.append(
                {
                    "insight_type": "priority_gap",
                    "severity": "high",
                    "skill_id": top_gap["skill_id"],
                    "skill_name": top_gap["display_name"],
                    "message": top_gap["reason"],
                }
            )

        if match_summary.semantic_match_count:
            insights.append(
                {
                    "insight_type": "transferable_skill",
                    "severity": "positive",
                    "message": (
                        f"{match_summary.semantic_match_count} required skill(s) were matched through semantic similarity."
                    ),
                }
            )

        if context_summary.semantic_context_ready:
            insights.append(
                {
                    "insight_type": "context_similarity",
                    "severity": "info" if context_summary.context_match_level != "weak" else "medium",
                    "message": context_summary.message,
                }
            )

        if market_signals.get("synced_job_postings_count"):
            insights.append(
                {
                    "insight_type": "market_signal",
                    "severity": "info",
                    "message": (
                        "Priority uses synced job-posting demand in addition to the role skill importance score."
                    ),
                }
            )
        return insights

    @staticmethod
    def _serialize_optimization_run(run: OptimizationRunModel) -> dict:
        skill_coverage = run.skill_coverage or {}
        selected_courses = skill_coverage.get("selected_courses") or []
        covered_skills = skill_coverage.get("covered_skills") or []
        remaining_gaps = skill_coverage.get("remaining_gaps") or []
        return {
            "optimization_run_id": str(run.id),
            "resume_id": str(run.resume_id) if run.resume_id else None,
            "target_role": run.target_role,
            "objective_version": run.objective_version,
            "status": run.status,
            "match_score_before": skill_coverage.get("match_score_before"),
            "projected_match_score_after": skill_coverage.get("projected_match_score_after") or run.total_score,
            "total_cost": run.total_cost,
            "total_hours": run.total_hours,
            "budget": run.budget,
            "available_hours": run.available_hours,
            "max_courses": run.max_courses,
            "selected_courses_count": len(selected_courses),
            "covered_skills_count": len(covered_skills),
            "remaining_gaps_count": len(remaining_gaps),
            "route_summary": skill_coverage.get("route_summary"),
            "solver_status": skill_coverage.get("solver_status"),
            "objective_value": skill_coverage.get("objective_value"),
            "created_at": run.created_at,
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

    async def _get_role_required_skills(self, target_role: str) -> list[dict]:
        real_skills = await self._get_role_required_skill_rows(
            target_role=target_role,
            require_real_job_posting=True,
        )
        if real_skills:
            return self._serialize_required_skills(real_skills, source_type="job_postings")

        seed_skills = await self._get_role_required_skill_rows(
            target_role=target_role,
            require_real_job_posting=False,
        )
        return self._serialize_required_skills(seed_skills, source_type="role_seed")

    async def _get_role_required_skill_rows(
        self,
        *,
        target_role: str,
        require_real_job_posting: bool,
    ) -> list[JobSkillModel]:
        job_posting_filter = (
            JobSkillModel.job_posting_id.is_not(None)
            if require_real_job_posting
            else JobSkillModel.job_posting_id.is_(None)
        )
        result = await self.session.execute(
            select(JobSkillModel)
            .options(selectinload(JobSkillModel.skill))
            .where(
                func.lower(JobSkillModel.target_role) == target_role.lower(),
                job_posting_filter,
            )
        )
        return list(result.scalars().all())

    @staticmethod
    def _serialize_required_skills(role_skills: list[JobSkillModel], *, source_type: str) -> list[dict]:
        best_by_skill: dict[UUID, JobSkillModel] = {}
        for job_skill in role_skills:
            current = best_by_skill.get(job_skill.skill_id)
            if current is None or (job_skill.importance_score or 0) > (current.importance_score or 0):
                best_by_skill[job_skill.skill_id] = job_skill

        return [
            {
                "skill_id": str(job_skill.skill_id),
                "normalized_name": job_skill.skill.normalized_name,
                "display_name": job_skill.skill.display_name,
                "category": job_skill.skill.category,
                "importance_score": job_skill.importance_score,
                "evidence_text": job_skill.evidence_text,
                "extraction_method": job_skill.extraction_method,
                "source_type": source_type,
            }
            for job_skill in sorted(
                best_by_skill.values(),
                key=lambda item: (-(item.importance_score or 0), item.skill.display_name.lower()),
            )
        ]

    async def _recommend_courses_for_missing_skills(self, missing_skills: list[dict]) -> list[dict]:
        missing_skill_ids = [skill["skill_id"] for skill in missing_skills]
        missing_by_id = {skill["skill_id"]: skill for skill in missing_skills}
        course_links = await load_active_course_links(self.session, missing_skill_ids)

        recommendations = []
        for course, links in course_links:
            skills_covered = []
            recommendation_score = 0.0
            for link in links:
                coverage_score = link.coverage_score if link.coverage_score is not None else 0.5
                gap_weight = float(
                    missing_by_id.get(str(link.skill_id), {}).get("skill_gap_score")
                    or missing_by_id.get(str(link.skill_id), {}).get("priority_score")
                    or missing_by_id.get(str(link.skill_id), {}).get("importance_score")
                    or 0.75
                )
                recommendation_score += coverage_score * gap_weight
                skills_covered.append(
                    {
                        "skill_id": str(link.skill_id),
                        "normalized_name": link.skill.normalized_name,
                        "display_name": link.skill.display_name,
                        "coverage_score": coverage_score,
                    }
                )
            skills_covered.sort(key=lambda skill: skill["display_name"].lower())
            recommendations.append(
                {
                    "course_id": str(course.id),
                    "title": course.title,
                    "provider": course.provider,
                    "url": course.url,
                    "cost": course.cost,
                    "currency": course.currency,
                    "duration_hours": course.duration_hours,
                    "difficulty": course.difficulty,
                    "rating": course.rating,
                    "skills_covered": skills_covered,
                    "recommendation_score": round(recommendation_score, 4),
                }
            )

        recommendations.sort(
            key=lambda course: (
                -course["recommendation_score"],
                course["duration_hours"] if course["duration_hours"] is not None else 10**9,
                course["title"].lower(),
            )
        )
        return recommendations[:10]
