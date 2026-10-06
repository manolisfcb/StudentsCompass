"""``job_targets`` and ``job_description_parses`` against a real server (TASK-077).

SQLite serialises writers on one connection and does not enforce foreign keys
by default, so none of these mean anything there: the revision against
pgvector, two workers racing for one lease, two users storing the same parse at
once, and what deleting a CV or a user does to a saved vacancy.
"""
from __future__ import annotations

import asyncio
import importlib.util
import uuid
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import func, select, text

from tests.integration.conftest import reset_public_schema

pytestmark = [pytest.mark.integration, pytest.mark.postgres]

REVISION_PATH = Path("alembic/versions/e5b2c9d4a817_add_job_targets.py")
POSTING = "Data Analyst. We need SQL and Python; Tableau is a plus."


@pytest.fixture
def metadata():
    from app.models.registry import Base, import_all_models

    import_all_models()
    return Base.metadata


def _bootstrap(sync_conn, metadata) -> None:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    from app.db_baseline import bootstrap

    config = Config("alembic.ini")
    config.set_main_option("script_location", "alembic")
    bootstrap(sync_conn, ScriptDirectory.from_config(config), metadata)


def _run(sync_conn, step: str) -> None:
    spec = importlib.util.spec_from_file_location(REVISION_PATH.stem, REVISION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with Operations.context(MigrationContext.configure(sync_conn)):
        getattr(module, step)()


def _differences(sync_conn, metadata) -> list:
    return compare_metadata(MigrationContext.configure(sync_conn), metadata)


@pytest.mark.asyncio
async def test_the_revision_builds_what_the_models_declare_and_downgrade_undoes_it(
    pg_engine, metadata
):
    await reset_public_schema(pg_engine)
    async with pg_engine.connect() as conn:
        await conn.run_sync(_bootstrap, metadata)
        await conn.commit()
    async with pg_engine.connect() as conn:
        # The baseline alone already agrees with the models.
        assert await conn.run_sync(_differences, metadata) == []

    # One revision ago.
    async with pg_engine.begin() as conn:
        await conn.execute(text("DROP TABLE job_targets"))
        await conn.execute(text("DROP TABLE job_description_parses"))

    async with pg_engine.begin() as conn:
        await conn.run_sync(_run, "upgrade")
    async with pg_engine.connect() as conn:
        assert await conn.run_sync(_differences, metadata) == []
        partial = await conn.execute(
            text("SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_job_targets_active_lease'")
        )
        assert "WHERE" in partial.scalar_one()
        checks = await conn.execute(
            text(
                "SELECT conname FROM pg_constraint WHERE conrelid IN "
                "('job_targets'::regclass, 'job_description_parses'::regclass) AND contype = 'c'"
            )
        )
        assert set(checks.scalars()) == {
            "ck_job_targets_status",
            "ck_job_targets_workplace_type",
            "ck_job_targets_attempts_non_negative",
            "ck_job_description_parses_embedding_has_model",
        }

    async with pg_engine.begin() as conn:
        await conn.run_sync(_run, "upgrade")  # replayable
    async with pg_engine.begin() as conn:
        await conn.run_sync(_run, "downgrade")
    async with pg_engine.connect() as conn:
        for table in ("job_targets", "job_description_parses"):
            gone = await conn.execute(text(f"SELECT to_regclass('public.{table}')"))
            assert gone.scalar() is None


@pytest.fixture
async def schema(pg_engine, metadata):
    async with pg_engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    yield


async def _user(session):
    from app.models.userModel import User

    user = User(
        id=uuid.uuid4(),
        email=f"jt-{uuid.uuid4().hex[:8]}@example.invalid",
        hashed_password="x",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    session.add(user)
    await session.commit()
    return user


async def _resume(session, user_id):
    from app.models.resumeModel import ResumeModel

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


@pytest.mark.asyncio
async def test_two_workers_racing_for_one_target_get_one_lease(schema, pg_two_sessions):
    from app.services.careerLab.jobTargetService import JobTargetService

    first, second = pg_two_sessions
    user = await _user(first)
    target = await JobTargetService(first).create_target(user_id=user.id, raw_text=POSTING)

    results = await asyncio.gather(
        JobTargetService(first).claim(target.id),
        JobTargetService(second).claim(target.id),
    )

    assert sorted(results) == [False, True]


@pytest.mark.asyncio
async def test_two_users_storing_one_parse_at_once_write_one_row(schema, pg_two_sessions):
    from app.models.jobTargetModel import JobDescriptionParseModel
    from app.services.careerLab.jobTargetService import JobTargetService, job_text_hash

    first, second = pg_two_sessions
    text_hash = job_text_hash(f"{POSTING} {uuid.uuid4()}")

    left, right = await asyncio.gather(
        JobTargetService(first).store_parse(
            text_hash=text_hash, parsed={"by": "first"}, model_id="rules", prompt_version="v1"
        ),
        JobTargetService(second).store_parse(
            text_hash=text_hash, parsed={"by": "second"}, model_id="rules", prompt_version="v1"
        ),
    )

    assert left.parsed == right.parsed
    count = await first.scalar(
        select(func.count())
        .select_from(JobDescriptionParseModel)
        .where(JobDescriptionParseModel.text_hash == text_hash)
    )
    assert count == 1


@pytest.mark.asyncio
async def test_deleting_a_cv_keeps_the_vacancy_and_deleting_the_user_removes_it(
    schema, pg_session
):
    from app.models.jobTargetModel import JobTargetModel
    from app.services.careerLab.jobTargetService import JobTargetService

    user = await _user(pg_session)
    resume = await _resume(pg_session, user.id)
    target = await JobTargetService(pg_session).create_target(
        user_id=user.id, raw_text=POSTING, resume_id=resume.id
    )

    await pg_session.execute(text("DELETE FROM resumes WHERE id = :id"), {"id": resume.id})
    await pg_session.commit()
    kept = await pg_session.execute(
        select(JobTargetModel.resume_id).where(JobTargetModel.id == target.id)
    )
    assert kept.one().resume_id is None

    await pg_session.execute(text("DELETE FROM users WHERE id = :id"), {"id": user.id})
    await pg_session.commit()
    left = await pg_session.scalar(
        select(func.count()).select_from(JobTargetModel).where(JobTargetModel.id == target.id)
    )
    assert left == 0
