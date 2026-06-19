from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
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
    ResumeSkillModel,
    SkillAliasModel,
    SkillModel,
)
from app.services.analytics.embeddingService import ResumeEmbeddingService, get_embedding_status
from app.services.analytics.capstoneAnalyticsSeedService import CAPSTONE_ROLE_SKILL_SEED_DATA


@dataclass(frozen=True)
class SkillMatch:
    skill: SkillModel
    matched_text: str


class CapstoneAnalyticsService:
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def normalize_skill_text(value: str) -> str:
        cleaned = re.sub(r"[^a-z0-9+#]+", " ", (value or "").lower()).strip()
        return re.sub(r"\s+", " ", cleaned)

    async def build_skill_lookup(self) -> dict[str, SkillModel]:
        skills_result = await self.session.execute(select(SkillModel))
        skills = list(skills_result.scalars().all())

        aliases_result = await self.session.execute(
            select(SkillAliasModel).options(selectinload(SkillAliasModel.skill))
        )
        aliases = list(aliases_result.scalars().all())

        lookup: dict[str, SkillModel] = {}
        for skill in skills:
            lookup[self.normalize_skill_text(skill.normalized_name.replace("_", " "))] = skill
            lookup[self.normalize_skill_text(skill.display_name)] = skill
        for alias in aliases:
            lookup[self.normalize_skill_text(alias.alias)] = alias.skill
        return lookup

    async def extract_known_skills_from_text(self, text: str) -> list[SkillMatch]:
        lookup = await self.build_skill_lookup()
        normalized_text = f" {self.normalize_skill_text(text)} "

        matches_by_skill: dict[UUID, SkillMatch] = {}
        for candidate, skill in sorted(lookup.items(), key=lambda item: len(item[0]), reverse=True):
            if f" {candidate} " not in normalized_text:
                continue
            matches_by_skill.setdefault(
                skill.id,
                SkillMatch(skill=skill, matched_text=candidate),
            )

        return sorted(matches_by_skill.values(), key=lambda match: match.skill.display_name.lower())

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

        matches = await self.extract_known_skills_from_text(text)
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
                confidence_score=0.75,
                extraction_method=extraction_method,
                evidence_text=match.matched_text,
                source_section=source_section,
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
    ) -> list[JobSkillModel]:
        job_posting = await self.session.get(JobPosting, job_posting_id)
        if job_posting is None:
            return []

        text = self._job_posting_text(job_posting)
        if not text.strip():
            return []

        matches = await self.extract_known_skills_from_text(text)
        created_or_existing: list[JobSkillModel] = []
        target_role = self._infer_target_role(job_posting.title)

        for match in matches:
            existing_result = await self.session.execute(
                select(JobSkillModel).where(
                    JobSkillModel.job_posting_id == job_posting.id,
                    JobSkillModel.skill_id == match.skill.id,
                    JobSkillModel.extraction_method == extraction_method,
                )
            )
            existing = existing_result.scalar_one_or_none()
            if existing:
                created_or_existing.append(existing)
                continue

            job_skill = JobSkillModel(
                job_posting_id=job_posting.id,
                skill_id=match.skill.id,
                target_role=target_role,
                importance_score=0.75,
                extraction_method=extraction_method,
                evidence_text=match.matched_text,
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

        total_links = 0
        jobs_with_matches = 0
        for job in jobs:
            links = await self.extract_job_skills_from_job_posting(job_posting_id=job.id)
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

    async def analyze_gap(self, *, resume_id: UUID, user_id: UUID, target_role: str) -> dict:
        resume = await self.get_user_resume(resume_id=resume_id, user_id=user_id)
        if resume is None:
            return {"status": "resume_not_found", "resume_id": str(resume_id)}

        await self._extract_from_resume_summary_if_needed(resume=resume, user_id=user_id)
        await self._sync_resume_embedding_if_possible(resume)

        current_skills = await self.get_resume_skills(resume.id)
        required_skills = await self._get_role_required_skills(target_role)
        requirements_source = required_skills[0]["source_type"] if required_skills else "none"

        current_ids = {skill["skill_id"] for skill in current_skills}
        missing_skills = [skill for skill in required_skills if skill["skill_id"] not in current_ids]
        matched_required_skills = [skill for skill in required_skills if skill["skill_id"] in current_ids]

        recommendations = await self._recommend_courses_for_missing_skills(missing_skills)
        coverage_ratio = len(matched_required_skills) / len(required_skills) if required_skills else 0.0

        return {
            "status": "ok",
            "resume_id": str(resume.id),
            "target_role": target_role,
            "requirements_source": requirements_source,
            "coverage_ratio": round(coverage_ratio, 4),
            "current_skills": current_skills,
            "required_skills": required_skills,
            "matched_required_skills": matched_required_skills,
            "missing_skills": missing_skills,
            "recommended_courses": recommendations,
        }

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

    async def get_resume_skills(self, resume_id: UUID) -> list[dict]:
        result = await self.session.execute(
            select(ResumeSkillModel)
            .options(selectinload(ResumeSkillModel.skill))
            .where(ResumeSkillModel.resume_id == resume_id)
        )
        resume_skills = result.scalars().all()
        return [
            {
                "skill_id": str(resume_skill.skill_id),
                "normalized_name": resume_skill.skill.normalized_name,
                "display_name": resume_skill.skill.display_name,
                "category": resume_skill.skill.category,
                "confidence_score": resume_skill.confidence_score,
                "evidence_text": resume_skill.evidence_text,
                "extraction_method": resume_skill.extraction_method,
            }
            for resume_skill in sorted(resume_skills, key=lambda item: item.skill.display_name.lower())
        ]

    async def _count(self, model) -> int:
        result = await self.session.execute(select(func.count(model.id)))
        return int(result.scalar_one() or 0)

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
        if not missing_skill_ids:
            return []

        result = await self.session.execute(
            select(CourseSkillModel)
            .options(
                selectinload(CourseSkillModel.course),
                selectinload(CourseSkillModel.skill),
            )
            .where(CourseSkillModel.skill_id.in_([UUID(skill_id) for skill_id in missing_skill_ids]))
        )
        course_skill_links = result.scalars().all()

        courses: dict[UUID, dict] = {}
        scores: dict[UUID, float] = defaultdict(float)
        for link in course_skill_links:
            course = link.course
            if not course.is_active:
                continue
            course_payload = courses.setdefault(
                course.id,
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
                    "skills_covered": [],
                },
            )
            coverage_score = link.coverage_score if link.coverage_score is not None else 0.5
            scores[course.id] += coverage_score
            course_payload["skills_covered"].append(
                {
                    "skill_id": str(link.skill_id),
                    "normalized_name": link.skill.normalized_name,
                    "display_name": link.skill.display_name,
                    "coverage_score": coverage_score,
                }
            )

        recommendations = []
        for course_id, payload in courses.items():
            payload["recommendation_score"] = round(scores[course_id], 4)
            payload["skills_covered"].sort(key=lambda skill: skill["display_name"].lower())
            recommendations.append(payload)

        recommendations.sort(
            key=lambda course: (
                -course["recommendation_score"],
                course["duration_hours"] if course["duration_hours"] is not None else 10**9,
                course["title"].lower(),
            )
        )
        return recommendations[:10]
