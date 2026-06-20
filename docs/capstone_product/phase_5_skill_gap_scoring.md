# Phase 5: Skill Gap Scoring

## What Changed

Phase 5 turns the existing gap analysis into an explicit scoring layer. Instead
of treating every missing skill as equally important, StudentsCompass now ranks
gaps by the weight of the role requirement minus any student evidence already
found.

The scoring logic lives in:

- `SkillGapScoringService`
- `CapstoneAnalyticsService.analyze_gap`
- `HeuristicLearningRouteOptimizer`

The API remains backward-compatible. Existing consumers can keep using
`priority_score`, while newer consumers can read the more explicit Phase 5
fields:

- `required_skill_weight`
- `student_skill_evidence`
- `skill_gap_score`

## Scoring Method

For each missing required skill:

```text
required_skill_weight =
  role_importance * (1 + market_demand_score * 0.35)
```

```text
student_skill_evidence =
  weak_semantic_similarity * 0.35
```

```text
skill_gap_score =
  required_skill_weight * (1 - student_skill_evidence)
```

Exact and strong semantic matches are already counted as matched skills, so
Phase 5 primarily scores remaining missing skills. Weak matches reduce the gap
but do not remove it, which lets the product say: "there is some transferable
evidence, but this still needs work."

`priority_score` is now an alias for `skill_gap_score` to preserve the current
Career Lab UI contract.

## Product Behavior

The gap analysis response now ranks missing skills by `skill_gap_score`.
Course recommendations and learning-route optimization also use this score
when choosing which gaps to cover first.

This makes recommendations more defensible because a course covering a
high-demand, high-importance missing skill is preferred over one covering a
lower-value gap.

## API Example

```json
{
  "normalized_name": "tableau",
  "display_name": "Tableau",
  "importance_score": 0.8,
  "market_demand_score": 1.0,
  "required_skill_weight": 1.08,
  "student_skill_evidence": 0.0,
  "skill_gap_score": 1.08,
  "priority_score": 1.08,
  "priority_rank": 1,
  "reason": "Tableau has a required-skill weight of 1.08 and appears in 2 synced market posting(s) for this role."
}
```

## Validation

Focused validation:

```bash
uv run pytest tests/test_capstone_analytics_models.py
```

Covered scenarios:

- required skill weight combines role importance and market demand;
- weak semantic evidence lowers but does not remove a gap;
- `priority_score` remains compatible with the UI;
- the gap-analysis endpoint exposes Phase 5 scoring fields;
- learning-route optimization consumes priority gaps.

## Limitations

The current score uses internal job-posting demand only. It does not yet include
external labor-market frequency, salary impact, seniority, or academic
criticality as separate calibrated inputs. Those are the next natural additions
once broader market data is available.
