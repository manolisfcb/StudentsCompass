"""The Gemini embedding provider (TASK-072).

What has to hold before a single Gemini vector is trusted:

* the width is the one the columns hold (384), asked for explicitly;
* every vector is unit length — truncated Gemini output is not, and a dot
  product over unnormalised vectors is a quietly wrong cosine;
* one task type on every side, or the two sides do not share a space;
* a failure never surfaces to the caller and never stores a hash vector under
  the Gemini name.

No test here touches the network: the client is replaced.
"""
from __future__ import annotations

import math
import uuid
from types import SimpleNamespace

import pytest

from app import config
from app.models.resumeModel import ResumeModel
from app.services.analytics import embeddingService
from app.services.analytics.embeddingService import (
    EMBEDDING_COLUMN_DIMS,
    GEMINI_EMBEDDING_TASK_TYPE,
    HASH_MODEL_NAME,
    ResumeEmbeddingService,
    compute_text_fingerprint,
    generate_embedding_with_model,
    generate_embeddings_batch,
    generate_hash_embedding,
    gemini_model_name,
    get_effective_model_name,
    get_embedding_status,
)


class FakeGeminiModels:
    """Answers like ``client.aio.models``: one deterministic vector per input.

    The vectors deliberately come back with norm != 1, as the real API's
    truncated output does, so the normalisation has something to do.
    """

    def __init__(self, *, dims: int = EMBEDDING_COLUMN_DIMS, error: Exception | None = None):
        self.dims = dims
        self.error = error
        self.calls: list[dict] = []

    async def embed_content(self, *, model, contents, config):
        self.calls.append({"model": model, "contents": list(contents), "config": config})
        if self.error is not None:
            raise self.error
        embeddings = []
        for text in contents:
            base = generate_hash_embedding(text, dims=self.dims)
            embeddings.append(SimpleNamespace(values=[value * 0.43 for value in base]))
        return SimpleNamespace(embeddings=embeddings)


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


@pytest.fixture
def metrics(monkeypatch):
    fresh = {key: 0 for key in embeddingService._EMBEDDING_METRICS}
    monkeypatch.setattr(embeddingService, "_EMBEDDING_METRICS", fresh)
    return fresh


def _norm(vector: list[float]) -> float:
    return math.sqrt(sum(value * value for value in vector))


# ---------------------------------------------------------------------------
# The vectors
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gemini_vectors_are_384_wide_and_unit_length(gemini):
    vector, model_name = await generate_embedding_with_model("Python pandas")

    assert len(vector) == EMBEDDING_COLUMN_DIMS
    assert _norm(vector) == pytest.approx(1.0, abs=1e-9)
    assert model_name == gemini_model_name() == "gemini-embedding-001@384"


@pytest.mark.asyncio
async def test_the_request_fixes_width_and_task_type(gemini):
    await generate_embedding_with_model("SQL")

    (call,) = gemini.calls
    assert call["model"] == "gemini-embedding-001"
    assert call["config"].output_dimensionality == EMBEDDING_COLUMN_DIMS
    assert call["config"].task_type == GEMINI_EMBEDDING_TASK_TYPE == "SEMANTIC_SIMILARITY"


@pytest.mark.asyncio
async def test_a_batch_is_chunked_at_the_api_cap_and_keeps_order(gemini):
    texts = [f"skill number {index}" for index in range(230)]

    vectors, model_name = await generate_embeddings_batch(texts)

    assert [len(call["contents"]) for call in gemini.calls] == [100, 100, 30]
    assert model_name == gemini_model_name()
    assert len(vectors) == 230
    # Order survives chunking: each vector is the one of its own text.
    for text, vector in zip(texts, vectors):
        expected = generate_hash_embedding(text)
        assert vector == pytest.approx(expected, abs=1e-7)


@pytest.mark.asyncio
async def test_the_text_sent_is_the_one_fingerprinted(gemini):
    await generate_embedding_with_model("  Tableau  ")

    assert gemini.calls[0]["contents"] == ["Tableau"]


@pytest.mark.asyncio
async def test_a_batch_refuses_an_empty_text(gemini):
    with pytest.raises(ValueError):
        await generate_embeddings_batch(["Python", "   "])
    assert gemini.calls == []


