"""Tests for the numpy/pgvector embedding optimizations.

Covers:
- Parity of the numpy ``generate_hash_embedding`` against a pure-Python
  reference (the stored "hash-v1" vectors must stay numerically equivalent).
- The vectorized cosine similarity for normalized and non-normalized inputs.
- Batched N x M semantic matching picking the highest-similarity candidate.
- ``ResumeEmbeddingService.find_similar_resumes`` (pgvector search). The ranking
  case requires PostgreSQL with the ``vector`` extension and is skipped on the
  SQLite test backend; the empty-source guard is exercised everywhere.
"""
import hashlib
import math
import re
import uuid

import pytest

from app.models.resumeModel import ResumeModel
from app.models.resumeEmbeddingsModel import ResumeEmbedding
from app.services.analytics.embeddingService import (
    EMBEDDING_DIMS,
    ResumeEmbeddingService,
    generate_hash_embedding,
)
from app.services.analytics.semanticMatchingService import (
    SemanticMatchingService,
    _cosine_similarity,
)


def _reference_hash_embedding(text: str, dims: int = EMBEDDING_DIMS) -> list[float]:
    """Original pure-Python implementation, kept here as the parity oracle."""
    tokens = re.findall(r"[a-z0-9+#]+", text.lower())
    vector = [0.0 for _ in range(dims)]
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dims
        sign = 1.0 if digest[4] % 2 else -1.0
        weight = 1.0 + min(len(token), 20) / 20.0
        vector[index] += sign * weight
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [round(value / norm, 8) for value in vector]


@pytest.mark.parametrize(
    "text",
    [
        "Python SQL data analysis",
        "Built dashboards with Tableau and PowerBI for stakeholders",
        "c++ c# go rust python python python",
        "",
        "   ",
    ],
)
def test_generate_hash_embedding_matches_reference(text):
    result = generate_hash_embedding(text)
    expected = _reference_hash_embedding(text)

    assert len(result) == EMBEDDING_DIMS
    assert result == pytest.approx(expected, abs=1e-7)


def test_generate_hash_embedding_is_unit_norm_for_non_empty_text():
    vector = generate_hash_embedding("Python SQL data analysis")
    norm = math.sqrt(sum(value * value for value in vector))
    assert norm == pytest.approx(1.0, abs=1e-6)


def test_generate_hash_embedding_empty_text_is_zero_vector():
    vector = generate_hash_embedding("   ")
    assert vector == [0.0] * EMBEDDING_DIMS


def test_cosine_similarity_normalized_vectors():
    assert _cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert _cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_similarity_uses_true_cosine_for_unnormalized_vectors():
    # Magnitude must not matter: [0, 0.96] is collinear with [0, 1].
    assert _cosine_similarity([0.0, 1.0], [0.0, 0.96]) == pytest.approx(1.0)


def test_cosine_similarity_handles_edge_cases():
    assert _cosine_similarity([], [1.0]) == 0.0
    assert _cosine_similarity([1.0, 2.0], [1.0]) == 0.0
    assert _cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0
    # Opposite vectors clamp to 0.0 (not negative).
    assert _cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == 0.0


@pytest.mark.asyncio
async def test_batched_semantic_match_picks_highest_similarity_candidate():
    # Keyed by keyword so it is robust to how _skill_text concatenates fields.
    async def fake_embedding(text: str):
        lowered = text.lower()
        if "kubernetes" in lowered:
            return [1.0, 0.0, 0.0]
        if "docker" in lowered:
            return [0.9, 0.1, 0.0]
        if "design" in lowered:
            return [0.0, 0.0, 1.0]
        raise AssertionError(f"unexpected embedding text: {text!r}")

    service = SemanticMatchingService(embedding_fn=fake_embedding, semantic_ready_override=True)
    summary = await service.analyze_required_skill_matches(
        current_skills=[
            {"skill_id": "docker-id", "normalized_name": "docker",
             "display_name": "Docker", "confidence_score": 0.9},
            {"skill_id": "design-id", "normalized_name": "design",
             "display_name": "Graphic Design", "confidence_score": 0.9},
        ],
        required_skills=[
            {"skill_id": "kubernetes-id", "normalized_name": "kubernetes",
             "display_name": "Kubernetes", "importance_score": 0.9},
        ],
    )

    assert summary.semantic_match_count == 1
    matched = summary.semantic_matched_skills[0]
    # Docker (cosine ~0.994) must win over graphic design (cosine 0.0).
    assert matched["matched_skill_display_name"] == "Docker"
    assert matched["similarity_score"] > 0.72


@pytest.mark.asyncio
async def test_find_similar_resumes_returns_empty_when_source_has_no_embedding(db_session):
    service = ResumeEmbeddingService(db_session)
    results = await service.find_similar_resumes(resume_id=uuid.uuid4(), k=5)
    assert results == []


@pytest.mark.asyncio
async def test_find_similar_resumes_ranks_by_cosine_distance(db_session, test_user):
    if db_session.bind.dialect.name != "postgresql":
        pytest.skip("pgvector cosine search requires a PostgreSQL backend")

    model_name = "hash-v1"

    def _make_resume(summary: str) -> ResumeModel:
        return ResumeModel(
            view_url="https://storage.example/resume.pdf",
            user_id=test_user.id,
            storage_file_id=f"resumes/{uuid.uuid4()}.pdf",
            original_filename="resume.pdf",
            folder_id="resumes",
            ai_summary=summary,
        )

    source = _make_resume("Python and SQL data analysis")
    near = _make_resume("Python SQL analytics and dashboards")
    far = _make_resume("Graphic design and illustration")
    db_session.add_all([source, near, far])
    await db_session.commit()
    for resume in (source, near, far):
        await db_session.refresh(resume)

    embedding_service = ResumeEmbeddingService(db_session)
    for resume in (source, near, far):
        await embedding_service.upsert_resume_embedding_from_text(
            resume_id=resume.id, text=resume.ai_summary, model_name=model_name,
        )

    results = await embedding_service.find_similar_resumes(
        resume_id=source.id, k=10, model_name=model_name,
    )

    returned_ids = [row["resume_id"] for row in results]
    assert source.id not in returned_ids
    assert results[0]["resume_id"] == near.id
    assert results[0]["similarity"] >= results[-1]["similarity"]
