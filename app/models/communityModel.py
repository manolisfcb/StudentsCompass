from datetime import datetime
import uuid

from sqlalchemy import Column, String, Text, DateTime, ForeignKey, UniqueConstraint, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.db import Base


class CommunityModel(Base):
    __tablename__ = "communities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(120), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    icon = Column(String(20), nullable=True)
    activity_status = Column(String(32), nullable=True)
    tags = Column(JSONB, nullable=True)
    member_count = Column(Integer, nullable=False, default=0)
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
