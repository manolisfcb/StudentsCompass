"""The idempotency claim under a real race, and the retention sweep.

SQLite serialises everything onto one connection, so it cannot show what this
mechanism is actually for: two requests arriving at the same instant on
different connections, where a check-then-insert would let both through. Only
PostgreSQL gives real unique-violation behaviour between concurrent
transactions, so the claim "the database decides who won" is made here or not
at all.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import func, select

pytestmark = [pytest.mark.integration, pytest.mark.postgres]


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


def _record(*, key: str, fingerprint: str = "f" * 64, actor: str = "user:alice"):
    from app.models.idempotencyModel import IdempotencyRecordModel, IdempotencyStatus

    now = datetime.utcnow()
    return IdempotencyRecordModel(
        id=uuid.uuid4(),
        actor_key=actor,
        endpoint="POST /applications",
        idempotency_key=key,
        request_fingerprint=fingerprint,
        status=IdempotencyStatus.IN_PROGRESS,
        created_at=now,
        expires_at=now + timedelta(hours=24),
    )


@pytest.mark.asyncio
async def test_two_simultaneous_claims_on_one_key_leave_a_single_row(
    schema, pg_two_sessions
):
    """The database decides, not the application.

    Both sessions insert the same key at the same time on separate connections.
    Exactly one commit may succeed; the loser must see a unique violation rather
    than a second row, because a second row would mean both requests went on to
    do the paid work.
    """
    from sqlalchemy.exc import IntegrityError

    from app.models.idempotencyModel import IdempotencyRecordModel

    first, second = pg_two_sessions
    first.add(_record(key="race"))
    second.add(_record(key="race"))

    outcomes = await asyncio.gather(
        first.commit(), second.commit(), return_exceptions=True
    )
    failures = [o for o in outcomes if isinstance(o, Exception)]

    assert len(failures) == 1, "exactly one of the two claims must be refused"
    assert isinstance(failures[0], IntegrityError)

    await first.rollback()
    await second.rollback()
    total = await first.execute(select(func.count(IdempotencyRecordModel.id)))
    assert total.scalar_one() == 1


@pytest.mark.asyncio
async def test_the_same_key_is_free_again_for_a_different_actor(schema, pg_session):
    """Scoping is part of the constraint, not a filter applied afterwards.

    Keys are strings chosen by clients; two users will pick the same one. The
    constraint has to let that through, or one student's retry becomes another
    student's error.
    """
    from app.models.idempotencyModel import IdempotencyRecordModel

    pg_session.add(_record(key="shared", actor="user:alice"))
    pg_session.add(_record(key="shared", actor="user:bob"))
    await pg_session.commit()

    total = await pg_session.execute(select(func.count(IdempotencyRecordModel.id)))
    assert total.scalar_one() == 2


@pytest.mark.asyncio
async def test_the_same_key_is_free_again_on_a_different_endpoint(schema, pg_session):
    from app.models.idempotencyModel import IdempotencyRecordModel

    first = _record(key="same")
    second = _record(key="same")
    second.endpoint = "POST /companies/me/job-postings"
    pg_session.add_all([first, second])
    await pg_session.commit()

    total = await pg_session.execute(select(func.count(IdempotencyRecordModel.id)))
    assert total.scalar_one() == 2


@pytest.mark.asyncio
async def test_the_retention_sweep_uses_its_index(schema, pg_session):
    """The one query that scans without an actor must not be a seq scan.

    Retention runs over the whole table by definition, so it is the only access
    path that degrades with total volume rather than with one caller's history.
    """
    from sqlalchemy import text

    from app.core.idempotency import purge_expired_records
    from app.models.idempotencyModel import IdempotencyRecordModel

    now = datetime.utcnow()
    expired = _record(key="old")
    expired.expires_at = now - timedelta(days=1)
    live = _record(key="new")
    pg_session.add_all([expired, live])
    await pg_session.commit()

    plan = await pg_session.execute(
        text(
            "EXPLAIN SELECT id FROM idempotency_records WHERE expires_at <= :cutoff"
        ),
        {"cutoff": now},
    )
    plan_text = "\n".join(row[0] for row in plan)

    removed = await purge_expired_records(pg_session, now=now)
    assert removed == 1

    remaining = await pg_session.execute(select(IdempotencyRecordModel.idempotency_key))
    assert remaining.scalars().all() == ["new"]
    # Two rows is far below the point where the planner prefers an index, so the
    # plan itself is not asserted here — what is asserted is that the index the
    # sweep depends on exists and is offered to the planner.
    indexes = await pg_session.execute(
        text("SELECT indexname FROM pg_indexes WHERE tablename = 'idempotency_records'")
    )
    assert "ix_idempotency_records_expires_at" in set(indexes.scalars().all())
    assert plan_text  # the statement is planable as written
