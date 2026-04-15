# Tenancy Audit

Line-by-line audit of every route that touches tenant data. Produced during Phase 1 / W1. See `docs/PHASE1_PLAN.md`.

## Legend

- `require_team_access(team_id)` — helper validates `TeamMembership(user_id, team_id)` before query
- `require_model_access(cm)` — same check, using `cm.team_id`
- `require_team_role(team_id, [roles])` — membership **plus** role check
- `global-by-design: <reason>` — reference data, OK to leave unscoped
- `super-admin only` — guarded by `require_super_admin`
- `LEAK` — query touches tenant-scoped model without validating user membership
- `FIXED (commit:<sha>)` — leak closed

## Helpers (single source of truth)

Currently duplicated across routers. W1 closes the holes in-place; W3 consolidates + adds the RLS GUC set.

- `require_super_admin` — `admin.py:18`; checks `User.is_super_admin` bool
- `require_team_access` — duplicated in `cost_models.py:29`, `products.py:16`, `suppliers.py:22`; queries `TeamMembership` by (user_id, team_id). Does **not** return membership; does **not** check role.
- `require_model_access` — duplicated in `costing.py:26`, `prices.py:18`, `volumes.py:18`; same check against `cm.team_id`.
- `require_team_role` — `teams.py:14`; checks membership **and** role within allowed list.
- `get_current_user` — `auth.py:34`; decodes JWT from `ca_token` cookie. JWT carries `user.id` only — **no team_id**.

---

## Summary of leaks found

| Router | Endpoint | Severity | Status |
|---|---|---|---|
| `indexes.py:41` | `GET /values` | High — reads any team's index view | FIXED (W1) |

**Fix pattern:** A local `require_team_access(db, user, team_id)` helper was added to `indexes.py` and `scenarios.py` (mirroring the pattern already used in `cost_models.py` / `products.py` / `suppliers.py`). Every endpoint now calls it before any DB read or write. Routes that resolve a resource by id first (`DELETE /overrides/{id}`, `DELETE /sources/{id}`, `POST /sources/{id}/scrape-now`) now look up the record and validate against `record.team_id`. `GET /` (list commodities) and `GET /detect-source` are now gated behind `get_current_user` (both were previously unauthenticated).
| `indexes.py:126` | `POST /overrides` | High — writes to any team | FIXED (W1) |
| `indexes.py:181` | `PUT /overrides/cell` | High — writes to any team | FIXED (W1) |
| `indexes.py:254` | `PUT /overrides/bulk` | High — writes to any team | FIXED (W1) |
| `indexes.py:310` | `DELETE /overrides/bulk` | High — wipes any team's overrides | FIXED (W1) |
| `indexes.py:343` | `DELETE /overrides/{id}` | High — deletes by id with no team check | FIXED (W1) |
| `indexes.py:360` | `GET /sources` | Medium — reads any team's source list | FIXED (W1) |
| `indexes.py:413` | `POST /sources` | High — creates sources in any team, auto-scrapes | FIXED (W1) |
| `indexes.py:487` | `DELETE /sources/{id}` | High — deletes by id with no team check | FIXED (W1) |
| `indexes.py:514` | `POST /sources/{id}/scrape-now` | High — triggers scrape on any team's source | FIXED (W1) |
| `indexes.py:662` | `GET /filter-options` | Medium — reads any team's products/suppliers | FIXED (W1) |
| `indexes.py:704` | `GET /{id}/impact` | Medium — reads any team's portfolio exposure | FIXED (W1) |
| `scenarios.py:15` | `GET /` | Medium — reads any team's scenarios | FIXED (W1) |
| `scenarios.py:29` | `POST /` | High — writes to any team | FIXED (W1) |
| `scenarios.py:49` | `DELETE /{id}` | High — deletes by id with no team check | FIXED (W1) |

No leaks found in: `admin.py`, `ai.py`, `audit.py`, `auth.py`, `chemical_families.py`, `cost_models.py`, `costing.py`, `fx_rates.py`, `portfolio.py`, `prices.py`, `products.py`, `suppliers.py`, `teams.py`, `volumes.py`.

## Celery task notes

- `scrape_indexes.py:scrape_team_sources` loops all `TeamIndexSource` rows across all teams. This is **by design** — it's a scheduled system task. No user context exists. Safe: writes only to `IndexOverride` scoped by `source.team_id`, which is already bound to the source row. W3 RLS: task must explicitly `SET app.current_team_id` per source or use the BYPASSRLS role.

---

## Router-by-router

### admin.py

