"""PostgreSQL + Redis lane.

Opt-in: every fixture here skips unless the lane is pointed at a disposable
local service. SQLite does not substitute for this lane — row locks, partial
and unique indexes, CHECK constraints, pgvector and the Alembic chain only
behave correctly here.

Start the services and run the lane with::

    docker run -d --name sc-test-pg -e POSTGRES_PASSWORD=testpw \
        -e POSTGRES_USER=testuser -e POSTGRES_DB=studentscompass_test \
        -p 55432:5432 pgvector/pgvector:pg16
    docker run -d --name sc-test-redis -p 56379:6379 redis:7-alpine

    TEST_DATABASE_URL_PG=postgresql+asyncpg://testuser:testpw@127.0.0.1:55432/studentscompass_test \
    TEST_REDIS_URL=redis://127.0.0.1:56379/0 \
    .venv/bin/python -m pytest -o addopts='' -p no:cacheprovider tests/integration
"""
from __future__ import annotations

import os
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from tests.isolation import allow_test_service, assert_local_url

PG_URL_ENV = "TEST_DATABASE_URL_PG"
REDIS_URL_ENV = "TEST_REDIS_URL"

_SKIP_PG = f"{PG_URL_ENV} is not set; PostgreSQL lane skipped"
_SKIP_REDIS = f"{REDIS_URL_ENV} is not set; Redis lane skipped"


def _lane_url(env_name: str) -> str | None:
    url = os.environ.get(env_name, "").strip()
    if not url:
        return None
    # A stale env var must never aim the lane at a real deployment.
    assert_local_url(url, setting=env_name)
    allow_test_service(url)
    return url


@pytest.fixture(scope="session")
def postgres_url() -> str:
    url = _lane_url(PG_URL_ENV)
    if not url:
        pytest.skip(_SKIP_PG)
    return url


@pytest.fixture(scope="session")
def redis_url() -> str:
    url = _lane_url(REDIS_URL_ENV)
    if not url:
        pytest.skip(_SKIP_REDIS)
    return url


#: Any 64-bit key works; it only has to be the same one everywhere. Named so a
#: `pg_locks` row during a wedged run says what is holding it.
SCHEMA_RESET_LOCK = 0x5C_7E_57_00  # "SC TEST"


async def reset_public_schema(engine) -> None:
    """Drop and rebuild ``public``, leaving the ``vector`` extension in place.

    Added by TASK-031. Eleven modules in this lane build the schema with
    ``metadata.create_all`` and tear it down with ``metadata.drop_all``, and
    several of them provoke an ``IntegrityError`` on purpose. An aborted
    transaction still holds row locks, so ``drop_all`` — which needs an
    ``AccessExclusiveLock`` per table — blocked against them and silently left
    tables behind; the next test's ``create_all`` then failed with "relation
    already exists". The lane produced different results on identical runs.

    Resetting here means a test cannot inherit what the previous one failed to
    clean up, whatever that was. ``DROP SCHEMA ... CASCADE`` also ignores table
    order and any constraint a test dropped deliberately.

    **This is the lane's only definition of "reset".** ``test_migrations.py`` used
    to carry a second one that dropped the schema without putting ``vector`` back;
    since the extension lives in ``public``, ``DROP SCHEMA public CASCADE`` takes it
    with it, and the next module's ``create_all`` then failed on the ``Vector``
    column of ``resume_embeddings``. That aborts its transaction, so nothing after
    it could insert either — the "relation \"users\" does not exist" cascade that
    made this lane reliable only file by file (TASK-070).

    The whole reset is serialised on an advisory lock. ``app/db_baseline.py``
    issues ``CREATE EXTENSION IF NOT EXISTS vector`` on the bootstrap path, and
    ``test_migrations.py`` drives that path from another thread; ``IF NOT EXISTS``
    reads the catalogue at statement start, so two creators can still collide on
    ``pg_extension_name_index``. The loser's transaction aborts and the cascade
    starts again from a different place.
    """
    # Release this engine's own connections first: dropping the schema while the
    # pool still holds one deadlocks rather than waiting.
    await engine.dispose()
    async with engine.begin() as conn:
        # Session-level, and this connection is closed at the end of the block,
        # which releases it. A transaction-level lock would be released by the
        # COMMIT between the two statements below.
        await conn.execute(text("SELECT pg_advisory_lock(:key)"), {"key": SCHEMA_RESET_LOCK})
        await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        # Recreated here, inside the lock and before anyone else can look: the
        # drop removed it, so putting it back is part of resetting, not a
        # separate step someone else might do first. Checked against the
        # catalogue rather than IF NOT EXISTS, which is not safe against a
        # concurrent creator outside this lock.
        present = await conn.scalar(
            text("SELECT COUNT(*) FROM pg_extension WHERE extname = 'vector'")
        )
        if not int(present or 0):
            await conn.execute(text("CREATE EXTENSION vector"))
        await conn.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": SCHEMA_RESET_LOCK})

    # The reset must leave the lane usable, not merely not raise. Asserting it
    # here turns "the extension went missing" into a failure at the place that
    # caused it, instead of a create_all failure in whichever module runs next.
    async with engine.begin() as conn:
        present = await conn.scalar(
            text("SELECT COUNT(*) FROM pg_extension WHERE extname = 'vector'")
        )
        if not int(present or 0):
            raise RuntimeError(
                "the schema reset left the lane without the 'vector' extension; "
                "every module that maps a Vector column would fail from here on"
            )


@pytest_asyncio.fixture
async def pg_engine(postgres_url: str):
    """A PostgreSQL engine with pgvector available, over an empty schema.

    NullPool because pytest-asyncio gives each test its own event loop.
    """
    engine = create_async_engine(postgres_url, poolclass=NullPool)
    await reset_public_schema(engine)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def pg_sessionmaker(pg_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(pg_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def pg_session(pg_sessionmaker) -> AsyncGenerator[AsyncSession, None]:
    async with pg_sessionmaker() as session:
        yield session


@pytest_asyncio.fixture
async def pg_two_sessions(pg_sessionmaker):
    """Two sessions on separate connections: real locks, real races."""
    from tests.harness import two_sessions

    async with two_sessions(pg_sessionmaker) as sessions:
        yield sessions


@pytest.fixture
def pg_query_counter(pg_engine):
    from tests.harness import count_queries

    def _counter():
        return count_queries(pg_engine)

    return _counter


@pytest_asyncio.fixture
async def redis_client(redis_url: str):
    from redis import asyncio as redis_asyncio

    client = redis_asyncio.from_url(redis_url, encoding="utf-8", decode_responses=True)
    await client.flushdb()
    try:
        yield client
    finally:
        await client.flushdb()
        await client.aclose()
