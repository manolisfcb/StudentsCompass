"""Migration guarantees that only a real PostgreSQL server can answer.

Three things are checked here, none of which SQLite can express:

* an empty database can be bootstrapped at all — the historical chain cannot
  be replayed from nothing, so ``app/db_baseline`` is the only path;
* the result of that bootstrap matches the mapped metadata, and a further
  autogenerate proposes neither a dropped table nor a dropped index;
* both historical shapes of ``resource_lesson_progress`` converge onto the
  same columns, and the application's own writer still inserts afterwards.

Every test works on its own throwaway PostgreSQL *schema* so the lane can run
repeatedly without leaving state behind.
"""
from __future__ import annotations

import asyncio
import uuid

import pytest
from alembic.autogenerate import compare_metadata
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import inspect, text

pytestmark = [pytest.mark.integration, pytest.mark.postgres]


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


# --------------------------------------------------------------------------
# Empty-database bootstrap
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_database_is_detected_as_empty(pg_engine):
    from app.db_baseline import database_is_empty

    await _reset_public_schema(pg_engine)
    async with pg_engine.connect() as conn:
        assert await conn.run_sync(database_is_empty) is True


@pytest.mark.asyncio
async def test_a_database_with_tables_is_never_treated_as_empty(pg_engine):
    """The expensive mistake would be running the baseline over live data."""
    from app.db_baseline import database_is_empty

    await _reset_public_schema(pg_engine)
    async with pg_engine.begin() as conn:
        await conn.execute(text("CREATE TABLE alembic_version (version_num varchar(32))"))
    async with pg_engine.connect() as conn:
        assert await conn.run_sync(database_is_empty) is False


@pytest.mark.asyncio
async def test_bootstrap_creates_the_schema_and_stamps_head(pg_engine, metadata):
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    await _reset_public_schema(pg_engine)

    async with pg_engine.connect() as conn:
        await conn.run_sync(_bootstrap, metadata)
        await conn.commit()

    async with pg_engine.connect() as conn:
        tables = set(await conn.run_sync(lambda c: inspect(c).get_table_names()))
        stamped = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar_one()

    assert {"users", "resumes", "roadmaps", "resource_lesson_progress"} <= tables

    config = Config("alembic.ini")
    config.set_main_option("script_location", "alembic")
    assert stamped == ScriptDirectory.from_config(config).get_current_head()


@pytest.mark.asyncio
async def test_bootstrapped_schema_matches_metadata(pg_engine, metadata):
    """No diff at all — this is the check that licenses the stamp."""
    await _reset_public_schema(pg_engine)

    async with pg_engine.connect() as conn:
        await conn.run_sync(_bootstrap, metadata)
        await conn.commit()

    async with pg_engine.connect() as conn:
        differences = await conn.run_sync(
            lambda c: compare_metadata(MigrationContext.configure(c), metadata)
        )

    assert differences == [], f"schema drifted from the models: {differences}"


@pytest.mark.asyncio
async def test_autogenerate_after_bootstrap_drops_nothing(pg_engine, metadata):
    """The regression that removed a batch of live indexes must not recur."""
    await _reset_public_schema(pg_engine)

    async with pg_engine.connect() as conn:
        await conn.run_sync(_bootstrap, metadata)
        await conn.commit()

    async with pg_engine.connect() as conn:
        differences = await conn.run_sync(
            lambda c: compare_metadata(MigrationContext.configure(c), metadata)
        )

    removals = [
        difference
        for difference in differences
        if isinstance(difference, tuple)
        and str(difference[0]).startswith(("remove_table", "remove_index", "remove_column"))
    ]
    assert removals == []


@pytest.mark.asyncio
async def test_baseline_refuses_to_stamp_a_schema_that_does_not_match(pg_engine, metadata):
    """A stale baseline must fail loudly rather than stamp a wrong database."""
    from sqlalchemy import Column, Integer, MetaData, Table

    from app.db_baseline import BaselineVerificationError

    await _reset_public_schema(pg_engine)

    extended = MetaData()
    for table in metadata.tables.values():
        table.to_metadata(extended)
    Table("table_the_baseline_does_not_create", extended, Column("id", Integer, primary_key=True))

    async with pg_engine.connect() as conn:
        with pytest.raises(BaselineVerificationError):
            await conn.run_sync(_bootstrap, extended)
        await conn.rollback()

    async with pg_engine.connect() as conn:
        tables = set(await conn.run_sync(lambda c: inspect(c).get_table_names()))
    assert "alembic_version" not in tables


