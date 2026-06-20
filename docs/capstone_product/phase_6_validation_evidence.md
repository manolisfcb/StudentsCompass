# Phase 6 Validation Evidence

## Purpose

This document records the synthetic evidence suite for the Phase 6 CP-SAT
optimizer. These tests are intentionally small and controlled. Their purpose is
to prove the mathematical behavior of the model before evaluating it on larger
catalog data in Phase 7.

The tested implementation is:

```text
objective_version = cp_sat_route_v1
optimizer = ORToolsLearningRouteOptimizer
```

## Why Synthetic Tests Matter

The full product catalog can make results harder to explain because many courses
share skills, costs, durations, and ratings. Synthetic cases isolate one model
property at a time. This makes the defense stronger because each test can be
mapped directly to one part of the mathematical formulation:

- objective value;
- budget constraint;
- time constraint;
- course-count constraint;
- redundancy penalty;
- skill coverage threshold;
- difficulty progression;
- prerequisite/foundation ordering.

## Evidence Cases

### 1. High-Value Gap Under Tight Course Count

Test:

```text
test_cp_sat_optimizer_prefers_high_value_gap_under_constraints
```

Setup:

- one high-value Python gap;
- one lower-value Excel gap;
- two feasible courses;
- `max_courses = 1`.

Expected result:

```text
selected_course_indexes = [0]
covered_skill_ids = {"skill-high"}
```

What it proves:

The optimizer does not choose by cheapest or highest rating alone. Under a
single-course limit, it selects the course that covers the higher weighted gap.

### 2. Budget, Hours, And Max-Course Feasibility

Test:

```text
test_cp_sat_optimizer_respects_budget_hours_and_course_count
```

Setup:

- one course violates budget;
- one course violates available hours;
- one course satisfies both;
- `budget = 50`;
- `available_hours = 10`;
- `max_courses = 1`.

Expected result:

```text
selected_course_indexes = [2]
covered_skill_ids = {"skill-high"}
```

What it proves:

The selected route is feasible. The solver rejects high-value courses when they
violate hard constraints.

### 3. Redundancy Avoidance

Test:

```text
test_cp_sat_optimizer_avoids_redundancy_when_distinct_gap_can_be_covered
```

Setup:

- two courses cover the same Python gap;
- one course covers a distinct Excel gap;
- `max_courses = 2`.

Expected result:

```text
selected_course_indexes in ({0, 2}, {1, 2})
covered_skill_ids = {"skill-high", "skill-low"}
```

What it proves:

The optimizer prefers breadth when a distinct gap can be covered. It avoids
selecting a redundant second Python course when Excel remains uncovered.

### 4. Difficulty Progression Inside The Solver

Test:

```text
test_cp_sat_optimizer_sequences_beginner_before_advanced_inside_solver
```

Setup:

- one advanced machine-learning course;
- one beginner Python foundation course;
- both courses are feasible and selected.

Expected result:

```text
sequence_positions[beginner_course] < sequence_positions[advanced_course]
```

What it proves:

Sequencing is now part of the CP-SAT model. The solver assigns route positions
that respect beginner-before-advanced progression.

### 5. Prerequisite/Foundation Signal Ordering

Test:

```text
test_cp_sat_optimizer_sequences_prerequisite_signal_before_same_difficulty_course
```

Setup:

- two intermediate courses;
- one course covers a skill marked with `is_prerequisite = true`;
- one course covers a non-prerequisite reporting skill;
- both courses are feasible and selected.

Expected result:

```text
sequence_positions[prerequisite_course] < sequence_positions[reporting_course]
```

What it proves:

The solver uses prerequisite-skill signals to place foundation courses earlier
when difficulty does not conflict.

## Endpoint Regression Evidence

Test:

```text
test_capstone_learning_route_optimization_respects_constraints_and_persists_run
```

What it proves:

- the API returns `cp_sat_route_v1` when OR-Tools is available;
- selected courses respect budget, hours, and max-course constraints;
- route explanations are present;
- `solver_status`, `objective_value`, and `model_explanation` are preserved in
  the optimization run payload.

## Run Commands

Focused Phase 6 validation:

```bash
uv run pytest tests/test_capstone_analytics_models.py -k "learning_route_optimization or cp_sat_optimizer"
```

Full capstone analytics validation:

```bash
uv run pytest tests/test_capstone_analytics_models.py
```

## Current Evidence Result

Latest focused run:

```text
8 passed, 24 deselected
```

This includes the endpoint regression test plus the five synthetic CP-SAT
behavior tests.

## Remaining Evidence For Phase 7

The next evidence layer should evaluate CP-SAT against baselines:

- cheapest feasible route;
- highest-rated feasible route;
- current heuristic route;
- semantic-only route;
- random feasible route.

Phase 7 should compare weighted skill coverage, critical-skill coverage,
projected readiness gain, cost, hours, redundancy rate, runtime, and explanation
completeness.

