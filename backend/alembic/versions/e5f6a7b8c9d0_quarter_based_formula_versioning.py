"""quarter-based formula versioning

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-03-23 14:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Deduplicate formula_versions rows with same (cost_model_id, base_year, base_quarter)
    #    Keep the highest id, delete the rest
    op.execute("""
        DELETE FROM formula_versions
        WHERE id NOT IN (
            SELECT MAX(id)
            FROM formula_versions
            GROUP BY cost_model_id, base_year, base_quarter
        )
    """)

    # 2. Drop formula_version_id FK + column from actual_prices (undo previous migration)
    op.drop_constraint('fk_actual_prices_formula_version', 'actual_prices', type_='foreignkey')
    op.drop_column('actual_prices', 'formula_version_id')

    # 3. Drop is_current and version_number columns
    op.drop_column('formula_versions', 'is_current')
    op.drop_column('formula_versions', 'version_number')

    # 4. Add updated_at column (default to created_at for existing rows)
    op.add_column('formula_versions', sa.Column(
        'updated_at', sa.DateTime(timezone=True), nullable=True,
    ))
    op.execute("UPDATE formula_versions SET updated_at = created_at")
    op.alter_column('formula_versions', 'updated_at', nullable=False)

    # 5. Add unique constraint on (cost_model_id, base_year, base_quarter)
    op.create_unique_constraint(
        'uq_formula_versions_model_quarter',
        'formula_versions',
        ['cost_model_id', 'base_year', 'base_quarter'],
    )


def downgrade() -> None:
    op.drop_constraint('uq_formula_versions_model_quarter', 'formula_versions', type_='unique')
    op.drop_column('formula_versions', 'updated_at')
    op.add_column('formula_versions', sa.Column('version_number', sa.SmallInteger(), nullable=False, server_default='1'))
    op.add_column('formula_versions', sa.Column('is_current', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('actual_prices', sa.Column('formula_version_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_actual_prices_formula_version',
        'actual_prices', 'formula_versions',
        ['formula_version_id'], ['id'],
        ondelete='SET NULL',
    )
