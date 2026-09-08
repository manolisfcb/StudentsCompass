"""An identical request must not regenerate an identical vector.

``upsert_resume_embedding_from_text`` used to generate the embedding, then look
for an existing row, then commit — in that order, every call. So opening the
gap analysis twice on an unchanged CV paid twice for the same vector and wrote
it twice. With the hash provider that is CPU on a warm path; with the local
sentence-transformer it is a forward pass and its resident memory, on a request
someone is waiting for.

The stored fingerprint of (text, model, scheme version) is what lets the second
call answer from the row it already has. These tests pin that the skip is real
(no generation, no write), that it is not too eager (changed text, changed
model, or a NULL fingerprint all regenerate), and that hash and local vectors
never end up sharing a space.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.models.resumeEmbeddingsModel import ResumeEmbedding
from app.models.resumeModel import ResumeModel
from app.services.analytics import embeddingService
from app.services.analytics.embeddingService import (
    EmbeddingDimensionMismatch,
    FINGERPRINT_VERSION,
    HASH_MODEL_NAME,
    ResumeEmbeddingService,
    compute_text_fingerprint,
    normalize_embedding_text,
)
from tests.harness import count_queries

SUMMARY = "Candidate has SQL, Python and Tableau experience across three internships."


@pytest.fixture(autouse=True)
def _hash_provider(monkeypatch):
    """The default provider, stated rather than inherited from the environment."""
    monkeypatch.setenv("EMBEDDINGS_PROVIDER", "hash")


@pytest.fixture
def generation_spy(monkeypatch):
    """Counts real generations without changing what they return."""
    calls: list[str] = []
    original = embeddingService.generate_embedding_with_model

    async def counted(text: str):
        calls.append(text)
        return await original(text)

    monkeypatch.setattr(embeddingService, "generate_embedding_with_model", counted)
    return calls


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


async def _rows(session, resume_id):
    result = await session.execute(
        select(ResumeEmbedding).where(ResumeEmbedding.resume_id == resume_id)
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# The fingerprint itself
# ---------------------------------------------------------------------------


def test_the_fingerprint_covers_text_model_and_version():
    text = "one two"
    base = compute_text_fingerprint(text, model_name=HASH_MODEL_NAME)

    assert compute_text_fingerprint(text, model_name=HASH_MODEL_NAME) == base
    assert compute_text_fingerprint("one three", model_name=HASH_MODEL_NAME) != base
    assert compute_text_fingerprint(text, model_name="other-model") != base


def test_normalisation_is_exactly_what_the_provider_receives():
    """Anything looser would let two different vectors share a fingerprint."""
    assert normalize_embedding_text("  hello  ") == "hello"
    # Inner whitespace and case are preserved: they change the vector.
    assert normalize_embedding_text("a  b") == "a  b"
    assert normalize_embedding_text("Hello") == "Hello"
    assert compute_text_fingerprint("a  b", model_name=HASH_MODEL_NAME) != (
        compute_text_fingerprint("a b", model_name=HASH_MODEL_NAME)
    )


# ---------------------------------------------------------------------------
# The skip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_an_identical_second_request_generates_nothing_and_writes_nothing(
    db_session, test_user, generation_spy
):
    from tests.conftest import test_engine

    resume = await _resume(db_session, test_user.id)
    service = ResumeEmbeddingService(db_session)

    first = await service.upsert_resume_embedding_from_text(
        resume_id=resume.id, text=SUMMARY
    )
    assert first is not None
    assert len(generation_spy) == 1

    with count_queries(test_engine) as counter:
        second = await service.upsert_resume_embedding_from_text(
            resume_id=resume.id, text=SUMMARY
        )

    assert len(generation_spy) == 1, "the vector was generated again"
    assert counter.writes == 0, "the row was rewritten with an identical vector"
    assert counter.selects == 1, f"{counter.selects} selects for a cache hit"
    assert second is not None
    assert second.id == first.id
    assert list(second.embedding) == list(first.embedding)


@pytest.mark.asyncio
async def test_the_stored_row_carries_its_fingerprint_and_version(db_session, test_user):
    resume = await _resume(db_session, test_user.id)
    stored = await ResumeEmbeddingService(db_session).upsert_resume_embedding_from_text(
        resume_id=resume.id, text=SUMMARY
    )

    assert stored.text_fingerprint == compute_text_fingerprint(
        SUMMARY, model_name=HASH_MODEL_NAME
    )
    assert stored.fingerprint_version == FINGERPRINT_VERSION
    assert stored.model_name == HASH_MODEL_NAME


@pytest.mark.asyncio
async def test_changed_text_regenerates(db_session, test_user, generation_spy):
    resume = await _resume(db_session, test_user.id)
    service = ResumeEmbeddingService(db_session)

    first = await service.upsert_resume_embedding_from_text(resume_id=resume.id, text=SUMMARY)
    # Copied out: the row is updated in place, so `first` and `second` are the
    # same identity-mapped object and comparing them would compare nothing.
    first_id, first_vector = first.id, list(first.embedding)

    second = await service.upsert_resume_embedding_from_text(
        resume_id=resume.id, text=SUMMARY + " Also Power BI."
    )

    assert len(generation_spy) == 2
    assert second.id == first_id, "a changed CV must update the row, not add one"
    assert list(second.embedding) != first_vector
    assert len(await _rows(db_session, resume.id)) == 1


@pytest.mark.asyncio
async def test_a_row_without_provenance_is_regenerated_once(
    db_session, test_user, generation_spy
):
    """NULL fingerprint means a pre-migration row: regenerate, then trust it."""
    resume = await _resume(db_session, test_user.id)
    service = ResumeEmbeddingService(db_session)

    stored = await service.upsert_resume_embedding_from_text(resume_id=resume.id, text=SUMMARY)
    stored.text_fingerprint = None
    stored.fingerprint_version = None
    await db_session.commit()
    assert len(generation_spy) == 1

    regenerated = await service.upsert_resume_embedding_from_text(
        resume_id=resume.id, text=SUMMARY
    )
    assert len(generation_spy) == 2
    assert regenerated.text_fingerprint is not None

    await service.upsert_resume_embedding_from_text(resume_id=resume.id, text=SUMMARY)
    assert len(generation_spy) == 2, "it should be trusted from the second call on"


@pytest.mark.asyncio
async def test_a_fingerprint_from_an_older_scheme_does_not_match(
    db_session, test_user, generation_spy
):
    resume = await _resume(db_session, test_user.id)
    service = ResumeEmbeddingService(db_session)

    stored = await service.upsert_resume_embedding_from_text(resume_id=resume.id, text=SUMMARY)
    stored.fingerprint_version = "v0"
    await db_session.commit()

    await service.upsert_resume_embedding_from_text(resume_id=resume.id, text=SUMMARY)
    assert len(generation_spy) == 2


@pytest.mark.asyncio
async def test_a_row_whose_vector_is_missing_is_regenerated(
    db_session, test_user, generation_spy
):
    """A matching fingerprint over a NULL vector is not a cache hit."""
    resume = await _resume(db_session, test_user.id)
    service = ResumeEmbeddingService(db_session)

    stored = await service.upsert_resume_embedding_from_text(resume_id=resume.id, text=SUMMARY)
    stored.embedding = None
    await db_session.commit()

    again = await service.upsert_resume_embedding_from_text(resume_id=resume.id, text=SUMMARY)
    assert len(generation_spy) == 2
    assert again.embedding is not None


# ---------------------------------------------------------------------------
# Vector spaces stay separate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hash_and_local_vectors_never_share_a_row(db_session, test_user, monkeypatch):
    """The fallback must not overwrite a semantic vector with a hash one."""
    resume = await _resume(db_session, test_user.id)
    service = ResumeEmbeddingService(db_session)

    await service.upsert_resume_embedding_from_text(resume_id=resume.id, text=SUMMARY)

    # A "local" provider that works, stored under the sentence-transformer name.
    async def local_result(text):
        return embeddingService.generate_hash_embedding(text), embeddingService.MODEL_NAME

    monkeypatch.setattr(embeddingService, "generate_embedding_with_model", local_result)
    monkeypatch.setenv("EMBEDDINGS_PROVIDER", "local")
    await service.upsert_resume_embedding_from_text(resume_id=resume.id, text=SUMMARY)

    rows = await _rows(db_session, resume.id)
    assert {row.model_name for row in rows} == {HASH_MODEL_NAME, embeddingService.MODEL_NAME}
    for row in rows:
        assert row.text_fingerprint == compute_text_fingerprint(
            SUMMARY, model_name=row.model_name
        )


@pytest.mark.asyncio
async def test_a_local_provider_that_falls_back_stores_under_the_hash_key(
    db_session, test_user, monkeypatch
):
    """The vector is fingerprinted under the model that actually produced it."""
    resume = await _resume(db_session, test_user.id)
    monkeypatch.setenv("EMBEDDINGS_PROVIDER", "local")
    monkeypatch.setattr(
        embeddingService,
        "_generate_local_embedding",
        lambda _text: (_ for _ in ()).throw(RuntimeError("no model on this box")),
    )

    stored = await ResumeEmbeddingService(db_session).upsert_resume_embedding_from_text(
        resume_id=resume.id, text=SUMMARY
    )

    assert stored.model_name == HASH_MODEL_NAME
    assert stored.text_fingerprint == compute_text_fingerprint(
        SUMMARY, model_name=HASH_MODEL_NAME
    )


# ---------------------------------------------------------------------------
# Dimensions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_vector_of_the_wrong_width_is_refused_with_the_numbers(db_session, test_user):
    resume = await _resume(db_session, test_user.id)

    with pytest.raises(EmbeddingDimensionMismatch) as raised:
        await ResumeEmbeddingService(db_session).upsert_resume_embedding(
            resume_id=resume.id,
            model_name="some-768-model",
            dims=768,
            embedding=[0.1] * 768,
        )

    assert raised.value.produced == 768
    assert raised.value.expected == 384
    assert "768" in str(raised.value) and "384" in str(raised.value)
    assert await _rows(db_session, resume.id) == []


@pytest.mark.asyncio
async def test_disabled_generation_stores_nothing(db_session, test_user, monkeypatch):
    monkeypatch.setenv("EMBEDDINGS_PROVIDER", "disabled")
    resume = await _resume(db_session, test_user.id)

    stored = await ResumeEmbeddingService(db_session).upsert_resume_embedding_from_text(
        resume_id=resume.id, text=SUMMARY
    )
    assert stored is None
    assert await _rows(db_session, resume.id) == []


@pytest.mark.asyncio
async def test_blank_text_stores_nothing(db_session, test_user):
    resume = await _resume(db_session, test_user.id)
    service = ResumeEmbeddingService(db_session)

    assert await service.upsert_resume_embedding_from_text(resume_id=resume.id, text="   ") is None
    assert await service.upsert_resume_embedding_from_text(resume_id=resume.id, text=None) is None
    assert await _rows(db_session, resume.id) == []
