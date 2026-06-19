# Phase 1 Status: Analytical Foundation

## Product Goal

Phase 1 turns StudentsCompass from a general student platform into a career
analytics product surface: uploaded resumes become skill profiles, target roles
become structured requirements, and the product can recommend learning resources
from a clear skill gap.

## Implemented

- Career analytics tables for skills, aliases, resume skills, job skills,
  courses, course-skill coverage, and optimization runs.
- Minimum seed catalog with starter roles, skills, aliases, courses, and
  course-skill mapping.
- Resume skill extraction from stored resume summaries.
- Job posting skill extraction for market-backed role requirements.
- Gap analysis endpoint for resume plus target role.
- Career Lab UI for role selection, match score, missing skills, resource route,
  readiness status, and market-signal explanation.
- Role discovery endpoint so the frontend no longer hardcodes supported roles.
- Resume embeddings reactivated through `resume_embeddings` with configurable
  provider support.

## Embedding Policy

Embeddings are enabled through `app.services.analytics.embeddingService`.

- Default provider: `hash`, deterministic and dependency-safe for development,
  tests, and environments without a local ML model.
- Local semantic provider: set `EMBEDDINGS_PROVIDER=local` to use
  `sentence-transformers/all-MiniLM-L6-v2`.
- If local model loading fails, the service falls back to hash embeddings so the
  product does not fail hard.

The readiness endpoint exposes provider, model name, stored embedding count, and
whether true semantic matching is currently ready.

## Evidence

- Capstone/Career Lab tests cover seed catalog, status, role discovery,
  market-backed role override, resume skill sync, job skill sync, gap analysis,
  and embedding persistence.
- Full test suite should be run before closing this phase.

## Remaining Before Phase 1 Closure

- Verify Career Lab manually while logged in.
- Decide whether production should default to `EMBEDDINGS_PROVIDER=local` after
  model packaging/caching is handled.
- Expand roles and catalog coverage beyond the minimum seed.
- Add admin-facing controls for seeding/syncing analytics data instead of only
  scripts/API calls.