| Route | Scoping | Notes |
|---|---|---|
| `GET /users` (42) | super-admin | Lists all users + memberships |
| `PUT /users/{id}` (71) | super-admin | Mutates `is_super_admin` — no audit log (W2) |
| `POST /impersonate/{id}` (92) | super-admin | Sets admin_token + target_token cookies — no audit log (W2) |
| `POST /stop-impersonate` (144) | cookie-only | Validates `ca_admin_token` JWT; acceptable — it's the restore-session path |
| `POST /users/{id}/set-team` (174) | super-admin | Emits audit log ✓ |
| `POST /users/{id}/add-team` (203) | super-admin | Emits audit log ✓ |
| `DELETE /users/{id}/teams/{tid}` (234) | super-admin | Emits audit log ✓ |
| `GET /teams` (255) | super-admin | Lists all teams |

### ai.py

| Route | Scoping | Notes |
|---|---|---|
| `POST /index-analysis` (58) | global-by-design: stateless | Caller supplies commodity_name/periods/impacts; no DB read of tenant data |

### audit.py

| Route | Scoping | Notes |
|---|---|---|
| `GET /` (15) | inline team check (26–32) | Super-admin can view any team; otherwise membership required ✓ |

### auth.py

| Route | Scoping | Notes |
|---|---|---|
| `GET /login` (55) | public | OAuth initiation |
| `GET /callback` (68) | public | First-login creates default team with user as owner (107) |
| `GET /me` (135) | user | Returns current user + memberships |
| `POST /logout` (141) | public | Clears cookie — fine, must work if session is stale |

### chemical_families.py

| Route | Scoping | Notes |
|---|---|---|
| `GET /` (18) | global-by-design | Reference data |
| `POST /` (26) | super-admin | Creates global family — no audit log (W2) |
| `DELETE /{id}` (43) | super-admin | — no audit log (W2) |

### cost_models.py

All routes use `require_team_access(cm.team_id)` or validate on POST. Audit log coverage partial — W2 will add missing calls.

| Route | Scoping | Notes |
|---|---|---|
| `GET /` (48) | `require_team_access(team_id)` | ✓ |
| `POST /` (59) | `require_team_access(team_id)` | Verifies `product.team_id == team_id` (72); emits audit log ✓ |
| `GET /{id}` (117) | `require_team_access(cm.team_id)` | ✓ |
| `PUT /{id}` (130) | `require_team_access(cm.team_id)` | Emits audit log ✓ |
| `DELETE /{id}` (157) | `require_team_access(cm.team_id)` | Emits audit log ✓ |
| `POST /{id}/renegotiate` (175) | `require_team_access(cm.team_id)` | Emits audit log ✓ |
| `GET /{id}/versions` (258) | `require_team_access(cm.team_id)` | ✓ |
| `DELETE /{id}/versions/{vid}` (276) | `require_team_access(cm.team_id)` | Emits audit log ✓ |
| `POST /{id}/clone` (309) | `require_team_access(original.team_id)` | No audit log — W2 |

### costing.py

All routes use `require_model_access(cm)`.

| Route | Scoping | Notes |
|---|---|---|
| `POST /should-cost` (35) | `require_model_access(cm)` | ✓ |
| `POST /evolution` (54) | `require_model_access(cm)` | ✓ |
| `POST /squeeze` (68) | `require_model_access(cm)` | ✓ |
| `POST /brief` (82) | `require_model_access(cm)` | ✓ |
| `POST /price-change` (112) | `require_model_access(cm)` | ✓ |

### fx_rates.py

| Route | Scoping | Notes |
|---|---|---|
| `GET /` (19) | global-by-design | Global reference data |
| `POST /upload` (34) | super-admin | — no audit log (W2) |

### indexes.py — LEAKY

| Route | Scoping | Notes |
|---|---|---|
| `GET /` (36) | **public** | No auth at all — list of tracked commodities. Low risk, but W1 gates behind `get_current_user`. |
| `GET /values` (41) | **LEAK** | `team_id` accepted without membership check. FIXED (W1). |
| `POST /upload` (77) | super-admin | Writes to global `IndexValue`. Emits audit log with placeholder team_id (120). |
| `POST /overrides` (126) | **LEAK** | FIXED (W1). |
| `PUT /overrides/cell` (181) | **LEAK** | FIXED (W1). |
| `PUT /overrides/bulk` (254) | **LEAK** | FIXED (W1). |
| `DELETE /overrides/bulk` (310) | **LEAK** | FIXED (W1). |
| `DELETE /overrides/{id}` (343) | **LEAK** | Deletes by id only — resolve override, check `override.team_id` membership. FIXED (W1). No audit log (W2). |
| `GET /sources` (360) | **LEAK** | FIXED (W1). |
| `POST /sources` (413) | **LEAK** | Auto-triggers scrape — worse leak because it writes. FIXED (W1). |
| `DELETE /sources/{id}` (487) | **LEAK** | FIXED (W1). |
| `GET /detect-source` (507) | **public** | Utility (URL pattern sniffing) — no DB touch. W1 gates behind `get_current_user` as baseline. |
| `POST /sources/{id}/scrape-now` (514) | **LEAK** | FIXED (W1). |
| `GET /filter-options` (662) | **LEAK** | `team_id` filters, but no membership check — any user gets any team's product/supplier list. FIXED (W1). |
| `GET /{cid}/impact` (704) | **LEAK** | FIXED (W1). |

