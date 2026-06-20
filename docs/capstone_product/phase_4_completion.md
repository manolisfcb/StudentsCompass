# Phase 4 Completion: Skill Extraction Productization

## Status

Phase 4 is complete for product MVP scope.

The delivered scope covers:

- rule-based skill extraction from resumes and job postings;
- centralized skill normalization and alias matching;
- expanded seed catalog for product coverage;
- resume skill review statuses and student correction workflow;
- Career Lab UI for reviewing detected skills;
- aggregate evaluation over the local resume dataset;
- migrations, seed script, tests, and operating runbook.

## Product Outcome

StudentsCompass can now turn an uploaded resume into a reviewable skill profile.
The student can inspect detected skills, confirm correct ones, reject false
positives, manually add missing catalog skills, and then run gap analysis and
learning-route recommendations from the corrected profile.

This closes the main product risk from earlier phases: a wrong extraction no
longer silently drives readiness scores or course recommendations.

## Delivered Files

Core extraction services:

- `app/services/analytics/skillNormalizer.py`
- `app/services/analytics/skillExtractionService.py`
- `app/services/analytics/resumeSkillDatasetEvaluator.py`

Capstone orchestration and contracts:

- `app/services/analytics/capstoneAnalyticsService.py`
- `app/services/analytics/capstoneAnalyticsSeedService.py`
- `app/routes/capstoneAnalyticsRoute.py`
- `app/schemas/capstoneAnalyticsSchema.py`
- `app/models/skillModel.py`

Database migrations:

- `alembic/versions/d3e4f5a6b7c8_add_resume_skill_review_status.py`
- `alembic/versions/c7d8e9f0a1b2_add_resume_embeddings_hnsw_index.py`
- `alembic/versions/e4f6a7b8c9d0_merge_capstone_review_and_embedding_heads.py`

Career Lab UI:

- `app/templates/career_lab.html`
- `app/static/js/career_lab.js`
- `app/static/css/career_lab.css`

Operations and evidence:

- `scripts/seed_capstone_analytics.py`
- `scripts/evaluate_resume_skill_extraction.py`
- `docs/capstone_product/evidence/phase_4_1_resume_skill_summary.json`

Tests:

- `tests/test_capstone_analytics_models.py`
- `tests/test_career_lab_view.py`
- `tests/test_embedding_service.py`

## API Surface

Existing endpoints preserved:

```text
POST /api/v1/capstone/resumes/{resume_id}/skills/extract
POST /api/v1/capstone/resumes/{resume_id}/skills/sync
POST /api/v1/capstone/job-postings/{job_posting_id}/skills/sync
POST /api/v1/capstone/job-postings/skills/sync-open
```

New student-owned review endpoints:

```text
GET    /api/v1/capstone/resumes/{resume_id}/skills
PATCH  /api/v1/capstone/resumes/{resume_id}/skills/{resume_skill_id}
POST   /api/v1/capstone/resumes/{resume_id}/skills/manual
DELETE /api/v1/capstone/resumes/{resume_id}/skills/{resume_skill_id}
```

Admin/operations endpoint:

```text
POST /api/v1/capstone/analytics/seed
```

## Review Status Semantics

Resume skill statuses are:

- `detected`: extracted automatically from resume text;
- `confirmed`: accepted by the student and preferred by matching;
- `rejected`: excluded from matching and recommendations;
- `manual`: added by the student and preferred by matching.

Gap analysis uses active skills only, so rejected skills do not affect readiness
or learning-route output.

## UI Behavior

The Career Lab now includes a review panel above readiness metrics.

The panel:

- loads the selected resume's current skill review set;
- shows counts for detected, confirmed, manual, and rejected skills;
- renders each skill with evidence text and status;
- supports confirm, reject, remove, and manual add actions;
- refreshes the gap analysis after a review change when an analysis is already
  active for the selected resume.

## Dataset Evidence

The local dataset evaluation uses `data/resumes 3/Resume/Resume.csv` and stores
only aggregate counts.

Latest versioned evidence:

```text
resumes_scanned: 2484
resumes_with_skills: 2444
coverage_ratio: 0.9839
categories: 24
```

Top extracted skills:

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

Evidence file:

```text
docs/capstone_product/evidence/phase_4_1_resume_skill_summary.json
```

## Operational Runbook

Apply migrations:

```bash
uv run alembic upgrade head
```

Seed the capstone analytics catalog:

```bash
uv run python scripts/seed_capstone_analytics.py
```

Evaluate aggregate resume dataset coverage:

```bash
uv run python scripts/evaluate_resume_skill_extraction.py --output docs/capstone_product/evidence/phase_4_1_resume_skill_summary.json
```

Validate the current catalog status from the app service:

```bash
uv run python -c "exec('''import asyncio
from app.db import async_session
from app.services.analytics.capstoneAnalyticsService import CapstoneAnalyticsService
async def main():
    async with async_session() as session:
        service = CapstoneAnalyticsService(session)
        print(await service.get_analytics_status())
asyncio.run(main())
''')"
```

Expected minimum readiness:

```text
schema_ready: True
catalog_ready: True
skills_count: 117
aliases_count: 158
courses_count: 12
course_skills_count: 29
role_seed_requirements_count: 28
```

## Validation

Final verification commands:

```bash
node --check app/static/js/career_lab.js
uv run pytest tests/test_career_lab_view.py tests/test_capstone_analytics_models.py
uv run pytest
git diff --check
```

Latest full-suite result:

```text
148 passed, 1 skipped
```

## Known Limitations

Phase 4 remains rule-based by design. It extracts explicit known skills from the
catalog and aliases, but it does not infer implicit skills, grade proficiency,
or use an LLM to summarize nuanced evidence spans.

The next product step is not another extraction refactor. The next meaningful
hardening step is production QA: browser walkthroughs with seeded demo users,
more curated course resources, more target role profiles, and optional semantic
or LLM-assisted evidence extraction once the baseline is stable.
