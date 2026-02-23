from datetime import datetime
import uuid

from sqlalchemy import Column, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db import Base


class CommunityPostModel(Base):
    __tablename__ = "community_posts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    community_id = Column(UUID(as_uuid=True), ForeignKey("communities.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(200), nullable=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    community = relationship("CommunityModel", back_populates="posts")
    user = relationship("User", back_populates="community_posts")
    likes = relationship("CommunityPostLikeModel", back_populates="post", cascade="all, delete-orphan")
    comments = relationship("CommunityPostCommentModel", back_populates="post", cascade="all, delete-orphan")


class CommunityPostLikeModel(Base):
    __tablename__ = "community_post_likes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    post_id = Column(UUID(as_uuid=True), ForeignKey("community_posts.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    post = relationship("CommunityPostModel", back_populates="likes")
    user = relationship("User", back_populates="community_post_likes")

    __table_args__ = (
        UniqueConstraint("post_id", "user_id", name="uq_community_post_like"),
    )


class CommunityPostCommentModel(Base):
    __tablename__ = "community_post_comments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    post_id = Column(UUID(as_uuid=True), ForeignKey("community_posts.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    post = relationship("CommunityPostModel", back_populates="comments")
    user = relationship("User", back_populates="community_post_comments")
