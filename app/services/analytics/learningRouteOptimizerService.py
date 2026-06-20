from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.analytics.courseCatalogQueries import load_active_course_links

try:
    from ortools.sat.python import cp_model
except ModuleNotFoundError:  # pragma: no cover - depends on optional runtime dependency.
    cp_model = None


OBJECTIVE_VERSION_HEURISTIC = "heuristic_route_v1"
OBJECTIVE_VERSION_CP_SAT = "cp_sat_route_v1"


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


class ORToolsUnavailableError(RuntimeError):
    """Raised when the CP-SAT optimizer is requested without OR-Tools."""


def get_learning_route_optimizer(session: AsyncSession) -> LearningRouteOptimizer:
    if ORToolsLearningRouteOptimizer.is_available():
        return ORToolsLearningRouteOptimizer(session)
    return HeuristicLearningRouteOptimizer(session)


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
            gap_weight = self._gap_weight(missing_skill)
            coverage_value += gap_weight * float(covered_skill.get("coverage_score") or 0.5)

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
                "gap_weight": self._gap_weight(missing_by_id.get(skill["skill_id"], {})),
            }
            for skill in course["skills_covered"]
            if skill["skill_id"] in missing_by_id
        ]
        covered_missing_skills.sort(
            key=lambda skill: (
                -skill["gap_weight"],
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
        total_missing_importance = sum(HeuristicLearningRouteOptimizer._gap_weight(skill) for skill in missing_skills)
        covered_importance = sum(HeuristicLearningRouteOptimizer._gap_weight(skill) for skill in covered_skills)
        if total_missing_importance <= 0:
            return round(match_score_before, 4)
        remaining_gap = 1.0 - match_score_before
        projected_gain = remaining_gap * (covered_importance / total_missing_importance)
        return round(max(0.0, min(match_score_before + projected_gain, 1.0)), 4)

    @staticmethod
    def _gap_weight(skill: dict) -> float:
        return float(
            skill.get("skill_gap_score")
            or skill.get("priority_score")
            or skill.get("importance_score")
            or 0.75
        )

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
    SCALE = 1000
    MONEY_SCALE = 100
    HOURS_SCALE = 100
    DEFAULT_MAX_COURSES = 5

    WEIGHT_GAP = 100
    WEIGHT_DEMAND = 35
    WEIGHT_CRITICAL = 50
    WEIGHT_QUALITY = 8
    PENALTY_COST = 10
    PENALTY_TIME = 10
    PENALTY_REDUNDANCY = 20
    PENALTY_UNCOVERED = 120

    def __init__(self, session: AsyncSession):
        self.session = session
        self._heuristic = HeuristicLearningRouteOptimizer(session)

    @staticmethod
    def is_available() -> bool:
        return cp_model is not None

    async def optimize(
        self,
        *,
        missing_skills: list[dict],
        match_score_before: float,
        constraints: LearningRouteConstraints,
    ) -> dict:
        if cp_model is None:
            raise ORToolsUnavailableError("OR-Tools is not installed; CP-SAT optimization is unavailable.")

        missing_by_id = {skill["skill_id"]: skill for skill in missing_skills}
        if not missing_by_id:
            return self._empty_result(match_score_before=match_score_before)

        candidates = await self._heuristic._load_course_candidates(missing_skill_ids=list(missing_by_id))
        scored_candidates = self._heuristic._dedupe_equivalent_courses(candidates, missing_by_id)
        if not scored_candidates:
            return self._no_candidate_result(
                match_score_before=match_score_before,
                remaining_gaps=list(missing_by_id.values()),
            )

        solution = self._solve_cp_sat(
            candidates=scored_candidates,
            missing_by_id=missing_by_id,
            constraints=constraints,
        )
        if solution["solver_status"] not in {"OPTIMAL", "FEASIBLE"}:
            return self._infeasible_result(
                match_score_before=match_score_before,
                remaining_gaps=list(missing_by_id.values()),
                solver_status=solution["solver_status"],
            )

        selected_course_entries = [
            (index, scored_candidates[index])
            for index in solution["selected_course_indexes"]
        ]
        selected_courses = self._apply_solver_sequence(
            selected_course_entries,
            sequence_positions=solution["sequence_positions"],
        )
        selected_courses = [
            self._add_solver_context(
                course,
                covered_skill_ids=solution["covered_skill_ids"],
                objective_value=solution["objective_value"],
            )
            for course in selected_courses
        ]

        covered_skills = [
            missing_by_id[skill_id]
            for skill_id in sorted(solution["covered_skill_ids"])
            if skill_id in missing_by_id
        ]
        remaining_gaps = [
            skill
            for skill_id, skill in missing_by_id.items()
            if skill_id not in solution["covered_skill_ids"]
        ]
        total_cost = round(sum(float(course["cost"] or 0) for course in selected_courses), 2)
        total_hours = round(sum(float(course["duration_hours"] or 0) for course in selected_courses), 2)
        projected_score = self._heuristic._project_match_score(
            match_score_before=match_score_before,
            missing_skills=list(missing_by_id.values()),
            covered_skills=covered_skills,
        )

        return {
            "objective_version": OBJECTIVE_VERSION_CP_SAT,
            "solver_status": solution["solver_status"],
            "objective_value": solution["objective_value"],
            "match_score_before": round(match_score_before, 4),
            "projected_match_score_after": projected_score,
            "total_cost": total_cost,
            "total_hours": total_hours,
            "selected_courses": selected_courses,
            "covered_skills": covered_skills,
            "remaining_gaps": remaining_gaps,
            "route_summary": self._build_cp_sat_route_summary(
                solver_status=solution["solver_status"],
                selected_courses=selected_courses,
                covered_skills=covered_skills,
                remaining_gaps=remaining_gaps,
            ),
            "model_explanation": self._build_model_explanation(solution),
        }

    def _solve_cp_sat(
        self,
        *,
        candidates: list[dict],
        missing_by_id: dict[str, dict],
        constraints: LearningRouteConstraints,
    ) -> dict:
        model = cp_model.CpModel()
        course_vars = [
            model.NewBoolVar(f"x_course_{index}")
            for index, _course in enumerate(candidates)
        ]
        max_courses = constraints.max_courses if constraints.max_courses is not None else self.DEFAULT_MAX_COURSES
        model.Add(sum(course_vars) <= max_courses)
        assignment_vars = self._build_sequence_assignment_variables(
            model=model,
            course_vars=course_vars,
            max_courses=max_courses,
        )
        position_exprs = [
            sum(position * assignment_vars[(index, position)] for position in range(1, max_courses + 1))
            for index, _course in enumerate(candidates)
        ]
        self._add_sequence_constraints(
            model=model,
            candidates=candidates,
            course_vars=course_vars,
            position_exprs=position_exprs,
            max_courses=max_courses,
        )

        if constraints.budget is not None:
            max_budget = self._scale_money(constraints.budget)
            model.Add(
                sum(self._scale_money(course["cost"]) * course_vars[index] for index, course in enumerate(candidates))
                <= max_budget
            )

        if constraints.available_hours is not None:
            max_hours = self._scale_hours(constraints.available_hours)
            model.Add(
                sum(
                    self._scale_hours(course["duration_hours"]) * course_vars[index]
                    for index, course in enumerate(candidates)
                )
                <= max_hours
            )

        objective_terms = []
        covered_skill_vars = {}
        uncovered_skill_vars = {}
        redundancy_vars = {}
        skill_to_course_indexes = self._build_skill_course_index(candidates)

        for skill_id, skill in missing_by_id.items():
            skill_course_links = skill_to_course_indexes.get(skill_id, [])
            coverage_terms = [
                self._scale_score(coverage_score) * course_vars[index]
                for index, coverage_score in skill_course_links
            ]
            max_coverage = sum(self._scale_score(coverage_score) for _index, coverage_score in skill_course_links)
            threshold = self._coverage_threshold(skill)

            y_skill = model.NewBoolVar(f"y_skill_{skill_id}")
            m_skill = model.NewBoolVar(f"m_skill_{skill_id}")
            covered_skill_vars[skill_id] = y_skill
            uncovered_skill_vars[skill_id] = m_skill
            model.Add(y_skill + m_skill == 1)

            if coverage_terms:
                coverage_expr = sum(coverage_terms)
                model.Add(coverage_expr >= threshold).OnlyEnforceIf(y_skill)
                model.Add(coverage_expr <= threshold - 1).OnlyEnforceIf(y_skill.Not())

                redundancy = model.NewIntVar(0, max(max_coverage, self.SCALE), f"r_skill_{skill_id}")
                redundancy_vars[skill_id] = redundancy
                model.Add(redundancy >= coverage_expr - self.SCALE)
                model.Add(redundancy >= 0)
                objective_terms.append(-self._redundancy_penalty(skill) * redundancy)
            else:
                model.Add(y_skill == 0)

            objective_terms.append(self._covered_skill_value(skill) * y_skill)
            objective_terms.append(-self._uncovered_skill_penalty(skill) * m_skill)

        for index, course in enumerate(candidates):
            objective_terms.append(self._course_value(course, constraints=constraints) * course_vars[index])
            for position in range(1, max_courses + 1):
                objective_terms.append(
                    self._sequence_position_value(course, position=position, max_courses=max_courses)
                    * assignment_vars[(index, position)]
                )

        model.Maximize(sum(objective_terms))

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 1
        solver.parameters.num_search_workers = 1
        solver.parameters.random_seed = 42

        status = solver.Solve(model)
        solver_status = self._solver_status_name(solver, status)
        if solver_status not in {"OPTIMAL", "FEASIBLE"}:
            return {
                "solver_status": solver_status,
                "objective_value": 0.0,
                "selected_course_indexes": [],
                "sequence_positions": {},
                "covered_skill_ids": set(),
            }

        selected_course_indexes = [
            index
            for index, var in enumerate(course_vars)
            if solver.BooleanValue(var)
        ]
        sequence_positions = {
            index: next(
                position
                for position in range(1, max_courses + 1)
                if solver.BooleanValue(assignment_vars[(index, position)])
            )
            for index in selected_course_indexes
        }
        covered_skill_ids = {
            skill_id
            for skill_id, var in covered_skill_vars.items()
            if solver.BooleanValue(var)
        }
        return {
            "solver_status": solver_status,
            "objective_value": round(float(solver.ObjectiveValue()) / self.SCALE, 4),
            "selected_course_indexes": selected_course_indexes,
            "sequence_positions": sequence_positions,
            "covered_skill_ids": covered_skill_ids,
        }

    def _build_skill_course_index(self, candidates: list[dict]) -> dict[str, list[tuple[int, float]]]:
        skill_to_course_indexes: dict[str, list[tuple[int, float]]] = {}
        for index, course in enumerate(candidates):
            for skill in course["skills_covered"]:
                skill_to_course_indexes.setdefault(skill["skill_id"], []).append(
                    (index, float(skill.get("coverage_score") or 0.5))
                )
        return skill_to_course_indexes

    def _build_sequence_assignment_variables(self, *, model, course_vars: list, max_courses: int) -> dict[tuple[int, int], object]:
        assignment_vars = {}
        for index, course_var in enumerate(course_vars):
            assigned_positions = []
            for position in range(1, max_courses + 1):
                assigned = model.NewBoolVar(f"a_course_{index}_position_{position}")
                assignment_vars[(index, position)] = assigned
                assigned_positions.append(assigned)
            model.Add(sum(assigned_positions) == course_var)

        for position in range(1, max_courses + 1):
            model.Add(sum(assignment_vars[(index, position)] for index in range(len(course_vars))) <= 1)
        return assignment_vars

    def _add_sequence_constraints(
        self,
        *,
        model,
        candidates: list[dict],
        course_vars: list,
        position_exprs: list,
        max_courses: int,
    ) -> None:
        big_m = max_courses + 1
        for left_index, left_course in enumerate(candidates):
            for right_index, right_course in enumerate(candidates):
                if left_index == right_index:
                    continue

                left_rank = self._difficulty_rank(left_course.get("difficulty"))
                right_rank = self._difficulty_rank(right_course.get("difficulty"))
                if left_rank < right_rank:
                    self._add_precedes_if_both_selected(
                        model=model,
                        first_position=position_exprs[left_index],
                        second_position=position_exprs[right_index],
                        first_selected=course_vars[left_index],
                        second_selected=course_vars[right_index],
                        big_m=big_m,
                    )
                    continue

                left_prerequisites = self._prerequisite_skill_count(left_course)
                right_prerequisites = self._prerequisite_skill_count(right_course)
                if left_prerequisites > right_prerequisites and left_rank <= right_rank:
                    self._add_precedes_if_both_selected(
                        model=model,
                        first_position=position_exprs[left_index],
                        second_position=position_exprs[right_index],
                        first_selected=course_vars[left_index],
                        second_selected=course_vars[right_index],
                        big_m=big_m,
                    )

    @staticmethod
    def _add_precedes_if_both_selected(
        *,
        model,
        first_position,
        second_position,
        first_selected,
        second_selected,
        big_m: int,
    ) -> None:
        model.Add(first_position + 1 <= second_position + big_m * (2 - first_selected - second_selected))

    def _covered_skill_value(self, skill: dict) -> int:
        gap = self._gap_weight(skill)
        demand = self._clamp(float(skill.get("market_demand_score") or 0.0), 0.0, 1.0)
        critical = 1.0 if self._is_critical_skill(skill) else 0.0
        value = (
            self.WEIGHT_GAP * gap
            + self.WEIGHT_DEMAND * demand
            + self.WEIGHT_CRITICAL * critical
        )
        return int(round(value * self.SCALE))

    def _course_value(self, course: dict, *, constraints: LearningRouteConstraints) -> int:
        rating = self._clamp(float(course.get("rating") or 0.0) / 5.0, 0.0, 1.0)
        quality_value = self.WEIGHT_QUALITY * rating

        cost = float(course.get("cost") or 0.0)
        if constraints.budget and constraints.budget > 0:
            normalized_cost = cost / constraints.budget
        else:
            normalized_cost = min(cost / 500.0, 0.4)

        hours = float(course.get("duration_hours") or 0.0)
        if constraints.available_hours and constraints.available_hours > 0:
            normalized_hours = hours / constraints.available_hours
        else:
            normalized_hours = min(hours / 120.0, 0.35)

        penalty = self.PENALTY_COST * normalized_cost + self.PENALTY_TIME * normalized_hours
        return int(round((quality_value - penalty) * self.SCALE))

    def _sequence_position_value(self, course: dict, *, position: int, max_courses: int) -> int:
        earlier_bonus = max_courses - position + 1
        prerequisite_bonus = self._prerequisite_skill_count(course) * 4
        difficulty_bonus = max(0, 4 - self._difficulty_rank(course.get("difficulty")))
        return int(round((prerequisite_bonus + difficulty_bonus) * earlier_bonus * self.SCALE))

    def _uncovered_skill_penalty(self, skill: dict) -> int:
        return int(round(self.PENALTY_UNCOVERED * self._gap_weight(skill) * self.SCALE))

    def _redundancy_penalty(self, skill: dict) -> int:
        return int(round(self.PENALTY_REDUNDANCY * self._gap_weight(skill)))

    def _coverage_threshold(self, skill: dict) -> int:
        if self._is_critical_skill(skill):
            return int(round(0.85 * self.SCALE))
        return int(round(0.70 * self.SCALE))

    def _add_solver_context(
        self,
        course: dict,
        *,
        covered_skill_ids: set[str],
        objective_value: float,
    ) -> dict:
        covered_names = [
            skill["display_name"]
            for skill in course["skills_covered"]
            if skill["skill_id"] in covered_skill_ids
        ]
        if covered_names:
            selection_reason = (
                "Selected by the CP-SAT model because it contributes to covered priority gaps: "
                + ", ".join(covered_names[:3])
                + "."
            )
        else:
            selection_reason = "Selected by the CP-SAT model because it improves the feasible route objective."

        return {
            **course,
            "covered_priority_skills": covered_names[:3],
            "selection_reason": selection_reason,
            "constraint_notes": [
                "Included in the best feasible CP-SAT solution under budget, time, and course-count constraints.",
                f"Route objective value: {objective_value:.4f}.",
            ],
        }

    def _apply_solver_sequence(
        self,
        selected_course_entries: list[tuple[int, dict]],
        *,
        sequence_positions: dict[int, int],
    ) -> list[dict]:
        sequenced_entries = sorted(
            selected_course_entries,
            key=lambda entry: (
                sequence_positions.get(entry[0], len(selected_course_entries) + 1),
                entry[1]["title"].lower(),
            ),
        )
        return [
            {
                **course,
                "solver_sequence_position": sequence_positions.get(candidate_index, order),
                "sequence_order": order,
            }
            for order, (candidate_index, course) in enumerate(sequenced_entries, start=1)
        ]

    def _no_candidate_result(self, *, match_score_before: float, remaining_gaps: list[dict]) -> dict:
        return {
            "objective_version": OBJECTIVE_VERSION_CP_SAT,
            "solver_status": "NO_CANDIDATES",
            "objective_value": 0.0,
            "match_score_before": round(match_score_before, 4),
            "projected_match_score_after": round(match_score_before, 4),
            "total_cost": 0.0,
            "total_hours": 0.0,
            "selected_courses": [],
            "covered_skills": [],
            "remaining_gaps": remaining_gaps,
            "route_summary": "No active course in the catalog covers the remaining priority gaps.",
            "model_explanation": "The CP-SAT model was not solved because there were no candidate courses.",
        }

    def _infeasible_result(
        self,
        *,
        match_score_before: float,
        remaining_gaps: list[dict],
        solver_status: str,
    ) -> dict:
        return {
            "objective_version": OBJECTIVE_VERSION_CP_SAT,
            "solver_status": solver_status,
            "objective_value": 0.0,
            "match_score_before": round(match_score_before, 4),
            "projected_match_score_after": round(match_score_before, 4),
            "total_cost": 0.0,
            "total_hours": 0.0,
            "selected_courses": [],
            "covered_skills": [],
            "remaining_gaps": remaining_gaps,
            "route_summary": "No feasible CP-SAT route satisfies the current catalog and constraints.",
            "model_explanation": (
                "The solver could not find a feasible route under the supplied budget, hours, and course-count limits."
            ),
        }

    def _empty_result(self, *, match_score_before: float) -> dict:
        return {
            "objective_version": OBJECTIVE_VERSION_CP_SAT,
            "solver_status": "NOT_NEEDED",
            "objective_value": 0.0,
            "match_score_before": round(match_score_before, 4),
            "projected_match_score_after": round(match_score_before, 4),
            "total_cost": 0.0,
            "total_hours": 0.0,
            "selected_courses": [],
            "covered_skills": [],
            "remaining_gaps": [],
            "route_summary": "No learning route was selected because there are no uncovered skills to optimize.",
            "model_explanation": "The CP-SAT model was not solved because the student has no missing required skills.",
        }

    @staticmethod
    def _build_cp_sat_route_summary(
        *,
        solver_status: str,
        selected_courses: list[dict],
        covered_skills: list[dict],
        remaining_gaps: list[dict],
    ) -> str:
        if not selected_courses:
            return "No CP-SAT route was selected under the current catalog and constraints."
        return (
            f"CP-SAT returned a {solver_status.lower()} route with {len(selected_courses)} course(s), "
            f"covering {len(covered_skills)} gap(s) and leaving {len(remaining_gaps)} gap(s)."
        )

    @staticmethod
    def _build_model_explanation(solution: dict) -> str:
        return (
            "The CP-SAT model selected the course set that maximized weighted skill-gap coverage, "
            "labor-market demand, critical-skill value, and course quality while penalizing cost, "
            "time, redundancy, and uncovered gaps. The same solver assigned route positions while "
            "respecting difficulty progression and prerequisite-skill ordering signals."
        )

    @staticmethod
    def _solver_status_name(solver, status: int) -> str:
        if status == cp_model.OPTIMAL:
            return "OPTIMAL"
        if status == cp_model.FEASIBLE:
            return "FEASIBLE"
        if status == cp_model.INFEASIBLE:
            return "INFEASIBLE"
        if status == cp_model.MODEL_INVALID:
            return "MODEL_INVALID"
        if status == cp_model.UNKNOWN:
            return "UNKNOWN"
        return solver.StatusName(status)

    @classmethod
    def _scale_score(cls, value: float) -> int:
        return int(round(cls._clamp(float(value or 0.0), 0.0, 1.0) * cls.SCALE))

    @classmethod
    def _scale_money(cls, value: float | None) -> int:
        return int(round(float(value or 0.0) * cls.MONEY_SCALE))

    @classmethod
    def _scale_hours(cls, value: float | None) -> int:
        return int(round(float(value or 0.0) * cls.HOURS_SCALE))

    @staticmethod
    def _gap_weight(skill: dict) -> float:
        return HeuristicLearningRouteOptimizer._gap_weight(skill)

    @staticmethod
    def _prerequisite_skill_count(course: dict) -> int:
        return sum(1 for skill in course.get("skills_covered", []) if skill.get("is_prerequisite"))

    @staticmethod
    def _difficulty_rank(difficulty: str | None) -> int:
        normalized = (difficulty or "").lower()
        if normalized == "beginner":
            return 1
        if normalized == "intermediate":
            return 2
        if normalized == "advanced":
            return 3
        return 4

    @classmethod
    def _is_critical_skill(cls, skill: dict) -> bool:
        importance = cls._clamp(float(skill.get("importance_score") or 0.0), 0.0, 1.0)
        priority_rank = int(skill.get("priority_rank") or 0)
        return importance >= 0.85 or (priority_rank > 0 and priority_rank <= 3)

    @staticmethod
    def _clamp(value: float, minimum: float, maximum: float) -> float:
        return max(minimum, min(value, maximum))
