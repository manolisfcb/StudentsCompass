"""Proves the two-session harness observes real PostgreSQL concurrency.

Later tasks (application transitions, interview slots, quota ledger) assert
correctness under interleaved transactions. Those assertions are only
trustworthy if the harness genuinely produces contention, which SQLite's shared
single connection cannot. This file pins that property.
"""
from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import text

pytestmark = [pytest.mark.integration, pytest.mark.postgres]


@pytest.fixture
async def scratch_table(pg_engine):
    async with pg_engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS harness_scratch"))
        await conn.execute(
            text(
                "CREATE TABLE harness_scratch ("
                "  id integer PRIMARY KEY,"
                "  slot text UNIQUE,"
                "  counter integer NOT NULL DEFAULT 0"
                ")"
            )
        )
        await conn.execute(text("INSERT INTO harness_scratch (id, counter) VALUES (1, 0)"))
    yield
    async with pg_engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS harness_scratch"))


@pytest.mark.asyncio
async def test_select_for_update_serialises_two_sessions(pg_two_sessions, scratch_table):
    """The second session blocks until the first commits: a real row lock."""
    first, second = pg_two_sessions

    await first.execute(text("SELECT counter FROM harness_scratch WHERE id = 1 FOR UPDATE"))

    second_acquired = asyncio.Event()

    async def contend():
        await second.execute(
            text("SELECT counter FROM harness_scratch WHERE id = 1 FOR UPDATE")
        )
        second_acquired.set()

    task = asyncio.create_task(contend())
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(asyncio.shield(second_acquired.wait()), timeout=0.5)

    await first.execute(text("UPDATE harness_scratch SET counter = counter + 1 WHERE id = 1"))
    await first.commit()

    await asyncio.wait_for(task, timeout=5)
    assert second_acquired.is_set()
    await second.rollback()


@pytest.mark.asyncio
async def test_unique_violation_surfaces_across_sessions(pg_two_sessions, scratch_table):
    """Check-then-insert loses: the unique index is the authority."""
    from sqlalchemy.exc import IntegrityError

    first, second = pg_two_sessions

    await first.execute(
        text("INSERT INTO harness_scratch (id, slot) VALUES (2, 'taken')")
    )
    await first.commit()

    with pytest.raises(IntegrityError):
        await second.execute(
            text("INSERT INTO harness_scratch (id, slot) VALUES (3, 'taken')")
        )
        await second.commit()
    await second.rollback()


@pytest.mark.asyncio
async def test_query_counter_sees_postgres_statements(pg_engine, pg_query_counter, scratch_table):
    """Query budgets are measurable on the PostgreSQL lane, not just SQLite."""
    with pg_query_counter() as counted:
        async with pg_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            await conn.execute(text("SELECT 2"))

    assert counted.selects == 2
    assert counted.writes == 0
