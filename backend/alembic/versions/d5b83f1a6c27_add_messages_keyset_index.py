"""Index messages for keyset pagination inside one conversation

``GET /conversations/{id}/messages`` selected every message a conversation had
ever contained and serialised all of them. The paged read that replaces it
orders by ``(created_at, id)`` within one conversation, and the table only
carried two single-column indexes — one on ``conversation_id``, one on
``created_at``. Neither can answer that ordering: the planner filters by
conversation and then sorts the whole history to find the newest page.

Adding an index is not destructive and nothing is backfilled; the existing
single-column indexes are left in place because other queries use them, and
removing them belongs to whoever can show they are unused.

Revision ID: d5b83f1a6c27
Revises: c4a71e2b90d8
Create Date: 2026-09-08
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d5b83f1a6c27"
down_revision: Union[str, Sequence[str], None] = "c4a71e2b90d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEX_NAME = "ix_messages_conversation_created_id"


def _table_exists(bind, name: str) -> bool:
    return sa.inspect(bind).has_table(name)


def _indexes(bind, table: str) -> set[str]:
    return {index["name"] for index in sa.inspect(bind).get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, "messages"):
        return
    if INDEX_NAME not in _indexes(bind, "messages"):
        op.create_index(INDEX_NAME, "messages", ["conversation_id", "created_at", "id"])


def downgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, "messages"):
        return
    if INDEX_NAME in _indexes(bind, "messages"):
        op.drop_index(INDEX_NAME, table_name="messages")
