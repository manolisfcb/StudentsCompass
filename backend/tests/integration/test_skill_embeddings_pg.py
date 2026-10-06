"""``skill_embeddings`` against a real server (TASK-074).

What SQLite cannot answer: whether the revision builds the table, the unique
index and the HNSW index on pgvector, whether its downgrade undoes exactly that,
whether the baseline and the revision agree with the models, and whether two
sessions embedding the same new skill at once end up with one row.
"""
from __future__ import annotations

import asyncio
import importlib.util
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic.autogenerate import compare_metadata
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import select, text

from tests.integration.conftest import reset_public_schema

pytestmark = [pytest.mark.integration, pytest.mark.postgres]

REVISION_PATH = Path("alembic/versions/d3e8a1f5c702_add_skill_embeddings.py")


@pytest.fixture
def metadata():
    from app.models.registry import Base, import_all_models

    import_all_models()
    return Base.metadata


@pytest.fixture
def gemini(monkeypatch):
    from app import config
    from app.services.analytics import embeddingService
    from app.services.analytics.embeddingService import generate_hash_embedding

    calls: list[list[str]] = []

    async def embed_content(*, model, contents, config):
        calls.append(list(contents))
        # Yield so two concurrent callers really interleave.
        await asyncio.sleep(0.05)
        return SimpleNamespace(
            embeddings=[SimpleNamespace(values=generate_hash_embedding(t)) for t in contents]
        )

    models = SimpleNamespace(embed_content=embed_content)
    monkeypatch.setenv("EMBEDDINGS_PROVIDER", "gemini")
    monkeypatch.setenv("GENAI_API_KEY", "test-key")
    monkeypatch.setattr(config, "AI_KILL_SWITCH", False)
    monkeypatch.setattr(
        embeddingService,
        "_get_gemini_client",
        lambda: SimpleNamespace(aio=SimpleNamespace(models=models)),
    )
    return calls


def _bootstrap(sync_conn, metadata) -> None:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    from app.db_baseline import bootstrap

    config = Config("alembic.ini")
    config.set_main_option("script_location", "alembic")
    bootstrap(sync_conn, ScriptDirectory.from_config(config), metadata)


def _revision():
    spec = importlib.util.spec_from_file_location(REVISION_PATH.stem, REVISION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(sync_conn, step: str) -> None:
    with Operations.context(MigrationContext.configure(sync_conn)):
        getattr(_revision(), step)()


def _differences(sync_conn, metadata) -> list:
    return compare_metadata(MigrationContext.configure(sync_conn), metadata)


async def _indexes(conn) -> dict[str, str]:
    result = await conn.execute(
        text("SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'skill_embeddings'")
    )
    return {row.indexname: row.indexdef for row in result}


@pytest.mark.asyncio
async def test_the_revision_builds_what_the_models_declare_and_downgrade_undoes_it(
    pg_engine, metadata
):
    await reset_public_schema(pg_engine)
    async with pg_engine.connect() as conn:
        await conn.run_sync(_bootstrap, metadata)
        await conn.commit()

    # The database as it was one revision ago.
    async with pg_engine.begin() as conn:
        await conn.execute(text("DROP TABLE skill_embeddings"))

    async with pg_engine.begin() as conn:
        await conn.run_sync(_run, "upgrade")
    async with pg_engine.connect() as conn:
        assert await conn.run_sync(_differences, metadata) == []
        indexes = await _indexes(conn)
    assert "UNIQUE" in indexes["uq_skill_embeddings_skill_model"]
    assert "hnsw" in indexes["ix_skill_embeddings_embedding_hnsw"]
    assert "vector_cosine_ops" in indexes["ix_skill_embeddings_embedding_hnsw"]

    # Replayable: a second upgrade is a no-op, not an error.
    async with pg_engine.begin() as conn:
        await conn.run_sync(_run, "upgrade")

    async with pg_engine.begin() as conn:
        await conn.run_sync(_run, "downgrade")
    async with pg_engine.connect() as conn:
        exists = await conn.execute(text("SELECT to_regclass('public.skill_embeddings')"))
        assert exists.scalar() is None


@pytest.mark.asyncio
async def test_the_baseline_and_the_models_agree(pg_engine, metadata):
    await reset_public_schema(pg_engine)
    async with pg_engine.connect() as conn:
        await conn.run_sync(_bootstrap, metadata)
        await conn.commit()
    async with pg_engine.connect() as conn:
        assert await conn.run_sync(_differences, metadata) == []
        assert "ix_skill_embeddings_embedding_hnsw" in await _indexes(conn)


@pytest.fixture
async def schema(pg_engine, metadata):
    async with pg_engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    yield


@pytest.mark.asyncio
async def test_two_first_embeddings_of_one_skill_write_one_row(
    schema, pg_two_sessions, gemini
):
    from app.models.skillEmbeddingModel import SkillEmbedding
    from app.models.skillModel import SkillModel
    from app.services.analytics.skillEmbeddingService import SkillEmbeddingService

    first, second = pg_two_sessions
    skill = SkillModel(
        id=uuid.uuid4(),
        normalized_name=f"pyspark_{uuid.uuid4().hex[:6]}",
        display_name="PySpark",
        category="data_engineering",
        source="manual",
    )
    first.add(skill)
    await first.commit()
    as_dict = {
        "skill_id": skill.id,
        "display_name": skill.display_name,
        "normalized_name": skill.normalized_name,
        "category": skill.category,
    }

    left, right = await asyncio.gather(
        SkillEmbeddingService(first).get_vectors([as_dict]),
        SkillEmbeddingService(second).get_vectors([as_dict]),
    )

    assert set(left) == set(right) == {skill.id}
    rows = (
        await first.execute(select(SkillEmbedding).where(SkillEmbedding.skill_id == skill.id))
    ).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_nearest_skill_search_runs_on_pgvector(schema, pg_session, gemini):
    from app.models.skillEmbeddingModel import SkillEmbedding
    from app.models.skillModel import SkillModel
    from app.services.analytics.skillEmbeddingService import SkillEmbeddingService

    skills = [
        SkillModel(
            id=uuid.uuid4(),
            normalized_name=f"{name.lower()}_{uuid.uuid4().hex[:6]}",
            display_name=name,
            category="tools",
            source="manual",
        )
        for name in ("Tableau", "Kubernetes", "Excel")
    ]
    pg_session.add_all(skills)
    await pg_session.commit()
    await SkillEmbeddingService(pg_session).sync_catalog()

    probe = (
        await pg_session.execute(
            select(SkillEmbedding.embedding).where(SkillEmbedding.skill_id == skills[1].id)
        )
    ).scalar_one()
    distance = SkillEmbedding.embedding.cosine_distance(probe)
    nearest = (
        await pg_session.execute(
            select(SkillEmbedding.skill_id).order_by(distance.asc()).limit(1)
        )
    ).scalar_one()

    assert nearest == skills[1].id
