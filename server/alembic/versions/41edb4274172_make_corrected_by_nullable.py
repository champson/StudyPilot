"""make_corrected_by_nullable

Revision ID: 41edb4274172
Revises: 90f3a0c48806
Create Date: 2026-03-21 12:55:52.551036

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '41edb4274172'
down_revision: Union[str, None] = '90f3a0c48806'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "manual_corrections",
        "corrected_by",
        existing_type=sa.Integer(),
        nullable=True,
    )
    # Fix existing rows with corrected_by=0 (invalid FK)
    op.execute(
        "UPDATE manual_corrections SET corrected_by = NULL WHERE corrected_by = 0"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE manual_corrections SET corrected_by = 0 WHERE corrected_by IS NULL"
    )
    op.alter_column(
        "manual_corrections",
        "corrected_by",
        existing_type=sa.Integer(),
        nullable=False,
    )
