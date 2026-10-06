# Matching Methodology

## Purpose

The matching engine compares a student's current resume-derived skill profile
with the skills required for a target role. It produces a compatibility score,
separates exact and semantic matches, and prioritizes the remaining gaps.

## Inputs

- Current skills extracted from the student's resume summary or manual text.
- Full resume context from `ai_summary` and extracted skill evidence.
- Required skills for a target role, sourced from real job postings when
  available or from the seeded role catalog otherwise.
- Full role context from required skills and synced job-posting text when
  available.
- Skill metadata:
  - normalized name;
  - display name;
  - category;
  - extraction confidence;
  - role importance.
- Embedding provider status from the analytics embedding service.

## Exact Matching

Exact matching compares skill IDs. If the resume has the same canonical skill as
the role requirement, it is an exact match.

Exact matches receive the strongest weight because they represent the cleanest
signal in the catalog. For example, a resume skill linked to `python` satisfies
a required role skill linked to `python`.

## Semantic Matching

Semantic matching is enabled only when the embedding status reports
`semantic_matching_ready`, which requires all of: generation on, a provider
whose vectors carry meaning and can be called, and a calibrated
`SimilarityProfile` for its model (`embeddingService.SIMILARITY_PROFILES`).

- `EMBEDDINGS_PROVIDER=hash` (the default) produces token hashes with no
  meaning to match on: never ready.
- The local sentence-transformer provider was retired (it pulled torch into
  the image); `EMBEDDINGS_PROVIDER=local` now falls back to hash.
- `EMBEDDINGS_PROVIDER=gemini` produces real `gemini-embedding-001` vectors at
  384 dimensions, L2-normalised and stored as `gemini-embedding-001@384`. It
  needs `GENAI_API_KEY`, honours `AI_KILL_SWITCH`, and falls back to hash
  (stored under `hash-v1`, counted in `provider_failure_count`) when the API
  fails. A fallback vector is never compared against a Gemini one: the matcher
  treats it as "no vector". Ready when the key is set.

Each catalog skill is embedded **once** from its display name, normalized name
and category, and stored in `skill_embeddings` per model, with the same
fingerprint versioning as `resume_embeddings`. The gap analysis reads every
vector it needs in one SELECT; a skill that has never been embedded costs one
batched provider call, after which it is stored. Over an embedded catalog an
analysis makes **no** embedding call. Fill or refresh the table with
`scripts/sync_skill_embeddings.py` after seeding the catalog or changing the
provider (117 seed skills: two requests, under two seconds; a second run makes
no call).

Per-occurrence evidence text is left out of the vector: it differs per CV and
posting, so it would make the vector uncacheable, and the seed catalog's
templated evidence ("X is part of the Data Analyst seed profile") pulled every
seed skill towards the same point. Callers that inject their own embedding
function still embed the full text, evidence included.

Thresholds depend on the model, because each model spreads its cosines over
its own range:

| Profile | Semantic match | Weak match | Context strong / moderate | Context reported as |
| --- | --- | --- | --- | --- |
| `gemini-embedding-001@384` | `>= 0.95` | `>= 0.88` | `>= 0.85` / `>= 0.80` | `(cos − 0.70) / 0.20`, clamped to [0, 1] |
| Legacy (MiniLM; injected embedders) | `>= 0.72` | `>= 0.48` | `>= 0.78` / `>= 0.62` | raw cosine |

The Gemini profile was measured on 2026-10-05: synonyms 0.95–0.99
(PostgreSQL / Postgres), related skills 0.88–0.94 (Tableau / Power BI, MySQL /
PostgreSQL), unrelated 0.74–0.80 (XGBoost / Tableau). A related skill is a weak
match — transferable, not a substitute. Under the legacy thresholds every one of
those pairs would have been a semantic match. The context values rest on four
synthetic CV↔posting pairs (aligned 0.87, adjacent role 0.84, other stack 0.76,
other profession 0.68) and are provisional until real postings calibrate them.

Semantic matches count as matched required skills. Weak matches are reported for
explanation but remain in `missing_skills` because the product should not claim
that a student fully satisfies a requirement from a weak signal.

## Deep Context Matching

Skill-level matching can miss fit that appears in broader resume language.
Phase 2 also builds:

- a resume context from `ai_summary` plus extracted skill evidence;
- a role context from target role, required skills, evidence text, and recent
  synced job postings when available.

When semantic embeddings are ready, the service embeds both context blocks and
computes cosine similarity. The result is exposed as:

- `context_similarity_score`;
- `context_match_level`;
- `semantic_context_ready`;
- `context_evidence_sources`.

The product-level readiness score blends both signals:

```text
overall_readiness_score = skill_match_score * 0.8 + context_similarity_score * 0.2
```

If semantic context is not ready, `overall_readiness_score` equals the skill
`match_score`.

## Scoring Formula

For each required skill:

- `importance_score` expresses how important the skill is for the role.
- `confidence_score` reduces the value of a resume skill if extraction was
  uncertain.
- exact matches earn `importance_score * confidence_score`.
- semantic matches earn `importance_score * similarity_score * 0.82`.
- weak matches earn `importance_score * similarity_score * 0.35`.

Overall:

```text
match_score = earned_weighted_score / total_required_importance
semantic_score = semantic_weighted_score / total_required_importance
priority_gap_score = 1 - match_score
coverage_ratio = (exact_match_count + semantic_match_count) / required_skill_count
```

Scores are clamped to the `0.0` to `1.0` range.

## Fallback Behavior

When local embeddings fail, the embedding service falls back to deterministic
hash embeddings for storage and stability. Semantic matching readiness remains
the gate for true semantic matching. The gap analysis endpoint must continue to
return exact matching, missing skills, recommendations, and scores without
returning a 500.

## Product Interpretation

- `match_score`: readiness estimate for a role.
- `overall_readiness_score`: skill score plus deep context score when semantic
  context is available.
- `semantic_score`: part of the readiness score supported by semantic similarity.
- `context_similarity_score`: full resume-to-role semantic alignment.
- `priority_gap_score`: remaining opportunity area.
- `priority_missing_skills`: missing requirements ranked by role importance and
  available market demand signal.
- `gap_insights`: explanation layer for the product UI.
- `market_signals`: market-backed demand counts when synced job postings exist.
- `semantic_matched_skills`: useful for explaining transferable skills.
- `weak_matched_skills`: useful for coaching language such as "you may have
  related experience, but the signal is not strong enough yet."

## Gap Priority Formula

Missing skills receive a product priority score:

```text
priority_score = importance_score * (1 + market_demand_score * 0.35)
```

This keeps role importance as the main signal while allowing market-backed
skills to rise when synced job postings repeatedly require them.

## MVP Limitations

- Matching quality depends on catalog quality and role-skill mappings.
- Context matching compares full resume and role text, but it does not yet
  locate exact paragraph-level evidence spans.
- Weak matches are intentionally conservative.
- The model does not yet learn from employer outcomes or student feedback.
- Market demand is limited to synced StudentsCompass job postings.
