"""Enable Postgres row-level security on tenant-scoped tables.

Uses session GUC `app.current_user_id` (set by `get_current_user` in auth.py)
and `app.bypass_rls` (set by Celery tasks, seed scripts, and migrations).

Policy structure:
- Tables with a direct `team_id` column: row is visible if the caller is a
  member of that team, OR if bypass is on.
- `cost_scenarios`: same, plus always-visible system scenarios (is_system=true).
- Tables transitively scoped via `cost_model_id`: row is visible if the
  caller is a member of the owning cost_model's team.
- `formula_components`: transitively via `formula_version_id → cost_model_id`.

`FORCE ROW LEVEL SECURITY` is applied so the table owner (the app DB user)
is also subject to policies. Bypass is the only escape.
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "h8i9j0k1l2m3"
down_revision = "g7h8i9j0k1l2"
branch_labels = None
depends_on = None


MEMBERSHIP_SUBQUERY = """
    team_id IN (
        SELECT team_id FROM team_memberships
        WHERE user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
    )
"""

COST_MODEL_SUBQUERY = """
    cost_model_id IN (
        SELECT id FROM cost_models
        WHERE team_id IN (
            SELECT team_id FROM team_memberships
            WHERE user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
        )
    )
"""

FORMULA_VERSION_SUBQUERY = """
    formula_version_id IN (
        SELECT fv.id FROM formula_versions fv
        JOIN cost_models cm ON cm.id = fv.cost_model_id
        WHERE cm.team_id IN (
            SELECT team_id FROM team_memberships
            WHERE user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
        )
    )
"""

BYPASS = "current_setting('app.bypass_rls', true) = 'on'"


DIRECT_TABLES = [
    "products",
    "suppliers",
    "cost_models",
    "index_overrides",
    "team_index_sources",
    "audit_logs",
]

TRANSITIVE_CM_TABLES = [
    "formula_versions",
    "actual_prices",
    "actual_volumes",
]


def _enable(table: str):
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def _disable(table: str):
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
    op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")


def upgrade():
    for table in DIRECT_TABLES:
        _enable(table)
        op.execute(f"""
            CREATE POLICY tenant_isolation ON {table}
            USING ({BYPASS} OR {MEMBERSHIP_SUBQUERY})
            WITH CHECK ({BYPASS} OR {MEMBERSHIP_SUBQUERY})
        """)

    # cost_scenarios: nullable team_id + is_system flag.
    # Read: bypass OR system-defined OR team-matched.
    # Write: bypass OR team-matched (no writing system scenarios from RLS-scoped sessions).
    _enable("cost_scenarios")
    op.execute(f"""
        CREATE POLICY tenant_isolation ON cost_scenarios
        USING ({BYPASS} OR is_system = true OR {MEMBERSHIP_SUBQUERY})
        WITH CHECK ({BYPASS} OR {MEMBERSHIP_SUBQUERY})
    """)

    for table in TRANSITIVE_CM_TABLES:
        _enable(table)
        op.execute(f"""
            CREATE POLICY tenant_isolation ON {table}
            USING ({BYPASS} OR {COST_MODEL_SUBQUERY})
            WITH CHECK ({BYPASS} OR {COST_MODEL_SUBQUERY})
        """)

    _enable("formula_components")
    op.execute(f"""
        CREATE POLICY tenant_isolation ON formula_components
        USING ({BYPASS} OR {FORMULA_VERSION_SUBQUERY})
        WITH CHECK ({BYPASS} OR {FORMULA_VERSION_SUBQUERY})
    """)


def downgrade():
    for table in DIRECT_TABLES + ["cost_scenarios"] + TRANSITIVE_CM_TABLES + ["formula_components"]:
        _disable(table)
