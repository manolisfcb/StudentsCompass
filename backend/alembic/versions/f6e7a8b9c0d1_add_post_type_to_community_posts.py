"""add post type to community posts

Revision ID: f6e7a8b9c0d1
Revises: a1b2c3d4e5f6
Create Date: 2026-04-07 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f6e7a8b9c0d1"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "community_posts",
        sa.Column("post_type", sa.String(length=32), nullable=False, server_default="discussion"),
    )
    op.alter_column("community_posts", "post_type", server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("community_posts", "post_type")