### portfolio.py

| Route | Scoping | Notes |
|---|---|---|
| `GET /summary` (48) | inline team check (55–61) | Super-admin bypass + membership check ✓ |

### prices.py

| Route | Scoping | Notes |
|---|---|---|
| `GET /{cmid}` (27) | `require_model_access(cm)` | ✓ |
| `POST /{cmid}/upload` (46) | `require_model_access(cm)` | Emits audit log ✓. Double `commit()` (86, 89) — harmless but redundant. |
| `PUT /{cmid}/{y}/{q}` (93) | `require_model_access(cm)` | No audit log (W2) |
| `DELETE /{cmid}/{y}/{q}` (131) | `require_model_access(cm)` | No audit log (W2) |

### products.py

| Route | Scoping | Notes |
|---|---|---|
| `GET /` (25) | `require_team_access(team_id)` | ✓ |
| `POST /` (35) | `require_team_access(team_id)` | Emits audit log ✓ |
| `GET /{id}` (61) | `require_team_access(product.team_id)` | ✓ |
| `PUT /{id}` (74) | `require_team_access(product.team_id)` | Emits audit log ✓ |
| `DELETE /{id}` (99) | `require_team_access(product.team_id)` | Emits audit log ✓ |

### scenarios.py — LEAKY

| Route | Scoping | Notes |
|---|---|---|
| `GET /` (15) | **LEAK** | `team_id` filter without membership check. FIXED (W1). |
| `POST /` (29) | **LEAK** | Writes to arbitrary team. FIXED (W1). No audit log (W2). |
| `DELETE /{id}` (49) | **LEAK** | Deletes by id only. FIXED (W1). No audit log (W2). |

### suppliers.py

| Route | Scoping | Notes |
|---|---|---|
| `GET /` (31) | `require_team_access(team_id)` | ✓ |
| `POST /` (41) | `require_team_access(team_id)` | Emits audit log ✓ |
| `PUT /{id}` (62) | `require_team_access(supplier.team_id)` | Emits audit log ✓ |
| `GET /{id}/purchase-history` (83) | `require_team_access(supplier.team_id)` | ✓ |
| `GET /{id}/export-excel` (170) | `require_team_access(supplier.team_id)` | No audit log (consider — exports can exfiltrate; W2 adds read-audit for exports) |
| `DELETE /{id}` (421) | `require_team_access(supplier.team_id)` | Emits audit log ✓ |

### teams.py

| Route | Scoping | Notes |
|---|---|---|
| `POST /` (25) | user | Creates own team, adds as owner |
| `GET /` (41) | user | Returns only memberships ✓ |
| `GET /{id}` (50) | `require_team_role(any)` | ✓ |
| `GET /{id}/members` (63) | `require_team_role(any)` | ✓ |
| `POST /{id}/invite` (84) | `require_team_role(owner/admin)` | No audit log (W2) |
| `PATCH /{id}/members/{uid}` (109) | `require_team_role(owner)` | No audit log (W2) |
| `DELETE /{id}/members/{uid}` (131) | `require_team_role(owner/admin)` | Prevents owner removal ✓. No audit log (W2) |

### volumes.py

| Route | Scoping | Notes |
|---|---|---|
| `GET /{cmid}` (27) | `require_model_access(cm)` | ✓ |
| `POST /{cmid}/upload` (45) | `require_model_access(cm)` | Emits audit log ✓. Double `commit()` (87, 90) — harmless. |
| `PUT /{cmid}/{y}/{q}` (94) | `require_model_access(cm)` | No audit log (W2) |
| `DELETE /{cmid}/{y}/{q}` (134) | `require_model_access(cm)` | No audit log (W2) |

---

## Observations for later phases

