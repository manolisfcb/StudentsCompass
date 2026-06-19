from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.analytics.courseCatalogQueries import load_active_course_links


OBJECTIVE_VERSION_HEURISTIC = "heuristic_route_v1"


@dataclass(frozen=True)
class LearningRouteConstraints:
    budget: float | None = None
    available_hours: float | None = None
    max_courses: int | None = None


class LearningRouteOptimizer(Protocol):
    async def optimize(
        self,
        *,
        missing_skills: list[dict],
        match_score_before: float,
        constraints: LearningRouteConstraints,
    ) -> dict:
        ...


class HeuristicLearningRouteOptimizer:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def optimize(
        self,
        *,
        missing_skills: list[dict],
        match_score_before: float,
        constraints: LearningRouteConstraints,
    ) -> dict:
        missing_by_id = {skill["skill_id"]: skill for skill in missing_skills}
        if not missing_by_id:
            return self._empty_result(match_score_before=match_score_before)

        candidates = await self._load_course_candidates(missing_skill_ids=list(missing_by_id))
        selected_courses = self._select_courses(
            candidates=candidates,
            missing_by_id=missing_by_id,
            constraints=constraints,
        )
        selected_courses = self._sequence_selected_courses(
            selected_courses,
            missing_by_id=missing_by_id,
        )

        covered_skill_ids = {
            skill["skill_id"]
            for course in selected_courses
            for skill in course["skills_covered"]
        }
        covered_skills = [
            missing_by_id[skill_id]
            for skill_id in sorted(covered_skill_ids)
            if skill_id in missing_by_id
        ]
        remaining_gaps = [
            skill
            for skill_id, skill in missing_by_id.items()
            if skill_id not in covered_skill_ids
        ]
        total_cost = round(sum(float(course["cost"] or 0) for course in selected_courses), 2)
        total_hours = round(sum(float(course["duration_hours"] or 0) for course in selected_courses), 2)
        projected_score = self._project_match_score(
            match_score_before=match_score_before,
            missing_skills=list(missing_by_id.values()),
            covered_skills=covered_skills,
        )

        return {
            "objective_version": OBJECTIVE_VERSION_HEURISTIC,
            "match_score_before": round(match_score_before, 4),
            "projected_match_score_after": projected_score,
            "total_cost": total_cost,
            "total_hours": total_hours,
            "selected_courses": selected_courses,
            "covered_skills": covered_skills,
            "remaining_gaps": remaining_gaps,
            "route_summary": self._build_route_summary(
                selected_courses=selected_courses,
                covered_skills=covered_skills,
                remaining_gaps=remaining_gaps,
            ),
        }

    async def _load_course_candidates(self, *, missing_skill_ids: list[str]) -> list[dict]:
        course_links = await load_active_course_links(self.session, missing_skill_ids)

        candidates = []
        for course, links in course_links:
            candidates.append(
                {
                    "course_id": str(course.id),
                    "title": course.title,
                    "provider": course.provider,
                    "url": course.url,
                    "cost": float(course.cost or 0),
                    "currency": course.currency,
                    "duration_hours": float(course.duration_hours or 0),
                    "difficulty": course.difficulty,
                    "rating": course.rating,
                    "skills_covered": [
                        {
                            "skill_id": str(link.skill_id),
                            "normalized_name": link.skill.normalized_name,
                            "display_name": link.skill.display_name,
                            "coverage_score": float(
                                link.coverage_score if link.coverage_score is not None else 0.5
                            ),
                            "is_prerequisite": bool(link.is_prerequisite),
                        }
                        for link in links
                    ],
                }
            )

        return candidates

    def _select_courses(
        self,
        *,
        candidates: list[dict],
        missing_by_id: dict[str, dict],
        constraints: LearningRouteConstraints,
    ) -> list[dict]:
        max_courses = constraints.max_courses if constraints.max_courses is not None else 5
        max_budget = constraints.budget if constraints.budget is not None else float("inf")
        max_hours = constraints.available_hours if constraints.available_hours is not None else float("inf")

        # _dedupe_equivalent_courses already returns scored courses, so reuse
        # them directly instead of re-running _score_course on each one.
        scored = self._dedupe_equivalent_courses(candidates, missing_by_id)
        scored.sort(
            key=lambda course: (
                -course["optimization_score"],
                course["cost"],
                course["duration_hours"],
                course["title"].lower(),
            )
        )

        selected = []
        covered_skill_ids: set[str] = set()
        total_cost = 0.0
        total_hours = 0.0

        for course in scored:
            if len(selected) >= max_courses:
                break
            cost = float(course["cost"] or 0)
            hours = float(course["duration_hours"] or 0)
            if total_cost + cost > max_budget:
                continue
            if total_hours + hours > max_hours:
                continue
            new_skill_ids = {
                skill["skill_id"]
                for skill in course["skills_covered"]
                if skill["skill_id"] not in covered_skill_ids
            }
            if not new_skill_ids:
                continue
            selected.append(course)
            covered_skill_ids.update(new_skill_ids)
            total_cost += cost
            total_hours += hours

        return selected

    def _dedupe_equivalent_courses(self, candidates: list[dict], missing_by_id: dict[str, dict]) -> list[dict]:
        best_by_skill_set: dict[tuple[str, ...], dict] = {}
        for course in candidates:
            skill_set = tuple(sorted(skill["skill_id"] for skill in course["skills_covered"]))
            scored_course = self._score_course(course, missing_by_id=missing_by_id)
            current = best_by_skill_set.get(skill_set)
            if current is None or (
                scored_course["optimization_score"],
                -scored_course["cost"],
                -scored_course["duration_hours"],
            ) > (
                current["optimization_score"],
                -current["cost"],
                -current["duration_hours"],
            ):
                best_by_skill_set[skill_set] = scored_course
        return list(best_by_skill_set.values())

    def _score_course(self, course: dict, *, missing_by_id: dict[str, dict]) -> dict:
        coverage_value = 0.0
        for covered_skill in course["skills_covered"]:
            missing_skill = missing_by_id.get(covered_skill["skill_id"])
            if not missing_skill:
                continue
            importance = float(missing_skill.get("importance_score") or 0.75)
            coverage_value += importance * float(covered_skill.get("coverage_score") or 0.5)

        rating_bonus = float(course.get("rating") or 0) / 5.0 * 0.08
        difficulty_bonus = self._difficulty_bonus(course.get("difficulty"))
        cost_penalty = min(float(course["cost"] or 0) / 500.0, 0.4)
        hours_penalty = min(float(course["duration_hours"] or 0) / 120.0, 0.35)
        optimization_score = max(0.0, coverage_value + rating_bonus + difficulty_bonus - cost_penalty - hours_penalty)

        return {
            **course,
            "optimization_score": round(optimization_score, 4),
        }

    def _sequence_selected_courses(self, selected_courses: list[dict], *, missing_by_id: dict[str, dict]) -> list[dict]:
        sequenced = [
            self._add_selection_context(course, missing_by_id=missing_by_id)
            for course in selected_courses
        ]
        sequenced.sort(
            key=lambda course: (
                -course["prerequisite_skill_count"],
                self._difficulty_rank(course.get("difficulty")),
                -course["optimization_score"],
                course["duration_hours"],
                course["title"].lower(),
            )
        )

        for index, course in enumerate(sequenced, start=1):
            course["sequence_order"] = index
            course.pop("prerequisite_skill_count", None)
        return sequenced

    def _add_selection_context(self, course: dict, *, missing_by_id: dict[str, dict]) -> dict:
        covered_missing_skills = [
            {
                **skill,
                "importance_score": float(
                    missing_by_id.get(skill["skill_id"], {}).get("importance_score") or 0.75
                ),
            }
            for skill in course["skills_covered"]
            if skill["skill_id"] in missing_by_id
        ]
        covered_missing_skills.sort(
            key=lambda skill: (
                -skill["importance_score"],
                -float(skill.get("coverage_score") or 0),
                skill["display_name"].lower(),
            )
        )
        priority_names = [skill["display_name"] for skill in covered_missing_skills[:3]]
        if priority_names:
            selection_reason = "Selected because it covers priority gaps: " + ", ".join(priority_names) + "."
        else:
            selection_reason = "Selected because it improves the learning route under the current constraints."

        return {
            **course,
            "covered_priority_skills": priority_names,
            "selection_reason": selection_reason,
            "prerequisite_skill_count": sum(1 for skill in course["skills_covered"] if skill.get("is_prerequisite")),
        }

    @staticmethod
    def _difficulty_rank(difficulty: str | None) -> int:
        normalized = (difficulty or "").lower()
        if normalized == "beginner":
            return 0
        if normalized == "intermediate":
            return 1
        if normalized == "advanced":
            return 2
        return 3

    @staticmethod
    def _build_route_summary(
        *,
        selected_courses: list[dict],
        covered_skills: list[dict],
        remaining_gaps: list[dict],
    ) -> str:
        if not selected_courses:
            if remaining_gaps:
                return "No route fits the current catalog and constraints; the remaining gaps are preserved."
            return "No route is needed because there are no uncovered required skills."

        course_count = len(selected_courses)
        covered_count = len(covered_skills)
        remaining_count = len(remaining_gaps)
        return (
            f"Selected {course_count} course(s) covering {covered_count} priority gap(s), "
            f"with {remaining_count} gap(s) still remaining."
        )

    @staticmethod
    def _difficulty_bonus(difficulty: str | None) -> float:
        normalized = (difficulty or "").lower()
        if normalized == "beginner":
            return 0.08
        if normalized == "intermediate":
            return 0.04
        if normalized == "advanced":
            return 0.01
        return 0.0

    @staticmethod
    def _project_match_score(
        *,
        match_score_before: float,
        missing_skills: list[dict],
        covered_skills: list[dict],
    ) -> float:
        total_missing_importance = sum(float(skill.get("importance_score") or 0.75) for skill in missing_skills)
        covered_importance = sum(float(skill.get("importance_score") or 0.75) for skill in covered_skills)
        if total_missing_importance <= 0:
            return round(match_score_before, 4)
        remaining_gap = 1.0 - match_score_before
        projected_gain = remaining_gap * (covered_importance / total_missing_importance)
        return round(max(0.0, min(match_score_before + projected_gain, 1.0)), 4)

    @staticmethod
    def _empty_result(*, match_score_before: float) -> dict:
        return {
            "objective_version": OBJECTIVE_VERSION_HEURISTIC,
            "match_score_before": round(match_score_before, 4),
            "projected_match_score_after": round(match_score_before, 4),
            "total_cost": 0.0,
            "total_hours": 0.0,
            "selected_courses": [],
            "covered_skills": [],
            "remaining_gaps": [],
            "route_summary": "No learning route was selected because there are no uncovered skills to optimize.",
        }


class ORToolsLearningRouteOptimizer:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def optimize(self, **kwargs) -> dict:
        raise NotImplementedError("OR-Tools optimization is reserved for a future optional backend.")
