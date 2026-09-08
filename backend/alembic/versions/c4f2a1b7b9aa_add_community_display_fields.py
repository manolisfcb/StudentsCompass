"""add community display fields

Revision ID: c4f2a1b7b9aa
Revises: b1d6f02d7f6b
Create Date: 2026-02-15 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "c4f2a1b7b9aa"
down_revision: Union[str, Sequence[str], None] = "b1d6f02d7f6b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("communities", sa.Column("icon", sa.String(length=20), nullable=True))
    op.add_column("communities", sa.Column("activity_status", sa.String(length=32), nullable=True))
    op.add_column("communities", sa.Column("tags", postgresql.JSONB(), nullable=True))
    op.add_column(
        "communities",
        sa.Column("member_count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("communities", "member_count")
    op.drop_column("communities", "tags")
    op.drop_column("communities", "activity_status")
    op.drop_column("communities", "icon")
