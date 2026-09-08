"""add communities and community posts

Revision ID: b1d6f02d7f6b
Revises: 7e1b9a4f2c10
Create Date: 2026-02-15 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b1d6f02d7f6b"
down_revision: Union[str, Sequence[str], None] = "7e1b9a4f2c10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "communities",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_communities_name"),
    )
    op.create_index("ix_communities_created_by", "communities", ["created_by"], unique=False)

    op.create_table(
        "community_members",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("community_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("joined_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["community_id"], ["communities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("community_id", "user_id", name="uq_community_member"),
    )
    op.create_index("ix_community_members_community_id", "community_members", ["community_id"], unique=False)
    op.create_index("ix_community_members_user_id", "community_members", ["user_id"], unique=False)

    op.create_table(
        "community_posts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("community_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["community_id"], ["communities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_community_posts_community_id", "community_posts", ["community_id"], unique=False)
    op.create_index("ix_community_posts_user_id", "community_posts", ["user_id"], unique=False)

    op.create_table(
        "community_post_likes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("post_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["post_id"], ["community_posts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("post_id", "user_id", name="uq_community_post_like"),
    )
    op.create_index("ix_community_post_likes_post_id", "community_post_likes", ["post_id"], unique=False)
    op.create_index("ix_community_post_likes_user_id", "community_post_likes", ["user_id"], unique=False)

    op.create_table(
        "community_post_comments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("post_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["post_id"], ["community_posts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_community_post_comments_post_id", "community_post_comments", ["post_id"], unique=False)
    op.create_index("ix_community_post_comments_user_id", "community_post_comments", ["user_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_community_post_comments_user_id", table_name="community_post_comments")
    op.drop_index("ix_community_post_comments_post_id", table_name="community_post_comments")
    op.drop_table("community_post_comments")

    op.drop_index("ix_community_post_likes_user_id", table_name="community_post_likes")
    op.drop_index("ix_community_post_likes_post_id", table_name="community_post_likes")
    op.drop_table("community_post_likes")

    op.drop_index("ix_community_posts_user_id", table_name="community_posts")
    op.drop_index("ix_community_posts_community_id", table_name="community_posts")
    op.drop_table("community_posts")

    op.drop_index("ix_community_members_user_id", table_name="community_members")
    op.drop_index("ix_community_members_community_id", table_name="community_members")
    op.drop_table("community_members")

    op.drop_index("ix_communities_created_by", table_name="communities")
    op.drop_table("communities")
