from __future__ import annotations

import random
from time import perf_counter

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.analytics.learningRouteOptimizerService import (
    OBJECTIVE_VERSION_CP_SAT,
    OBJECTIVE_VERSION_HEURISTIC,
    HeuristicLearningRouteOptimizer,
    LearningRouteConstraints,
    ORToolsLearningRouteOptimizer,
)


PHASE_7_EVALUATION_VERSION = "phase_7_baseline_eval_v1"
BASELINE_RANDOM_SEED = 42


class LearningRouteBaselineEvaluationService:
    """Compare CP-SAT route selection against deterministic baseline methods."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.heuristic = HeuristicLearningRouteOptimizer(session)

    async def evaluate(
        self,
        *,
        missing_skills: list[dict],
        match_score_before: float,
        constraints: LearningRouteConstraints,
    ) -> dict:
        missing_by_id = {skill["skill_id"]: skill for skill in missing_skills}
        candidates = await self.heuristic._load_course_candidates(missing_skill_ids=list(missing_by_id))
        scored_candidates = self.heuristic._dedupe_equivalent_courses(candidates, missing_by_id)
        return self.evaluate_candidates(
            candidates=scored_candidates,
            missing_skills=missing_skills,
            match_score_before=match_score_before,
            constraints=constraints,
        )

    def evaluate_candidates(
        self,
        *,
        candidates: list[dict],
        missing_skills: list[dict],
        match_score_before: float,
        constraints: LearningRouteConstraints,
    ) -> dict:
        missing_by_id = {skill["skill_id"]: skill for skill in missing_skills}
        method_results = [
            self._time_method(
                method="cheapest_feasible",
                objective_version="baseline_cheapest_feasible_v1",
                match_score_before=match_score_before,
                runner=lambda: self._select_greedy(
                    candidates=candidates,
                    missing_by_id=missing_by_id,
                    constraints=constraints,
                    sort_key=lambda course: (
                        float(course.get("cost") or 0),
                        float(course.get("duration_hours") or 0),
                        -self._course_coverage_value(course, missing_by_id),
                        course["title"].lower(),
                    ),
                ),
            ),
            self._time_method(
                method="highest_rated_feasible",
                objective_version="baseline_highest_rated_feasible_v1",
                match_score_before=match_score_before,
                runner=lambda: self._select_greedy(
                    candidates=candidates,
                    missing_by_id=missing_by_id,
                    constraints=constraints,
                    sort_key=lambda course: (
                        -float(course.get("rating") or 0),
                        float(course.get("cost") or 0),
                        -self._course_coverage_value(course, missing_by_id),
                        course["title"].lower(),
                    ),
                ),
            ),
            self._time_method(
                method="similarity_only",
                objective_version="baseline_similarity_only_v1",
                match_score_before=match_score_before,
                runner=lambda: self._select_greedy(
                    candidates=candidates,
                    missing_by_id=missing_by_id,
                    constraints=constraints,
                    sort_key=lambda course: (
                        -self._course_coverage_value(course, missing_by_id),
                        -self._course_average_coverage(course),
                        course["title"].lower(),
                    ),
                ),
            ),
            self._time_method(
                method="heuristic_route_v1",
                objective_version=OBJECTIVE_VERSION_HEURISTIC,
                match_score_before=match_score_before,
                runner=lambda: (
                    self.heuristic._select_courses(
                        candidates=candidates,
                        missing_by_id=missing_by_id,
                        constraints=constraints,
                    ),
                    self._metadata(missing_by_id=missing_by_id, constraints=constraints),
                ),
            ),
            self._time_method(
                method="random_feasible_seeded",
                objective_version="baseline_random_feasible_seeded_v1",
                match_score_before=match_score_before,
                runner=lambda: self._select_random_feasible(
                    candidates=candidates,
                    missing_by_id=missing_by_id,
                    constraints=constraints,
                ),
            ),
            self._time_method(
                method="cp_sat_route_v1",
                objective_version=OBJECTIVE_VERSION_CP_SAT,
                match_score_before=match_score_before,
                runner=lambda: self._select_cp_sat(
                    candidates=candidates,
                    missing_by_id=missing_by_id,
                    constraints=constraints,
                ),
            ),
        ]

        return {
            "evaluation_version": PHASE_7_EVALUATION_VERSION,
            "baseline_seed": BASELINE_RANDOM_SEED,
            "constraints": self._serialize_constraints(constraints),
            "methods": method_results,
            "winner_summary": self._build_winner_summary(method_results),
        }

    def _time_method(self, *, method: str, objective_version: str, match_score_before: float, runner) -> dict:
        started_at = perf_counter()
        selected_courses, metadata = runner()
        metadata["match_score_before"] = match_score_before
        runtime_ms = round((perf_counter() - started_at) * 1000, 4)
        explanation = metadata.get("explanation") or self._baseline_explanation(method)
        metrics = self._evaluate_selected_courses(
            selected_courses=selected_courses,
            missing_by_id=metadata["missing_by_id"],
            match_score_before=metadata["match_score_before"],
            constraints=metadata["constraints"],
        )
        return {
            "method": method,
            "objective_version": objective_version,
            "solver_status": metadata.get("solver_status"),
            "metrics": {
                **metrics,
                "runtime_ms": runtime_ms,
                "explanation_completeness": self._explanation_completeness(
                    explanation=explanation,
                    selected_courses=selected_courses,
                ),
            },
            "selected_courses": self._serialize_selected_courses(selected_courses),
            "explanation": explanation,
        }

    def _select_greedy(
        self,
        *,
        candidates: list[dict],
        missing_by_id: dict[str, dict],
        constraints: LearningRouteConstraints,
        sort_key,
    ) -> tuple[list[dict], dict]:
        selected: list[dict] = []
        covered_skill_ids: set[str] = set()
        total_cost = 0.0
        total_hours = 0.0
        max_courses = self._max_courses(constraints)

        for course in sorted(candidates, key=sort_key):
            if len(selected) >= max_courses:
                break
            cost = float(course.get("cost") or 0)
            hours = float(course.get("duration_hours") or 0)
            if not self._fits_constraints(
                total_cost=total_cost + cost,
                total_hours=total_hours + hours,
                course_count=len(selected) + 1,
                constraints=constraints,
            ):
                continue
            new_skill_ids = {
                skill["skill_id"]
                for skill in course.get("skills_covered", [])
                if skill["skill_id"] in missing_by_id and skill["skill_id"] not in covered_skill_ids
            }
            if not new_skill_ids:
                continue
            selected.append(course)
            covered_skill_ids.update(new_skill_ids)
            total_cost += cost
            total_hours += hours

        return selected, self._metadata(missing_by_id=missing_by_id, constraints=constraints)

    def _select_random_feasible(
        self,
        *,
        candidates: list[dict],
        missing_by_id: dict[str, dict],
        constraints: LearningRouteConstraints,
    ) -> tuple[list[dict], dict]:
        shuffled = list(candidates)
        random.Random(BASELINE_RANDOM_SEED).shuffle(shuffled)
        return self._select_greedy(
            candidates=shuffled,
            missing_by_id=missing_by_id,
            constraints=constraints,
            sort_key=lambda course: shuffled.index(course),
        )

    def _select_cp_sat(
        self,
        *,
        candidates: list[dict],
        missing_by_id: dict[str, dict],
        constraints: LearningRouteConstraints,
    ) -> tuple[list[dict], dict]:
        if not ORToolsLearningRouteOptimizer.is_available():
            return [], self._metadata(
                missing_by_id=missing_by_id,
                constraints=constraints,
                solver_status="UNAVAILABLE",
                explanation="OR-Tools is unavailable, so the CP-SAT baseline could not be evaluated.",
            )
        if not candidates:
            return [], self._metadata(
                missing_by_id=missing_by_id,
                constraints=constraints,
                solver_status="NO_CANDIDATES",
                explanation="No active candidate courses cover the missing skills.",
            )

        optimizer = ORToolsLearningRouteOptimizer(self.session)
        solution = optimizer._solve_cp_sat(
            candidates=candidates,
            missing_by_id=missing_by_id,
            constraints=constraints,
        )
        selected = [
            {
                **candidates[index],
                "solver_sequence_position": solution["sequence_positions"].get(index),
            }
            for index in solution["selected_course_indexes"]
        ]
        selected.sort(key=lambda course: (course.get("solver_sequence_position") or 999, course["title"].lower()))
        return selected, self._metadata(
            missing_by_id=missing_by_id,
            constraints=constraints,
            solver_status=solution["solver_status"],
            explanation=(
                "CP-SAT maximizes weighted skill-gap coverage while penalizing cost, time, "
                "redundancy, and uncovered gaps under the same constraints as every baseline."
            ),
        )

    def _evaluate_selected_courses(
        self,
        *,
        selected_courses: list[dict],
        missing_by_id: dict[str, dict],
        match_score_before: float,
        constraints: LearningRouteConstraints,
    ) -> dict:
        coverage_by_skill = {skill_id: 0.0 for skill_id in missing_by_id}
        for course in selected_courses:
            for skill in course.get("skills_covered", []):
                skill_id = skill["skill_id"]
                if skill_id in coverage_by_skill:
                    coverage_by_skill[skill_id] += float(skill.get("coverage_score") or 0.5)

        covered_skill_ids = {
            skill_id
            for skill_id, coverage_amount in coverage_by_skill.items()
            if coverage_amount >= self._coverage_threshold(missing_by_id[skill_id])
        }
        critical_skill_ids = {
            skill_id
            for skill_id, skill in missing_by_id.items()
            if self._is_critical_skill(skill)
        }
        total_gap_weight = sum(self._gap_weight(skill) for skill in missing_by_id.values())
        covered_gap_weight = sum(self._gap_weight(missing_by_id[skill_id]) for skill_id in covered_skill_ids)
        weighted_skill_coverage = covered_gap_weight / total_gap_weight if total_gap_weight else 0.0
        critical_skill_coverage = (
            len(covered_skill_ids & critical_skill_ids) / len(critical_skill_ids)
            if critical_skill_ids
            else 0.0
        )
        total_cost = round(sum(float(course.get("cost") or 0) for course in selected_courses), 2)
        total_hours = round(sum(float(course.get("duration_hours") or 0) for course in selected_courses), 2)
        total_coverage_amount = sum(coverage_by_skill.values())
        redundant_coverage_amount = sum(max(0.0, value - 1.0) for value in coverage_by_skill.values())
        redundancy_rate = redundant_coverage_amount / total_coverage_amount if total_coverage_amount else 0.0
        projected_after = HeuristicLearningRouteOptimizer._project_match_score(
            match_score_before=match_score_before,
            missing_skills=list(missing_by_id.values()),
            covered_skills=[missing_by_id[skill_id] for skill_id in covered_skill_ids],
        )

        return {
            "weighted_skill_coverage": round(weighted_skill_coverage, 4),
            "critical_skill_coverage": round(critical_skill_coverage, 4),
            "covered_skills_count": len(covered_skill_ids),
            "remaining_gaps_count": max(0, len(missing_by_id) - len(covered_skill_ids)),
            "selected_courses_count": len(selected_courses),
            "total_cost": total_cost,
            "total_hours": total_hours,
            "score_per_dollar": (
                round(weighted_skill_coverage / total_cost, 4)
                if total_cost > 0
                else round(weighted_skill_coverage, 4)
            ),
            "score_per_hour": round(weighted_skill_coverage / total_hours, 4) if total_hours > 0 else 0.0,
            "redundancy_rate": round(redundancy_rate, 4),
            "constraint_satisfaction": 1.0 if self._fits_constraints(
                total_cost=total_cost,
                total_hours=total_hours,
                course_count=len(selected_courses),
                constraints=constraints,
            ) else 0.0,
            "projected_readiness_gain": round(projected_after - match_score_before, 4),
        }

    def _serialize_selected_courses(self, selected_courses: list[dict]) -> list[dict]:
        serialized = []
        for index, course in enumerate(selected_courses, start=1):
            serialized.append(
                {
                    **course,
                    "sequence_order": course.get("sequence_order") or index,
                    "covered_priority_skills": [
                        skill["display_name"]
                        for skill in course.get("skills_covered", [])[:3]
                    ],
                    "selection_reason": course.get("selection_reason") or "Selected by this Phase 7 comparison method.",
                    "constraint_notes": course.get("constraint_notes") or [],
                }
            )
        return serialized

    def _course_coverage_value(self, course: dict, missing_by_id: dict[str, dict]) -> float:
        value = 0.0
        for skill in course.get("skills_covered", []):
            missing_skill = missing_by_id.get(skill["skill_id"])
            if not missing_skill:
                continue
            value += self._gap_weight(missing_skill) * float(skill.get("coverage_score") or 0.5)
        return value

    @staticmethod
    def _course_average_coverage(course: dict) -> float:
        coverages = [float(skill.get("coverage_score") or 0.5) for skill in course.get("skills_covered", [])]
        return sum(coverages) / len(coverages) if coverages else 0.0

    @staticmethod
    def _build_winner_summary(method_results: list[dict]) -> dict:
        if not method_results:
            return {
                "best_method": None,
                "summary": "No methods were evaluated.",
            }
        best = max(
            method_results,
            key=lambda result: (
                result["metrics"]["constraint_satisfaction"],
                result["metrics"]["weighted_skill_coverage"],
                result["metrics"]["critical_skill_coverage"],
                result["metrics"]["projected_readiness_gain"],
                -result["metrics"]["redundancy_rate"],
                -result["metrics"]["total_cost"],
                -result["metrics"]["total_hours"],
            ),
        )
        return {
            "best_method": best["method"],
            "best_objective_version": best["objective_version"],
            "summary": (
                f"{best['method']} produced the strongest feasible route by weighted coverage, "
                "critical-skill coverage, readiness gain, redundancy, cost, and hours."
            ),
        }

    @staticmethod
    def _baseline_explanation(method: str) -> str:
        explanations = {
            "cheapest_feasible": (
                "Greedy baseline that selects the lowest-cost feasible courses "
                "that add new gap coverage."
            ),
            "highest_rated_feasible": (
                "Greedy baseline that selects the highest-rated feasible courses "
                "that add new gap coverage."
            ),
            "similarity_only": (
                "Greedy baseline that prioritizes skill coverage strength and "
                "ignores cost/time except as hard constraints."
            ),
            "heuristic_route_v1": (
                "Existing MVP optimizer baseline using weighted coverage, cost, "
                "hours, rating, and difficulty."
            ),
            "random_feasible_seeded": (
                "Seeded random feasible selection used as a reproducible "
                "lower-control baseline."
            ),
        }
        return explanations.get(method, "Phase 7 comparison method.")

    @staticmethod
    def _explanation_completeness(*, explanation: str, selected_courses: list[dict]) -> float:
        if not explanation.strip():
            return 0.0
        if not selected_courses:
            return 1.0
        courses_with_skill_context = sum(
            1 for course in selected_courses if course.get("title") and course.get("skills_covered")
        )
        return round(courses_with_skill_context / len(selected_courses), 4)

    @staticmethod
    def _metadata(
        *,
        missing_by_id: dict[str, dict],
        constraints: LearningRouteConstraints,
        solver_status: str | None = None,
        explanation: str | None = None,
    ) -> dict:
        return {
            "missing_by_id": missing_by_id,
            "constraints": constraints,
            "match_score_before": 0.0,
            "solver_status": solver_status,
            "explanation": explanation,
        }

    @staticmethod
    def _serialize_constraints(constraints: LearningRouteConstraints) -> dict:
        return {
            "budget": constraints.budget,
            "available_hours": constraints.available_hours,
            "max_courses": constraints.max_courses,
        }

    @classmethod
    def _fits_constraints(
        cls,
        *,
        total_cost: float,
        total_hours: float,
        course_count: int,
        constraints: LearningRouteConstraints,
    ) -> bool:
        if constraints.budget is not None and total_cost > constraints.budget:
            return False
        if constraints.available_hours is not None and total_hours > constraints.available_hours:
            return False
        return course_count <= cls._max_courses(constraints)

    @staticmethod
    def _max_courses(constraints: LearningRouteConstraints) -> int:
        return constraints.max_courses if constraints.max_courses is not None else 5

    @staticmethod
    def _gap_weight(skill: dict) -> float:
        return HeuristicLearningRouteOptimizer._gap_weight(skill)

    @staticmethod
    def _coverage_threshold(skill: dict) -> float:
        return 0.85 if LearningRouteBaselineEvaluationService._is_critical_skill(skill) else 0.70

    @staticmethod
    def _is_critical_skill(skill: dict) -> bool:
        importance = float(skill.get("importance_score") or 0.0)
        priority_rank = int(skill.get("priority_rank") or 0)
        return importance >= 0.85 or (priority_rank > 0 and priority_rank <= 3)
