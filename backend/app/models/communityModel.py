from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func, select
from sqlalchemy.dialects.postgresql import JSONB
from app.db_types import UUID
from sqlalchemy.orm import column_property, relationship

from app.db import Base

JSON_VARIANT = JSON().with_variant(JSONB, "postgresql")


class CommunityModel(Base):
    __tablename__ = "communities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(120), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    icon = Column(String(20), nullable=True)
    activity_status = Column(String(32), nullable=True)
    tags = Column(JSON_VARIANT, nullable=True)
    # Legacy cache of the membership count, kept up to date atomically and kept
    # around for a rollback — but never the answer to "how many members?".
    # ``member_count`` below is. The column keeps its name in the database; the
    # attribute is renamed so that reading the stale number has to be deliberate.
    member_count_cache = Column("member_count", Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    creator = relationship("User", back_populates="communities_created")
    members = relationship("CommunityMemberModel", back_populates="community", cascade="all, delete-orphan")
    posts = relationship("CommunityPostModel", back_populates="community", cascade="all, delete-orphan")


class CommunityMemberModel(Base):
    __tablename__ = "community_members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    community_id = Column(UUID(as_uuid=True), ForeignKey("communities.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    joined_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    community = relationship("CommunityModel", back_populates="members")
    user = relationship("User", back_populates="community_memberships")

    __table_args__ = (
        UniqueConstraint("community_id", "user_id", name="uq_community_member"),
    )


# The authority for how many members a community has is the membership table.
# A Python-side counter drifted for two reasons that no amount of care fixes:
# simultaneous joins each read the same number before writing it back, and a
# deleted user takes their memberships with them (ON DELETE CASCADE) without
# anyone updating a counter.
#
# A correlated subquery in the SELECT list keeps this to *one* query no matter
# how many communities are listed, and the leading column of
# ``uq_community_member`` makes each lookup an index scan. Mapped after both
# classes exist because it names them both.
CommunityModel.member_count = column_property(
    select(func.count(CommunityMemberModel.id))
    .where(CommunityMemberModel.community_id == CommunityModel.id)
    .correlate_except(CommunityMemberModel)
    .scalar_subquery(),
    deferred=False,
)
