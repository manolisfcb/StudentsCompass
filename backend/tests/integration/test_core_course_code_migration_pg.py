"""The core-course identity migration, against a real server.

Two things SQLite cannot settle: whether the unique index actually refuses a
second row with the same code, and whether the backfill behaves on the shapes a
deployed database can be in — one clean match, no match, or an ambiguous pair.

Nothing is renamed, merged or deleted by the migration; an ambiguous match is
left for an operator, which is what these tests pin.
"""
from __future__ import annotations

import uuid

import pytest
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import text

pytestmark = [pytest.mark.integration, pytest.mark.postgres]

REVISION_PATH = "alembic/versions/a7d3f81c9e64_add_core_code_to_resources.py"


@pytest.fixture
def metadata():
    from app.models.registry import Base, import_all_models

    import_all_models()
    return Base.metadata


async def _reset_public_schema(engine) -> None:
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))


def _bootstrap(sync_conn, metadata) -> None:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    from app.db_baseline import bootstrap

    config = Config("alembic.ini")
    config.set_main_option("script_location", "alembic")
    bootstrap(sync_conn, ScriptDirectory.from_config(config), metadata)


def _run_core_code_upgrade(sync_conn) -> None:
    """Run a7d3f81c9e64's upgrade against this connection."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("revision_a7d3f81c9e64", REVISION_PATH)
    revision = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(revision)

    with Operations.context(MigrationContext.configure(sync_conn)):
        revision.upgrade()


async def _database_without_core_code(pg_engine, metadata) -> None:
    """A schema in the shape it had before this revision."""
    await _reset_public_schema(pg_engine)
    async with pg_engine.connect() as conn:
        await conn.run_sync(_bootstrap, metadata)
        await conn.commit()
    async with pg_engine.begin() as conn:
        await conn.execute(text("DROP INDEX IF EXISTS ix_resources_core_code"))
        await conn.execute(text("ALTER TABLE resources DROP COLUMN core_code"))


async def _insert_resource(conn, *, title: str, published: bool = True) -> uuid.UUID:
    resource_id = uuid.uuid4()
    await conn.execute(
        text(
            "INSERT INTO resources (id, title, description, category, created_at,"
            " updated_at, is_published, is_locked)"
            " VALUES (:id, :title, 'd', 'Career', now(), now(), :published, false)"
        ),
        {"id": resource_id, "title": title, "published": published},
    )
    return resource_id


async def _code_of(pg_engine, resource_id: uuid.UUID) -> str | None:
    async with pg_engine.connect() as conn:
        return await conn.scalar(
            text("SELECT core_code FROM resources WHERE id = :id"), {"id": resource_id}
        )


@pytest.mark.asyncio
async def test_the_backfill_claims_exactly_one_row_per_core_course(pg_engine, metadata):
    await _database_without_core_code(pg_engine, metadata)

    async with pg_engine.begin() as conn:
        resume = await _insert_resource(conn, title="Resume Templates")
        linkedin = await _insert_resource(conn, title="LinkedIn Optimization")
        interview = await _insert_resource(conn, title="Interview Preparation")
        unrelated = await _insert_resource(conn, title="Salary Negotiation")

    async with pg_engine.connect() as conn:
        await conn.run_sync(_run_core_code_upgrade)
        await conn.commit()

    assert await _code_of(pg_engine, resume) == "resume_templates"
    assert await _code_of(pg_engine, linkedin) == "linkedin_optimization"
    assert await _code_of(pg_engine, interview) == "interview_preparation"
    # An ordinary resource is not required to carry a code.
    assert await _code_of(pg_engine, unrelated) is None


@pytest.mark.asyncio
async def test_an_ambiguous_title_is_left_for_an_operator(pg_engine, metadata):
    """Two published courses share a title: neither is claimed, neither is touched."""
    await _database_without_core_code(pg_engine, metadata)

    async with pg_engine.begin() as conn:
        first = await _insert_resource(conn, title="Resume Templates")
        second = await _insert_resource(conn, title="Resume Templates")

    async with pg_engine.connect() as conn:
        await conn.run_sync(_run_core_code_upgrade)
        await conn.commit()

    assert await _code_of(pg_engine, first) is None
    assert await _code_of(pg_engine, second) is None
    async with pg_engine.connect() as conn:
        surviving = await conn.scalar(text("SELECT COUNT(*) FROM resources"))
    assert surviving == 2  # nothing was merged or deleted


@pytest.mark.asyncio
async def test_an_unpublished_course_is_not_claimed(pg_engine, metadata):
    await _database_without_core_code(pg_engine, metadata)

    async with pg_engine.begin() as conn:
        hidden = await _insert_resource(conn, title="Resume Templates", published=False)

    async with pg_engine.connect() as conn:
        await conn.run_sync(_run_core_code_upgrade)
        await conn.commit()

    assert await _code_of(pg_engine, hidden) is None


@pytest.mark.asyncio
async def test_a_second_row_cannot_take_a_code_that_is_taken(pg_engine, metadata):
    """The unique index is real, and NULLs stay unconstrained beside it."""
    from sqlalchemy.exc import IntegrityError

    await _database_without_core_code(pg_engine, metadata)

    async with pg_engine.begin() as conn:
        await _insert_resource(conn, title="Resume Templates")

    async with pg_engine.connect() as conn:
        await conn.run_sync(_run_core_code_upgrade)
        await conn.commit()

    with pytest.raises(IntegrityError):
        async with pg_engine.begin() as conn:
            impostor = await _insert_resource(conn, title="Resume Templates Copy")
            await conn.execute(
                text("UPDATE resources SET core_code = 'resume_templates' WHERE id = :id"),
                {"id": impostor},
            )

    # Any number of rows may carry no code at all.
    async with pg_engine.begin() as conn:
        await _insert_resource(conn, title="Something Else")
        await _insert_resource(conn, title="Another Thing")
    async with pg_engine.connect() as conn:
        uncoded = await conn.scalar(text("SELECT COUNT(*) FROM resources WHERE core_code IS NULL"))
    assert uncoded == 2


@pytest.mark.asyncio
async def test_the_migration_is_re_runnable(pg_engine, metadata):
    await _database_without_core_code(pg_engine, metadata)

    async with pg_engine.begin() as conn:
        resume = await _insert_resource(conn, title="Resume Templates")

    for _ in range(2):
        async with pg_engine.connect() as conn:
            await conn.run_sync(_run_core_code_upgrade)
            await conn.commit()

    assert await _code_of(pg_engine, resume) == "resume_templates"


@pytest.mark.asyncio
async def test_an_operator_assignment_is_not_overwritten(pg_engine, metadata):
    """A code placed by hand survives a later run, even against a title match."""
    await _database_without_core_code(pg_engine, metadata)

    async with pg_engine.begin() as conn:
        chosen = await _insert_resource(conn, title="Resume Fundamentals")
        by_title = await _insert_resource(conn, title="Resume Templates")

    async with pg_engine.begin() as conn:
        await conn.execute(text("ALTER TABLE resources ADD COLUMN IF NOT EXISTS core_code VARCHAR(64)"))
        await conn.execute(
            text("UPDATE resources SET core_code = 'resume_templates' WHERE id = :id"),
            {"id": chosen},
        )

    async with pg_engine.connect() as conn:
        await conn.run_sync(_run_core_code_upgrade)
        await conn.commit()

    assert await _code_of(pg_engine, chosen) == "resume_templates"
    assert await _code_of(pg_engine, by_title) is None
