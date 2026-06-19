# Phase 2 Plan: Matching Intelligence and Learning Route Optimization

## Product Goal

Phase 2 turns the Phase 1 analytical foundation into a decision engine for
StudentsCompass. The product should move beyond "these skills are missing" and
answer a more valuable student question: "how close am I to this role, what
matters most, and what learning route should I take under my constraints?"

This phase is backend/API first. The existing Career Lab UI can keep consuming
the compatible gap analysis response while richer fields become available for a
future UI pass.

## Implemented Scope

- Semantic gap analysis contract through `analysis_version = "semantic_gap_v1"`.
- Exact skill matches kept as the highest-confidence signal.
- Semantic matches added when `EMBEDDINGS_PROVIDER=local` reports semantic
  readiness.
- Deep context matching compares the full resume context against the target role
  and job-posting context when semantic embeddings are available.
- Safe fallback when the local embedding provider fails; gap analysis still
  returns a controlled payload instead of a 500.
- Enriched gap analysis fields:
  - `match_score`
  - `overall_readiness_score`
  - `semantic_score`
  - `context_similarity_score`
  - `context_match_level`
  - `semantic_context_ready`
  - `exact_match_count`
  - `semantic_match_count`
  - `weak_match_count`
  - `priority_gap_score`
  - `semantic_matched_skills`
  - `weak_matched_skills`
- Learning route optimization endpoint:
  - `POST /api/v1/capstone/learning-route/optimize`
- Learning route history endpoint:
  - `GET /api/v1/capstone/learning-route/runs`
- Catalog quality endpoint:
  - `GET /api/v1/capstone/catalog/quality`
- Heuristic route optimizer:
  - filters active courses;
  - considers courses covering missing skills;
  - scores courses by coverage, importance, cost, duration, difficulty, and
    rating;
  - respects `budget`, `available_hours`, and `max_courses`;
  - avoids equivalent duplicated coverage when a better cost-benefit option
    exists.
- Product polish signals:
  - priority-ranked missing skills;
  - gap insights for readiness, priority gaps, semantic matches, and market
    signals;
  - market demand counts and demand score per required skill when synced job
    postings exist;
  - selected-course reasons and sequence order;
  - route summary persisted with each optimization run.
- Embedding operations signals:
  - local provider configuration;
  - local package availability;
  - fallback provider;
  - process-local fallback counters;
  - production recommendation for semantic readiness.
- Optimization run persistence in `optimization_runs`.
- Internal optimizer contract prepared for a future OR-Tools implementation.

## API Contract

### Gap Analysis

`GET /api/v1/capstone/gap-analysis`

The endpoint remains backward-compatible with the Phase 1 payload and now
includes richer matching fields. Existing consumers can keep reading
`current_skills`, `required_skills`, `missing_skills`, `coverage_ratio`, and
`recommended_courses`.

The enriched response also includes `priority_missing_skills`, `gap_insights`,
and `market_signals`. These are intended for the future product UI so the
student sees not only what is missing, but why it matters.

When semantic embeddings are ready, the response also includes a context-level
comparison between the resume summary plus extracted evidence and the target
role context built from required skills and synced job postings.

### Learning Route Optimization

`POST /api/v1/capstone/learning-route/optimize`

Minimum request:

```json
{
  "resume_id": "uuid",
  "target_role": "Data Analyst",
  "budget": 150,
  "available_hours": 40,
  "max_courses": 4
}
```

Minimum response:

```json
{
  "status": "ok",
  "optimization_run_id": "uuid",
  "objective_version": "heuristic_route_v1",
  "target_role": "Data Analyst",
  "match_score_before": 0.58,
  "projected_match_score_after": 0.82,
  "total_cost": 120,
  "total_hours": 35,
  "selected_courses": [],
  "covered_skills": [],
  "remaining_gaps": []
}
```

### Learning Route History

`GET /api/v1/capstone/learning-route/runs`

Returns the authenticated student's previous optimization runs. This supports
future product history, auditability, and capstone evidence.

### Catalog Quality

`GET /api/v1/capstone/catalog/quality`

Returns catalog maturity signals such as skill count, course count, metadata
completeness, mapped course ratio, market-backed role count, and recommended
next actions. This prevents the product from treating a seed catalog as
production-ready.

## Product Connection

For StudentsCompass as a real product, this phase creates the backend needed for
a premium career-planning workflow:

- students can understand readiness for a target role;
- the platform can explain why a gap matters;
- recommendations can be constrained by time and budget;
- routes can explain why each course was selected;
- previous optimization runs can be retrieved for comparison;
- catalog readiness can be measured before presenting the optimizer as a
  production-grade advisor;
- future UI can show a credible roadmap instead of a static list of courses;
- admin/market data can gradually replace seed requirements without changing
  the student-facing contract.

## Acceptance Evidence

- Capstone analytics tests cover semantic matching separation, deep context
  matching, fallback behavior, enriched gap payload compatibility, market
  signals, catalog quality, optimization constraints, persistence, route
  history, selected-course explanations, privacy, and empty-route behavior.
- Required validation commands:

```bash
uv run pytest tests/test_capstone_analytics_models.py
uv run pytest
```

## Limitations

- Semantic matching is only real when the local sentence-transformers provider
  is available and configured.
- The default hash embedding provider remains deterministic but is not semantic.
- Embedding fallback counters are process-local; production monitoring should
  export these to logs or metrics.
- Course selection is heuristic; it is product-safe for MVP, but not a formal
  mathematical optimum.
- Match projection estimates improvement from covered missing skills; it does
  not yet verify actual learning completion or post-course assessment.
- Market demand only reflects synced internal job postings; it is not yet a
  broad Canadian labor-market index.
- Course sequencing is rule-based by prerequisites, difficulty, and score; it
  is not yet a full prerequisite graph solver.
- Catalog quality is measured, but the seed catalog still needs manual curation
  before a commercial launch.
- UI/UX polish is intentionally deferred until the backend contract stabilizes.
