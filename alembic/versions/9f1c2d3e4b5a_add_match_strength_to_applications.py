"""add match strength to applications

Revision ID: 9f1c2d3e4b5a
Revises: 5e6f7a8b9c0d
Create Date: 2026-03-13 16:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9f1c2d3e4b5a"
down_revision: Union[str, Sequence[str], None] = "5e6f7a8b9c0d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


application_match_strength = sa.Enum(
    "strong_match",
    "match",
    "weak_match",
    name="applicationmatchstrength",
)


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    application_match_strength.create(bind, checkfirst=True)

    op.add_column(
        "applications",
        sa.Column(
            "match_strength",
            application_match_strength,
            nullable=False,
            server_default="match",
        ),
    )

    op.execute(
        sa.text(
            """
            WITH ranked AS (
                SELECT id, ROW_NUMBER() OVER (ORDER BY created_at, id) AS rn
                FROM applications
            )
            UPDATE applications AS a
            SET match_strength = (
                CASE MOD(r.rn, 3)
                WHEN 1 THEN 'strong_match'
                WHEN 2 THEN 'match'
                ELSE 'weak_match'
                END
            )::applicationmatchstrength
            FROM ranked AS r
            WHERE a.id = r.id
            """
        )
    )

    op.alter_column("applications", "match_strength", server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("applications", "match_strength")
    application_match_strength.drop(op.get_bind(), checkfirst=True)
