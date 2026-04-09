"""add team_index_sources

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-18 12:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'team_index_sources',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('team_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('commodity_id', sa.Integer(), nullable=False),
        sa.Column('region', sa.String(20), nullable=False),
        sa.Column('source_type', sa.String(20), nullable=False),
        sa.Column('scrape_url', sa.String(512), nullable=True),
        sa.Column('scrape_config', postgresql.JSONB(), nullable=True),
        sa.Column('source_file', sa.String(255), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['commodity_id'], ['commodity_indexes.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('team_id', 'commodity_id', 'region'),
    )


def downgrade() -> None:
    op.drop_table('team_index_sources')
