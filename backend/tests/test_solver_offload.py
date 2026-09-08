"""CP-SAT runs in a thread now, and produces exactly what it produced before.

``solver.Solve`` is a C++ call that never yields, and the model is capped at
``max_time_in_seconds = 1``. So every optimisation froze the whole worker for up
to a second, plus however long building the model over the catalogue took —
long enough for a health check to time out behind it.

Two things have to hold at once: the event loop must stay responsive, and the
route must not change. The golden tests below re-solve the same models the
existing suite pins and compare the answers, because an optimiser that is fast
and wrong is worse than the one it replaced.
"""
from __future__ import annotations

import asyncio
import time

import pytest

from app.core.offload import BoundedOffload, OffloadRejected
from app.services.analytics.learningRouteOptimizerService import (
    SOLVER_MAX_QUEUED,
    SOLVER_MAX_WORKERS,
    LearningRouteConstraints,
    ORToolsLearningRouteOptimizer,
)

requires_ortools = pytest.mark.skipif(
    not ORToolsLearningRouteOptimizer.is_available(),
    reason="OR-Tools is not installed in this environment.",
)

TICK_INTERVAL = 0.01


def _skill(skill_id, *, importance, demand, gap, rank):
    return {
        "skill_id": skill_id,
        "normalized_name": skill_id,
        "display_name": skill_id.title(),
        "importance_score": importance,
        "market_demand_score": demand,
        "skill_gap_score": gap,
        "priority_rank": rank,
    }


def _course(course_id, *, cost, hours, difficulty, rating, skills):
    return {
        "course_id": course_id,
        "title": course_id.title(),
        "provider": "Test",
        "url": None,
        "cost": cost,
        "currency": "CAD",
        "duration_hours": hours,
        "difficulty": difficulty,
        "rating": rating,
        "optimization_score": 1.0,
        "skills_covered": [
            {
                "skill_id": skill_id,
                "normalized_name": skill_id,
                "display_name": skill_id.title(),
                "coverage_score": 0.9,
                "is_prerequisite": False,
            }
            for skill_id in skills
        ],
    }


GOLDEN_MISSING = {
    "python": _skill("python", importance=0.95, demand=1.0, gap=1.2, rank=1),
    "excel": _skill("excel", importance=0.4, demand=0.2, gap=0.3, rank=2),
}
GOLDEN_CANDIDATES = [
    _course("course-high", cost=50, hours=8, difficulty="intermediate", rating=4.8, skills=["python"]),
    _course("course-low", cost=10, hours=2, difficulty="beginner", rating=5.0, skills=["excel"]),
]


async def _measure_loop_lag(stop: asyncio.Event) -> float:
    worst = 0.0
    while not stop.is_set():
        started = time.perf_counter()
        await asyncio.sleep(TICK_INTERVAL)
        worst = max(worst, time.perf_counter() - started - TICK_INTERVAL)
    return worst


# ---------------------------------------------------------------------------
# The answer does not change
# ---------------------------------------------------------------------------


@requires_ortools
@pytest.mark.asyncio
async def test_the_offloaded_solve_returns_exactly_the_synchronous_solution(db_session):
    """Golden: same model, same selection, same objective, same coverage."""
    optimizer = ORToolsLearningRouteOptimizer(db_session)
    constraints = LearningRouteConstraints(budget=60, available_hours=10, max_courses=1)

    in_thread = await optimizer._solve_cp_sat_off_loop(
        candidates=GOLDEN_CANDIDATES,
        missing_by_id=GOLDEN_MISSING,
        constraints=constraints,
    )
    in_loop = optimizer._solve_cp_sat(
        candidates=GOLDEN_CANDIDATES,
        missing_by_id=GOLDEN_MISSING,
        constraints=constraints,
    )

    assert in_thread == in_loop
    assert in_thread["solver_status"] == "OPTIMAL"
    assert in_thread["selected_course_indexes"] == [0]
    assert in_thread["covered_skill_ids"] == {"python"}


