"""Writing a dispatch down, and delivering it later.

The write happens inside the caller's transaction — the same one that creates
the job — so "the job exists" and "someone was told to run it" commit together
or not at all. Delivery is a separate step whose only failure mode is "try
again", which is the property the enqueue itself does not have.

Nothing here decides anything about a job. ``job_analysis`` remains the durable
source of state, lease and idempotency exactly as TASK-013 built it; this
module only changes *who tells a worker to look*.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Iterable
from uuid import UUID, uuid4

from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import (
    TASK_OUTBOX_MAX_ATTEMPTS,
    TASK_OUTBOX_RETRY_BASE_SECONDS,
)
from app.core.errors import redact
from app.models.taskOutboxModel import TASK_CV_ANALYSIS, OutboxStatus, TaskOutboxModel

LOGGER = logging.getLogger(__name__)

#: How many rows one sweep will try to deliver. Bounded so a backlog is worked
#: through steadily rather than in one burst that holds a session open.
MAX_ROWS_PER_SWEEP = 20


def cv_analysis_dedupe_key(job_id: UUID) -> str:
    return f"{TASK_CV_ANALYSIS}:{job_id}"


async def enqueue_cv_analysis(session: AsyncSession, *, job_id: UUID) -> bool:
    """Write the dispatch for one analysis. **Does not commit.**

    Deliberately not committing: the point of the outbox is that this row lands
    in the caller's transaction, beside the job it refers to. A commit here
    would reintroduce the gap it exists to close.

    Returns ``False`` when the dispatch was already written — a retried request
    joining an existing job, which must not produce a second task.
    """
    now = datetime.utcnow()
    statement = insert(TaskOutboxModel).values(
        id=uuid4(),
        task_type=TASK_CV_ANALYSIS,
        payload={"job_id": str(job_id)},
        dedupe_key=cv_analysis_dedupe_key(job_id),
        status=OutboxStatus.PENDING,
        attempts=0,
        available_at=now,
        created_at=now,
        updated_at=now,
    )
    try:
        # A Core INSERT inside a savepoint, not an ORM flush — the same shape
        # ``create_pending_analysis`` uses, and for the same reason: a failed
        # flush marks the *whole* session for rollback, and the caller still has
        # a response to build. Only the savepoint is undone here.
        async with session.begin_nested():
            await session.execute(statement)
    except IntegrityError:
        LOGGER.info("Dispatch for analysis %s was already written", job_id)
        return False
    return True


async def claim_due_rows(
    session: AsyncSession, *, limit: int = MAX_ROWS_PER_SWEEP, now: datetime | None = None
) -> list[TaskOutboxModel]:
    """Rows that are due for delivery, oldest first."""
    moment = now or datetime.utcnow()
    result = await session.execute(
        select(TaskOutboxModel)
        .where(
            TaskOutboxModel.status == OutboxStatus.PENDING,
            TaskOutboxModel.available_at <= moment,
        )
        .order_by(TaskOutboxModel.available_at, TaskOutboxModel.created_at)
        .limit(limit)
    )
    return list(result.scalars().all())


async def mark_dispatched(session: AsyncSession, row: TaskOutboxModel) -> None:
    row.status = OutboxStatus.DISPATCHED
    row.dispatched_at = datetime.utcnow()
    row.attempts = (row.attempts or 0) + 1
    row.last_error = None
    session.add(row)
    await session.commit()


async def mark_failed_attempt(
    session: AsyncSession, row: TaskOutboxModel, error: BaseException
) -> None:
    """Back off, or give up and leave the row where an operator will see it."""
    attempts = (row.attempts or 0) + 1
    row.attempts = attempts
    # Redacted: a transport error carries URLs and sometimes credentials, and
    # this column is read by whoever is debugging, not by a machine.
    row.last_error = redact(f"{type(error).__name__}: {error}")[:1000]
    if attempts >= TASK_OUTBOX_MAX_ATTEMPTS:
        row.status = OutboxStatus.FAILED
        LOGGER.error(
            "Dispatch %s gave up after %s attempts", row.dedupe_key, attempts
        )
    else:
        backoff = TASK_OUTBOX_RETRY_BASE_SECONDS * (2 ** (attempts - 1))
        row.available_at = datetime.utcnow() + timedelta(seconds=backoff)
    session.add(row)
    await session.commit()


async def deliver_pending(
    session: AsyncSession,
    transport,
    *,
    limit: int = MAX_ROWS_PER_SWEEP,
    now: datetime | None = None,
) -> int:
    """Deliver what is due. Returns how many rows were dispatched.

    One row at a time, each committed on its own: a transport failure on the
    third row must not undo the two that were delivered, because "delivered"
    and "not delivered again" are the same fact.
    """
    delivered = 0
    for row in await claim_due_rows(session, limit=limit, now=now):
        try:
            await transport.deliver(row)
        except Exception as exc:  # noqa: BLE001 — every transport failure retries
            await mark_failed_attempt(session, row, exc)
            continue
        await mark_dispatched(session, row)
        delivered += 1
    return delivered


async def requeue_for_job(session: AsyncSession, *, job_id: UUID) -> bool:
    """Make a job's dispatch due again, writing one if it is missing.

    Used by reconciliation: a job that is still pending long after its lease
    would have run out either never had a task, or had one that was lost. Both
    are answered by making the outbox row due now.
    """
    key = cv_analysis_dedupe_key(job_id)
    result = await session.execute(
        select(TaskOutboxModel).where(TaskOutboxModel.dedupe_key == key)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return await enqueue_cv_analysis(session, job_id=job_id)
    row.status = OutboxStatus.PENDING
    row.available_at = datetime.utcnow()
    session.add(row)
    return True


def payload_job_ids(rows: Iterable[TaskOutboxModel]) -> list[UUID]:
    ids: list[UUID] = []
    for row in rows:
        payload: dict[str, Any] = row.payload or {}
        raw = payload.get("job_id")
        if raw:
            ids.append(UUID(str(raw)))
    return ids
