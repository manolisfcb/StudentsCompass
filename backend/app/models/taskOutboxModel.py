"""The row that stands between a committed job and its dispatch.

Enqueuing a Cloud Task cannot join a database transaction, which leaves exactly
two orderings and both lose work:

* enqueue **before** the commit — the task can arrive, and be handled, before
  the job row exists, or the commit can fail after the task was created;
* enqueue **after** the commit — the process can die in between, and the job is
  committed with nobody ever told to run it.

So the dispatch is written *as a row*, inside the same transaction as the job.
It is then delivered by something whose only failure mode is "try again": a row
that is not yet delivered is visible, retryable and countable, which none of
the lost dispatches above are.

``dedupe_key`` is what keeps a retry of the enqueue from producing a second
task for the same job. It is a unique constraint rather than a check, for the
same reason the idempotency registry is: two concurrent requests both read
"not there yet".
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Enum as SQLEnum,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from app.db_types import UUID

from app.db import Base

JSON_VARIANT = JSON().with_variant(JSONB, "postgresql")


class OutboxStatus(str, enum.Enum):
    #: Written, not yet delivered. The only state a sweep looks at.
    PENDING = "pending"
    #: Handed to the queue. The job's own state takes over from here.
    DISPATCHED = "dispatched"
    #: Gave up after ``TASK_OUTBOX_MAX_ATTEMPTS``. Kept, not deleted: a
    #: dispatch that never happened is exactly what an operator needs to see.
    FAILED = "failed"


#: The only task type today. Spelled as a constant so the column is not a
#: free-text field that grows undocumented values.
TASK_CV_ANALYSIS = "cv_analysis"


class TaskOutboxModel(Base):
    __tablename__ = "task_outbox"
    __table_args__ = (
        UniqueConstraint("dedupe_key", name="uq_task_outbox_dedupe_key"),
        # The sweep's only query: due work, oldest first.
        Index("ix_task_outbox_status_available_at", "status", "available_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_type = Column(String(64), nullable=False)
    #: Everything the consumer needs to act, so delivery does not depend on
    #: joining back to a table that may have moved on.
    payload = Column(JSON_VARIANT, nullable=False)
    #: ``"cv_analysis:<job id>"``. One dispatch per job, decided by the database.
    dedupe_key = Column(String(200), nullable=False)
    status = Column(SQLEnum(OutboxStatus), nullable=False, default=OutboxStatus.PENDING)
    attempts = Column(Integer, nullable=False, default=0, server_default="0")
    #: Not before this moment. Backoff between attempts lives here rather than
    #: in a sleeping worker, so a restart does not reset the wait.
    available_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    dispatched_at = Column(DateTime, nullable=True)
    #: Redacted at the call site before it is written.
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
