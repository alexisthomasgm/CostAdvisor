"""restructure data model

Revision ID: a1b2c3d4e5f6
Revises: f5f3c2044043
Create Date: 2026-03-16 10:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f5f3c2044043'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- New tables ---

    op.create_table('chemical_families',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('custom_attribute_schema', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    op.create_table('suppliers',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('team_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('country', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('fx_rates',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('from_currency', sa.String(length=3), nullable=False),
        sa.Column('to_currency', sa.String(length=3), nullable=False),
        sa.Column('year', sa.SmallInteger(), nullable=False),
        sa.Column('quarter', sa.SmallInteger(), nullable=False),
        sa.Column('rate', sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column('uploaded_by', sa.UUID(), nullable=False),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['uploaded_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('from_currency', 'to_currency', 'year', 'quarter')
    )

    op.create_table('audit_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('team_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('entity_id', sa.String(length=64), nullable=False),
        sa.Column('previous_value', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('new_value', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('cost_models',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('team_id', sa.UUID(), nullable=False),
        sa.Column('product_id', sa.UUID(), nullable=False),
        sa.Column('supplier_id', sa.Integer(), nullable=True),
        sa.Column('destination_country', sa.String(length=64), nullable=True),
        sa.Column('region', sa.String(length=20), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['supplier_id'], ['suppliers.id']),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('formula_versions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('cost_model_id', sa.UUID(), nullable=False),
        sa.Column('version_number', sa.SmallInteger(), nullable=False),
        sa.Column('base_price', sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column('base_year', sa.SmallInteger(), nullable=False),
        sa.Column('base_quarter', sa.SmallInteger(), nullable=False),
        sa.Column('margin_type', sa.String(length=10), nullable=False),
        sa.Column('margin_value', sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column('is_current', sa.Boolean(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['cost_model_id'], ['cost_models.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('formula_components',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('formula_version_id', sa.Integer(), nullable=False),
        sa.Column('label', sa.String(length=64), nullable=False),
        sa.Column('commodity_id', sa.Integer(), nullable=True),
        sa.Column('weight', sa.Numeric(precision=6, scale=4), nullable=False),
        sa.ForeignKeyConstraint(['commodity_id'], ['commodity_indexes.id']),
        sa.ForeignKeyConstraint(['formula_version_id'], ['formula_versions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('actual_volumes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('cost_model_id', sa.UUID(), nullable=False),
        sa.Column('uploaded_by', sa.UUID(), nullable=False),
        sa.Column('year', sa.SmallInteger(), nullable=False),
        sa.Column('quarter', sa.SmallInteger(), nullable=False),
        sa.Column('volume', sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column('unit', sa.String(length=10), nullable=False),
        sa.Column('source_file', sa.String(length=255), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['cost_model_id'], ['cost_models.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['uploaded_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('cost_model_id', 'year', 'quarter')
    )

    # --- Modify existing tables ---

    # Add is_super_admin to users
    op.add_column('users', sa.Column('is_super_admin', sa.Boolean(), nullable=False, server_default='false'))

    # Add new columns to products
    op.add_column('products', sa.Column('chemical_family_id', sa.Integer(), nullable=True))
    op.add_column('products', sa.Column('unit', sa.String(length=10), nullable=False, server_default='kg'))
    op.add_column('products', sa.Column('custom_attributes', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.create_foreign_key('fk_products_chemical_family', 'products', 'chemical_families', ['chemical_family_id'], ['id'])

    # Remove cost-model fields from products (data migration should happen first in production)
    op.drop_column('products', 'region')
    op.drop_column('products', 'reference_cost')
    op.drop_column('products', 'reference_year')
    op.drop_column('products', 'reference_quarter')
    op.drop_column('products', 'margin_pct')
    op.drop_column('products', 'scenario_type')

    # Migrate actual_prices FK: product_id -> cost_model_id
    # Drop old FK and column, add new one
    op.drop_constraint('actual_prices_product_id_year_quarter_key', 'actual_prices', type_='unique')
    op.drop_constraint('actual_prices_product_id_fkey', 'actual_prices', type_='foreignkey')
    op.alter_column('actual_prices', 'product_id', new_column_name='cost_model_id')
    op.create_foreign_key('actual_prices_cost_model_id_fkey', 'actual_prices', 'cost_models', ['cost_model_id'], ['id'], ondelete='CASCADE')
    op.create_unique_constraint('actual_prices_cost_model_id_year_quarter_key', 'actual_prices', ['cost_model_id', 'year', 'quarter'])

    # Drop old product_compositions table (replaced by formula_components)
    op.drop_table('product_compositions')


def downgrade() -> None:
    # Recreate product_compositions
    op.create_table('product_compositions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('product_id', sa.UUID(), nullable=False),
        sa.Column('component_type', sa.String(length=10), nullable=False),
        sa.Column('component_name', sa.String(length=64), nullable=False),
        sa.Column('commodity_id', sa.Integer(), nullable=True),
        sa.Column('weight', sa.Numeric(precision=6, scale=4), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column('unit_cost', sa.Numeric(precision=12, scale=4), nullable=True),
        sa.ForeignKeyConstraint(['commodity_id'], ['commodity_indexes.id']),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Restore actual_prices FK
    op.drop_constraint('actual_prices_cost_model_id_year_quarter_key', 'actual_prices', type_='unique')
    op.drop_constraint('actual_prices_cost_model_id_fkey', 'actual_prices', type_='foreignkey')
    op.alter_column('actual_prices', 'cost_model_id', new_column_name='product_id')
    op.create_foreign_key('actual_prices_product_id_fkey', 'actual_prices', 'products', ['product_id'], ['id'], ondelete='CASCADE')
    op.create_unique_constraint('actual_prices_product_id_year_quarter_key', 'actual_prices', ['product_id', 'year', 'quarter'])

    # Restore product columns
    op.add_column('products', sa.Column('scenario_type', sa.String(length=20), nullable=False, server_default='High'))
    op.add_column('products', sa.Column('margin_pct', sa.Numeric(precision=5, scale=2), nullable=False, server_default='20'))
    op.add_column('products', sa.Column('reference_quarter', sa.SmallInteger(), nullable=True))
    op.add_column('products', sa.Column('reference_year', sa.SmallInteger(), nullable=True))
    op.add_column('products', sa.Column('reference_cost', sa.Numeric(precision=12, scale=4), nullable=True))
    op.add_column('products', sa.Column('region', sa.String(length=20), nullable=False, server_default='Europe'))

    op.drop_constraint('fk_products_chemical_family', 'products', type_='foreignkey')
    op.drop_column('products', 'custom_attributes')
    op.drop_column('products', 'unit')
    op.drop_column('products', 'chemical_family_id')

    op.drop_column('users', 'is_super_admin')

    op.drop_table('actual_volumes')
    op.drop_table('formula_components')
    op.drop_table('formula_versions')
    op.drop_table('cost_models')
    op.drop_table('audit_logs')
    op.drop_table('fx_rates')
    op.drop_table('suppliers')
    op.drop_table('chemical_families')
