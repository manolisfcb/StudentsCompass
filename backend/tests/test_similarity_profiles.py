"""Semantic matching with a real provider reads cosines with that model's scale (TASK-073).

A cosine is not portable between models. Under the MiniLM thresholds the
matcher always had (0.72 semantic, 0.48 weak), ``gemini-embedding-001`` at 384
dimensions — where two unrelated skills score 0.74–0.80 — would count almost
every candidate as a substitute for every requirement. These tests pin that:

* readiness needs a provider with meaning, its key, and a calibrated profile;
* the default matcher picks the profile of the configured model, and an
  injected embedder keeps the thresholds its callers were written against;
* a hash fallback never takes part in a comparison against model vectors;
* context similarity is banded on the raw cosine and reported rescaled.
"""
from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

from app import config
from app.services.analytics import embeddingService
from app.services.analytics.embeddingService import (
    LEGACY_SIMILARITY_PROFILE,
    SIMILARITY_PROFILES,
    generate_embedding_in_active_space,
    generate_hash_embedding,
    get_embedding_status,
)
from app.services.analytics.semanticMatchingService import SemanticMatchingService

GEMINI_PROFILE = SIMILARITY_PROFILES["gemini-embedding-001@384"]


class FakeGeminiModels:
    def __init__(self):
        self.error: Exception | None = None
        self.calls = 0

    async def embed_content(self, *, model, contents, config):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return SimpleNamespace(
            embeddings=[SimpleNamespace(values=generate_hash_embedding(text)) for text in contents]
        )


@pytest.fixture
def gemini(monkeypatch):
    models = FakeGeminiModels()
    monkeypatch.setenv("EMBEDDINGS_PROVIDER", "gemini")
    monkeypatch.setenv("GENAI_API_KEY", "test-key")
    monkeypatch.setattr(config, "AI_KILL_SWITCH", False)
    monkeypatch.setattr(
        embeddingService,
        "_get_gemini_client",
        lambda: SimpleNamespace(aio=SimpleNamespace(models=models)),
    )
    return models


def _at_cosine(cosine: float) -> list[float]:
    """A unit vector whose cosine with ``[1, 0]`` is exactly ``cosine``."""
    return [cosine, math.sqrt(1.0 - cosine * cosine)]


def _skill(skill_id: str, name: str) -> dict:
    return {
        "skill_id": skill_id,
        "display_name": name,
        "normalized_name": name.lower(),
        "importance_score": 1.0,
    }


# ---------------------------------------------------------------------------
# Readiness
# ---------------------------------------------------------------------------


def test_hash_is_never_ready(monkeypatch):
    monkeypatch.setenv("EMBEDDINGS_PROVIDER", "hash")
    assert get_embedding_status()["semantic_matching_ready"] is False


def test_gemini_with_its_key_and_a_profile_is_ready(gemini):
    assert get_embedding_status()["semantic_matching_ready"] is True


def test_gemini_without_its_key_is_not_ready(gemini, monkeypatch):
    monkeypatch.delenv("GENAI_API_KEY")
    assert get_embedding_status()["semantic_matching_ready"] is False


def test_a_model_without_a_calibrated_profile_is_not_ready(gemini, monkeypatch):
    monkeypatch.setattr(embeddingService, "GEMINI_EMBEDDING_MODEL", "gemini-embedding-002")
    status = get_embedding_status()

    assert status["model_name"] == "gemini-embedding-002@384"
    assert status["semantic_matching_ready"] is False


def test_disabled_generation_is_not_ready(gemini, monkeypatch):
    monkeypatch.setenv("EMBEDDINGS_PROVIDER", "off")
    assert get_embedding_status()["semantic_matching_ready"] is False


# ---------------------------------------------------------------------------
# Which profile the matcher reads
# ---------------------------------------------------------------------------


def test_the_default_matcher_reads_the_configured_models_profile(gemini):
    assert SemanticMatchingService().profile is GEMINI_PROFILE


def test_under_hash_the_default_matcher_keeps_the_legacy_profile(monkeypatch):
    monkeypatch.setenv("EMBEDDINGS_PROVIDER", "hash")
    assert SemanticMatchingService().profile is LEGACY_SIMILARITY_PROFILE