# --------------------------------------------------------------------------
# resource_lesson_progress convergence
# --------------------------------------------------------------------------

# Verbatim from 6e4bc7a18f21: resource_id NOT NULL, audit columns, nullable
# progress timestamps.
SHAPE_WITH_RESOURCE_ID = """
CREATE TABLE resource_lesson_progress (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    resource_id uuid NOT NULL,
    lesson_id uuid NOT NULL,
    completed_at timestamp NULL,
    last_opened_at timestamp NULL,
    created_at timestamp NOT NULL DEFAULT now(),
    updated_at timestamp NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    CONSTRAINT uq_resource_lesson_progress_user_lesson UNIQUE (user_id, lesson_id),
    FOREIGN KEY (lesson_id) REFERENCES resource_lessons (id) ON DELETE CASCADE,
    FOREIGN KEY (resource_id) REFERENCES resources (id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
)
"""

# Verbatim from 8c1d4a2b9f77: no resource_id, no audit columns, NOT NULL
# progress timestamps.
SHAPE_WITHOUT_RESOURCE_ID = """
CREATE TABLE resource_lesson_progress (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    lesson_id uuid NOT NULL,
    completed_at timestamp NOT NULL DEFAULT now(),
    last_opened_at timestamp NOT NULL DEFAULT now(),
    PRIMARY KEY (id),
    CONSTRAINT uq_resource_lesson_progress_user_lesson UNIQUE (user_id, lesson_id),
    FOREIGN KEY (lesson_id) REFERENCES resource_lessons (id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
)
"""


