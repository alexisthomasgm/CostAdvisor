"""Add User.deleted_at (soft-delete tombstone) and tighten FK cascades so a
team hard-delete removes all team-scoped data cleanly.

Changes:
- `users.deleted_at` column (nullable timestamptz)
- `cost_scenarios.team_id` FK gains ON DELETE CASCADE
- `cost_models.supplier_id` FK gains ON DELETE SET NULL (nullable already)
"""

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "i9j0k1l2m3n4"
down_revision = "h8i9j0k1l2m3"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # cost_scenarios.team_id: add CASCADE
    op.execute("ALTER TABLE cost_scenarios DROP CONSTRAINT IF EXISTS cost_scenarios_team_id_fkey")
    op.create_foreign_key(
        "cost_scenarios_team_id_fkey",
        "cost_scenarios", "teams",
        ["team_id"], ["id"],
        ondelete="CASCADE",
    )

    # cost_models.supplier_id: add SET NULL so supplier delete doesn't block
    op.execute("ALTER TABLE cost_models DROP CONSTRAINT IF EXISTS cost_models_supplier_id_fkey")
    op.create_foreign_key(
        "cost_models_supplier_id_fkey",
        "cost_models", "suppliers",
        ["supplier_id"], ["id"],
        ondelete="SET NULL",
    )


def downgrade():
    op.execute("ALTER TABLE cost_models DROP CONSTRAINT IF EXISTS cost_models_supplier_id_fkey")
    op.create_foreign_key(
        "cost_models_supplier_id_fkey",
        "cost_models", "suppliers",
        ["supplier_id"], ["id"],
    )

    op.execute("ALTER TABLE cost_scenarios DROP CONSTRAINT IF EXISTS cost_scenarios_team_id_fkey")
    op.create_foreign_key(
        "cost_scenarios_team_id_fkey",
        "cost_scenarios", "teams",
        ["team_id"], ["id"],
    )

    op.drop_column("users", "deleted_at")
