# Phase 4: Skill Extraction and Normalization

## Completion Status

Phase 4 is complete for the product MVP. The final closure, UI behavior,
operations runbook, and validation checklist are documented in
`phase_4_completion.md`.

## What Changed

Phase 4 separates skill extraction from the broader capstone analytics
orchestrator. `CapstoneAnalyticsService` still owns the resume, job-posting,
gap-analysis, and optimization workflows, but the text-to-skill conversion now
lives in dedicated services:

- `SkillNormalizer` centralizes text normalization and dictionary lookup keys.
- `SkillExtractionService` extracts known skills from resume and job text using
  the canonical skills catalog plus aliases.

The public API contract is unchanged. Existing resume and job-posting skill sync
endpoints keep returning the same response shape.

## Normalization Method

The normalizer lowercases text, removes punctuation that is not meaningful for
skills, keeps `+` and `#` for skills such as `C++` and `C#`, and collapses
repeated whitespace. Canonical names are converted to underscore form, for
example `Scikit Learn` becomes `scikit_learn`.

The lookup is built from:

- `skills.normalized_name`;
- `skills.display_name`;
- `skill_aliases.alias`.

Extraction sorts candidates by longest phrase first, then deduplicates by
`skill_id`. This lets a phrase such as `python programming` win over a shorter
`python` match while still storing one canonical resume or job skill.

## Manual Evaluation Sample

The reproducible baseline sample is covered by
`test_phase_4_manual_skill_extraction_sample_meets_baseline_quality` in
`tests/test_capstone_analytics_models.py`.

Sample inputs cover:

- resume text with Python, SQL, pandas, Tableau, and stakeholder wording;
- job text with PowerBI, Excel, KPI design, data wrangling, and presentation
  skills;
- business analyst text with Agile, requirements elicitation, and a `noSQL`
  false-positive guard.

Baseline metrics from the sample:

```text
true positives: 12
false positives: 0
false negatives: 2
precision: 1.00
recall: 0.86
```

## Evidence

Run:

```bash
uv run pytest tests/test_capstone_analytics_models.py
uv run pytest
```

The focused tests validate:

- alias lookup such as `powerbi` to `Power BI`;
- punctuation handling for `Python, SQL & Tableau`;
- symbol skills such as `C#` and `C++`;
- substring safety so `noSQL` does not extract `SQL`;
- deduplication and longest-alias priority;
- current resume and job-posting extraction endpoints.

## Limitations

This phase intentionally stays rule-based. It does not yet use an LLM to
discover unknown skills, infer implicit experience, grade proficiency, or
extract nuanced paragraph-level evidence spans.

The product hardening layer, including review statuses, manual additions,
expanded catalog coverage, dataset evidence, and the Career Lab review UI, is
covered in `phase_4_1_product_hardening.md` and `phase_4_completion.md`.