@requires_ortools
@pytest.mark.asyncio
async def test_the_seed_still_makes_the_solve_reproducible(db_session):
    """random_seed = 42 is preserved, so repeated solves agree."""
    optimizer = ORToolsLearningRouteOptimizer(db_session)
    constraints = LearningRouteConstraints(budget=200, available_hours=40, max_courses=3)

    answers = [
        await optimizer._solve_cp_sat_off_loop(
            candidates=GOLDEN_CANDIDATES,
            missing_by_id=GOLDEN_MISSING,
            constraints=constraints,
        )
        for _ in range(5)
    ]
    assert all(answer == answers[0] for answer in answers)


@requires_ortools
def test_the_solver_limits_are_untouched():
    """max_time_in_seconds=1, one search worker, seed 42 — still the real bound."""
    import inspect

    source = inspect.getsource(ORToolsLearningRouteOptimizer._solve_cp_sat)
    assert "solver.parameters.max_time_in_seconds = 1" in source
    assert "solver.parameters.num_search_workers = 1" in source
    assert "solver.parameters.random_seed = 42" in source


# ---------------------------------------------------------------------------
# The loop stays responsive
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_slow_solve_does_not_stall_other_requests(db_session, monkeypatch):
    """A one-second solve must cost its own request, not the worker."""
    optimizer = ORToolsLearningRouteOptimizer(db_session)

    def slow_solve(_self, **_kwargs):
        time.sleep(1.0)
        return {
            "solver_status": "OPTIMAL",
            "objective_value": 1.0,
            "selected_course_indexes": [0],
            "sequence_positions": {0: 1},
            "covered_skill_ids": {"python"},
        }

    monkeypatch.setattr(ORToolsLearningRouteOptimizer, "_solve_cp_sat", slow_solve)

    stop = asyncio.Event()
    ticker = asyncio.create_task(_measure_loop_lag(stop))
    await asyncio.sleep(0.1)

    started = time.perf_counter()
    solution = await optimizer._solve_cp_sat_off_loop(
        candidates=GOLDEN_CANDIDATES,
        missing_by_id=GOLDEN_MISSING,
        constraints=LearningRouteConstraints(),
    )
    elapsed = time.perf_counter() - started

    stop.set()
    worst_lag = await ticker

    assert solution["solver_status"] == "OPTIMAL"
    assert elapsed >= 1.0
    assert worst_lag < 0.5, f"event loop blocked for {worst_lag:.3f}s"


@pytest.mark.asyncio
async def test_a_light_coroutine_finishes_while_a_solve_is_running(db_session, monkeypatch):
    optimizer = ORToolsLearningRouteOptimizer(db_session)
    def slow_solve(_self, **_kwargs):
        time.sleep(1.0)
        return {
            "solver_status": "UNKNOWN",
            "objective_value": 0.0,
            "selected_course_indexes": [],
            "sequence_positions": {},
            "covered_skill_ids": set(),
        }

    monkeypatch.setattr(ORToolsLearningRouteOptimizer, "_solve_cp_sat", slow_solve)

    solve = asyncio.create_task(
        optimizer._solve_cp_sat_off_loop(
            candidates=GOLDEN_CANDIDATES,
            missing_by_id=GOLDEN_MISSING,
            constraints=LearningRouteConstraints(),
        )
    )
    await asyncio.sleep(0.05)
    assert not solve.done()
    await solve


# ---------------------------------------------------------------------------
# Bounds and degradation
# ---------------------------------------------------------------------------


def test_the_solver_pool_bounds_are_stated_and_finite():
    assert 0 < SOLVER_MAX_WORKERS <= 8
    assert 0 <= SOLVER_MAX_QUEUED <= 64


@pytest.mark.asyncio
async def test_a_full_queue_answers_unknown_instead_of_queueing(db_session, monkeypatch):
    """UNKNOWN is CP-SAT's own word for "no answer within the limits"."""
    optimizer = ORToolsLearningRouteOptimizer(db_session)

    class _AlwaysFull:
        async def run(self, work, *, timeout):
            raise OffloadRejected(99, 10)

    monkeypatch.setattr(
        "app.services.analytics.learningRouteOptimizerService.SOLVER_OFFLOAD", _AlwaysFull()
    )
    solution = await optimizer._solve_cp_sat_off_loop(
        candidates=GOLDEN_CANDIDATES,
        missing_by_id=GOLDEN_MISSING,
        constraints=LearningRouteConstraints(),
    )

    assert solution["solver_status"] == "UNKNOWN"
    assert solution["selected_course_indexes"] == []
    assert solution["covered_skill_ids"] == set()


