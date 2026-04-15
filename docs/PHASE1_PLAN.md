# Phase 1 Implementation Plan

Customer-grade POC hardening before first customer signup. See `/home/alexis/costadvisor/DEPLOYMENT.md` for context — this is the detailed breakdown of Phase 1 of that runbook.

## Discovered constraints

1. Users belong to multiple teams. JWT carries only `user.id`; active `team_id` comes from request path/query. RLS GUC must be set after `require_team_access()` validates the team context per-request, not from the JWT.
2. Global reference tables stay global: `CommodityIndex`, `IndexValue`, `FxRate`, `ChemicalFamily` are read-shared by design. RLS applies only to genuinely tenant-scoped tables.
3. No tests exist at all — pytest must be set up from zero.
4. Frontend has no footer — new `Footer.jsx` required, not just two new routes.

## Tenant-scoped tables (RLS targets)

Direct `team_id`: Product, CostModel, Supplier, IndexOverride, TeamIndexSource, AuditLog, CostScenario (when `team_id IS NOT NULL`).

Transitive via `cost_model_id`: ActualPrice, ActualVolume.

## Workstreams

| # | Name | Effort | Depends on |
|---|---|---|---|
| W1 | Tenancy verification pass — `docs/tenancy_audit.md` | 0.5d | — |
| W2 | Complete audit log wiring | 0.5d | W1 |
| W3 | Postgres RLS backstop | 1d | W1 |
| W4 | Test infrastructure + tenancy/RLS/audit tests | 1d | W2, W3 |
| W5 | Rate limiting via slowapi | 0.5d | — |
| W6 | Account deletion (backend + UI) | 0.5d | — |
| W7 | Self-signup hardening | 0.25d | — |
| W8 | Footer + Privacy + Terms pages | 0.5d | — |
| W9 | Support email + Sentry user-context hooks | 0.25d | — |

**Sequential total: 5d. Realistic with parallelism: 3–4d.**

## Execution order

```
W1 → W2 → W4 → smoke test
      ↘    ↗
       W3
W5, W6, W7, W8, W9 in parallel with W3
```

## Per-workstream deliverables

### W1 — Tenancy verification pass
- `docs/tenancy_audit.md`: every route from every router, columns = route / model / scoping mechanism / reviewer note
- Line-by-line read of router bodies (explore-agent scan looked at signatures only)
- Audit Celery tasks under `backend/app/tasks/` — any that touch team-scoped models must accept/set team_id explicitly
- Fix commits for any leaks found

### W2 — Audit log completion
- Add `log_event()` to: `cost_models.py` (POST/PUT/DELETE + formula versions), `volumes.py` (uploads + mutations), `teams.py` (invite, remove member)
- Confirm coverage in `prices.py`, `suppliers.py`, `products.py`

### W3 — Postgres RLS backstop
- `backend/app/db.py`: `current_team_id_var: ContextVar`, `before_cursor_execute` listener issuing `SET LOCAL app.current_team_id`
- `require_team_access()` / `require_model_access()` set the ContextVar after validation
- Alembic migration `enable_rls.py`: `ENABLE ROW LEVEL SECURITY` + `CREATE POLICY tenant_isolation` on each tenant-scoped table
- Transitive policies on `ActualPrice` / `ActualVolume` via `cost_model_id IN (...)` subquery
- `costadvisor_admin` role with `BYPASSRLS`; super-admin routes use `SET LOCAL ROLE`
- Celery tasks that touch tenant data set GUC explicitly
- Local verify: two `psql` sessions with different GUC, counts match per-team data

### W4 — Test infrastructure + tests
- Add `pytest`, `pytest-asyncio`, `httpx`, `pytest-postgresql` to `requirements-dev.txt`
- `backend/pytest.ini`, `backend/tests/conftest.py` with fixtures: `db`, `client`, `user_factory`, `tenant_a`, `tenant_b`
- `tests/test_tenancy.py`: parametrized cross-tenant test, every model-id-bearing route, assert 404 (not 403)
- `tests/test_audit_log.py`: each write endpoint → assert `AuditLog` row with expected `event_type`
- `tests/test_rls.py`: direct DB test — non-bypass role + GUC, cross-team returns zero, no GUC returns zero
- `pytest` green locally before declaring W4 done

### W5 — Rate limiting
- Add `slowapi` to `requirements.txt`, Redis-backed via existing `REDIS_URL`
- Decorate: `auth.py` callbacks `10/min` per IP; LLM endpoints (`costing.py` /brief, `ai.py` /ask) `30/min` per user; default `120/min` per user
- Frontend `api.js`: catch 429, show toast with `Retry-After` seconds
- `tests/test_rate_limiting.py`

### W6 — Account deletion
- Add `deleted_at` column to User (Alembic migration)
- `backend/app/routers/account.py`: `DELETE /api/account`
  - Soft-delete user
  - Sole-member teams: hard-delete + cascade
  - Shared teams: remove membership only
  - Log deletion to AuditLog
  - Clear cookie
- Verify/add `ON DELETE CASCADE` on all team_id columns
- `frontend/src/pages/Settings.jsx`: Account section + typed-confirmation modal

### W7 — Self-signup hardening
- `ALLOW_SIGNUP` env gate in `auth.py` callback
- Document behaviour on email reuse after soft-delete (default: fresh row, since Google controls the identifier)
- "By signing in you agree to [Terms](/terms) and [Privacy](/privacy)" on login screen

### W8 — Footer + legal
- `frontend/src/components/Footer.jsx`: copyright, `/privacy`, `/terms`, `mailto:alexis@staminachem.com`
- Mount in root layout
- `frontend/src/pages/Privacy.jsx` (~300 words, honest plain English)
- `frontend/src/pages/Terms.jsx` (~300 words, as-is / no warranty / you own your data / jurisdiction TBD)
- Routes reachable when logged out

### W9 — Support email + Sentry user-context
- Backend middleware setting Sentry user context (email+id) — gated on `SENTRY_DSN` being set (Phase 13 wires the DSN)
- Frontend axios interceptor same
- Generic 500 page showing support email
- Email visible in footer, login, 500 page

## Local Phase 1 smoke test (exit criteria)

1. `pytest` all green
2. Two browsers, two Google accounts: cross-tenant requests 404
3. Hammer login 15× — 429 around the 10th
4. Delete-account flow end-to-end on throwaway account
5. Privacy/Terms load while logged out
6. Footer visible on every page with support email
