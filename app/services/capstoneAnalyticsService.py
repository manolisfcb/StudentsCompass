from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.resumeModel import ResumeModel
from app.models.skillModel import (
    CourseModel,
    CourseSkillModel,
    JobSkillModel,
    ResumeSkillModel,
    SkillAliasModel,
    SkillModel,
)


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

    async def get_user_resume(self, *, resume_id: UUID, user_id: UUID) -> ResumeModel | None:
        result = await self.session.execute(
            select(ResumeModel).where(
                ResumeModel.id == resume_id,
                ResumeModel.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def analyze_gap(self, *, resume_id: UUID, user_id: UUID, target_role: str) -> dict:
        resume = await self.get_user_resume(resume_id=resume_id, user_id=user_id)
        if resume is None:
            return {"status": "resume_not_found", "resume_id": str(resume_id)}

        await self._extract_from_resume_summary_if_needed(resume=resume, user_id=user_id)

        current_skills = await self.get_resume_skills(resume.id)
        required_skills = await self._get_role_required_skills(target_role)

        current_ids = {skill["skill_id"] for skill in current_skills}
        missing_skills = [skill for skill in required_skills if skill["skill_id"] not in current_ids]
        matched_required_skills = [skill for skill in required_skills if skill["skill_id"] in current_ids]

        recommendations = await self._recommend_courses_for_missing_skills(missing_skills)
        coverage_ratio = len(matched_required_skills) / len(required_skills) if required_skills else 0.0

        return {
            "status": "ok",
            "resume_id": str(resume.id),
            "target_role": target_role,
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

    async def _get_role_required_skills(self, target_role: str) -> list[dict]:
        result = await self.session.execute(
            select(JobSkillModel)
            .options(selectinload(JobSkillModel.skill))
            .where(func.lower(JobSkillModel.target_role) == target_role.lower())
        )
        role_skills = result.scalars().all()
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
            for job_skill in sorted(
                role_skills,
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
