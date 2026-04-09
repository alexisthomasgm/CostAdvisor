"""add formula_version_id to actual_prices

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-03-23 10:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('actual_prices', sa.Column('formula_version_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_actual_prices_formula_version',
        'actual_prices', 'formula_versions',
        ['formula_version_id'], ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_actual_prices_formula_version', 'actual_prices', type_='foreignkey')
    op.drop_column('actual_prices', 'formula_version_id')
