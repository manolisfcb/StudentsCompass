"""add friendships tables

Revision ID: 1c2d3e4f5a6b
Revises: f6e7a8b9c0d1
Create Date: 2026-04-07 12:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "1c2d3e4f5a6b"
down_revision: Union[str, Sequence[str], None] = "f6e7a8b9c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "friend_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sender_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("receiver_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("responded_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["receiver_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_friend_requests_sender_id", "friend_requests", ["sender_id"])
    op.create_index("ix_friend_requests_receiver_id", "friend_requests", ["receiver_id"])
    op.create_index("ix_friend_requests_status", "friend_requests", ["status"])
    op.alter_column("friend_requests", "status", server_default=None)

    op.create_table(
        "friendships",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("friend_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["friend_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "friend_id", name="uq_friendships_user_friend"),
    )
    op.create_index("ix_friendships_user_id", "friendships", ["user_id"])
    op.create_index("ix_friendships_friend_id", "friendships", ["friend_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_friendships_friend_id", table_name="friendships")
    op.drop_index("ix_friendships_user_id", table_name="friendships")
    op.drop_table("friendships")

    op.drop_index("ix_friend_requests_status", table_name="friend_requests")
    op.drop_index("ix_friend_requests_receiver_id", table_name="friend_requests")
    op.drop_index("ix_friend_requests_sender_id", table_name="friend_requests")
    op.drop_table("friend_requests")
