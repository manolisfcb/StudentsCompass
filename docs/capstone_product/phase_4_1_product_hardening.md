# Phase 4.1: Product Hardening for Skill Extraction

## What Changed

Phase 4.1 turns the rule-based skill extractor into a product-ready MVP
foundation:

- expanded the capstone skill catalog from 25 to 117 canonical skills;
- added review status to resume skills: `detected`, `confirmed`, `rejected`,
  and `manual`;
- added student-owned API flows to list, confirm, reject, manually add, and
  delete resume skills;
- added Career Lab UI controls for reviewing, correcting, and manually adding
  resume skills;
- updated gap analysis so rejected skills are excluded and manual/confirmed
  skills are preferred;
- added aggregate dataset evaluation against the local resume CSV.

## Dataset Evidence

The local resume dataset includes `data/resumes 3/Resume/Resume.csv`, which
contains extracted text and category labels. The evaluator reads this CSV and
outputs only aggregate skill counts; it does not persist resume text.

Command:

```bash
uv run python scripts/evaluate_resume_skill_extraction.py --output /tmp/phase_4_1_resume_skill_summary.json
```

Observed aggregate run:

```text
resumes_scanned: 2484
resumes_with_skills: 2444
coverage_ratio: 0.9839
categories: 24
```

Versioned evidence:

- `docs/capstone_product/evidence/phase_4_1_resume_skill_summary.json`

Top extracted skills by resume count:

```text
Communication: 1313
Sales: 1311
Customer Service: 1029
Leadership: 1026
Excel: 1018
Project Management: 680
Accounting: 576
Problem Solving: 516
Time Management: 420
Quality Assurance: 385
```

## Product Behavior

Detected skills are now treated as reviewable evidence:

- `detected`: extracted automatically from resume text;
- `confirmed`: student reviewed and accepted the detected skill;
- `rejected`: student rejected the skill; excluded from matching;
- `manual`: student manually added the skill; preferred in matching.

This prevents one bad extraction from silently influencing readiness scores or
learning-route recommendations.

## Career Lab UI

The Career Lab now includes a review panel between analytics readiness and the
readiness metrics.

The panel shows:

- detected, confirmed, manual, and rejected skill counts;
- each resume skill with display name, status, and evidence text;
- actions to confirm, reject, or remove a skill;
- a manual skill form that adds known catalog skills to the selected resume.

When a student edits skills after running a gap analysis, the page refreshes the
analysis for the selected resume without re-running extraction. This keeps
student corrections intact while updating readiness scores and recommendations.

## API Contract

New student-owned endpoints:

```text
GET    /api/v1/capstone/resumes/{resume_id}/skills
PATCH  /api/v1/capstone/resumes/{resume_id}/skills/{resume_skill_id}
POST   /api/v1/capstone/resumes/{resume_id}/skills/manual
DELETE /api/v1/capstone/resumes/{resume_id}/skills/{resume_skill_id}
```

`PATCH` accepts:

```json
{
  "status": "confirmed"
}
```

or:

```json
{
  "status": "rejected"
}
```

Manual add accepts either a `skill_id` or a `normalized_name` from the catalog.

## Validation

Focused validation:

```bash
uv run pytest tests/test_capstone_analytics_models.py
```

UI and full validation:

```bash
node --check app/static/js/career_lab.js
uv run pytest tests/test_career_lab_view.py tests/test_capstone_analytics_models.py
uv run pytest
```

Covered scenarios:

- expanded seed catalog remains idempotent;
- aliases and symbol skills still normalize correctly;
- dataset evaluator returns aggregate counts without resume text;
- students can confirm, reject, add, and delete their own resume skills;
- students cannot modify another user's resume skills;
- rejected skills do not affect gap analysis;
- existing extraction, gap-analysis, and route-optimization flows still pass.
- Career Lab renders the review panel for authenticated students.

## Limitations

The extractor is still intentionally rule-based. It has strong coverage for
explicit skills, but it does not infer implicit experience or use LLMs to
extract nuanced evidence spans.

The review UI is now implemented. The next meaningful steps are product QA with
seeded demo users, more target role profiles, more active learning resources,
and optional semantic or LLM-assisted evidence extraction.
