"""converge resource_lesson_progress to a single shape

Two branches off ``1720e86014a0`` each created ``resource_lesson_progress``:

* ``6e4bc7a18f21`` — with ``resource_id`` NOT NULL, ``created_at``/``updated_at``,
  and nullable progress timestamps.
* ``8c1d4a2b9f77`` — without ``resource_id``, without the audit columns, and
  with NOT NULL progress timestamps.

The first branch guards its ``CREATE TABLE`` with an existence check and the
second does not, so which shape a database ended up with depends on the order
Alembic happened to walk the branches in. This revision reconciles both onto
the union shape the model now maps, without dropping a column or a row:

* ``resource_id`` is added when missing and backfilled through
  ``lesson -> module -> resource``; it stays nullable because the writer does
  not set it and because a row whose lesson was deleted has nothing to derive
  from. Making it NOT NULL is a separate, forward-only step once every row is
  verified.
* ``created_at``/``updated_at`` are added when missing, NOT NULL with a
  server default so existing rows are valid immediately.
* ``completed_at``/``last_opened_at`` are relaxed to NULL-able, which is the
  permissive side of the disagreement: a database that already allows NULLs
  keeps its rows, and one that does not loses no data by allowing them.

Revision ID: a7f4c2b8d590
Revises: e4f6a7b8c9d0
Create Date: 2026-09-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a7f4c2b8d590"
down_revision: Union[str, Sequence[str], None] = "e4f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "resource_lesson_progress"


def _columns(inspector) -> dict:
    return {column["name"]: column for column in inspector.get_columns(TABLE)}


def _index_names(inspector) -> set:
    return {index["name"] for index in inspector.get_indexes(TABLE)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if TABLE not in inspector.get_table_names():
        # Neither branch ran: nothing deployed to converge.
        return

    columns = _columns(inspector)

    if "resource_id" not in columns:
        op.add_column(TABLE, sa.Column("resource_id", sa.UUID(), nullable=True))
        op.create_foreign_key(
            "fk_resource_lesson_progress_resource_id_resources",
            TABLE,
            "resources",
            ["resource_id"],
            ["id"],
            ondelete="CASCADE",
        )

    # Backfill is expressed as a single set-based statement and is re-runnable:
    # it only touches rows that are still NULL, so an interrupted migration can
    # be resumed by running it again.
    op.execute(
        sa.text(
            f"""
            UPDATE {TABLE} AS progress
            SET resource_id = modules.resource_id
            FROM resource_lessons AS lessons
            JOIN resource_modules AS modules ON modules.id = lessons.module_id
            WHERE lessons.id = progress.lesson_id
              AND progress.resource_id IS NULL
            """
        )
    )

    for column_name in ("created_at", "updated_at"):
        if column_name not in columns:
            op.add_column(
                TABLE,
                sa.Column(
                    column_name,
                    sa.DateTime(),
                    nullable=False,
                    server_default=sa.text("now()"),
                ),
            )

    # The branch that created ``resource_id`` made it NOT NULL. The writer
    # never sets it, so a database on that branch rejects every new progress
    # row; relaxing the column is what makes both shapes writable by the same
    # code. Tightening it again belongs to the task that also stops deriving
    # the resource from the lesson.
    for column_name in ("resource_id", "completed_at", "last_opened_at"):
        if columns.get(column_name, {}).get("nullable") is False:
            op.alter_column(
                TABLE,
                column_name,
                existing_type=sa.UUID() if column_name == "resource_id" else sa.DateTime(),
                nullable=True,
            )

    if "ix_resource_lesson_progress_resource_id" not in _index_names(inspector):
        op.create_index(
            "ix_resource_lesson_progress_resource_id", TABLE, ["resource_id"], unique=False
        )


def downgrade() -> None:
    """Forward-only by design: the columns added here may already hold data.

    Dropping ``resource_id`` would discard a backfill that a later revision is
    expected to depend on, and re-imposing NOT NULL would fail on exactly the
    rows this revision made representable. Reverting the application code is
    safe on its own; the schema stays as the permissive union.
    """
    pass
