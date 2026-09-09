"""Add the feed's keyset index

The global feed is read in ``(created_at DESC, id DESC)`` order and paged by
that pair. The table carried no index on ``created_at`` at all, so the previous
unbounded read sorted every post on the platform, and a bounded page would
still sort — an index on ``created_at`` alone cannot answer an order that
tie-breaks on ``id``, which is exactly what makes the cursor unambiguous when
posts share a timestamp.

Additive: an index only. No column, no data, no behaviour of its own. Creating
it takes a lock proportional to the table, which for this table is small; on a
large deployment it would be worth ``CONCURRENTLY``, and that is noted rather
than done because it cannot run inside a migration's transaction.

Revision ID: a2b7e4d10f36
Revises: f1a6d3c85e02
Create Date: 2026-09-08
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a2b7e4d10f36"
down_revision: Union[str, Sequence[str], None] = "f1a6d3c85e02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEX = "ix_posts_created_at_id"


def _index_exists(bind, table: str, name: str) -> bool:
    return name in {index["name"] for index in sa.inspect(bind).get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()
    # Replayable: see the note in f1a6d3c85e02.
    if _index_exists(bind, "posts", INDEX):
        return

    op.create_index(INDEX, "posts", ["created_at", "id"])


def downgrade() -> None:
    op.drop_index(INDEX, table_name="posts")