def _run_convergence(sync_conn) -> None:
    """Run a7f4c2b8d590's upgrade against this connection."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "revision_a7f4c2b8d590",
        "alembic/versions/a7f4c2b8d590_converge_resource_lesson_progress_shape.py",
    )
    revision = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(revision)

    with Operations.context(MigrationContext.configure(sync_conn)):
        revision.upgrade()


async def _seed_shape(pg_engine, metadata, create_sql: str) -> dict:
    """Build a database in one of the two historical shapes, with one row."""
    await _reset_public_schema(pg_engine)

    async with pg_engine.connect() as conn:
        await conn.run_sync(_bootstrap, metadata)
        await conn.commit()

    ids = {key: uuid.uuid4() for key in ("user", "resource", "module", "lesson", "progress")}

    async with pg_engine.begin() as conn:
        await conn.execute(text("DROP TABLE resource_lesson_progress"))
        await conn.execute(text(create_sql))
        await conn.execute(
            text(
                "INSERT INTO users (id, email, hashed_password, is_active, is_superuser,"
                " is_verified, created_at, updated_at)"
                " VALUES (:id, :email, 'x', true, false, true, now(), now())"
            ),
            {"id": ids["user"], "email": f"converge-{ids['user']}@example.invalid"},
        )
        await conn.execute(
            text(
                "INSERT INTO resources (id, title, description, category, created_at,"
                " updated_at, is_published, is_locked)"
                " VALUES (:id, 't', 'd', 'c', now(), now(), true, false)"
            ),
            {"id": ids["resource"]},
        )
        await conn.execute(
            text(
                "INSERT INTO resource_modules (id, resource_id, title, position, created_at,"
                " updated_at) VALUES (:id, :resource_id, 'm', 1, now(), now())"
            ),
            {"id": ids["module"], "resource_id": ids["resource"]},
        )
        await conn.execute(
            text(
                "INSERT INTO resource_lessons (id, module_id, title, position, content_type,"
                " content, created_at, updated_at)"
                " VALUES (:id, :module_id, 'l', 1, 'text', 'body', now(), now())"
            ),
            {"id": ids["lesson"], "module_id": ids["module"]},
        )

        columns = "id, user_id, lesson_id"
        values = ":id, :user_id, :lesson_id"
        params = {
            "id": ids["progress"],
            "user_id": ids["user"],
            "lesson_id": ids["lesson"],
        }
        if "resource_id uuid NOT NULL" in create_sql:
            columns += ", resource_id"
            values += ", :resource_id"
            params["resource_id"] = ids["resource"]
        await conn.execute(
            text(f"INSERT INTO resource_lesson_progress ({columns}) VALUES ({values})"), params
        )

    return ids


async def _converged_columns(pg_engine) -> dict:
    async with pg_engine.connect() as conn:
        await conn.run_sync(_run_convergence)
        await conn.commit()
    async with pg_engine.connect() as conn:
        columns = await conn.run_sync(
            lambda c: {col["name"]: col for col in inspect(c).get_columns("resource_lesson_progress")}
        )
    return columns


@pytest.mark.asyncio
async def test_both_historical_shapes_converge_to_the_same_columns(pg_engine, metadata):
    await _seed_shape(pg_engine, metadata, SHAPE_WITH_RESOURCE_ID)
    with_resource_id = await _converged_columns(pg_engine)

    await _seed_shape(pg_engine, metadata, SHAPE_WITHOUT_RESOURCE_ID)
    without_resource_id = await _converged_columns(pg_engine)

    assert set(with_resource_id) == set(without_resource_id)
    assert {
        "id",
        "user_id",
        "resource_id",
        "lesson_id",
        "completed_at",
        "last_opened_at",
        "created_at",
        "updated_at",
    } == set(with_resource_id)

    for columns in (with_resource_id, without_resource_id):
        assert columns["completed_at"]["nullable"] is True
        assert columns["last_opened_at"]["nullable"] is True
        assert columns["created_at"]["nullable"] is False


@pytest.mark.asyncio
async def test_convergence_backfills_resource_id_and_keeps_the_row(pg_engine, metadata):
    ids = await _seed_shape(pg_engine, metadata, SHAPE_WITHOUT_RESOURCE_ID)

    async with pg_engine.connect() as conn:
        await conn.run_sync(_run_convergence)
        await conn.commit()

    async with pg_engine.connect() as conn:
        rows = (
            await conn.execute(
                text("SELECT id, resource_id FROM resource_lesson_progress")
            )
        ).all()

    assert len(rows) == 1, "convergence must not discard progress rows"
    assert rows[0][0] == ids["progress"]
    assert rows[0][1] == ids["resource"], "resource_id derived through lesson -> module"


@pytest.mark.asyncio
async def test_convergence_is_re_runnable(pg_engine, metadata):
    """An interrupted migration has to be resumable by running it again."""
    await _seed_shape(pg_engine, metadata, SHAPE_WITHOUT_RESOURCE_ID)

    for _ in range(2):
        async with pg_engine.connect() as conn:
            await conn.run_sync(_run_convergence)
            await conn.commit()

    async with pg_engine.connect() as conn:
        count = (
            await conn.execute(text("SELECT count(*) FROM resource_lesson_progress"))
        ).scalar_one()
    assert count == 1


@pytest.mark.asyncio
async def test_current_writer_still_records_progress_after_convergence(pg_engine, pg_sessionmaker, metadata):
    """The application inserts without resource_id; that must keep working."""
    from app.models.resourceModel import ResourceLessonProgressModel

    ids = await _seed_shape(pg_engine, metadata, SHAPE_WITH_RESOURCE_ID)
    async with pg_engine.connect() as conn:
        await conn.run_sync(_run_convergence)
        await conn.commit()

    # Free the unique (user_id, lesson_id) pair the seed row occupies.
    async with pg_engine.begin() as conn:
        await conn.execute(text("DELETE FROM resource_lesson_progress"))

    async with pg_sessionmaker() as session:
        session.add(
            ResourceLessonProgressModel(
                user_id=ids["user"],
                lesson_id=ids["lesson"],
            )
        )
        await session.commit()

    async with pg_engine.connect() as conn:
        stored = (
            await conn.execute(
                text("SELECT lesson_id, resource_id, created_at FROM resource_lesson_progress")
            )
        ).all()

    assert len(stored) == 1
    assert stored[0][0] == ids["lesson"]
    assert stored[0][1] is None
    assert stored[0][2] is not None


# --------------------------------------------------------------------------
# Existing installations
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_existing_installation_upgrades_forward_to_the_new_head(pg_engine, metadata):
    """A database stamped at the previous head takes the chain, not the baseline."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    await _reset_public_schema(pg_engine)

    async with pg_engine.connect() as conn:
        await conn.run_sync(_bootstrap, metadata)
        await conn.commit()

    config = Config("alembic.ini")
    config.set_main_option("script_location", "alembic")
    script = ScriptDirectory.from_config(config)
    head = script.get_current_head()
    previous = script.get_revision(head).down_revision

    async with pg_engine.begin() as conn:
        await conn.execute(
            text("UPDATE alembic_version SET version_num = :previous"), {"previous": previous}
        )

    async with pg_engine.connect() as conn:
        await conn.run_sync(_run_convergence)
        await conn.execute(
            text("UPDATE alembic_version SET version_num = :head"), {"head": head}
        )
        await conn.commit()

    async with pg_engine.connect() as conn:
        differences = await conn.run_sync(
            lambda c: compare_metadata(MigrationContext.configure(c), metadata)
        )
    assert differences == []