# ---------------------------------------------------------------------------
# Failures fall back to hash, under the hash name, counted
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_provider_error_falls_back_to_hash_under_the_hash_name(gemini, metrics):
    gemini.error = RuntimeError("503 UNAVAILABLE")

    vector, model_name = await generate_embedding_with_model("Python")

    assert model_name == HASH_MODEL_NAME
    assert vector == generate_hash_embedding("Python")
    assert metrics["provider_failure_count"] == 1
    assert metrics["fallback_to_hash_count"] == 1


@pytest.mark.asyncio
async def test_one_failed_chunk_falls_the_whole_batch_back(gemini, metrics):
    """A caller never holds a list that mixes two vector spaces."""
    original = gemini.embed_content
    calls = 0

    async def second_chunk_fails(**kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("429 RESOURCE_EXHAUSTED")
        return await original(**kwargs)

    gemini.embed_content = second_chunk_fails
    texts = [f"skill {index}" for index in range(150)]

    vectors, model_name = await generate_embeddings_batch(texts)

    assert model_name == HASH_MODEL_NAME
    assert vectors == [generate_hash_embedding(text) for text in texts]
    assert metrics["provider_failure_count"] == 1


@pytest.mark.asyncio
async def test_a_vector_of_the_wrong_width_is_a_failure_not_a_vector(monkeypatch, gemini, metrics):
    wrong = FakeGeminiModels(dims=768)
    monkeypatch.setattr(
        embeddingService,
        "_get_gemini_client",
        lambda: SimpleNamespace(aio=SimpleNamespace(models=wrong)),
    )

    vector, model_name = await generate_embedding_with_model("Python")

    assert model_name == HASH_MODEL_NAME
    assert len(vector) == embeddingService.EMBEDDING_DIMS
    assert metrics["provider_failure_count"] == 1


@pytest.mark.asyncio
async def test_without_an_api_key_nothing_is_called(monkeypatch, metrics):
    monkeypatch.setenv("EMBEDDINGS_PROVIDER", "gemini")
    monkeypatch.delenv("GENAI_API_KEY", raising=False)
    monkeypatch.setattr(config, "AI_KILL_SWITCH", False)

    vector, model_name = await generate_embedding_with_model("Python")

    assert model_name == HASH_MODEL_NAME
    assert metrics["fallback_to_hash_count"] == 1
    assert get_embedding_status()["provider_configured"] is False


@pytest.mark.asyncio
async def test_the_kill_switch_stops_embedding_calls_too(monkeypatch, gemini, metrics):
    monkeypatch.setattr(config, "AI_KILL_SWITCH", True)

    _, model_name = await generate_embedding_with_model("Python")

    assert gemini.calls == []
    assert model_name == HASH_MODEL_NAME
    assert metrics["fallback_to_hash_count"] == 1


# ---------------------------------------------------------------------------
# Naming and status
# ---------------------------------------------------------------------------


def test_the_effective_model_name_follows_the_provider(monkeypatch):
    monkeypatch.setenv("EMBEDDINGS_PROVIDER", "hash")
    assert get_effective_model_name() == HASH_MODEL_NAME

    monkeypatch.setenv("EMBEDDINGS_PROVIDER", "gemini")
    assert get_effective_model_name() == "gemini-embedding-001@384"

    # An unknown provider falls back to hash, so it must report hash.
    monkeypatch.setenv("EMBEDDINGS_PROVIDER", "local")
    assert get_effective_model_name() == HASH_MODEL_NAME


def test_the_status_reports_the_gemini_space(gemini):
    status = get_embedding_status()

    assert status["provider"] == "gemini"
    assert status["provider_configured"] is True
    assert status["model_name"] == gemini_model_name()
    assert status["dims"] == EMBEDDING_COLUMN_DIMS


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


async def _resume(session, user_id):
    resume = ResumeModel(
        id=uuid.uuid4(),
        user_id=user_id,
        view_url=f"https://example.invalid/{uuid.uuid4().hex}",
        storage_file_id=uuid.uuid4().hex,
        original_filename="cv.pdf",
        folder_id="resumes",
    )
    session.add(resume)
    await session.commit()
    return resume


SUMMARY = "Candidate has SQL, Python and Tableau experience across three internships."


@pytest.mark.asyncio
async def test_a_gemini_vector_is_stored_under_its_name_and_skipped_next_time(
    db_session, test_user, gemini
):
    resume = await _resume(db_session, test_user.id)
    service = ResumeEmbeddingService(db_session)

    stored = await service.upsert_resume_embedding_from_text(resume_id=resume.id, text=SUMMARY)
    again = await service.upsert_resume_embedding_from_text(resume_id=resume.id, text=SUMMARY)

    assert stored.model_name == gemini_model_name()
    assert stored.text_fingerprint == compute_text_fingerprint(
        SUMMARY, model_name=gemini_model_name()
    )
    assert _norm(list(stored.embedding)) == pytest.approx(1.0, abs=1e-6)
    # The second request found the row the provider wrote: one paid call, not two.
    assert len(gemini.calls) == 1
    assert again.id == stored.id


@pytest.mark.asyncio
async def test_a_failed_gemini_call_never_writes_under_the_gemini_name(
    db_session, test_user, gemini
):
    gemini.error = RuntimeError("503 UNAVAILABLE")
    resume = await _resume(db_session, test_user.id)

    stored = await ResumeEmbeddingService(db_session).upsert_resume_embedding_from_text(
        resume_id=resume.id, text=SUMMARY
    )

    assert stored.model_name == HASH_MODEL_NAME
    assert stored.text_fingerprint == compute_text_fingerprint(SUMMARY, model_name=HASH_MODEL_NAME)


# ---------------------------------------------------------------------------
# Every fallback is logged with stable fields (TASK-076)
# ---------------------------------------------------------------------------


def _fallback_records(caplog) -> list:
    return [record for record in caplog.records if getattr(record, "embedding_fallback", False)]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("setup", "reason"),
    [
        ("provider_error", "provider_error"),
        ("missing_api_key", "missing_api_key"),
        ("kill_switch", "kill_switch"),
    ],
)
async def test_each_fallback_is_one_structured_warning(gemini, monkeypatch, caplog, setup, reason):
    if setup == "provider_error":
        gemini.error = RuntimeError("503 UNAVAILABLE")
    elif setup == "missing_api_key":
        monkeypatch.setattr(embeddingService, "_get_gemini_client", lambda: None)
    else:
        monkeypatch.setattr(config, "AI_KILL_SWITCH", True)

    with caplog.at_level("WARNING", logger=embeddingService.LOGGER.name):
        await generate_embeddings_batch(["Python", "SQL"])

    (record,) = _fallback_records(caplog)
    assert record.levelname == "WARNING"
    assert record.embedding_provider == "gemini"
    assert record.embedding_fallback_reason == reason
    assert record.embedding_texts == 2


