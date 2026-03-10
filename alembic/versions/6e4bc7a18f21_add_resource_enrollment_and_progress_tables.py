"""add resource enrollment and progress tables

Revision ID: 6e4bc7a18f21
Revises: 1720e86014a0
Create Date: 2026-02-24 19:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6e4bc7a18f21"
down_revision: Union[str, Sequence[str], None] = "1720e86014a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "resource_enrollments" not in existing_tables:
        op.create_table(
            "resource_enrollments",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("user_id", sa.UUID(), nullable=False),
            sa.Column("resource_id", sa.UUID(), nullable=False),
            sa.Column("last_opened_lesson_id", sa.UUID(), nullable=True),
            sa.Column("enrolled_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["last_opened_lesson_id"], ["resource_lessons.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["resource_id"], ["resources.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "resource_id", name="uq_resource_enrollments_user_resource"),
        )

    enrollment_indexes = {index["name"] for index in inspector.get_indexes("resource_enrollments")} if "resource_enrollments" in inspector.get_table_names() else set()
    if "ix_resource_enrollments_user_id" not in enrollment_indexes:
        op.create_index("ix_resource_enrollments_user_id", "resource_enrollments", ["user_id"], unique=False)
    if "ix_resource_enrollments_resource_id" not in enrollment_indexes:
        op.create_index("ix_resource_enrollments_resource_id", "resource_enrollments", ["resource_id"], unique=False)

    if "resource_lesson_progress" not in existing_tables:
        op.create_table(
            "resource_lesson_progress",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("user_id", sa.UUID(), nullable=False),
            sa.Column("resource_id", sa.UUID(), nullable=False),
            sa.Column("lesson_id", sa.UUID(), nullable=False),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.Column("last_opened_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
            sa.ForeignKeyConstraint(["lesson_id"], ["resource_lessons.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["resource_id"], ["resources.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "lesson_id", name="uq_resource_lesson_progress_user_lesson"),
        )

    progress_indexes = {index["name"] for index in inspector.get_indexes("resource_lesson_progress")} if "resource_lesson_progress" in inspector.get_table_names() else set()
    if "ix_resource_lesson_progress_user_id" not in progress_indexes:
        op.create_index("ix_resource_lesson_progress_user_id", "resource_lesson_progress", ["user_id"], unique=False)
    if "ix_resource_lesson_progress_resource_id" not in progress_indexes and any(col["name"] == "resource_id" for col in inspector.get_columns("resource_lesson_progress")):
        op.create_index("ix_resource_lesson_progress_resource_id", "resource_lesson_progress", ["resource_id"], unique=False)
    if "ix_resource_lesson_progress_lesson_id" not in progress_indexes:
        op.create_index("ix_resource_lesson_progress_lesson_id", "resource_lesson_progress", ["lesson_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_resource_lesson_progress_lesson_id", table_name="resource_lesson_progress")
    op.drop_index("ix_resource_lesson_progress_resource_id", table_name="resource_lesson_progress")
    op.drop_index("ix_resource_lesson_progress_user_id", table_name="resource_lesson_progress")
    op.drop_table("resource_lesson_progress")

    op.drop_index("ix_resource_enrollments_resource_id", table_name="resource_enrollments")
    op.drop_index("ix_resource_enrollments_user_id", table_name="resource_enrollments")
    op.drop_table("resource_enrollments")
