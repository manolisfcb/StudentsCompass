# Phase 7: Baseline Evaluation

## Purpose

Phase 7 evaluates the StudentsCompass CP-SAT learning-route optimizer against
simple, reproducible baselines.

The academic claim is:

```text
The CP-SAT optimizer produces a feasible learning route that improves weighted
skill-gap coverage and critical-skill coverage under practical student
constraints, while remaining explainable and reproducible.
```

This phase does not replace the production optimizer. It adds an evidence layer
that runs several methods on the same missing skills, candidate courses, budget,
available hours, and max-course constraint.

## Implementation

The implementation lives in:

```text
app/services/analytics/learningRouteBaselineEvaluationService.py
```

Evaluation version:

```text
phase_7_baseline_eval_v1
```

Endpoint:

```text
POST /api/v1/capstone/learning-route/evaluate-baselines
```

The endpoint accepts the same request shape as the optimizer endpoint:

```json
{
  "resume_id": "...",
  "target_role": "Data Analyst",
  "budget": 100,
  "available_hours": 30,
  "max_courses": 2
}
```

It runs the existing gap-analysis pipeline first, then evaluates every method
against the same priority missing skills and active course catalog.

## Compared Methods

### Cheapest Feasible

Objective version:

```text
baseline_cheapest_feasible_v1
```

Greedy method that selects the lowest-cost feasible courses that add new gap
coverage.

### Highest Rated Feasible

Objective version:

```text
baseline_highest_rated_feasible_v1
```

Greedy method that selects the highest-rated feasible courses that add new gap
coverage.

### Similarity Only

Objective version:

```text
baseline_similarity_only_v1
```

Greedy method that prioritizes skill coverage strength and gap value. Cost and
hours are only treated as hard constraints.

### Heuristic Route

Objective version:

```text
heuristic_route_v1
```

Existing MVP optimizer from the earlier product phase.

### Random Feasible Seeded

Objective version:

```text
baseline_random_feasible_seeded_v1
```

Seeded random feasible selection. The fixed seed is:

```text
42
```

This creates a reproducible lower-control baseline.

### CP-SAT Route

Objective version:

```text
cp_sat_route_v1
```

The formal optimizer from Phase 6. It maximizes weighted gap coverage while
penalizing cost, time, redundancy, and uncovered gaps under the same
constraints.

## Metrics

Every method returns the same metrics:

- `weighted_skill_coverage`
- `critical_skill_coverage`
- `covered_skills_count`
- `remaining_gaps_count`
- `selected_courses_count`
- `total_cost`
- `total_hours`
- `score_per_dollar`
- `score_per_hour`
- `redundancy_rate`
- `constraint_satisfaction`
- `projected_readiness_gain`
- `runtime_ms`
- `explanation_completeness`

## Metric Definitions

`weighted_skill_coverage` measures the share of total missing-skill gap weight
covered by the route. A skill is counted as covered when aggregate course
coverage reaches the Phase 6 threshold:

```text
critical skill threshold = 0.85
non-critical skill threshold = 0.70
```

`critical_skill_coverage` measures the share of critical missing skills covered.
A skill is critical when importance is at least `0.85` or priority rank is in
the top three.

`redundancy_rate` measures extra aggregate coverage above `1.0` as a share of
all selected coverage.

`constraint_satisfaction` is `1.0` when selected cost, selected hours, and
selected course count satisfy the supplied constraints.

`projected_readiness_gain` reuses the existing route projection calculation so
all methods are compared on the same readiness scale.

`explanation_completeness` is `1.0` when the method explanation exists and each
selected course includes enough course-skill context to explain why it was
selected. Empty routes can still receive `1.0` if the method explains why no
course was selected.

## Winner Selection

The winner summary ranks feasible methods by:

1. constraint satisfaction;
2. weighted skill coverage;
3. critical skill coverage;
4. projected readiness gain;
5. lower redundancy;
6. lower cost;
7. lower hours.

This ranking intentionally puts feasibility and learning value before price.
Cost and hours break ties after the route proves it closes important gaps.

## Validation Evidence

Focused validation command:

```bash
uv run pytest tests/test_capstone_analytics_models.py -k "phase_7 or learning_route_optimization or cp_sat_optimizer"
```

Latest focused result:

```text
4 passed, 32 deselected
```

Latest full capstone analytics result:

```text
36 passed
```

The Phase 7-specific tests are:

- `test_phase_7_baseline_evaluation_endpoint_compares_all_methods`
- `test_phase_7_cp_sat_beats_cheapest_on_weighted_critical_coverage`
- `test_phase_7_cp_sat_reduces_similarity_only_redundancy_and_cost`
- `test_phase_7_random_baseline_is_reproducible`

The synthetic comparison proves that CP-SAT can reject the cheapest course when
the cheapest path covers only a low-value support skill and a feasible
higher-value course covers the critical gap.

