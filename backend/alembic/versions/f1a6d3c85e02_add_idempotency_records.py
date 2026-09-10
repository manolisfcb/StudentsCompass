"""Add the idempotency record registry

Plan 08 §5.1 asks for ``Idempotency-Key`` where a repeated request costs money
or creates a duplicate. The header only means something if the server remembers
what it already answered, and this table is that memory.

Purely additive: one new table, no existing column touched, nothing backfilled.
An empty registry behaves exactly like the code did before it existed — a
request with no matching record does its work — so the migration is safe to
apply ahead of the code and safe to leave in place if the code is reverted.

The unique constraint over ``(actor_key, endpoint, idempotency_key)`` is the
mechanism, not an optimisation: two concurrent retries are separated by the
database refusing the second insert, which is the only way to decide it without
a race. It is scoped by actor because keys are chosen by clients, and no caller
may read back a response that belongs to someone else.

Retention is enforced by the application against ``expires_at``; the index on
it exists for that sweep, which is the one query that scans without an actor.

Revision ID: f1a6d3c85e02
Revises: e7c2d940ab15
Create Date: 2026-09-08
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f1a6d3c85e02"
down_revision: Union[str, Sequence[str], None] = "e7c2d940ab15"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "idempotency_records"

# SQLAlchemy persists Enum *names*, so these are the labels the column holds.
IDEMPOTENCY_STATUSES = ("IN_PROGRESS", "COMPLETED")


def _table_exists(bind, name: str) -> bool:
    return sa.inspect(bind).has_table(name)


def upgrade() -> None:
    bind = op.get_bind()
    # Replayable on purpose. `test_upgrade_head_commits_on_an_existing_database`
    # rewinds the stamp one revision and runs the head again over a database
    # that already has its result, which is how it proves the upgrade *commits*
    # rather than rolling back. A head that cannot survive that would fail the
    # guard instead of the bug the guard is for.
    if _table_exists(bind, TABLE):
        return

    op.create_table(
        TABLE,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("actor_key", sa.String(length=128), nullable=False),
        sa.Column("endpoint", sa.String(length=200), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.Enum(*IDEMPOTENCY_STATUSES, name="idempotencystatus"),
            nullable=False,
        ),
        sa.Column("response_status_code", sa.Integer(), nullable=True),
        sa.Column("response_body", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "actor_key",
            "endpoint",
            "idempotency_key",
            name="uq_idempotency_actor_endpoint_key",
        ),
    )
    op.create_index("ix_idempotency_records_expires_at", TABLE, ["expires_at"])


def downgrade() -> None:
    # Dropping the table loses stored responses, so a retry that would have
    # replayed re-runs instead. That is the pre-existing behaviour, not data
    # loss of a user's own records: nothing here is a source of truth.
    op.drop_index("ix_idempotency_records_expires_at", table_name=TABLE)
    op.drop_table(TABLE)
    sa.Enum(name="idempotencystatus").drop(op.get_bind(), checkfirst=True)
