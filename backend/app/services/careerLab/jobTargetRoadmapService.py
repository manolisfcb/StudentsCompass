"""What to study first for one vacancy, in the days left before the interview.

TASK-080, plan 11 §1 question 2. The optimiser is the existing one
(``learningRouteOptimizerService``: CP-SAT, or its heuristic when OR-Tools is
absent); this module only feeds it the gaps of a stored job-target analysis
(TASK-079) and turns "N days at H hours a day" into its hours constraint.

No LLM, and nothing is stored: the answer depends on how many days are left,
which changes every day, and recomputing costs one bounded solve.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.jobTargetModel import JOB_TARGET_STATUS_READY, JobTargetModel
from app.services.analytics.courseCatalogQueries import load_active_course_links
from app.services.analytics.learningRouteOptimizerService import (
    LearningRouteConstraints,
    get_learning_route_optimizer,
)

#: Why a gap is not in the route. The first is a catalogue limit the student
#: cannot fix by finding more time; the second is the opposite.
UNCOVERED_NO_COURSE = "no_course"
UNCOVERED_OUT_OF_REACH = "out_of_reach"


class JobTargetRoadmapError(RuntimeError):
    """The vacancy has no analysis to plan from; the message is safe to show."""


@dataclass(frozen=True)
class RoadmapConstraints:
    days_until_interview: int
    hours_per_day: float
    budget: float | None = None
    max_courses: int | None = None

    @property
    def available_hours(self) -> float:
        return round(self.days_until_interview * self.hours_per_day, 2)


def _gap_for_optimizer(gap: dict) -> dict:
    """A gap of the stored analysis, in the shape the optimiser reads.

    ``skill_gap_score`` is its weight and ``priority_rank`` marks the first
    three as critical, exactly as for a role's gaps. The vacancy-specific
    fields ride along untouched and come back in ``covered_skills`` and
    ``remaining_gaps``.
    """
    return {
        "skill_id": gap["skill_id"],
        "display_name": gap["display_name"],
        "requirement": gap.get("requirement"),
        "kind": gap["kind"],
        "priority_rank": gap["priority_rank"],
        "skill_gap_score": gap["skill_gap_score"],
    }


def _gap_read(gap: dict) -> dict:
    return {
        "skill_id": gap["skill_id"],
        "display_name": gap["display_name"],
        "requirement": gap.get("requirement"),
        "kind": gap["kind"],
        "priority_rank": gap["priority_rank"],
    }


def schedule_steps(courses: list[dict], *, hours_per_day: float) -> list[dict]:
    """Lay the courses end to end at ``hours_per_day``: day X to day Y of each.

    Days are 1-based. A course starts the day after the previous one finished
    only if that day was used up; otherwise it starts on the same day. A
    course with no recorded duration takes no days of its own.
    """
    steps = []
    elapsed = 0.0
    for order, course in enumerate(courses, start=1):
        hours = float(course.get("duration_hours") or 0.0)
        start_day = math.floor(elapsed / hours_per_day) + 1
        elapsed += hours
        end_day = max(start_day, math.ceil(elapsed / hours_per_day))
        steps.append({**course, "order": order, "start_day": start_day, "end_day": end_day})
    return steps


class JobTargetRoadmapService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def build(self, *, target: JobTargetModel, constraints: RoadmapConstraints) -> dict:
        snapshot = target.match_snapshot or {}
        if target.status != JOB_TARGET_STATUS_READY or not snapshot:
            raise JobTargetRoadmapError("This vacancy has no analysis to plan from yet.")

        gaps = sorted(snapshot.get("gaps") or [], key=lambda gap: gap["priority_rank"])
        missing = [_gap_for_optimizer(gap) for gap in gaps]
        gap_ids = [gap["skill_id"] for gap in missing]

        route = await get_learning_route_optimizer(self.session).optimize(
            missing_skills=missing,
            # Only the optimiser's projection reads it, and that projection is
            # of role readiness, not of this vacancy's score: not returned.
            match_score_before=float(snapshot.get("score") or 0.0),
            constraints=LearningRouteConstraints(
                budget=constraints.budget,
                available_hours=constraints.available_hours,
                max_courses=constraints.max_courses,
            ),
        )

        # One query to tell "no course teaches it" from "it did not fit": the
        # optimiser reports both as an uncovered gap.
        taught = {
            str(link.skill_id)
            for _course, links in await load_active_course_links(self.session, gap_ids)
            for link in links
        }
        covered_ids = {gap["skill_id"] for gap in route["covered_skills"]}
        uncovered = [
            {
                **_gap_read(gap),
                "reason": UNCOVERED_OUT_OF_REACH if gap["skill_id"] in taught else UNCOVERED_NO_COURSE,
            }
            for gap in missing
            if gap["skill_id"] not in covered_ids
        ]

        total_weight = sum(gap["skill_gap_score"] for gap in missing)
        covered_weight = sum(gap["skill_gap_score"] for gap in missing if gap["skill_id"] in covered_ids)
        selected = sorted(
            route["selected_courses"],
            key=lambda course: course.get("sequence_order") or 0,
        )
        steps = schedule_steps(
            [self._step(course, gap_ids=set(gap_ids)) for course in selected],
            hours_per_day=constraints.hours_per_day,
        )

        return {
            "target_id": str(target.id),
            "objective_version": route["objective_version"],
            "solver_status": route.get("solver_status"),
            "constraints": {
                "days_until_interview": constraints.days_until_interview,
                "hours_per_day": constraints.hours_per_day,
                "available_hours": constraints.available_hours,
                "budget": constraints.budget,
                "max_courses": constraints.max_courses,
            },
            "total_cost": route["total_cost"],
            "total_hours": route["total_hours"],
            #: Share of the gaps' weight the route covers; null with no gaps.
            "gap_coverage": round(covered_weight / total_weight, 4) if total_weight > 0 else None,
            "steps": steps,
            "covered_gaps": [_gap_read(gap) for gap in missing if gap["skill_id"] in covered_ids],
            "uncovered_gaps": uncovered,
        }

    @staticmethod
    def _step(course: dict, *, gap_ids: set[str]) -> dict:
        return {
            "course_id": course["course_id"],
            "title": course["title"],
            "provider": course["provider"],
            "url": course.get("url"),
            "cost": course.get("cost"),
            "currency": course.get("currency"),
            "duration_hours": course.get("duration_hours"),
            "difficulty": course.get("difficulty"),
            "rating": course.get("rating"),
            "skills": [
                {"skill_id": skill["skill_id"], "display_name": skill["display_name"]}
                for skill in course.get("skills_covered", [])
                if skill["skill_id"] in gap_ids
            ],
        }
