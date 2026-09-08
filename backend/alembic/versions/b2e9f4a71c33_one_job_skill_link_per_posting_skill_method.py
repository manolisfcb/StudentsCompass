"""At most one job_skills link per posting, skill and extraction method

``extract_job_skills_from_job_posting`` reads the links a posting already has,
decides which matches are missing and inserts them. Nothing serialises those
three steps, so two extractions running together — the per-posting endpoint and
the open-postings sweep, or two sweeps — each read an empty set and each insert
the same link. ``resume_skills`` has carried
``uq_resume_skills_resume_skill_method`` since the analytics foundation; the
job side was left without the equivalent.

The index is **partial**: ``job_posting_id`` is nullable, and in PostgreSQL a
plain unique constraint would let unlimited rows through whenever it is NULL.
Restricting it to ``job_posting_id IS NOT NULL`` states the rule where it
actually applies and leaves detached links alone.

Duplicates that already exist are **merged, not silently dropped**: the
earliest row per (posting, skill, method) survives, and any provenance the
survivor lacks — ``evidence_text``, ``target_role``, ``importance_score`` — is
taken from its duplicates before they go. The method is part of the key, so two
extractions that disagree about *how* a skill was found stay as two rows: that
is provenance, not duplication.

Revision ID: b2e9f4a71c33
Revises: a7d3f81c9e64
Create Date: 2026-09-08
"""
from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2e9f4a71c33"
down_revision: Union[str, Sequence[str], None] = "a7d3f81c9e64"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

LOGGER = logging.getLogger("alembic.runtime.migration")

INDEX_NAME = "uq_job_skills_posting_skill_method"
NOT_NULL_PREDICATE = "job_posting_id IS NOT NULL"

#: Columns whose value is provenance: worth carrying over from a duplicate the
#: survivor cannot supply. ``created_at`` is deliberately absent — the
#: survivor's own timestamp is the fact being kept.
PROVENANCE_COLUMNS = ("evidence_text", "target_role", "importance_score")


def _table_exists(bind, name: str) -> bool:
    return sa.inspect(bind).has_table(name)


def _indexes(bind, table: str) -> set[str]:
    return {index["name"] for index in sa.inspect(bind).get_indexes(table)}


def _inventory_duplicates(bind) -> list[tuple]:
    """Every (posting, skill, method) carrying more than one link, before anything changes."""
    return bind.execute(
        sa.text(
            """
            SELECT job_posting_id, skill_id, extraction_method, COUNT(*) AS link_count
            FROM job_skills
            WHERE job_posting_id IS NOT NULL
            GROUP BY job_posting_id, skill_id, extraction_method
            HAVING COUNT(*) > 1
            """
        )
    ).fetchall()


def _survivor_and_losers(bind, job_posting_id, skill_id, extraction_method) -> tuple:
    """The earliest link of the group and the ids of the rest.

    Ordered by ``created_at`` then id so the choice is deterministic on every
    engine, including rows written inside the same clock tick.
    """
    rows = bind.execute(
        sa.text(
            """
            SELECT id, evidence_text, target_role, importance_score
            FROM job_skills
            WHERE job_posting_id = :job_posting_id
              AND skill_id = :skill_id
              AND extraction_method = :extraction_method
            ORDER BY created_at ASC, CAST(id AS VARCHAR) ASC
            """
        ),
        {
            "job_posting_id": job_posting_id,
            "skill_id": skill_id,
            "extraction_method": extraction_method,
        },
    ).fetchall()
    return rows[0], [row[0] for row in rows[1:]]


def _merge_provenance(bind, survivor, duplicates: list) -> dict:
    """Fill the survivor's empty provenance columns from its duplicates."""
    filled: dict = {}
    for position, column in enumerate(PROVENANCE_COLUMNS, start=1):
        if survivor[position] is not None:
            continue
        donor = next((row[position] for row in duplicates if row[position] is not None), None)
        if donor is not None:
            filled[column] = donor
    if filled:
        assignments = ", ".join(f"{column} = :{column}" for column in filled)
        bind.execute(
            sa.text(f"UPDATE job_skills SET {assignments} WHERE id = :id"),
            {**filled, "id": survivor[0]},
        )
    return filled


def _resolve_duplicates(bind) -> int:
    conflicts = _inventory_duplicates(bind)
    if not conflicts:
        return 0

    removed = 0
    for job_posting_id, skill_id, extraction_method, link_count in conflicts:
        LOGGER.warning(
            "job_skills: posting %s / skill %s / method %s has %s links; keeping the earliest",
            job_posting_id,
            skill_id,
            extraction_method,
            link_count,
        )
        survivor, loser_ids = _survivor_and_losers(
            bind, job_posting_id, skill_id, extraction_method
        )
        if not loser_ids:
            continue

        duplicate_rows = bind.execute(
            sa.text(
                "SELECT id, evidence_text, target_role, importance_score "
                "FROM job_skills WHERE id IN :ids"
            ).bindparams(sa.bindparam("ids", expanding=True)),
            {"ids": loser_ids},
        ).fetchall()
        filled = _merge_provenance(bind, survivor, duplicate_rows)
        if filled:
            LOGGER.warning(
                "job_skills: link %s inherited %s from a duplicate before it was removed",
                survivor[0],
                ", ".join(sorted(filled)),
            )

        bind.execute(
            sa.text("DELETE FROM job_skills WHERE id IN :ids").bindparams(
                sa.bindparam("ids", expanding=True)
            ),
            {"ids": loser_ids},
        )
        removed += len(loser_ids)

    LOGGER.warning(
        "job_skills: %s redundant link(s) merged into their earliest row across %s group(s)",
        removed,
        len(conflicts),
    )
    return removed


def upgrade() -> None:
    bind = op.get_bind()
    if not _table_exists(bind, "job_skills"):
        return

    _resolve_duplicates(bind)

    if INDEX_NAME not in _indexes(bind, "job_skills"):
        op.create_index(
            INDEX_NAME,
            "job_skills",
            ["job_posting_id", "skill_id", "extraction_method"],
            unique=True,
            postgresql_where=sa.text(NOT_NULL_PREDICATE),
            sqlite_where=sa.text(NOT_NULL_PREDICATE),
        )


def downgrade() -> None:
    """Drop the index. The merged links stay merged.

    Re-splitting them would recreate exactly the ambiguity this revision
    resolved — the same skill attached twice to one posting by one method — and
    the duplicate rows carried no fact the survivor does not now carry.
    """
    bind = op.get_bind()
    if not _table_exists(bind, "job_skills"):
        return
    if INDEX_NAME in _indexes(bind, "job_skills"):
        op.drop_index(INDEX_NAME, table_name="job_skills")
