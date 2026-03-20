"""add status to manual_corrections

Revision ID: a4cf3f83562f
Revises: 
Create Date: 2026-03-20 08:50:47.674010

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a4cf3f83562f'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "manual_corrections",
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
    )


def downgrade() -> None:
    op.drop_column("manual_corrections", "status")
