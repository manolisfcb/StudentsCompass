"""add ai usage quota tables

Revision ID: 3f8a2c9d1e7b
Revises: 2d4e6f8a0b1c
Create Date: 2026-06-17 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "3f8a2c9d1e7b"
down_revision: Union[str, Sequence[str], None] = "2d4e6f8a0b1c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_usage_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("feature", sa.String(length=64), nullable=False),
        sa.Column("units", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("source", sa.String(length=64), nullable=False, server_default="base_daily"),
        sa.Column("reference_type", sa.String(length=64), nullable=True),
        sa.Column("reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_usage_events_user_id", "ai_usage_events", ["user_id"], unique=False)
    op.create_index("ix_ai_usage_events_feature", "ai_usage_events", ["feature"], unique=False)
    op.create_index("ix_ai_usage_events_created_at", "ai_usage_events", ["created_at"], unique=False)
    op.create_index(
        "ix_ai_usage_events_user_feature_created",
        "ai_usage_events",
        ["user_id", "feature", "created_at"],
        unique=False,
    )
    op.alter_column("ai_usage_events", "units", server_default=None)
    op.alter_column("ai_usage_events", "source", server_default=None)
    op.alter_column("ai_usage_events", "created_at", server_default=None)

    op.create_table(
        "ai_quota_grants",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("feature", sa.String(length=64), nullable=True),
        sa.Column("daily_extra_units", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("starts_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("ends_at", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("reason", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_quota_grants_user_id", "ai_quota_grants", ["user_id"], unique=False)
    op.create_index("ix_ai_quota_grants_feature", "ai_quota_grants", ["feature"], unique=False)
    op.create_index(
        "ix_ai_quota_grants_user_feature_active",
        "ai_quota_grants",
        ["user_id", "feature", "is_active"],
        unique=False,
    )
    op.alter_column("ai_quota_grants", "daily_extra_units", server_default=None)
    op.alter_column("ai_quota_grants", "starts_at", server_default=None)
    op.alter_column("ai_quota_grants", "is_active", server_default=None)
    op.alter_column("ai_quota_grants", "created_at", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_ai_quota_grants_user_feature_active", table_name="ai_quota_grants")
    op.drop_index("ix_ai_quota_grants_feature", table_name="ai_quota_grants")
    op.drop_index("ix_ai_quota_grants_user_id", table_name="ai_quota_grants")
    op.drop_table("ai_quota_grants")

    op.drop_index("ix_ai_usage_events_user_feature_created", table_name="ai_usage_events")
    op.drop_index("ix_ai_usage_events_created_at", table_name="ai_usage_events")
    op.drop_index("ix_ai_usage_events_feature", table_name="ai_usage_events")
    op.drop_index("ix_ai_usage_events_user_id", table_name="ai_usage_events")
    op.drop_table("ai_usage_events")