The redundancy comparison proves that CP-SAT can choose a lower-cost,
lower-overlap route while matching the coverage of a similarity-only baseline.

The reproducibility test proves that the random feasible baseline is stable
under seed `42`, so repeated evidence runs can be compared fairly.

## Response Contract

The endpoint returns:

```json
{
  "status": "ok",
  "resume_id": "...",
  "target_role": "Data Analyst",
  "match_score_before": 0.42,
  "evaluation_version": "phase_7_baseline_eval_v1",
  "baseline_seed": 42,
  "constraints": {
    "budget": 100,
    "available_hours": 30,
    "max_courses": 2
  },
  "methods": [
    {
      "method": "cp_sat_route_v1",
      "objective_version": "cp_sat_route_v1",
      "solver_status": "OPTIMAL",
      "metrics": {
        "weighted_skill_coverage": 0.82,
        "critical_skill_coverage": 1.0,
        "covered_skills_count": 4,
        "remaining_gaps_count": 2,
        "selected_courses_count": 2,
        "total_cost": 85,
        "total_hours": 12,
        "score_per_dollar": 0.0096,
        "score_per_hour": 0.0683,
        "redundancy_rate": 0.0,
        "constraint_satisfaction": 1.0,
        "projected_readiness_gain": 0.24,
        "runtime_ms": 8.2,
        "explanation_completeness": 1.0
      },
      "selected_courses": [],
      "explanation": "..."
    }
  ],
  "winner_summary": {
    "best_method": "cp_sat_route_v1",
    "best_objective_version": "cp_sat_route_v1",
    "summary": "..."
  }
}
```

The numeric values above are illustrative. The actual values depend on the
resume, target role, active course catalog, and constraints.

## Representative Scenario Matrix

Use this matrix when generating final capstone evidence:

| Scenario | Target role | Budget | Hours | Max courses | Expected comparison pressure |
|---|---:|---:|---:|---:|---|
| Low budget | Data Analyst | 40 | 30 | 2 | Cheapest baseline should be competitive on cost, CP-SAT should protect critical coverage. |
| Low time | Data Analyst | 150 | 8 | 2 | CP-SAT should avoid long courses and prioritize high-value gaps. |
| Balanced | Data Analyst | 100 | 30 | 3 | CP-SAT should improve or tie weighted coverage while controlling redundancy. |
| Role variation | Business Analyst | 100 | 25 | 3 | Confirms the evaluator is not tied to one role seed. |
| Hard constraints | Junior Data Scientist | 25 | 5 | 1 | Demonstrates controlled empty or partial-route behavior. |

For each scenario, record the method table:

```text
Method                 Weighted   Critical   Cost   Hours   Redundancy   Gain   Feasible
cheapest_feasible      ...
highest_rated_feasible ...
similarity_only        ...
heuristic_route_v1     ...
random_feasible_seeded ...
cp_sat_route_v1        ...
```

## Step-By-Step Evidence Runbook

Use this runbook to generate the final Phase 7 evidence tables.

### 1. Prepare The Database

Run migrations so the capstone analytics tables exist:

```bash
uv run alembic upgrade head
```

Seed the minimum capstone catalog from an authenticated admin session:

```text
POST /api/v1/capstone/analytics/seed
```

Then confirm the catalog is ready:

```text
GET /api/v1/capstone/analytics/status
```

Minimum readiness checks:

- `schema_ready` should be `true`.
- `catalog_ready` should be `true`.
- `courses_count` should be greater than `0`.
- `role_seed_requirements_count` should be greater than `0`.

### 2. Choose Evidence Resumes

Pick 3-5 resumes that represent different readiness levels.

Recommended set:

- one resume already strong in Python/SQL;
- one resume with mostly business or communication skills;
- one resume with very few target-role skills;
- one resume aimed at Business Analyst;
- one resume aimed at Junior Data Scientist.

Each resume needs a valid `resume_id` and enough `ai_summary` text for skill
extraction.

### 3. Sync Or Review Resume Skills

For each resume, sync detected skills from the resume summary:

```text
POST /api/v1/capstone/resumes/{resume_id}/skills/sync
```

Review detected skills:

```text
GET /api/v1/capstone/resumes/{resume_id}/skills
```

If needed, confirm or reject a detected skill:

```text
PATCH /api/v1/capstone/resumes/{resume_id}/skills/{resume_skill_id}
```

Example body:

```json
{
  "status": "confirmed"
}
```

If a real skill is missing, add it manually:

```text
POST /api/v1/capstone/resumes/{resume_id}/skills/manual
```

Example body:

```json
{
  "normalized_name": "python",
  "evidence_text": "Portfolio project with pandas and SQL",
  "source_section": "student_review"
}
```

### 4. Confirm Gap Analysis

Before running baseline evaluation, inspect the gap payload:

