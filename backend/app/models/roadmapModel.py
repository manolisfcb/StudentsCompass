from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.db import Base

JSON_VARIANT = JSON().with_variant(JSONB, "postgresql")


class TaskType(str, enum.Enum):
    LEARN = "learn"
    PRACTICE = "practice"
    BUILD = "build"
    READ = "read"
    WATCH = "watch"


class TaskProgressStatus(str, enum.Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class ProjectSubmissionStatus(str, enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    REVIEWED = "reviewed"


class RoadmapModel(Base):
    __tablename__ = "roadmaps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug = Column(String(140), nullable=False, unique=True, index=True)
    title = Column(String(180), nullable=False)
    description = Column(Text, nullable=False)
    role_target = Column(String(140), nullable=False)
    difficulty = Column(String(32), nullable=False)
    duration_weeks_min = Column(Integer, nullable=False)
    duration_weeks_max = Column(Integer, nullable=False)
    is_public = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    stages = relationship(
        "RoadmapStageModel",
        back_populates="roadmap",
        cascade="all, delete-orphan",
        order_by="RoadmapStageModel.order_index",
    )
    saved_by = relationship(
        "UserRoadmapModel",
        back_populates="roadmap",
        cascade="all, delete-orphan",
    )


class RoadmapStageModel(Base):
    __tablename__ = "roadmap_stages"
    __table_args__ = (UniqueConstraint("roadmap_id", "order_index", name="uq_roadmap_stage_order"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    roadmap_id = Column(UUID(as_uuid=True), ForeignKey("roadmaps.id", ondelete="CASCADE"), nullable=False, index=True)
    order_index = Column(Integer, nullable=False)
    title = Column(String(180), nullable=False)
    objective = Column(Text, nullable=False)
    duration_weeks = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    roadmap = relationship("RoadmapModel", back_populates="stages")
    tasks = relationship(
        "StageTaskModel",
        back_populates="stage",
        cascade="all, delete-orphan",
        order_by="StageTaskModel.order_index",
    )
    projects = relationship("StageProjectModel", back_populates="stage", cascade="all, delete-orphan")
    user_progress = relationship("UserStageProgressModel", back_populates="stage", cascade="all, delete-orphan")


class StageTaskModel(Base):
    __tablename__ = "stage_tasks"
    __table_args__ = (UniqueConstraint("stage_id", "order_index", name="uq_stage_task_order"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stage_id = Column(UUID(as_uuid=True), ForeignKey("roadmap_stages.id", ondelete="CASCADE"), nullable=False, index=True)
    order_index = Column(Integer, nullable=False)
    title = Column(String(220), nullable=False)
    description = Column(Text, nullable=False)
    estimated_hours = Column(Integer, nullable=False)
    task_type = Column(
        Enum(
            TaskType,
            name="task_type_enum",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
            validate_strings=True,
        ),
        nullable=False,
    )
    resource_url = Column(String(600), nullable=True)
    resource_title = Column(String(220), nullable=True)

    stage = relationship("RoadmapStageModel", back_populates="tasks")
    progress_records = relationship("UserTaskProgressModel", back_populates="task", cascade="all, delete-orphan")


class StageProjectModel(Base):
    __tablename__ = "stage_projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stage_id = Column(UUID(as_uuid=True), ForeignKey("roadmap_stages.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(220), nullable=False)
    brief = Column(Text, nullable=False)
    acceptance_criteria = Column(JSON_VARIANT, nullable=False)
    rubric = Column(JSON_VARIANT, nullable=False)
    estimated_hours = Column(Integer, nullable=False)

    stage = relationship("RoadmapStageModel", back_populates="projects")
    submissions = relationship("UserProjectSubmissionModel", back_populates="project", cascade="all, delete-orphan")


class UserRoadmapModel(Base):
    __tablename__ = "user_roadmaps"
    __table_args__ = (UniqueConstraint("user_id", "roadmap_id", name="uq_user_roadmap"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    roadmap_id = Column(UUID(as_uuid=True), ForeignKey("roadmaps.id", ondelete="CASCADE"), nullable=False, index=True)
    saved_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    roadmap = relationship("RoadmapModel", back_populates="saved_by")


class UserTaskProgressModel(Base):
    __tablename__ = "user_task_progress"
    __table_args__ = (UniqueConstraint("user_id", "task_id", name="uq_user_task_progress"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id = Column(UUID(as_uuid=True), ForeignKey("stage_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(
        Enum(
            TaskProgressStatus,
            name="task_progress_status_enum",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
            validate_strings=True,
        ),
        nullable=False,
        default=TaskProgressStatus.NOT_STARTED,
    )
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    task = relationship("StageTaskModel", back_populates="progress_records")


class UserStageProgressModel(Base):
    __tablename__ = "user_stage_progress"
    __table_args__ = (UniqueConstraint("user_id", "stage_id", name="uq_user_stage_progress"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    stage_id = Column(UUID(as_uuid=True), ForeignKey("roadmap_stages.id", ondelete="CASCADE"), nullable=False, index=True)
    progress_percent = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    stage = relationship("RoadmapStageModel", back_populates="user_progress")


class UserProjectSubmissionModel(Base):
    __tablename__ = "user_project_submissions"
    __table_args__ = (UniqueConstraint("user_id", "project_id", name="uq_user_project_submission"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("stage_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    repo_url = Column(String(600), nullable=True)
    live_url = Column(String(600), nullable=True)
    notes = Column(Text, nullable=True)
    status = Column(
        Enum(
            ProjectSubmissionStatus,
            name="project_submission_status_enum",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
            validate_strings=True,
        ),
        nullable=False,
        default=ProjectSubmissionStatus.DRAFT,
    )
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    project = relationship("StageProjectModel", back_populates="submissions")
