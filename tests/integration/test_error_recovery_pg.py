"""TASK-011 on the real backend: a failed statement aborts the PostgreSQL
transaction, and the error handler must hand the session back usable.

SQLite raises the same SQLAlchemy state error, but only PostgreSQL reproduces
the actual server-side abort ("current transaction is aborted, commands ignored
until end of transaction block"), which is what makes a missing rollback fatal
for the rest of a request in production.
"""
from __future__ import annotations

import logging

import pytest
from sqlalchemy import text

from app.core.errors import client_failure, server_failure

pytestmark = [pytest.mark.integration, pytest.mark.postgres]

LOGGER = logging.getLogger(__name__)


@pytest.fixture
async def scratch_table(pg_engine):
    async with pg_engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS error_recovery_scratch"))
        await conn.execute(
            text("CREATE TABLE error_recovery_scratch (id integer PRIMARY KEY, label text UNIQUE)")
        )
        await conn.execute(text("INSERT INTO error_recovery_scratch VALUES (1, 'taken')"))
    yield
    async with pg_engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS error_recovery_scratch"))


async def _poison(session) -> Exception:
    """Abort the transaction the way a real constraint violation does."""
    with pytest.raises(Exception) as failure:
        await session.execute(text("INSERT INTO error_recovery_scratch VALUES (2, 'taken')"))
    with pytest.raises(Exception):
        # Precondition: PostgreSQL refuses everything until the block ends.
        await session.execute(text("SELECT 1"))
    return failure.value


@pytest.mark.asyncio
async def test_server_failure_leaves_the_session_usable(pg_session, scratch_table):
    exc = await _poison(pg_session)

    error = await server_failure(exc, logger=LOGGER, session=pg_session)

    assert error.status_code == 500
    assert (await pg_session.execute(text("SELECT 1"))).scalar_one() == 1


@pytest.mark.asyncio
async def test_client_failure_leaves_the_session_usable(pg_session, scratch_table):
    exc = await _poison(pg_session)

    error = await client_failure(exc, logger=LOGGER, session=pg_session)

    assert error.status_code == 400
    assert (await pg_session.execute(text("SELECT 1"))).scalar_one() == 1


@pytest.mark.asyncio
async def test_a_driver_error_never_becomes_the_public_message(pg_session, scratch_table):
    """The real asyncpg message names the table, the constraint and the values."""
    exc = await _poison(pg_session)
    raw = str(exc)
    assert "error_recovery_scratch" in raw  # the leak this task removes

    error = await client_failure(exc, logger=LOGGER, session=pg_session)

    assert "error_recovery_scratch" in raw
    assert "error_recovery_scratch" not in error.detail
    assert "INSERT" not in error.detail
