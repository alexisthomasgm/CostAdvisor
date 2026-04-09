"""make index_overrides.value nullable for blank overrides

Revision ID: g7h8i9j0k1l2
Revises: f6a7b8c9d0e1
Create Date: 2026-03-24 12:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'g7h8i9j0k1l2'
down_revision: Union[str, None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'index_overrides', 'value',
        existing_type=sa.Numeric(14, 4),
        nullable=True,
    )


def downgrade() -> None:
    # Delete any null-value overrides before making column NOT NULL again
    op.execute("DELETE FROM index_overrides WHERE value IS NULL")
    op.alter_column(
        'index_overrides', 'value',
        existing_type=sa.Numeric(14, 4),
        nullable=False,
    )
