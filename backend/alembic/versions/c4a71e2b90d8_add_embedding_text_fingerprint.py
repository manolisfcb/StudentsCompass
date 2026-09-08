"""Record what each resume embedding was made from

``upsert_resume_embedding_from_text`` generated a vector, then looked to see
whether one existed, then wrote — every call, whether or not anything had
changed. With the hash provider that is CPU burned on a warm path; with the
local sentence-transformer it is a forward pass and the resident memory that
comes with it, on a request a user is waiting for.

Skipping the work needs a stored answer to "would regenerating produce the same
vector?". These two columns are that answer: the SHA-256 of the exact text
handed to the provider, the model name, and the version of the recipe.

Existing rows are left **NULL on purpose**. The text that produced them is not
recoverable — ``resumes.ai_summary`` may have been rewritten since — so there is
no demonstrable input to fingerprint. Inventing one would make the service skip
a regeneration on the strength of a guess. NULL means "no provenance": the row
is regenerated once, on demand, and carries a real fingerprint from then on.

Revision ID: c4a71e2b90d8
Revises: b2e9f4a71c33
Create Date: 2026-09-08
"""
from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4a71e2b90d8"
down_revision: Union[str, Sequence[str], None] = "b2e9f4a71c33"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

LOGGER = logging.getLogger("alembic.runtime.migration")

TABLE = "resume_embeddings"


def _table_exists(bind) -> bool:
    return sa.inspect(bind).has_table(TABLE)


def _columns(bind) -> set[str]:
    return {column["name"] for column in sa.inspect(bind).get_columns(TABLE)}


def _inventory(bind) -> int:
    """How many stored vectors are about to be left without provenance."""
    return int(bind.execute(sa.text(f"SELECT COUNT(*) FROM {TABLE}")).scalar() or 0)


def upgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind):
        return

    without_provenance = _inventory(bind)
    existing = _columns(bind)

    if "text_fingerprint" not in existing:
        op.add_column(TABLE, sa.Column("text_fingerprint", sa.String(length=64), nullable=True))
    if "fingerprint_version" not in existing:
        op.add_column(TABLE, sa.Column("fingerprint_version", sa.String(length=16), nullable=True))

    if without_provenance:
        LOGGER.warning(
            "%s: %s existing vector(s) keep a NULL fingerprint; each is regenerated "
            "once on its next use. No fingerprint was invented for them.",
            TABLE,
            without_provenance,
        )


def downgrade() -> None:
    """Drop the columns. The vectors themselves are untouched.

    Losing the fingerprints only costs one regeneration per row afterwards,
    which is exactly the behaviour this revision replaced.
    """
    bind = op.get_bind()
    if not _table_exists(bind):
        return
    existing = _columns(bind)
    if "fingerprint_version" in existing:
        op.drop_column(TABLE, "fingerprint_version")
    if "text_fingerprint" in existing:
        op.drop_column(TABLE, "text_fingerprint")
