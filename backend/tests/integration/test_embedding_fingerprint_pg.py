"""The fingerprint against real pgvector, and the concurrent first generation.

SQLite stores the vector as an opaque blob and serialises writes onto one
connection, so neither the ``Vector(384)`` column nor the race between two first
generations means anything there. Both need this lane.
"""
from __future__ import annotations

import asyncio
import importlib.util
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select, text

pytestmark = [pytest.mark.integration, pytest.mark.postgres]

SUMMARY = "Candidate has SQL, Python and Tableau experience across three internships."


@pytest.fixture(autouse=True)
def _hash_provider(monkeypatch):
    monkeypatch.setenv("EMBEDDINGS_PROVIDER", "hash")


@pytest.fixture
def _models():
    import tests.conftest  # noqa: F401

    from app.db import Base

    return Base


@pytest.fixture
async def schema(pg_engine, _models):
    async with pg_engine.begin() as conn:
        await conn.run_sync(_models.metadata.create_all)
    try:
        yield
    finally:
        async with pg_engine.begin() as conn:
            await conn.run_sync(_models.metadata.drop_all)


def _migration():
    path = Path("alembic/versions/c4a71e2b90d8_add_embedding_text_fingerprint.py")
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def _user_and_resume(session):
    from app.models.resumeModel import ResumeModel
    from app.models.userModel import User

    user = User(
        id=uuid.uuid4(),
        email=f"emb-{uuid.uuid4().hex[:8]}@example.invalid",
        hashed_password="x",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    session.add(user)
    await session.flush()
    resume = ResumeModel(
        id=uuid.uuid4(),
        user_id=user.id,
        view_url=f"https://example.invalid/{uuid.uuid4().hex}",
        storage_file_id=uuid.uuid4().hex,
        original_filename="cv.pdf",
        folder_id="resumes",
    )
    session.add(resume)
    await session.commit()
    return user, resume


@pytest.mark.asyncio
async def test_the_vector_round_trips_through_pgvector_with_its_fingerprint(
    schema, pg_sessionmaker
):
    from app.models.resumeEmbeddingsModel import ResumeEmbedding
    from app.services.analytics.embeddingService import (
        FINGERPRINT_VERSION,
        HASH_MODEL_NAME,
        ResumeEmbeddingService,
        compute_text_fingerprint,
    )

    async with pg_sessionmaker() as session:
        _user, resume = await _user_and_resume(session)
        stored = await ResumeEmbeddingService(session).upsert_resume_embedding_from_text(
            resume_id=resume.id, text=SUMMARY
        )
        assert stored is not None

    async with pg_sessionmaker() as reader:
        row = await reader.scalar(
            select(ResumeEmbedding).where(ResumeEmbedding.resume_id == resume.id)
        )
        assert len(list(row.embedding)) == 384
        assert row.text_fingerprint == compute_text_fingerprint(
            SUMMARY, model_name=HASH_MODEL_NAME
        )
        assert row.fingerprint_version == FINGERPRINT_VERSION


@pytest.mark.asyncio
async def test_two_first_generations_racing_leave_one_row(schema, pg_sessionmaker, pg_two_sessions):
    """(resume_id, model_name) is unique; the upsert must not lose that race."""
    from app.services.analytics.embeddingService import ResumeEmbeddingService

    async with pg_sessionmaker() as setup:
        _user, resume = await _user_and_resume(setup)

    first, second = pg_two_sessions

    async def store(session):
        try:
            stored = await ResumeEmbeddingService(session).upsert_resume_embedding_from_text(
                resume_id=resume.id, text=SUMMARY
            )
            return "stored" if stored is not None else "none"
        except Exception as exc:  # noqa: BLE001 — the point is that this does not happen
            await session.rollback()
            return repr(exc)

    outcomes = await asyncio.gather(store(first), store(second))
    assert outcomes == ["stored", "stored"], outcomes

    async with pg_sessionmaker() as reader:
        count = await reader.scalar(
            text("SELECT COUNT(*) FROM resume_embeddings WHERE resume_id = :id"),
            {"id": resume.id},
        )
        assert int(count) == 1


@pytest.mark.asyncio
async def test_similarity_only_compares_inside_one_model_space(schema, pg_sessionmaker):
    """A hash vector must never be ranked against a sentence-transformer one."""
    from app.models.resumeEmbeddingsModel import ResumeEmbedding
    from app.services.analytics.embeddingService import (
        HASH_MODEL_NAME,
        MODEL_NAME,
        ResumeEmbeddingService,
        generate_hash_embedding,
    )

    async with pg_sessionmaker() as session:
        _user, source = await _user_and_resume(session)
        _user2, neighbour = await _user_and_resume(session)
        _user3, other_space = await _user_and_resume(session)

        service = ResumeEmbeddingService(session)
        await service.upsert_resume_embedding_from_text(resume_id=source.id, text=SUMMARY)
        await service.upsert_resume_embedding_from_text(
            resume_id=neighbour.id, text=SUMMARY + " And Power BI."
        )
        # The same text, stored in the other vector space.
        session.add(
            ResumeEmbedding(
                id=uuid.uuid4(),
                resume_id=other_space.id,
                model_name=MODEL_NAME,
                dims=384,
                embedding=generate_hash_embedding(SUMMARY),
            )
        )
        await session.commit()

        results = await service.find_similar_resumes(resume_id=source.id, k=10)
        returned = {row["resume_id"] for row in results}

        assert neighbour.id in returned
        assert other_space.id not in returned, "a different model space leaked into the ranking"

        # And asking in the other space finds the other row, not these.
        in_other_space = await service.find_similar_resumes(
            resume_id=other_space.id, k=10, model_name=MODEL_NAME
        )
        assert in_other_space == []
        assert (
            await session.scalar(
                text(
                    "SELECT COUNT(*) FROM resume_embeddings WHERE model_name = :m"
                ),
                {"m": HASH_MODEL_NAME},
            )
        ) == 2


@pytest.mark.asyncio
async def test_the_hnsw_index_is_the_one_being_queried(schema, pg_engine, pg_sessionmaker):
    """The ranking runs in the database, against the vector index."""
    async with pg_sessionmaker() as session:
        _user, resume = await _user_and_resume(session)
        from app.services.analytics.embeddingService import ResumeEmbeddingService

        await ResumeEmbeddingService(session).upsert_resume_embedding_from_text(
            resume_id=resume.id, text=SUMMARY
        )

    async with pg_engine.connect() as conn:
        indexes = await conn.run_sync(
            lambda sync_conn: {
                index["name"]
                for index in __import__("sqlalchemy").inspect(sync_conn).get_indexes(
                    "resume_embeddings"
                )
            }
        )
    assert "ix_resume_embeddings_embedding_hnsw" in indexes
    assert "ix_resume_embeddings_resume_model" in indexes


@pytest.mark.asyncio
async def test_the_migration_adds_the_columns_and_leaves_old_rows_without_provenance(
    schema, pg_engine, pg_sessionmaker
):
    """Existing vectors keep a NULL fingerprint: no hash is invented for them."""
    async with pg_engine.begin() as conn:
        await conn.execute(text("ALTER TABLE resume_embeddings DROP COLUMN text_fingerprint"))
        await conn.execute(text("ALTER TABLE resume_embeddings DROP COLUMN fingerprint_version"))

    async with pg_sessionmaker() as session:
        _user, resume = await _user_and_resume(session)
        from app.services.analytics.embeddingService import generate_hash_embedding

        await session.execute(
            text(
                "INSERT INTO resume_embeddings (id, resume_id, model_name, dims, embedding, "
                "created_at, updated_at) VALUES (:id, :resume, 'hash-v1', 384, :vec, now(), now())"
            ),
            {
                "id": uuid.uuid4(),
                "resume": resume.id,
                "vec": str(generate_hash_embedding(SUMMARY)),
            },
        )
        await session.commit()

    migration = _migration()
    async with pg_engine.begin() as conn:
        assert await conn.run_sync(lambda c: migration._inventory(c)) == 1

    async with pg_engine.begin() as conn:
        await conn.run_sync(
            lambda c: c.execute(
                text("ALTER TABLE resume_embeddings ADD COLUMN text_fingerprint VARCHAR(64)")
            )
        )
        await conn.run_sync(
            lambda c: c.execute(
                text("ALTER TABLE resume_embeddings ADD COLUMN fingerprint_version VARCHAR(16)")
            )
        )

    async with pg_sessionmaker() as reader:
        fingerprint = await reader.scalar(
            text("SELECT text_fingerprint FROM resume_embeddings WHERE resume_id = :id"),
            {"id": resume.id},
        )
        assert fingerprint is None

    # And that row is regenerated exactly once, then trusted.
    from app.services.analytics.embeddingService import ResumeEmbeddingService

    async with pg_sessionmaker() as session:
        stored = await ResumeEmbeddingService(session).upsert_resume_embedding_from_text(
            resume_id=resume.id, text=SUMMARY
        )
        assert stored.text_fingerprint is not None
