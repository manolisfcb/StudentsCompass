"""Gap analysis and learning-route optimisation: the coordinator.

Split out of ``CapstoneAnalyticsService`` by TASK-023. This is the part that
*composes* the others — it reads the CV's skills, the role's requirements and the
market signals, hands them to the semantic matcher and the route optimiser, and
records the run. It owns none of those; it decides the order and shape of the
answer.

Weights, heuristics, thresholds and the historical snapshots are untouched by
that split: this module moved code, it did not re-derive any of it.
"""
from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.jobPostingModel import JobPosting
from app.models.resumeModel import ResumeModel
from app.models.skillModel import (
    JobSkillModel,
    OptimizationRunModel,
    ResumeSkillModel,
)
from app.services.analytics.courseCatalogQueries import load_active_course_links
from app.services.analytics.embeddingService import ResumeEmbeddingService
from app.services.analytics.jobPostingText import job_posting_text
from app.services.analytics.learningRouteBaselineEvaluationService import (
    LearningRouteBaselineEvaluationService,
)
from app.services.analytics.learningRouteOptimizerService import (
    LearningRouteConstraints,
    get_learning_route_optimizer,
)
from app.services.analytics.resumeSkillExtractionService import ResumeSkillExtractionService
from app.services.analytics.resumeSkillReviewService import ResumeSkillReviewService
from app.services.analytics.semanticMatchingService import SemanticMatchingService
from app.services.analytics.skillGapScoringService import SkillGapScoringService

LOGGER = logging.getLogger(__name__)


class CapstoneGapService:
    """What a CV is missing for a role, and the cheapest route to close it."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        review: ResumeSkillReviewService | None = None,
        extraction: ResumeSkillExtractionService | None = None,
    ):
        self.session = session
        self.review = review or ResumeSkillReviewService(session)
        self.extraction = extraction or ResumeSkillExtractionService(session, review=self.review)

    async def analyze_gap(
        self,
        *,
        resume_id: UUID,
        user_id: UUID,
        target_role: str,
        include_course_recommendations: bool = True,
    ) -> dict:
        resume = await self.review.get_user_resume(resume_id=resume_id, user_id=user_id)
        if resume is None:
            return {"status": "resume_not_found", "resume_id": str(resume_id)}

        await self.extraction._extract_from_resume_summary_if_needed(resume=resume, user_id=user_id)
        await self._sync_resume_embedding_if_possible(resume)

        current_skills = await self.review.get_resume_skills(resume.id)
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
            job_posting_text(job_posting)
            for job_posting in job_postings
            if job_posting_text(job_posting).strip()
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