@pytest.mark.asyncio
async def test_an_unknown_provider_is_logged_as_such(monkeypatch, caplog):
    monkeypatch.setenv("EMBEDDINGS_PROVIDER", "local")

    with caplog.at_level("WARNING", logger=embeddingService.LOGGER.name):
        await generate_embedding_with_model("Python")

    (record,) = _fallback_records(caplog)
    assert record.embedding_fallback_reason == "unknown_provider"


@pytest.mark.asyncio
async def test_a_working_provider_logs_no_fallback(gemini, caplog):
    with caplog.at_level("WARNING", logger=embeddingService.LOGGER.name):
        await generate_embeddings_batch(["Python"])

    assert _fallback_records(caplog) == []


def test_the_json_formatter_emits_the_fallback_fields_as_fields():
    """The log metric filters on jsonPayload.embedding_fallback; it has to exist."""
    import json
    import logging

    from app.logging import CloudLoggingFormatter

    record = logging.LogRecord(embeddingService.LOGGER.name, logging.WARNING, __file__, 1, "x", None, None)
    record.embedding_fallback = True
    record.embedding_fallback_reason = "missing_api_key"

    payload = json.loads(CloudLoggingFormatter().format(record))

    assert payload["embedding_fallback"] is True
    assert payload["embedding_fallback_reason"] == "missing_api_key"
    assert payload["severity"] == "WARNING"
