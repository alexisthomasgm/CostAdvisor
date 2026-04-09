"""add currency and category to commodity_indexes

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-03-24 10:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('commodity_indexes', sa.Column('currency', sa.String(3), nullable=True))
    op.add_column('commodity_indexes', sa.Column('category', sa.String(32), nullable=True))


def downgrade() -> None:
    op.drop_column('commodity_indexes', 'category')
    op.drop_column('commodity_indexes', 'currency')
