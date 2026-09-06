"""add storage_deletion_intents

Records that a stored object should no longer exist, in the same transaction as
the row that stopped referencing it. Without it, deleting a file was ordered
storage-first and a rollback or a provider error left either a row pointing at a
missing file or an object nothing could ever find again.

Purely additive: a new table, no data touched, nothing dropped.

Revision ID: c3e8b1a7d240
Revises: a7f4c2b8d590
Create Date: 2026-09-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c3e8b1a7d240"
down_revision: Union[str, Sequence[str], None] = "a7f4c2b8d590"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "storage_deletion_intents"


def upgrade() -> None:
    bind = op.get_bind()
    if TABLE in sa.inspect(bind).get_table_names():
        return

    op.create_table(
        TABLE,
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("storage_location_id", sa.String(length=255), nullable=False),
        sa.Column("object_key", sa.String(length=1024), nullable=False),
        sa.Column("requested_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_attempt_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "storage_location_id", "object_key", name="uq_storage_deletion_intents_object"
        ),
    )
    op.create_index(
        "ix_storage_deletion_intents_pending",
        TABLE,
        ["completed_at", "requested_at"],
        unique=False,
    )


def downgrade() -> None:
    """Dropping this table discards deletions that have not run yet.

    Those objects would then be paid for indefinitely with nothing left that
    knows they are unwanted, so the table stays. Reverting the application code
    is safe on its own: an unused intents table costs nothing.
    """
    pass
