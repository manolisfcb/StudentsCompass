"""add resources hub tables

Revision ID: d9a2c30c6f11
Revises: c4f2a1b7b9aa
Create Date: 2026-02-15 19:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "d9a2c30c6f11"
down_revision: Union[str, Sequence[str], None] = "c4f2a1b7b9aa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "resources",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("icon", sa.String(length=120), nullable=True),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("tags", postgresql.JSONB(), nullable=True),
        sa.Column("level", sa.String(length=32), nullable=True),
        sa.Column("estimated_duration_minutes", sa.Integer(), nullable=True),
        sa.Column("external_url", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_resources_category", "resources", ["category"], unique=False)
    op.create_index("ix_resources_created_at", "resources", ["created_at"], unique=False)
    op.create_index("ix_resources_is_published", "resources", ["is_published"], unique=False)

    op.create_table(
        "resource_modules",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("resource_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["resource_id"], ["resources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_resource_modules_resource_id", "resource_modules", ["resource_id"], unique=False)

    op.create_table(
        "resource_lessons",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("module_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=220), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("content_type", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("reading_time_minutes", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["module_id"], ["resource_modules.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_resource_lessons_module_id", "resource_lessons", ["module_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_resource_lessons_module_id", table_name="resource_lessons")
    op.drop_table("resource_lessons")

    op.drop_index("ix_resource_modules_resource_id", table_name="resource_modules")
    op.drop_table("resource_modules")

    op.drop_index("ix_resources_is_published", table_name="resources")
    op.drop_index("ix_resources_created_at", table_name="resources")
    op.drop_index("ix_resources_category", table_name="resources")
    op.drop_table("resources")
