"""The record that makes a retried request cost nothing extra.

A network retry is indistinguishable, from the server's side, from a second
intention: the same POST arrives twice and the second one books another
interview slot, files another application, or spends another AI credit. The
client's ``Idempotency-Key`` is what separates the two cases, and this table is
where that answer is kept long enough to be given again.

The unique constraint is the whole mechanism. Checking "has this key been used?"
and then inserting is two statements, and two simultaneous retries both read
"no" and both proceed. Inserting first and letting the database refuse the
loser makes the decision atomic.
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
    String,
    Text,
    UniqueConstraint,
)
from app.db_types import UUID

from app.db import Base


class IdempotencyStatus(str, enum.Enum):
    #: Claimed, the work is running. A second request arriving now is a genuine
    #: concurrent duplicate, not a replay of a finished result.
    IN_PROGRESS = "in_progress"
    #: Finished, and the response is stored beside it.
    COMPLETED = "completed"


class IdempotencyRecordModel(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (
        # Scoped by actor *and* endpoint, not by key alone: keys are chosen by
        # clients, so two users — or one user on two endpoints — may pick the
        # same string, and nobody may read back a result that is not theirs.
        UniqueConstraint(
            "actor_key",
            "endpoint",
            "idempotency_key",
            name="uq_idempotency_actor_endpoint_key",
        ),
        # Retention sweep: the only query that scans without an actor.
        Index("ix_idempotency_records_expires_at", "expires_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    #: Who the caller is, as ``"<actor type>:<id>"``. A string rather than a
    #: foreign key because the actors are not one table: students, companies
    #: and recruiters all reach these endpoints.
    actor_key = Column(String(128), nullable=False)
    #: ``"POST /applications"`` — the route, not the concrete URL.
    endpoint = Column(String(200), nullable=False)
    idempotency_key = Column(String(255), nullable=False)
    #: SHA-256 of the canonical request payload. The same key with a *different*
    #: body is a client bug, and answering it with the first body would be
    #: worse than an error: it would confirm a request that was never made.
    request_fingerprint = Column(String(64), nullable=False)
    status = Column(
        SQLEnum(IdempotencyStatus),
        nullable=False,
        default=IdempotencyStatus.IN_PROGRESS,
    )
    response_status_code = Column(Integer, nullable=True)
    #: The stored response body, serialised JSON. Text rather than JSON so the
    #: replayed bytes are exactly the bytes that were sent the first time.
    response_body = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    #: When this record stops being an answer. Retention is finite on purpose:
    #: a key is a retry window, not a permanent log, and an unbounded table of
    #: stored response bodies is its own problem.
    expires_at = Column(DateTime, nullable=False)