# --------------------------------------------------------------------------
# The real entry point
# --------------------------------------------------------------------------


def _alembic_config(url: str):
    from alembic.config import Config

    config = Config("alembic.ini")
    config.set_main_option("script_location", "alembic")
    config.set_main_option("sqlalchemy.url", url)
    return config


def _run_upgrade_head(url: str) -> None:
    """Drive `alembic upgrade head` exactly as a deploy would."""
    import os

    from alembic import command

    previous = os.environ.get("ALEMBIC_DATABASE_URL")
    os.environ["ALEMBIC_DATABASE_URL"] = url
    try:
        command.upgrade(_alembic_config(url), "head")
    finally:
        if previous is None:
            os.environ.pop("ALEMBIC_DATABASE_URL", None)
        else:
            os.environ["ALEMBIC_DATABASE_URL"] = previous


@pytest.mark.asyncio
async def test_upgrade_head_bootstraps_an_empty_database(pg_engine, postgres_url, metadata):
    """End to end through env.py, not just the bootstrap helper."""
    from alembic.script import ScriptDirectory

    await _reset_public_schema(pg_engine)
    sync_url = postgres_url.replace("+asyncpg", "+psycopg")

    await asyncio.to_thread(_run_upgrade_head, sync_url)

    async with pg_engine.connect() as conn:
        stamped = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar_one()
        differences = await conn.run_sync(
            lambda c: compare_metadata(MigrationContext.configure(c), metadata)
        )

    assert stamped == ScriptDirectory.from_config(_alembic_config(sync_url)).get_current_head()
    assert differences == []


@pytest.mark.asyncio
async def test_upgrade_head_commits_on_an_existing_database(pg_engine, postgres_url, metadata):
    """Regression: inspecting for emptiness left a transaction open, and the
    chain then ran and rolled straight back without stamping anything."""
    from alembic.script import ScriptDirectory

    await _reset_public_schema(pg_engine)
    sync_url = postgres_url.replace("+asyncpg", "+psycopg")
    await asyncio.to_thread(_run_upgrade_head, sync_url)

    script = ScriptDirectory.from_config(_alembic_config(sync_url))
    head = script.get_current_head()
    previous = script.get_revision(head).down_revision

    # Rewind one revision, undoing what it created, and replay it.
    async with pg_engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS storage_deletion_intents"))
        await conn.execute(
            text("UPDATE alembic_version SET version_num = :previous"), {"previous": previous}
        )

    await asyncio.to_thread(_run_upgrade_head, sync_url)

    async with pg_engine.connect() as conn:
        stamped = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar_one()
        tables = set(await conn.run_sync(lambda c: inspect(c).get_table_names()))

    assert stamped == head, "the upgrade must be committed, not rolled back"
    assert "storage_deletion_intents" in tables
