"""PostgreSQL-only guarantees the SQLite fast lane cannot express.

The mapped metadata must actually build on PostgreSQL (JSONB, UUID, pgvector,
partial and expression indexes), and vector search must run against a real
``vector`` column rather than the SQLite stand-in.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select, text

pytestmark = [pytest.mark.integration, pytest.mark.postgres]


@pytest.fixture
def _models():
    """Import every mapped model so ``Base.metadata`` is complete."""
    import tests.conftest  # noqa: F401  (fixture module imports the model set)
    from app.db import Base

    return Base


@pytest.mark.asyncio
async def test_metadata_builds_on_postgres(pg_engine, _models):
    """create_all/drop_all round-trips: no SQLite-only type or index sneaks in."""
    from app.db import Base

    async with pg_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        async with pg_engine.connect() as conn:
            tables = set(
                (
                    await conn.execute(
                        text(
                            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
                        )
                    )
                ).scalars()
            )
        assert "users" in tables
        assert "resume_embeddings" in tables
    finally:
        async with pg_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)


@pytest.mark.asyncio
async def test_vector_column_supports_nearest_neighbour_search(pg_engine, pg_sessionmaker):
    """pgvector distance ordering works on the real column type.

    SQLite stores the embedding as an opaque value and cannot answer this, so
    this assertion is only meaningful in the PostgreSQL lane.
    """
    from app.db import Base
    from app.models.resumeEmbeddingsModel import ResumeEmbedding
    from app.models.resumeModel import ResumeModel
    from app.models.userModel import User

    async with pg_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    try:
        user_id = uuid.uuid4()
        async with pg_sessionmaker() as session:
            session.add(
                User(
                    id=user_id,
                    email=f"vector-{user_id}@example.invalid",
                    hashed_password="not-a-real-hash",
                    is_active=True,
                    is_superuser=False,
                    is_verified=True,
                )
            )
            await session.commit()

            near_id, far_id = uuid.uuid4(), uuid.uuid4()
            for resume_id, first_axis in ((near_id, 1.0), (far_id, -1.0)):
                session.add(
                    ResumeModel(
                        id=resume_id,
                        user_id=user_id,
                        view_url=f"https://files.invalid/{resume_id}.pdf",
                        storage_file_id=str(resume_id),
                        original_filename=f"{resume_id}.pdf",
                        folder_id="test-folder",
                    )
                )
                await session.flush()
                embedding = [0.0] * 384
                embedding[0] = first_axis
                session.add(
                    ResumeEmbedding(
                        resume_id=resume_id,
                        model_name="all-MiniLM-L6-v2",
                        dims=384,
                        embedding=embedding,
                    )
                )
            await session.commit()

            query = [0.0] * 384
            query[0] = 1.0
            ordered = (
                await session.execute(
                    select(ResumeEmbedding.resume_id).order_by(
                        ResumeEmbedding.embedding.l2_distance(query)
                    )
                )
            ).scalars().all()

        assert ordered[0] == near_id
        assert ordered[-1] == far_id
    finally:
        async with pg_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
