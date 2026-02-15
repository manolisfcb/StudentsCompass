from datetime import datetime
import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.db import Base


class ResourceModel(Base):
    __tablename__ = "resources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(180), nullable=False)
    description = Column(Text, nullable=False)
    icon = Column(String(120), nullable=True)
    category = Column(String(64), nullable=False)
    tags = Column(JSONB, nullable=True)
    level = Column(String(32), nullable=True)
    estimated_duration_minutes = Column(Integer, nullable=True)
    external_url = Column(String(512), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    is_published = Column(Boolean, nullable=False, default=True)

    modules = relationship(
        "ResourceModuleModel",
        back_populates="resource",
        cascade="all, delete-orphan",
        order_by="ResourceModuleModel.position",
    )

    # TODO(progress): Keep this entity read-only for users for now.
    # Later we can add per-user progress via a ResourceLessonProgress table:
    # user_id + lesson_id + completed_at + last_opened_at.


class ResourceModuleModel(Base):
    __tablename__ = "resource_modules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resource_id = Column(UUID(as_uuid=True), ForeignKey("resources.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(180), nullable=False)
    position = Column(Integer, nullable=False)
    description = Column(Text, nullable=True)

    resource = relationship("ResourceModel", back_populates="modules")
    lessons = relationship(
        "ResourceLessonModel",
        back_populates="module",
        cascade="all, delete-orphan",
        order_by="ResourceLessonModel.position",
    )


class ResourceLessonModel(Base):
    __tablename__ = "resource_lessons"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    module_id = Column(UUID(as_uuid=True), ForeignKey("resource_modules.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(220), nullable=False)
    position = Column(Integer, nullable=False)
    content_type = Column(String(32), nullable=False, default="text")
    content = Column(Text, nullable=False)
    reading_time_minutes = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    module = relationship("ResourceModuleModel", back_populates="lessons")
