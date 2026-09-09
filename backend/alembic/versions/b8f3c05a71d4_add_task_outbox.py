"""Add the task dispatch outbox

Plan 08 §6.3: the CV-analysis runner must stop being a loop inside every web
replica. What replaces it needs somewhere to record "this job still has to be
handed to a worker", because enqueuing a Cloud Task cannot join the database
transaction that created the job — enqueue before the commit and a task can
outlive a rolled-back job; enqueue after it and a crash in between loses the
dispatch entirely.

Purely additive: one new table. No existing column is touched and nothing is
backfilled. Applying it changes no behaviour on its own; jobs already queued
keep being recovered by ``job_analysis``'s own lease, which this migration does
not alter.

``uq_task_outbox_dedupe_key`` is load-bearing rather than hygienic: it is what
makes a retried enqueue produce one task instead of two, decided by the
database rather than by a read followed by an insert.

Revision ID: b8f3c05a71d4
Revises: a2b7e4d10f36
Create Date: 2026-09-08
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b8f3c05a71d4"
down_revision: Union[str, Sequence[str], None] = "a2b7e4d10f36"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "task_outbox"

# SQLAlchemy persists Enum *names*, so these are the labels stored.
OUTBOX_STATUSES = ("PENDING", "DISPATCHED", "FAILED")


def _table_exists(bind, name: str) -> bool:
    return sa.inspect(bind).has_table(name)


def upgrade() -> None:
    bind = op.get_bind()
    # Replayable: see the note in f1a6d3c85e02. Without this the ENUM type is
    # what fails first — `CREATE TYPE outboxstatus` has no IF NOT EXISTS.
    if _table_exists(bind, TABLE):
        return

    op.create_table(
        TABLE,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("task_type", sa.String(length=64), nullable=False),
        sa.Column(
            "payload",
            sa.JSON().with_variant(postgresql.JSONB, "postgresql"),
            nullable=False,
        ),
        sa.Column("dedupe_key", sa.String(length=200), nullable=False),
        sa.Column(
            "status",
            sa.Enum(*OUTBOX_STATUSES, name="outboxstatus"),
            nullable=False,
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available_at", sa.DateTime(), nullable=False),
        sa.Column("dispatched_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("dedupe_key", name="uq_task_outbox_dedupe_key"),
    )
    op.create_index(
        "ix_task_outbox_status_available_at", TABLE, ["status", "available_at"]
    )


def downgrade() -> None:
    # Undelivered rows are lost with the table, which means their jobs go back
    # to being recovered by the lease sweep alone — the behaviour before this
    # task. No job state is touched.
    op.drop_index("ix_task_outbox_status_available_at", table_name=TABLE)
    op.drop_table(TABLE)
    sa.Enum(name="outboxstatus").drop(op.get_bind(), checkfirst=True)