```text
GET /api/v1/capstone/gap-analysis?resume_id={resume_id}&target_role=Data%20Analyst
```

Check:

- `status` is `ok`;
- `priority_missing_skills` is not empty for comparison scenarios;
- `overall_readiness_score` is present;
- `market_signals.source` is either `role_seed` or `job_postings`;
- `recommended_courses` is populated when the catalog covers gaps.

If `priority_missing_skills` is empty, keep the case only if you want to show
the controlled no-route behavior.

### 5. Run Baseline Evaluation

Call the Phase 7 endpoint:

```text
POST /api/v1/capstone/learning-route/evaluate-baselines
```

Example body:

```json
{
  "resume_id": "REPLACE_WITH_RESUME_ID",
  "target_role": "Data Analyst",
  "budget": 100,
  "available_hours": 30,
  "max_courses": 3
}
```

Repeat this for each scenario in the representative scenario matrix.

### 6. Save The Raw Payload

For each run, save the full JSON response before summarizing it.

Recommended filename pattern:

```text
docs/capstone_product/evidence/phase_7_{scenario_slug}.json
```

Examples:

```text
docs/capstone_product/evidence/phase_7_low_budget_data_analyst.json
docs/capstone_product/evidence/phase_7_low_time_data_analyst.json
docs/capstone_product/evidence/phase_7_business_analyst.json
```

The raw JSON matters because the final table is a summary, while the JSON is the
reproducible evidence trail.

### 7. Build The Method Table

For each method in `methods`, copy these fields:

- `method`
- `metrics.weighted_skill_coverage`
- `metrics.critical_skill_coverage`
- `metrics.total_cost`
- `metrics.total_hours`
- `metrics.redundancy_rate`
- `metrics.projected_readiness_gain`
- `metrics.constraint_satisfaction`
- `metrics.explanation_completeness`

Use this Markdown table:

```text
| Method | Weighted coverage | Critical coverage | Cost | Hours | Redundancy | Gain | Feasible | Explainability |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| cheapest_feasible |  |  |  |  |  |  |  |  |
| highest_rated_feasible |  |  |  |  |  |  |  |  |
| similarity_only |  |  |  |  |  |  |  |  |
| heuristic_route_v1 |  |  |  |  |  |  |  |  |
| random_feasible_seeded |  |  |  |  |  |  |  |  |
| cp_sat_route_v1 |  |  |  |  |  |  |  |  |
```

### 8. Write The Scenario Interpretation

Under each table, write 3-5 sentences:

- Which method won by `winner_summary.best_method`.
- Whether CP-SAT improved weighted coverage or critical coverage.
- Whether CP-SAT reduced cost, hours, or redundancy when coverage tied.
- Any tradeoff where a baseline was cheaper but covered less important skills.
- Any limitation caused by the current catalog.

Suggested template:

```text
In this scenario, {best_method} produced the strongest route under the supplied
constraints. CP-SAT {improved/tied} weighted coverage and {improved/tied}
critical-skill coverage compared with the strongest baseline. The main tradeoff
was {cost/time/redundancy}. This supports the Phase 7 claim because the route is
feasible, explainable, and prioritizes high-value missing skills.
```

### 9. Validate The Evidence Suite

After adding tables and raw JSON files, rerun the focused tests:

```bash
uv run pytest tests/test_capstone_analytics_models.py -k "phase_7"
```

Then run the full capstone analytics suite:

```bash
uv run pytest tests/test_capstone_analytics_models.py
```

Current expected result for the full suite:

```text
36 passed
```

### 10. Final Phase 7 Checklist

Phase 7 is ready for the final capstone writeup when:

- at least 3 representative scenarios have raw JSON evidence;
- each scenario has a Markdown method table;
- each scenario has a short interpretation paragraph;
- CP-SAT is compared against all five baselines;
- tests pass with `36 passed`;
- limitations are stated clearly instead of hidden.

## Evidence Interpretation Guide

Use these rules when interpreting a table:

- CP-SAT wins clearly when it has higher weighted or critical coverage under the
  same constraints.
- CP-SAT still supports the academic claim when it ties coverage but reduces
  cost, hours, or redundancy.
- A cheapest baseline can win score-per-dollar on narrow cases; this should be
  described as a cost-efficiency tradeoff, not a failure of optimization.
- A similarity-only route can look strong on coverage but should be checked for
  redundant overlap and practical feasibility.
- Random feasible results are only a reproducibility/control baseline.

## Current Limitations

- The random baseline is intentionally simple and should not be interpreted as a
  serious recommendation strategy.
- Runtime is measured inside the application process and should be used for
  relative local comparison, not infrastructure benchmarking.
- The current endpoint computes evaluation evidence on demand and does not
  persist baseline runs.
- Salary impact remains out of scope until reliable salary-skill data exists.

## Next Step

Use the endpoint with several representative resumes and target roles, then
copy the resulting method table into the final capstone evidence section.
