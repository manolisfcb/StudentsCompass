"""merge capstone review and embedding heads

Revision ID: e4f6a7b8c9d0
Revises: c7d8e9f0a1b2, d3e4f5a6b7c8
Create Date: 2026-06-20 00:00:00.000000

"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "e4f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = ("c7d8e9f0a1b2", "d3e4f5a6b7c8")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
