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


@pytest_asyncio.fixture
async def pg_engine(postgres_url: str):
    """A PostgreSQL engine with pgvector available.

    NullPool because pytest-asyncio gives each test its own event loop.
    """
    engine = create_async_engine(postgres_url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
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