1. **Helpers are duplicated five ways.** W3 consolidates into `backend/app/deps.py` while adding the RLS GUC-set. Not done in W1 — minimizes diff surface for the fix commits.
2. **JWT carries no team_id.** Correct: users belong to multiple teams, active team is per-request. RLS GUC in W3 is set after team access is validated, inside the shared helper.
3. **Resource-by-id then team-check** is the standard pattern (e.g. `GET /cost-models/{id}`). Leaks team membership existence via 404-vs-403 timing but not data. RLS will close this residual.
4. **Global-by-design tables** (`CommodityIndex`, `IndexValue`, `FxRate`, `ChemicalFamily`) are correctly unscoped. RLS won't apply to them.
5. **Super-admin write endpoints** on global tables (`chemical_families` POST/DELETE, `fx_rates` POST, `indexes` POST /upload, `admin` user mutations, `admin` impersonate) remain unaudited after W2. `AuditLog.team_id` is NOT NULL with FK to `teams`, and the existing `indexes` upload uses a zeroes-UUID placeholder that only works if a matching team row exists. Closing this hole requires either a migration to make `team_id` nullable or seeding a reserved system team. Deferred to post-Phase-1 — the omissions are all super-admin actions, and super-admin is one person (you) in the POC.

## W4 — Test suite

14 tests, all passing:
- `tests/test_rls.py` (3) — proves Postgres policies filter correctly at the DB level, independent of app code
- `tests/test_tenancy.py` (8) — cross-tenant request rejection (403) on all the routes that were leaky in W1
- `tests/test_audit_log.py` (2) — write endpoints emit `AuditLog` with the expected `event_type`
- `tests/test_rate_limiting.py` (1) — `/auth/login` 429s after 10 requests/min

Fixtures in `tests/conftest.py` create fresh users + personal teams per test (random UUIDs), authenticate via minted JWTs in a cookie-backed `TestClient`, and hard-delete the team (FK CASCADE) in teardown. RLS is live during tests — fixtures `bypass_rls_var.set(True)` for setup/teardown only.

## W3 — RLS backstop

Enabled Postgres row-level security on every tenant-scoped table with `FORCE ROW LEVEL SECURITY` (no bypass via table ownership). Identity is established by a session GUC `app.current_user_id`, set by `get_current_user` after JWT validation. Policies join through `team_memberships` so a row is visible iff the caller shares a team with it. `app.bypass_rls = 'on'` is the only escape and is set by: (1) Celery scheduled tasks with no user context, (2) Alembic migrations, (3) `get_current_user` itself during the initial user-row lookup, (4) super-admin requests.

**Tables covered:**
- Direct `team_id`: `products`, `suppliers`, `cost_models`, `index_overrides`, `team_index_sources`, `audit_logs`
- `cost_scenarios`: `is_system` scenarios always visible, team scenarios scoped by membership
- Transitive via `cost_model_id`: `formula_versions`, `actual_prices`, `actual_volumes`
- Transitive via `formula_version_id` → `cost_model_id`: `formula_components`

**Intentionally global (no RLS):** `users`, `teams`, `team_memberships`, `chemical_families`, `commodity_indexes`, `index_values`, `fx_rates`. App-layer scoping handles these.

**Smoke test (local):**
- No GUC, no bypass → 0 rows on all RLS tables (safe default)
- User in team A → sees only team A's rows
- User in team B (different team, no shared data) → sees 0 rows
- Bypass on → sees everything

Files changed: `app/database.py` (ContextVars + `after_begin` listener), `app/routers/auth.py` (set GUC in `get_current_user`), `app/tasks/scrape_indexes.py` (bypass for system tasks), `alembic/env.py` (bypass for migrations), `alembic/versions/h8i9j0k1l2m3_enable_rls.py` (the migration).

## W2 — audit log additions

Added `log_event()` calls to the following write endpoints:

- `cost_models.py` — `POST /{id}/clone` (event: `clone`)
- `prices.py` — `PUT /{cmid}/{y}/{q}` (event: `update`), `DELETE /{cmid}/{y}/{q}` (event: `delete`)
- `volumes.py` — `PUT /{cmid}/{y}/{q}` (event: `update`), `DELETE /{cmid}/{y}/{q}` (event: `delete`)
- `teams.py` — `POST /{id}/invite` (event: `invite`), `PATCH /{id}/members/{uid}` (event: `update_role`), `DELETE /{id}/members/{uid}` (event: `remove`)
- `scenarios.py` — `POST /` (event: `create`), `DELETE /{id}` (event: `delete`, only for team-scoped)
- `indexes.py` — `DELETE /overrides/{id}` (event: `delete`), `_scrape_and_replace_overrides` (event: `scrape`)

All capture meaningful `previous_value` / `new_value` payloads so audit consumers can reconstruct what changed.
