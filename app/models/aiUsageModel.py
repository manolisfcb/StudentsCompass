from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID

from app.db import Base


class AIUsageEventModel(Base):
    __tablename__ = "ai_usage_events"
    # Declared here because the index exists in every deployed database:
    # an autogenerate run against metadata that omits it proposes dropping
    # it, which is how a previous revision silently removed a batch of them.
    __table_args__ = (
        Index("ix_ai_usage_events_user_feature_created", "user_id", "feature", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    feature = Column(String(64), nullable=False, index=True)
    units = Column(Integer, nullable=False, default=1)
    source = Column(String(64), nullable=False, default="base_daily")
    reference_type = Column(String(64), nullable=True)
    reference_id = Column(UUID(as_uuid=True), nullable=True)
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
