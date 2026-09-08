"""add roadmaps domain tables

Revision ID: f2b6c1d7e8f9
Revises: e1f7c2b9a4d3
Create Date: 2026-02-27 16:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "f2b6c1d7e8f9"
down_revision: Union[str, Sequence[str], None] = "1720e86014a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    task_type_enum_create = postgresql.ENUM(
        "learn",
        "practice",
        "build",
        "read",
        "watch",
        name="task_type_enum",
    )
    task_progress_status_enum_create = postgresql.ENUM(
        "not_started",
        "in_progress",
        "completed",
        name="task_progress_status_enum",
    )
    project_submission_status_enum_create = postgresql.ENUM(
        "draft",
        "submitted",
        "reviewed",
        name="project_submission_status_enum",
    )

    # Column enums must not auto-create again when tables are created.
    task_type_enum = postgresql.ENUM(
        "learn",
        "practice",
        "build",
        "read",
        "watch",
        name="task_type_enum",
        create_type=False,
    )
    task_progress_status_enum = postgresql.ENUM(
        "not_started",
        "in_progress",
        "completed",
        name="task_progress_status_enum",
        create_type=False,
    )
    project_submission_status_enum = postgresql.ENUM(
        "draft",
        "submitted",
        "reviewed",
        name="project_submission_status_enum",
        create_type=False,
    )

    bind = op.get_bind()
    task_type_enum_create.create(bind, checkfirst=True)
    task_progress_status_enum_create.create(bind, checkfirst=True)
    project_submission_status_enum_create.create(bind, checkfirst=True)

    op.create_table(
        "roadmaps",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("slug", sa.String(length=140), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("role_target", sa.String(length=140), nullable=False),
        sa.Column("difficulty", sa.String(length=32), nullable=False),
        sa.Column("duration_weeks_min", sa.Integer(), nullable=False),
        sa.Column("duration_weeks_max", sa.Integer(), nullable=False),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_roadmaps_slug", "roadmaps", ["slug"], unique=True)

    op.create_table(
        "roadmap_stages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("roadmap_id", sa.UUID(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("duration_weeks", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["roadmap_id"], ["roadmaps.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("roadmap_id", "order_index", name="uq_roadmap_stage_order"),
    )
    op.create_index("ix_roadmap_stages_roadmap_id", "roadmap_stages", ["roadmap_id"], unique=False)

    op.create_table(
        "stage_tasks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("stage_id", sa.UUID(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=220), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("estimated_hours", sa.Integer(), nullable=False),
        sa.Column("task_type", task_type_enum, nullable=False),
        sa.Column("resource_url", sa.String(length=600), nullable=True),
        sa.Column("resource_title", sa.String(length=220), nullable=True),
        sa.ForeignKeyConstraint(["stage_id"], ["roadmap_stages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stage_id", "order_index", name="uq_stage_task_order"),
    )
    op.create_index("ix_stage_tasks_stage_id", "stage_tasks", ["stage_id"], unique=False)

    op.create_table(
        "stage_projects",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("stage_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=220), nullable=False),
        sa.Column("brief", sa.Text(), nullable=False),
        sa.Column("acceptance_criteria", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("rubric", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("estimated_hours", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["stage_id"], ["roadmap_stages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stage_projects_stage_id", "stage_projects", ["stage_id"], unique=False)

    op.create_table(
        "user_roadmaps",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("roadmap_id", sa.UUID(), nullable=False),
        sa.Column("saved_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["roadmap_id"], ["roadmaps.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "roadmap_id", name="uq_user_roadmap"),
    )
    op.create_index("ix_user_roadmaps_user_id", "user_roadmaps", ["user_id"], unique=False)
    op.create_index("ix_user_roadmaps_roadmap_id", "user_roadmaps", ["roadmap_id"], unique=False)

    op.create_table(
        "user_task_progress",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("task_id", sa.UUID(), nullable=False),
        sa.Column("status", task_progress_status_enum, nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["stage_tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "task_id", name="uq_user_task_progress"),
    )
    op.create_index("ix_user_task_progress_user_id", "user_task_progress", ["user_id"], unique=False)
    op.create_index("ix_user_task_progress_task_id", "user_task_progress", ["task_id"], unique=False)

    op.create_table(
        "user_stage_progress",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("stage_id", sa.UUID(), nullable=False),
        sa.Column("progress_percent", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["stage_id"], ["roadmap_stages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "stage_id", name="uq_user_stage_progress"),
    )
    op.create_index("ix_user_stage_progress_user_id", "user_stage_progress", ["user_id"], unique=False)
    op.create_index("ix_user_stage_progress_stage_id", "user_stage_progress", ["stage_id"], unique=False)

    op.create_table(
        "user_project_submissions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("repo_url", sa.String(length=600), nullable=True),
        sa.Column("live_url", sa.String(length=600), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", project_submission_status_enum, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["stage_projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "project_id", name="uq_user_project_submission"),
    )
    op.create_index("ix_user_project_submissions_user_id", "user_project_submissions", ["user_id"], unique=False)
    op.create_index("ix_user_project_submissions_project_id", "user_project_submissions", ["project_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_user_project_submissions_project_id", table_name="user_project_submissions")
    op.drop_index("ix_user_project_submissions_user_id", table_name="user_project_submissions")
    op.drop_table("user_project_submissions")

    op.drop_index("ix_user_stage_progress_stage_id", table_name="user_stage_progress")
    op.drop_index("ix_user_stage_progress_user_id", table_name="user_stage_progress")
    op.drop_table("user_stage_progress")

    op.drop_index("ix_user_task_progress_task_id", table_name="user_task_progress")
    op.drop_index("ix_user_task_progress_user_id", table_name="user_task_progress")
    op.drop_table("user_task_progress")

    op.drop_index("ix_user_roadmaps_roadmap_id", table_name="user_roadmaps")
    op.drop_index("ix_user_roadmaps_user_id", table_name="user_roadmaps")
    op.drop_table("user_roadmaps")

    op.drop_index("ix_stage_projects_stage_id", table_name="stage_projects")
    op.drop_table("stage_projects")

    op.drop_index("ix_stage_tasks_stage_id", table_name="stage_tasks")
    op.drop_table("stage_tasks")

    op.drop_index("ix_roadmap_stages_roadmap_id", table_name="roadmap_stages")
    op.drop_table("roadmap_stages")

    op.drop_index("ix_roadmaps_slug", table_name="roadmaps")
    op.drop_table("roadmaps")

    bind = op.get_bind()
    sa.Enum(name="project_submission_status_enum").drop(bind, checkfirst=True)
    sa.Enum(name="task_progress_status_enum").drop(bind, checkfirst=True)
    sa.Enum(name="task_type_enum").drop(bind, checkfirst=True)
