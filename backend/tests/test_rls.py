"""Direct DB-level RLS tests. Proves Postgres policies filter correctly
regardless of app-layer checks, so a future query bug can't leak data."""
from __future__ import annotations

import uuid

import pytest

from app.database import SessionLocal, bypass_rls_var, current_user_id_var
from app.models.product import Product


def _make_product(db, team_id, created_by, name) -> Product:
    p = Product(
        id=uuid.uuid4(),
        team_id=team_id,
        created_by=created_by,
        name=name,
    )
    db.add(p)
    db.commit()
    return p


def test_no_guc_returns_zero_rows(tenant_a, db):
    _make_product(db, tenant_a["team_id"], tenant_a["user_id"], "a-widget")

    s = SessionLocal()
    current_user_id_var.set(None)
    bypass_rls_var.set(False)
    try:
        assert s.query(Product).count() == 0
    finally:
        s.close()


def test_user_sees_only_their_team(tenant_a, tenant_b, db):
    _make_product(db, tenant_a["team_id"], tenant_a["user_id"], "a-widget")
    _make_product(db, tenant_b["team_id"], tenant_b["user_id"], "b-widget")

    s = SessionLocal()
    bypass_rls_var.set(False)
    current_user_id_var.set(str(tenant_a["user_id"]))
    try:
        names = {p.name for p in s.query(Product).all()}
        assert names == {"a-widget"}
    finally:
        s.close()


def test_bypass_sees_everything(tenant_a, tenant_b, db):
    _make_product(db, tenant_a["team_id"], tenant_a["user_id"], "a-widget")
    _make_product(db, tenant_b["team_id"], tenant_b["user_id"], "b-widget")

    s = SessionLocal()
    bypass_rls_var.set(True)
    try:
        names = {p.name for p in s.query(Product).all()}
        assert {"a-widget", "b-widget"}.issubset(names)
    finally:
        s.close()
