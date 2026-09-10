from datetime import datetime
import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from app.db_types import UUID
from sqlalchemy.orm import relationship

from app.db import Base

JSON_VARIANT = JSON().with_variant(JSONB, "postgresql")


class ResourceModel(Base):
    __tablename__ = "resources"
    # Declared here because the index exists in every deployed database:
    # an autogenerate run against metadata that omits it proposes dropping
    # it, which is how a previous revision silently removed a batch of them.
    __table_args__ = (
        Index("ix_resources_is_locked", "is_locked"),
        # Unique as an index rather than a constraint so it matches what the
        # migration creates, and so the rows without a code stay unconstrained:
        # both PostgreSQL and SQLite treat NULLs in a unique index as distinct.
        Index("ix_resources_core_code", "core_code", unique=True),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(180), nullable=False)
    description = Column(Text, nullable=False)
    icon = Column(String(120), nullable=True)
    category = Column(String(64), nullable=False)
    tags = Column(JSON_VARIANT, nullable=True)
    level = Column(String(32), nullable=True)
    estimated_duration_minutes = Column(Integer, nullable=True)
    external_url = Column(String(512), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_published = Column(Boolean, nullable=False, default=True)
    is_locked = Column(Boolean, nullable=False, default=False)
    # Stable identity for the courses the product treats as mandatory. Titles
    # are editable, so keying progress on them made an admin's rename silently
    # zero a user's dashboard. Nullable: ordinary resources carry no code, and
    # the unique index only constrains the rows that do (NULLs stay distinct).
    core_code = Column(String(64), nullable=True)

    modules = relationship(
        "ResourceModuleModel",
        back_populates="resource",
        cascade="all, delete-orphan",
        order_by="ResourceModuleModel.position",
    )

    # Per-user progress lives in ``ResourceLessonProgressModel`` below, keyed on
    # user_id + lesson_id with completed_at and last_opened_at. A TODO here
    # proposed building exactly that table long after it existed.


class ResourceModuleModel(Base):
    __tablename__ = "resource_modules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resource_id = Column(UUID(as_uuid=True), ForeignKey("resources.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(180), nullable=False)
    position = Column(Integer, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    module = relationship("ResourceModuleModel", back_populates="lessons")
    progress_records = relationship(
        "ResourceLessonProgressModel",
        back_populates="lesson",
        cascade="all, delete-orphan",
    )


class ResourceLessonProgressModel(Base):
    """Per-user lesson progress.

    Two migration branches created this table with different shapes: one with a
    ``resource_id`` column and nullable timestamps, one without ``resource_id``
    and with NOT NULL timestamps. Whichever branch ran first decided the shape
    of a given database, so the mapping has to be the permissive union of both:
    ``resource_id`` is present but nullable (the writer derives the resource
    from the lesson and does not set it), and the progress timestamps are
    nullable so a database built from the branch that allowed NULLs converges
    without discarding rows. Application defaults still populate both on every
    insert, so what the readers see is unchanged.
    """

    __tablename__ = "resource_lesson_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "lesson_id", name="uq_resource_lesson_progress_user_lesson"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    resource_id = Column(UUID(as_uuid=True), ForeignKey("resources.id", ondelete="CASCADE"), nullable=True, index=True)
    lesson_id = Column(UUID(as_uuid=True), ForeignKey("resource_lessons.id", ondelete="CASCADE"), nullable=False, index=True)
    completed_at = Column(DateTime, nullable=True, default=datetime.utcnow)
    last_opened_at = Column(DateTime, nullable=True, default=datetime.utcnow)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    lesson = relationship("ResourceLessonModel", back_populates="progress_records")


class ResourceEnrollmentModel(Base):
    """Mapped so the table stays visible to autogenerate.

    ``resource_enrollments`` was created by a migration but never mapped, so
    every autogenerate run proposed dropping it. No caller reads or writes it
    yet; retiring it needs an inventory of deployed data and is a separate,
    destructive task. Mapping it keeps the table out of the drop list without
    committing the application to using it.
    """

    __tablename__ = "resource_enrollments"
    __table_args__ = (
        UniqueConstraint("user_id", "resource_id", name="uq_resource_enrollments_user_resource"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    resource_id = Column(UUID(as_uuid=True), ForeignKey("resources.id", ondelete="CASCADE"), nullable=False, index=True)
    last_opened_lesson_id = Column(
        UUID(as_uuid=True), ForeignKey("resource_lessons.id", ondelete="SET NULL"), nullable=True
    )
    enrolled_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