@pytest.mark.asyncio
async def test_a_timed_out_solve_answers_unknown(db_session, monkeypatch):
    optimizer = ORToolsLearningRouteOptimizer(db_session)

    class _AlwaysSlow:
        async def run(self, work, *, timeout):
            raise asyncio.TimeoutError

    monkeypatch.setattr(
        "app.services.analytics.learningRouteOptimizerService.SOLVER_OFFLOAD", _AlwaysSlow()
    )
    solution = await optimizer._solve_cp_sat_off_loop(
        candidates=GOLDEN_CANDIDATES,
        missing_by_id=GOLDEN_MISSING,
        constraints=LearningRouteConstraints(),
    )
    assert solution["solver_status"] == "UNKNOWN"


@requires_ortools
@pytest.mark.asyncio
async def test_an_unanswered_solve_surfaces_as_an_infeasible_route(db_session, monkeypatch):
    """The public contract: UNKNOWN becomes the existing infeasible payload."""
    optimizer = ORToolsLearningRouteOptimizer(db_session)
    monkeypatch.setattr(
        optimizer._heuristic,
        "_load_course_candidates",
        lambda **_kwargs: _coroutine(GOLDEN_CANDIDATES),
    )

    class _AlwaysFull:
        async def run(self, work, *, timeout):
            raise OffloadRejected(99, 10)

    monkeypatch.setattr(
        "app.services.analytics.learningRouteOptimizerService.SOLVER_OFFLOAD", _AlwaysFull()
    )

    payload = await optimizer.optimize(
        missing_skills=list(GOLDEN_MISSING.values()),
        match_score_before=0.5,
        constraints=LearningRouteConstraints(),
    )

    assert payload["solver_status"] == "UNKNOWN"
    assert payload["objective_version"] == "cp_sat_route_v1"
    assert payload["selected_courses"] == []
    assert {skill["skill_id"] for skill in payload["remaining_gaps"]} == set(GOLDEN_MISSING)
    assert payload["match_score_before"] == 0.5
    assert payload["projected_match_score_after"] == 0.5


async def _coroutine(value):
    return value


@pytest.mark.asyncio
async def test_the_session_never_crosses_into_the_worker_thread(db_session):
    """Only plain data may be handed to the pool."""
    import threading

    optimizer = ORToolsLearningRouteOptimizer(db_session)
    loop_thread = threading.get_ident()
    seen: dict = {}

    def spy(_self, **kwargs):
        seen["thread"] = threading.get_ident()
        seen["kwargs"] = set(kwargs)
        return {
            "solver_status": "OPTIMAL",
            "objective_value": 0.0,
            "selected_course_indexes": [],
            "sequence_positions": {},
            "covered_skill_ids": set(),
        }

    original = ORToolsLearningRouteOptimizer._solve_cp_sat
    try:
        ORToolsLearningRouteOptimizer._solve_cp_sat = spy
        await optimizer._solve_cp_sat_off_loop(
            candidates=GOLDEN_CANDIDATES,
            missing_by_id=GOLDEN_MISSING,
            constraints=LearningRouteConstraints(),
        )
    finally:
        ORToolsLearningRouteOptimizer._solve_cp_sat = original

    assert seen["thread"] != loop_thread, "the solve ran on the event loop thread"
    assert seen["kwargs"] == {"candidates", "missing_by_id", "constraints"}


@pytest.mark.asyncio
async def test_the_pool_releases_its_slots_after_a_burst():
    """A burst of solves must not leak capacity."""
    offload = BoundedOffload(max_workers=2, max_queued=4, thread_name_prefix="test-solver")

    async def one():
        return await offload.run(lambda: time.sleep(0.01) or "ok", timeout=5)

    assert await asyncio.gather(*[one() for _ in range(6)]) == ["ok"] * 6
    await asyncio.sleep(0.05)
    assert offload.in_flight == 0