def test_an_injected_embedder_keeps_the_legacy_profile(gemini):
    async def fake(text):
        return [1.0, 0.0]

    assert SemanticMatchingService(embedding_fn=fake).profile is LEGACY_SIMILARITY_PROFILE


# ---------------------------------------------------------------------------
# Skill matching under the Gemini profile
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("cosine", "expected"),
    [
        # Measured: unrelated skills (XGBoost / Tableau) score 0.74–0.80.
        (0.79, "missing"),
        # Measured: related skills (Tableau / Power BI, MySQL / PostgreSQL).
        (0.92, "weak"),
        # Measured: synonyms (PostgreSQL / Postgres, AWS / Amazon Web Services).
        (0.97, "semantic"),
    ],
)
async def test_gemini_cosines_are_read_on_the_gemini_scale(cosine, expected):
    async def fake(text):
        return [1.0, 0.0] if "required" in text else _at_cosine(cosine)

    service = SemanticMatchingService(
        embedding_fn=fake, semantic_ready_override=True, profile=GEMINI_PROFILE
    )
    summary = await service.analyze_required_skill_matches(
        current_skills=[_skill("have", "candidate skill")],
        required_skills=[_skill("need", "required skill")],
    )

    outcome = {
        "semantic": summary.semantic_match_count,
        "weak": summary.weak_match_count,
        "missing": len(summary.missing_skills) - summary.weak_match_count,
    }
    assert outcome == {key: int(key == expected) for key in outcome}


@pytest.mark.asyncio
async def test_the_same_unrelated_cosine_would_have_matched_under_legacy_thresholds():
    """The defect TASK-073 closes, stated as a fact rather than assumed."""

    async def fake(text):
        return [1.0, 0.0] if "required" in text else _at_cosine(0.79)

    service = SemanticMatchingService(
        embedding_fn=fake, semantic_ready_override=True, profile=LEGACY_SIMILARITY_PROFILE
    )
    summary = await service.analyze_required_skill_matches(
        current_skills=[_skill("have", "candidate skill")],
        required_skills=[_skill("need", "required skill")],
    )

    assert summary.semantic_match_count == 1


# ---------------------------------------------------------------------------
# Context similarity under the Gemini profile
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("cosine", "level", "score"),
    [
        # Percentiles measured on 168 real CV × posting pairs (TASK-079).
        (0.794, "strong", 0.94),  # aligned p90
        (0.768, "strong", 0.68),  # aligned median
        (0.728, "moderate", 0.28),  # adjacent median
        (0.708, "weak", 0.08),  # unrelated median
        (0.68, "weak", 0.0),  # below the unrelated median
    ],
)
async def test_context_is_banded_raw_and_reported_rescaled(cosine, level, score):
    async def fake(text):
        return [1.0, 0.0] if text == "resume" else _at_cosine(cosine)

    service = SemanticMatchingService(
        embedding_fn=fake, semantic_ready_override=True, profile=GEMINI_PROFILE
    )
    summary = await service.analyze_context_similarity(
        resume_text="resume", role_text="role", evidence_sources=[]
    )

    assert summary.context_match_level == level
    assert summary.context_similarity_score == pytest.approx(score, abs=1e-3)


def test_the_legacy_profile_does_not_rescale():
    assert LEGACY_SIMILARITY_PROFILE.rescale_context(0.83) == pytest.approx(0.83)


# ---------------------------------------------------------------------------
# A fallback vector never meets a model vector
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_fallback_is_no_vector_for_the_matcher(gemini):
    assert await generate_embedding_in_active_space("Python") is not None

    gemini.error = RuntimeError("503 UNAVAILABLE")

    assert await generate_embedding_in_active_space("Python") is None


@pytest.mark.asyncio
async def test_under_hash_the_active_space_is_hash(monkeypatch):
    monkeypatch.setenv("EMBEDDINGS_PROVIDER", "hash")
    assert await generate_embedding_in_active_space("Python") == generate_hash_embedding("Python")
