"""legacy bridge revision

Revision ID: 1720e86014a0
Revises: e1f7c2b9a4d3
Create Date: 2026-02-27 16:55:00.000000

"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "1720e86014a0"
down_revision: Union[str, Sequence[str], None] = "e1f7c2b9a4d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Bridge revision to recover missing historical migration file.
    pass


def downgrade() -> None:
    pass
