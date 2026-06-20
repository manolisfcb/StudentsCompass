# Optimization Methodology

## Purpose

The optimization engine recommends a learning route that improves a student's
readiness for a target role while respecting practical constraints: money, time,
and number of courses.

## Request Constraints

The MVP optimizer accepts:

- `budget`: maximum total course cost.
- `available_hours`: maximum total learning time.
- `max_courses`: maximum number of courses to recommend.

If a constraint is omitted, the optimizer treats it as open-ended while still
using the other constraints.

## Explainability Additions

Phase 2 now returns a short `route_summary` and each selected course includes:

- `sequence_order`: the recommended order in the route.
- `selection_reason`: a student-facing reason for why the course was selected.
- `covered_priority_skills`: the highest-priority gaps covered by the course.

These fields are deliberately computed in the backend so a future UI can render
the route consistently across web, mobile, or reports.

## Candidate Selection

The optimizer starts from the enriched gap analysis:

1. Read `missing_skills`.
2. Load active courses mapped to those missing skills.
3. Ignore inactive courses.
4. Group course-skill coverage by course.
5. Remove equivalent duplicate routes when courses cover the exact same skill
   set and another option has a better score/cost/time profile.

## Heuristic Objective

Current objective version: `heuristic_route_v1`.

Each course receives an optimization score based on:

- coverage of missing skills;
- role importance of each covered skill;
- course coverage strength;
- rating bonus when available;
- beginner/intermediate difficulty bonus for accessibility;
- cost penalty;
- duration penalty.

Simplified scoring:

```text
coverage_value = sum(skill_importance * course_skill_coverage)
optimization_score =
  coverage_value
  + rating_bonus
  + difficulty_bonus
  - cost_penalty
  - hours_penalty
```

Courses are selected greedily by best score, then lower cost, lower duration,
and stable title ordering. A selected course must add at least one newly covered
missing skill.

## Course Sequencing

After selection, courses are sequenced with a lightweight product rule:

1. Courses covering prerequisite-marked skills go earlier.
2. Beginner courses come before intermediate courses.
3. Intermediate courses come before advanced courses.
4. Higher optimization score breaks ties.
5. Shorter duration and stable title ordering make the result deterministic.

This is not a full dependency graph yet, but it gives the student a more usable
route than an unordered list.

## Constraint Handling

During selection, the optimizer rejects any course that would exceed:

- total budget;
- total available hours;
- maximum selected courses.

This makes the route predictable and product-safe for users who need an
actionable plan, not an unconstrained recommendation list.

## Projected Score

The response includes:

- `match_score_before`: the current overall readiness score, using semantic
  context when available.
- `projected_match_score_after`: estimated readiness after completing the
  selected courses.

Projection is calculated from the share of missing-skill importance covered by
the chosen route:

```text
remaining_gap = 1 - match_score_before
projected_gain = remaining_gap * covered_missing_importance / total_missing_importance
projected_match_score_after = match_score_before + projected_gain
```

The score is clamped to `1.0`.

## Persistence

Each optimization call writes an `optimization_runs` row with:

- user and resume;
- target role;
- budget, hours, and max course constraints;
- objective version;
- total projected score;
- total cost and hours;
- selected courses, covered skills, and remaining gaps in JSON fields.
- route summary in the JSON skill coverage field.

This creates a product audit trail for future UI history, analytics, and capstone
evidence.

The endpoint `GET /api/v1/capstone/learning-route/runs` exposes previous runs
for the authenticated user.

## OR-Tools Readiness

The service layer defines a `LearningRouteOptimizer` contract and ships
`HeuristicLearningRouteOptimizer` as the baseline implementation.

Phase 6 adds `ORToolsLearningRouteOptimizer` and `cp_sat_route_v1`. When
OR-Tools is installed, the capstone service selects the CP-SAT optimizer
automatically. If OR-Tools is unavailable, the service falls back to the
heuristic baseline instead of failing the user request.

The formal Phase 6 mathematical model is documented in
`phase_6_optimization_model.md`. The implemented CP-SAT cut covers the core
model: course-selection variables, covered/uncovered skill variables, aggregate
coverage thresholds, budget, available-hours, max-course constraints, weighted
skill-gap value, labor-market demand, critical-skill value, course quality,
cost/time penalties, redundancy penalty, uncovered-gap penalty, sequence
assignment variables, unique route positions, difficulty progression, and
prerequisite-skill ordering signals.

The synthetic Phase 6 evidence suite is documented in
`phase_6_validation_evidence.md`.

The heuristic should now be treated as the MVP baseline that the Phase 6
optimizer must beat or tie under the Phase 7 evaluation plan.

## Empty Route Behavior

If there are no missing skills or no active courses covering the gaps, the
endpoint returns a controlled empty route:

- no selected courses;
- no covered skills;
- remaining gaps preserved;
- no server error.

This matters for product trust: the system should admit when the catalog cannot
help yet instead of pretending to have a route.

## MVP Limitations

- It optimizes expected skill coverage, not verified skill acquisition.
- Prerequisite handling is currently a simple sequencing signal, not a hard
  dependency constraint.
- It does not yet personalize difficulty to the student's learning history.
- It does not yet balance employer demand trends beyond role skill importance.
