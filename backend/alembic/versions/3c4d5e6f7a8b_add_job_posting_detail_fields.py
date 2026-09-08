"""add detail fields to job_postings

Revision ID: 3c4d5e6f7a8b
Revises: f3a8c1d2e4b5
Create Date: 2026-03-10 14:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3c4d5e6f7a8b"
down_revision: Union[str, Sequence[str], None] = "f3a8c1d2e4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("job_postings", sa.Column("workplace_type", sa.String(), nullable=True))
    op.add_column("job_postings", sa.Column("seniority_level", sa.String(), nullable=True))
    op.add_column("job_postings", sa.Column("benefits", sa.Text(), nullable=True))
    op.add_column("job_postings", sa.Column("listed_context", sa.String(), nullable=True))
    op.add_column("job_postings", sa.Column("source_context", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("job_postings", "source_context")
    op.drop_column("job_postings", "listed_context")
    op.drop_column("job_postings", "benefits")
    op.drop_column("job_postings", "seniority_level")
    op.drop_column("job_postings", "workplace_type")
