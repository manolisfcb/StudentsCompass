from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String
from app.db_types import UUID

from app.db import Base


class AIUsageStatus:
    """Lifecycle of a single ledger row.

    A row starts as ``RESERVED`` (a slot claimed before any provider spend) and
    ends in exactly one terminal state, so the accounting is never ambiguous:

    * ``COMMITTED`` — the spend happened; this row is what a daily quota counts.
    * ``RELEASED``  — the caller gave the slot back (no spend, or a failure
      before one).
    * ``EXPIRED``   — nobody ever finished the cycle (the process died between
      reserve and commit) and the lease ran out, so the slot was reclaimed.
    * ``SUPERSEDED``— a duplicate of an already-committed reference, kept for
      history instead of deleted.

    Only ``COMMITTED`` rows, plus ``RESERVED`` rows whose lease is still live,
    count against a user's daily allowance.
    """

    RESERVED = "reserved"
    COMMITTED = "committed"
    RELEASED = "released"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"


class AIUsageEventModel(Base):
    __tablename__ = "ai_usage_events"
    # Declared here because the index exists in every deployed database:
    # an autogenerate run against metadata that omits it proposes dropping
    # it, which is how a previous revision silently removed a batch of them.
    __table_args__ = (
        Index("ix_ai_usage_events_user_feature_created", "user_id", "feature", "created_at"),
        # Identity of a spend: one committed ledger row per referenced object.
        # A replay of the same commit (retry, duplicated background task) hits
        # this index instead of adding a second charge. Partial so that
        # reservations (no reference yet) and non-committed history are exempt.
        Index(
            "uq_ai_usage_events_reference",
            "reference_type",
            "reference_id",
            unique=True,
            postgresql_where=Column("reference_id").isnot(None) & (Column("status") == AIUsageStatus.COMMITTED),
            sqlite_where=Column("reference_id").isnot(None) & (Column("status") == AIUsageStatus.COMMITTED),
        ),
        # Reclaiming leases scans only in-flight reservations.
        Index(
            "ix_ai_usage_events_reserved_expiry",
            "user_id",
            "feature",
            "expires_at",
            postgresql_where=Column("status") == AIUsageStatus.RESERVED,
            sqlite_where=Column("status") == AIUsageStatus.RESERVED,
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    feature = Column(String(64), nullable=False, index=True)
    units = Column(Integer, nullable=False, default=1)
    source = Column(String(64), nullable=False, default="base_daily")
    reference_type = Column(String(64), nullable=True)
    reference_id = Column(UUID(as_uuid=True), nullable=True)
    # Existing rows predate the reservation cycle and are all settled spends,
    # so the server default keeps them counting exactly as they did before.
    status = Column(String(16), nullable=False, default=AIUsageStatus.COMMITTED, server_default=AIUsageStatus.COMMITTED)
    # Lease deadline for RESERVED rows; NULL once the row reaches a terminal state.
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)


class AIQuotaGrantModel(Base):
    __tablename__ = "ai_quota_grants"
    __table_args__ = (
        Index("ix_ai_quota_grants_user_feature_active", "user_id", "feature", "is_active"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    feature = Column(String(64), nullable=True, index=True)
    daily_extra_units = Column(Integer, nullable=False, default=0)
    starts_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    ends_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    reason = Column(String(120), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
