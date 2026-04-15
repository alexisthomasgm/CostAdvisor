# CostAdvisor — Deployment Runbook (Customer-Grade POC)

This is the complete walkthrough from your laptop to a hosted website that real customers can sign up for. Follow it top to bottom in order. Every step that requires your hands on a keyboard or a console is here. Any step marked with a clipboard 📋 is something only you can do (signup, click, payment, OAuth console).

This is **POC-grade**, not enterprise. It is built to be safely usable by a small number of paying or trial customers. It is not SOC2, not multi-region, not zero-downtime. The deltas from a real production system are listed at the bottom.

---

## Architecture

```
                       ┌─────────────────────────┐
                       │  Cloudflare (DNS+CDN)   │
                       └─┬───────────────────┬───┘
                         │                   │
       yourdomain.com    │                   │   api.yourdomain.com
                         ▼                   ▼
              ┌────────────────────┐  ┌──────────────────────┐
              │  Cloudflare Pages  │  │   Railway: API svc   │
              │  (React SPA)       │  │   FastAPI / uvicorn  │
              └────────────────────┘  └──┬─────────────┬─────┘
                                         │             │
                              ┌──────────▼──┐    ┌─────▼─────────┐
                              │  Postgres   │    │     Redis     │
                              │ (Railway)   │    │  (Railway)    │
                              └─────┬───────┘    └─────▲─────────┘
                                    │                  │
                                    │       ┌──────────┴──────────┐
                                    │       │ Railway: Worker svc │
                                    │       │ celery worker+beat  │
                                    │       └─────────────────────┘
                                    │
                              ┌─────▼───────────┐
                              │  Backblaze B2   │
                              │  Nightly dumps  │
                              └─────────────────┘

      ┌────────────────────────────────────────────────────────┐
      │  Tailscale tailnet                                     │
      │                                                        │
      │   Railway api+worker  ◄──────►  Hetzner CCX13          │
      │                                  Ollama llama3.2:3b    │
      └────────────────────────────────────────────────────────┘

  Sentry (errors) + UptimeRobot (health) observe both Railway services.
```

**Cost target:** ~$30–45/mo all-in. Breakdown:
- Railway (API + Worker + Postgres + Redis): ~$10–20
- Hetzner CCX13 (Ollama): ~$13
- Backblaze B2 (backups): <$1
- Cloudflare domain: ~$10/yr
- Sentry, UptimeRobot, Tailscale: free hobby tiers

---

## What's already done in the codebase

These changes were made during deployment prep — you don't need to redo them:

### Code fixes
- `backend/app/config.py` — added `environment` and `llm_enabled` settings
- `backend/app/routers/auth.py` — login cookie now uses `secure=True`/`samesite=none` in production
- `backend/app/routers/admin.py` — same fix for impersonation cookies
- `backend/app/services/ollama.py` — respects `LLM_ENABLED=false` (cache-only mode, kept as a fallback knob)
- `backend/celeryconfig.py` — fixed beat schedule to use proper `crontab()`
- `backend/app/tasks/__init__.py` — added `autodiscover_tasks` so the worker finds task modules
- `backend/alembic.ini` — removed hardcoded dev DB URL
- `frontend/src/api.js` — `baseURL` now reads `VITE_API_BASE_URL` env var

### Files created
- `backend/Dockerfile` — production-ready, honors Railway's `$PORT`, runs as non-root
- `backend/.dockerignore` — keeps secrets and venv out of the image
- `backend/.env.example` — sanitized template
- `frontend/.env.example` — documents `VITE_API_BASE_URL`
- `frontend/public/_redirects` — Cloudflare Pages SPA fallback
- `.gitignore` (repo root)

### What's NOT yet done — built in Phase 1 below
- Tenancy audit + RLS policies + cross-tenant tests
- Account deletion endpoint
- Audit-log enforcement on writes
- Rate limiting
- Privacy policy + Terms pages, support email wiring
- New-user provisioning hardening on first Google login

---

## Accounts you need (one-time setup)

📋 Create accounts at all of these before starting:

| Service | Used for | Cost |
|---|---|---|
| **GitHub** | Source repo (private) | Free |
| **Cloudflare** | DNS, domain, Pages | Free, ~$10/yr for the domain |
| **Railway** | API, Worker, Postgres, Redis | ~$10–20/mo |
| **Hetzner Cloud** | Ollama VM (CCX13) | ~$13/mo |
| **Tailscale** | Private mesh between Railway and Hetzner | Free (hobby tier ≤3 users, 100 devices) |
| **Backblaze B2** | Encrypted off-site backups | <$1/mo for this volume |
| **Sentry** | Error tracking | Free hobby tier |
| **UptimeRobot** | Health pings | Free tier (5-min interval, 50 monitors) |
| **Google Cloud Console** | OAuth credentials | Free, you already have this |

---

## Phase 0 — Local sanity check (10 min)

📋 Verify the local app still runs after the prep work.

```bash
cd /home/alexis/costadvisor

pg_isready
redis-cli ping   # should print PONG

cd backend
source venv/bin/activate
alembic upgrade head

cd ..
./start.sh
```

**Verify:**
- `http://localhost:8000/health` returns `{"status":"ok"}`
- `http://localhost:8000/docs` loads
- `http://localhost:5173` loads
- Google OAuth login works end-to-end
- You see your data

If anything fails here, fix it before proceeding.

---

## Phase 1 — Code work for customer-grade (1–2 days)

📋 This is the single biggest delta from the old demo plan. None of this can be deferred without exposing customer data. Do it before touching any deploy infra. Each item is a separate commit.

### 1a. Tenancy audit (read-the-code work)

Walk every file under `backend/app/routers/` and `backend/app/services/`. For each function that reads or writes a model with a `team_id` or `user_id` column, confirm the query filters by the current user's team. Make a checklist file as you go (`docs/tenancy_audit.md`, gitignored or kept) and tick off each route.

What to look for:
- `db.query(Model).filter(Model.id == ...)` with **no** `team_id` filter — this is the bug pattern
- `.all()` calls that return everything in a table
- Joins where the join condition crosses tenant boundaries
- Background tasks (Celery) that loop over models without scoping — these are easy to miss

Fix every leak you find. This is not optional.

### 1b. Postgres Row-Level Security as backstop

Even after a clean audit, add RLS policies so a future query bug can't accidentally leak across tenants. The database physically refuses.

Create `backend/alembic/versions/<timestamp>_enable_rls.py` that:
1. Enables RLS on every team-scoped table (`ALTER TABLE foo ENABLE ROW LEVEL SECURITY`)
2. Creates a policy per table: `USING (team_id = current_setting('app.current_team_id')::uuid)`
3. Adds a SQLAlchemy `before_cursor_execute` event listener in `backend/app/db.py` that issues `SET LOCAL app.current_team_id = '<uuid>'` at the start of every request, sourced from the authenticated user's team.

Tables likely needing RLS (verify against your schema): `cost_models`, `cost_periods`, `purchases`, `formulas`, `audit_log`, anything else with `team_id`. Indexes (the licensed shared data) are global — no RLS, just read-only for non-admin users.

### 1c. Cross-tenant integration tests

Add `backend/tests/test_tenancy.py`. Test pattern:
1. Create Tenant A user, create a `cost_model` owned by A
2. Create Tenant B user, log in as B
3. Hit every read/write endpoint that takes a model ID, passing A's model ID
4. Assert 404 (preferred — don't leak existence) on every one

Run in CI before any deploy. If you don't have CI yet, run them locally before each `git push`.

### 1d. Self-signup hardening

Your Google OAuth handles login for existing users. Verify the **first-time** flow:
- New Google user lands on `/auth/callback` → user row created → default team created (just for them) → logged in
- The default team should have them as the sole owner. No silent membership in someone else's team.
- If you want to gate signup (e.g., invite-only later), add an `allow_signup` flag now in `config.py` and check it in `auth.py`. Default `true` for the POC.

### 1e. Account deletion endpoint

GDPR baseline plus general hygiene. Add `DELETE /api/account` that:
- Soft-deletes the user (sets `deleted_at`)
- Hard-deletes their team's data **if they are the sole member** (cost models, periods, purchases, formulas, etc.)
- If they are a member of a team with others, just removes them from the team
- Logs the deletion to `audit_log`
- Invalidates their session

UI: a "Delete account" button in account settings, behind a typed-confirmation modal.

### 1f. Audit log enforcement

You already have an `audit_log` model. Walk the same routers from 1a and confirm every **write** (POST/PUT/PATCH/DELETE) on tenant data calls `log_event(user_id, team_id, action, resource_type, resource_id, metadata)`. Add the calls where missing.

### 1g. Rate limiting

Add `slowapi` (FastAPI-friendly Redis-backed rate limiter). Limits to apply:
- `/auth/*` — 10/min per IP (brute-force defense)
- LLM-backed endpoints (brief generation, AI analysis) — 30/min per user (cost defense)
- Everything else — 120/min per user (sanity ceiling)

Returns 429 with a `Retry-After` header. Frontend should show a friendly toast on 429.

### 1h. Privacy policy + Terms pages

Two static React routes: `/privacy` and `/terms`. Linked from the footer and the signup screen ("By signing in you agree to ..."). Keep them short and honest. Cover at minimum:
- What data you collect (email, OAuth subject, anything they enter)
- That you process it on Railway (US) and a Hetzner box (Germany or wherever)
- That you back up to Backblaze B2 encrypted
- That they can delete their account at any time (link to the flow from 1e)
- Support contact: **alexis@staminachem.com**

You don't need a lawyer for a POC, but write them yourself — don't paste a generator template you haven't read.

### 1i. Support email wiring

- Footer: `Questions? alexis@staminachem.com`
- Generic error page: same email
- 500 errors logged to Sentry (set up in Phase 13) get tagged with the user's email (so when someone emails support you can find their session)
- Set up an inbox/forwarding for `alexis@staminachem.com` if you haven't already

### 1j. Commit, push, run the tenancy tests

```bash
cd /home/alexis/costadvisor
cd backend && pytest tests/test_tenancy.py -v
```

All green before you continue. If anything fails, the leak is real — fix it now.

---

## Phase 2 — Git + GitHub (5 min)

📋 The repo is currently not under version control.

```bash
cd /home/alexis/costadvisor

git init
git branch -M main
git status
```

**The following files should NOT appear in untracked files:**
- `backend/.env`
- `backend/venv/`
- `frontend/node_modules/`
- `backend/__pycache__/` or any `*.pyc`
- `backend/celerybeat-schedule`

If any show up, fix `.gitignore` before committing.

```bash
git add .
git status   # one more sanity check
git commit -m "Initial commit: customer-grade POC ready"
```

📋 On GitHub: create a **private** repo named `costadvisor`. Do NOT initialize with README/license/.gitignore.

```bash
git remote add origin git@github.com:YOURNAME/costadvisor.git
git push -u origin main
```

**Verify on GitHub** that no `.env` is visible.

---

## Phase 3 — Domain (parallel with Phase 4)

📋 Two options:

**Option A — Cloudflare Registrar.** Cheapest, no markup. Dashboard → Domain Registration → Register Domains → buy. Auto-creates the DNS zone.

**Option B — Domain elsewhere.** Add it to Cloudflare: Dashboard → Add a Site → Free plan → copy nameservers → change them at your current registrar. 5–60 min propagation.

Pick the subdomain plan now:
- Frontend: `https://yourdomain.com`
- API: `https://api.yourdomain.com`

Write these down. They go into Railway, Cloudflare Pages, and Google OAuth.

---

## Phase 4 — Hetzner: Ollama box (20 min)

📋 The LLM runs on a private VM, reachable from Railway only over Tailscale. Customers' data never leaves your perimeter.

### 4a. Provision the VM

1. Hetzner Cloud Console → New Project (`costadvisor`) → New Server
2. **Location:** pick the same region as your Railway deployment (Railway is US-East by default → Hetzner Ashburn). Latency between API and LLM matters.
3. **Image:** Ubuntu 24.04
4. **Type:** CCX13 (2 dedicated vCPU, 8 GB RAM, ~$13/mo)
5. **SSH key:** add yours
6. **Name:** `ollama-1`
7. Create

### 4b. Install Ollama + Tailscale

SSH in:

```bash
ssh root@<vm-ip>

# Updates + basic hardening
apt update && apt upgrade -y
apt install -y ufw fail2ban
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw --force enable

# Ollama
curl -fsSL https://ollama.com/install.sh | sh
systemctl enable --now ollama

# Pull the model (will take a minute)
ollama pull llama3.2:3b

# Tailscale
curl -fsSL https://tailscale.com/install.sh | sh
tailscale up --ssh
# Follow the printed URL to authenticate against your Tailscale account
# Once joined, copy the Tailscale IP — looks like 100.x.y.z
tailscale ip -4
```

### 4c. Lock Ollama to Tailscale only

By default Ollama listens on `127.0.0.1:11434`. Bind it to the Tailscale interface so only Railway (also on the tailnet) can reach it.

```bash
mkdir -p /etc/systemd/system/ollama.service.d
cat > /etc/systemd/system/ollama.service.d/override.conf <<EOF
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
EOF

systemctl daemon-reload
systemctl restart ollama

# Confirm UFW still blocks 11434 from public — only Tailscale (which uses WireGuard, not 11434) can reach it
ufw status
```

**Verify from your laptop (also on the tailnet):**

```bash
curl http://<tailscale-ip>:11434/api/tags
# Should return JSON listing llama3.2:3b
```

Write down the Tailscale IP. It becomes `OLLAMA_URL` in Railway.

---

## Phase 5 — Railway: project + Postgres + Redis (5 min)

📋 In Railway:

1. **New Project → Empty Project**, name `costadvisor`
2. **+ New → Database → Add PostgreSQL**
3. **+ New → Database → Add Redis**

**Verify** both services have `DATABASE_URL` and `REDIS_URL` populated in their Variables tab. Don't touch them — referenced from API/Worker next.

---

## Phase 6 — Railway: API service (15 min)

📋 In the same Railway project:

1. **+ New → GitHub Repo → costadvisor**. Authorize Railway if prompted.
2. After it spins up: click the service → **Settings**
   - **Service Name:** `api`
   - **Root Directory:** `backend`
   - **Builder:** Dockerfile

### 6a. Tailscale on Railway

Railway services need to be on the tailnet to reach Ollama.

- In Tailscale admin → Settings → Auth Keys → Generate auth key → **Reusable: yes, Ephemeral: yes, Tagged: `tag:railway`** → copy the key
- In Railway api service Variables, add `TAILSCALE_AUTHKEY = <the key>`
- Edit `backend/Dockerfile` to install Tailscale and start it before uvicorn. Add this near the top of the runtime stage:

  ```dockerfile
  RUN curl -fsSL https://tailscale.com/install.sh | sh
  ```

  And replace the CMD with an entrypoint script that brings Tailscale up first:

  ```bash
  #!/bin/sh
  /usr/sbin/tailscaled --tun=userspace-networking --socks5-server=localhost:1055 &
  sleep 2
  tailscale up --authkey=$TAILSCALE_AUTHKEY --hostname=railway-api-$(hostname) --ephemeral
  exec uvicorn app.main:app --host 0.0.0.0 --port $PORT
  ```

  Commit this change and push.

### 6b. Variables

| Name | Value |
|---|---|
| `ENVIRONMENT` | `production` |
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` |
| `REDIS_URL` | `${{Redis.REDIS_URL}}` |
| `JWT_SECRET` | `python -c "import secrets; print(secrets.token_urlsafe(48))"` output |
| `JWT_ALGORITHM` | `HS256` |
| `JWT_EXPIRY_HOURS` | `72` |
| `GOOGLE_CLIENT_ID` | from Google Console (rotate from your dev value — see Phase 9) |
| `GOOGLE_CLIENT_SECRET` | from Google Console (rotated) |
| `APP_URL` | `https://yourdomain.com` |
| `API_URL` | `https://api.yourdomain.com` |
| `LLM_ENABLED` | `true` |
| `OLLAMA_URL` | `http://<hetzner-tailscale-ip>:11434` |
| `OLLAMA_MODEL` | `llama3.2:3b` |
| `OLLAMA_TIMEOUT` | `60` |
| `TAILSCALE_AUTHKEY` | (from Phase 6a) |
| `SENTRY_DSN` | (filled in Phase 13) |
| `SUPPORT_EMAIL` | `alexis@staminachem.com` |
| `ALLOW_SIGNUP` | `true` |

3. **Networking → Generate Domain**. Copy the `*.up.railway.app` URL.

### 6c. Verify

- Build logs show no errors, including the Tailscale install
- Deployment is "Active"
- `https://<railway-url>/health` returns `{"status":"ok"}`
- In Railway Logs, you should see Tailscale connect messages
- In Tailscale admin, you should see `railway-api-*` ephemeral nodes appear

If the API can't reach Ollama: `railway run curl http://<hetzner-tailscale-ip>:11434/api/tags` from your laptop with the project linked. Should return the model list. If it doesn't, Tailscale isn't up inside the container — check the entrypoint logs.

---

## Phase 7 — Railway: Worker service (10 min)

📋 Same image, different command, same Tailscale setup (the worker also needs Ollama for any background LLM tasks).

1. **+ New → GitHub Repo → costadvisor** (same repo, second service)
2. **Settings:**
   - **Service Name:** `worker`
   - **Root Directory:** `backend`
   - **Builder:** Dockerfile
   - **Custom Start Command:** `/app/entrypoint-worker.sh`
3. Create `backend/entrypoint-worker.sh`:

   ```bash
   #!/bin/sh
   /usr/sbin/tailscaled --tun=userspace-networking --socks5-server=localhost:1055 &
   sleep 2
   tailscale up --authkey=$TAILSCALE_AUTHKEY --hostname=railway-worker-$(hostname) --ephemeral
   exec celery -A app.tasks worker --beat --loglevel=info
   ```

   Make it executable, commit, push.
4. **Variables:** copy the entire api set via Raw Editor (worker needs all the same env).
5. **Networking:** no public domain.

**Verify:** worker logs show Celery banner + Tailscale up. No tracebacks.

---

## Phase 8 — Migrations + seed (10 min)

📋 The Postgres is empty. Public index data → seed directly on Railway, no laptop dump dance.

### Run migrations

In Railway, click the **api** service → **... menu → "Run a command"**:

```
alembic upgrade head
```

Verify migrations applied (Postgres → Data tab → tables exist, including the new RLS migration from Phase 1b).

### Seed the public index data

The seed scripts (`seed_jacobi.py`, `seed_jacobi_purchases.py`, `seed_jacobi_formulas.py`) read public data and populate indexes. Run them on Railway:

```
python seed_jacobi.py
python seed_jacobi_purchases.py
python seed_jacobi_formulas.py
```

(If any of these read a local Excel file, commit the file to the repo first — it's public per your call.)

**Verify:** Postgres → Data → indexes table has rows. Sign up as a test user later (Phase 14) and confirm you can see them.

---

## Phase 9 — Google OAuth: production credentials (10 min)

📋 The dev OAuth client has `localhost` redirect URIs. For production, **create a new client** rather than reusing dev — keeps prod secrets separate from a secret that's been on your laptop.

1. https://console.cloud.google.com/apis/credentials → **Create Credentials → OAuth client ID → Web application**
2. Name: `costadvisor-prod`
3. **Authorized JavaScript origins:**
   - `https://yourdomain.com`
4. **Authorized redirect URIs:**
   - `https://api.yourdomain.com/auth/callback`
5. Save → copy the new Client ID + Secret
6. Paste them into Railway api **and** worker Variables (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`)
7. Redeploy both services

OAuth changes can take up to 5 minutes to propagate.

**Keep the dev OAuth client.** Different ID, different redirect — they coexist fine.

---

## Phase 10 — Cloudflare Pages: frontend (10 min)

📋 In Cloudflare Dashboard:

1. **Workers & Pages → Create application → Pages → Connect to Git**
2. Authorize Cloudflare on GitHub
3. Pick `costadvisor`
4. Build:
   - **Project name:** `costadvisor`
   - **Production branch:** `main`
   - **Framework preset:** Vite
   - **Build command:** `npm run build`
   - **Build output directory:** `dist`
   - **Root directory (advanced):** `frontend`
5. **Environment variables:**
   - `VITE_API_BASE_URL` = `https://api.yourdomain.com`
   - `VITE_SENTRY_DSN` = (filled in Phase 13, frontend Sentry project)
6. **Save and Deploy**

**Verify:** the `*.pages.dev` URL loads. Don't try to log in yet — DNS first.

---

## Phase 11 — DNS wiring (5 min + propagation)

📋 In Cloudflare → DNS → Records:

| Type | Name | Target | Proxy |
|---|---|---|---|
| `CNAME` | `@` | `costadvisor.pages.dev` | Proxied |
| `CNAME` | `api` | `costadvisor-api-production-xxxx.up.railway.app` | Proxied |

Then in Railway → api service → **Settings → Networking → Custom Domain → Add `api.yourdomain.com`**. Railway issues a verification record if needed.

In Cloudflare Pages → project → Custom domains → Set up custom domain → `yourdomain.com` (auto-handled).

**Verify:**
- `https://yourdomain.com` loads
- `https://api.yourdomain.com/health` returns `{"status":"ok"}`
- Both have valid HTTPS

---

## Phase 12 — Backups: nightly dumps to Backblaze B2 (20 min)

📋 Railway backs up Postgres but you want your own copy you can restore from independently.

### 12a. Backblaze setup

1. B2 → Buckets → Create Bucket: `costadvisor-backups`, **private**
2. Lifecycle rules: keep newest 30 days, then delete
3. App Keys → Add a new application key, **scope: this bucket only**, capabilities: `listFiles`, `readFiles`, `writeFiles`. Copy `keyID` and `applicationKey`

### 12b. Backup task on the worker

Add `backend/app/tasks/backup.py`:

```python
import subprocess, datetime, os, gnupg
from celery import shared_task
import b2sdk.v2 as b2

@shared_task
def nightly_backup():
    ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    raw = f"/tmp/dump-{ts}.sql"
    enc = f"{raw}.gpg"

    subprocess.check_call([
        "pg_dump", os.environ["DATABASE_URL"],
        "--no-owner", "--no-acl", "-f", raw,
    ])

    gpg = gnupg.GPG()
    with open(raw, "rb") as f:
        gpg.encrypt_file(f, recipients=None, symmetric="AES256",
                         passphrase=os.environ["BACKUP_PASSPHRASE"],
                         output=enc)

    info = b2.InMemoryAccountInfo()
    api = b2.B2Api(info)
    api.authorize_account("production", os.environ["B2_KEY_ID"], os.environ["B2_APP_KEY"])
    bucket = api.get_bucket_by_name(os.environ["B2_BUCKET"])
    bucket.upload_local_file(local_file=enc, file_name=f"dump-{ts}.sql.gpg")

    os.remove(raw); os.remove(enc)
```

Schedule in `celeryconfig.py`:

```python
beat_schedule = {
    "nightly-backup": {
        "task": "app.tasks.backup.nightly_backup",
        "schedule": crontab(hour=3, minute=0),  # 03:00 UTC
    },
    # ... existing entries
}
```

Add to worker Variables in Railway:
- `B2_KEY_ID`, `B2_APP_KEY`, `B2_BUCKET=costadvisor-backups`
- `BACKUP_PASSPHRASE` — generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"`. **Store this passphrase in your password manager. Without it the backups are unrecoverable.**

Add `python-gnupg` and `b2sdk` to `requirements.txt`. The Dockerfile needs `gnupg` apt-installed.

### 12c. Test the restore — DO THIS, don't skip it

Untested backups are a story you tell yourself. The restore drill:

1. Wait for one nightly run, or trigger manually: `railway run python -c "from app.tasks.backup import nightly_backup; nightly_backup()"` on the worker
2. From your laptop, download the latest dump from B2
3. Decrypt: `gpg --decrypt --batch --passphrase $BACKUP_PASSPHRASE dump-*.sql.gpg > restored.sql`
4. Spin up a throwaway local Postgres (`docker run --rm -e POSTGRES_PASSWORD=x -p 5433:5432 postgres:16`)
5. `psql -h localhost -p 5433 -U postgres < restored.sql`
6. Connect, count rows on a few key tables, confirm they match prod

Schedule this drill on your calendar **monthly**.

---

## Phase 13 — Monitoring (15 min)

📋 Two pieces: errors (Sentry) and uptime (UptimeRobot).

### Sentry

1. sentry.io → New Project → Python/FastAPI → name `costadvisor-backend` → copy DSN
2. New Project → React → name `costadvisor-frontend` → copy DSN
3. Backend: `pip install sentry-sdk[fastapi]`, add to `backend/app/main.py` near startup:

   ```python
   import sentry_sdk
   if settings.environment == "production":
       sentry_sdk.init(
           dsn=settings.sentry_dsn,
           traces_sample_rate=0.1,
           send_default_pii=False,
       )
   ```

   Add a middleware that tags events with `user.email` (so you can find a customer's session when they email support).
4. Frontend: `npm i @sentry/react`, init in `frontend/src/main.jsx`. Skip in dev.
5. Set `SENTRY_DSN` (Railway) and `VITE_SENTRY_DSN` (Cloudflare Pages). Redeploy both.
6. Trigger a test error from each side. Confirm it shows up in Sentry within a minute.

### UptimeRobot

1. uptimerobot.com → Add New Monitor
2. Monitor type: HTTPS
3. URL: `https://api.yourdomain.com/health`
4. Interval: 5 min
5. Alert contact: your email + (optional) a phone for SMS
6. Add a second monitor for `https://yourdomain.com` (the frontend)

**Verify:** both monitors green within 10 min.

---

## Phase 14 — Production smoke test (20 min)

📋 Everything below must pass before you tell a single customer to sign up.

### 14a. Solo flow

1. Open `https://yourdomain.com` in a fresh incognito window
2. Click Login → Google consent → land back logged in
3. DevTools → Application → Cookies: `ca_token` on `api.yourdomain.com`, `Secure: true`, `SameSite: None`, `HttpOnly: true`
4. Refresh — still logged in
5. Click through every screen. Generate a brief, request an AI analysis on an index. **First-time generations should take ~5–15 sec on Hetzner CPU and return a real LLM narrative, not the rule-based fallback.** Subsequent identical requests should be near-instant (cache hit).

### 14b. Tenancy isolation (the critical one)

1. Sign up as a SECOND Google account in a separate incognito
2. As user B, try to load user A's resources by guessing IDs (or by reading them from A's URL bar)
3. Expected: 404 every time. **If you get user A's data back, stop and re-do Phase 1a/1b before going live.**

### 14c. Account deletion

1. As user B, hit the delete-account flow
2. Confirm: logged out, B's user row marked deleted, B's team/data gone (or membership removed if team had others)
3. Try to log back in as B — should work (creates a new account; the old one is tombstoned)

### 14d. Rate limiting

1. Hit the login endpoint 15 times in a minute from one IP
2. Expect 429 starting around the 10th
3. Same for an LLM endpoint after ~30 calls/min

### 14e. Backup + restore drill

Already covered in Phase 12c. Confirm you've actually run it before going live.

### 14f. Observability

- Trigger a 500 (e.g., POST garbage to a JSON endpoint) → confirm Sentry receives it
- Stop the api service in Railway briefly → confirm UptimeRobot alerts within 10 min → restart

---

## Phase 15 — Launch checklist + first-week ops (ongoing)

📋 Before announcing to your first customer:

- [ ] All of Phase 14 passed
- [ ] Privacy policy + Terms live and linked
- [ ] Support email forwards to a real inbox you check daily
- [ ] Backups have run at least once and you've decrypted one to confirm
- [ ] Sentry receiving events from both backend and frontend
- [ ] UptimeRobot has been green for 24h
- [ ] Secrets in your password manager: `JWT_SECRET`, `GOOGLE_CLIENT_SECRET`, `BACKUP_PASSPHRASE`, B2 keys, Railway/Cloudflare/Hetzner/Tailscale account creds

First-week ops cadence:
- **Daily:** glance at Sentry (any new error groups?), Railway logs (anything weird?), Hetzner box (`tailscale status`, `systemctl status ollama`)
- **Weekly:** check B2 has a fresh backup per day. Check Postgres size growth.
- **Monthly:** restore drill (Phase 12c). Rotate any secret that's been touched by anyone besides you.

---

## Environment variable reference

| Variable | Local dev (`backend/.env`) | Production | Notes |
|---|---|---|---|
| `ENVIRONMENT` | `development` | `production` | Cookie security flags |
| `DATABASE_URL` | local Postgres URL | `${{Postgres.DATABASE_URL}}` | Railway reference |
| `REDIS_URL` | `redis://localhost:6379/0` | `${{Redis.REDIS_URL}}` | |
| `GOOGLE_CLIENT_ID` | dev client | **prod client (separate)** | Phase 9 |
| `GOOGLE_CLIENT_SECRET` | dev secret | **prod secret** | |
| `JWT_SECRET` | any random | `secrets.token_urlsafe(48)` | Never reuse dev |
| `JWT_ALGORITHM` | `HS256` | `HS256` | |
| `JWT_EXPIRY_HOURS` | `72` | `72` | |
| `APP_URL` | `http://localhost:5173` | `https://yourdomain.com` | CORS + OAuth redirect |
| `API_URL` | `http://localhost:8000` | `https://api.yourdomain.com` | OAuth callback |
| `LLM_ENABLED` | `true` | `true` | Cache-only fallback knob still exists |
| `OLLAMA_URL` | `http://localhost:11434` | `http://<tailscale-ip>:11434` | Hetzner over Tailscale |
| `OLLAMA_MODEL` | `llama3.2:3b` | `llama3.2:3b` | Must match |
| `OLLAMA_TIMEOUT` | `60` | `60` | |
| `TAILSCALE_AUTHKEY` | unset | reusable ephemeral key | Phase 6a |
| `SENTRY_DSN` | unset | from Sentry | Phase 13 |
| `SUPPORT_EMAIL` | `alexis@staminachem.com` | same | |
| `ALLOW_SIGNUP` | `true` | `true` | Flip to `false` to gate later |
| `B2_KEY_ID` | unset | from B2 | Worker only |
| `B2_APP_KEY` | unset | from B2 | Worker only |
| `B2_BUCKET` | unset | `costadvisor-backups` | Worker only |
| `BACKUP_PASSPHRASE` | unset | random 32-byte | Worker only — store in password manager |
| `EIA_API_KEY`, `FRED_API_KEY` | optional | optional | Index scrapers |
| `VITE_API_BASE_URL` (frontend) | unset (Vite proxy) | `https://api.yourdomain.com` | Cloudflare Pages |
| `VITE_SENTRY_DSN` (frontend) | unset | from Sentry | Cloudflare Pages |

---

## Troubleshooting

**Login redirects to Google then back to a 400 / "redirect_uri_mismatch"**
The redirect URI registered in Google Console doesn't exactly match what the app sent. Check protocol, domain, no trailing slash. Wait 5 min after edits.

**Login appears to succeed but user is immediately redirected back to login**
Cookie set but not sent on subsequent requests. Causes: `ENVIRONMENT` not `production` → cookie not `Secure` → browser drops it on HTTPS. Or `APP_URL` mismatch → CORS rejection.

**CORS error in browser console**
`APP_URL` env on api doesn't exactly match the frontend URL. Update Railway, redeploy.

**API responds with rule-based fallback instead of LLM**
- Check Railway api logs for `OLLAMA_URL` connection errors
- From a Railway shell: `curl http://<tailscale-ip>:11434/api/tags` — does it return the model?
- On Hetzner: `tailscale status` — is the railway-api node listed?
- `systemctl status ollama` — is the daemon up?

**RLS blocking everything with "permission denied" or no rows returned where there should be some**
The `SET LOCAL app.current_team_id` listener isn't firing, or the value is wrong. Check `backend/app/db.py`. In Postgres: `SHOW app.current_team_id;` inside a transaction to debug.

**Cross-tenant test fails (user B can read user A's data)**
Real leak. Re-do Phase 1a for the affected router. Don't deploy until green.

**Build fails on Railway with "No such file requirements.txt"**
Service Root Directory not set to `backend`.

**Tailscale fails to come up inside Railway container**
Auth key wrong, expired, or not reusable. Generate a new reusable+ephemeral key in Tailscale admin and update `TAILSCALE_AUTHKEY`.

**Page reload on `/admin` returns 404**
SPA fallback missing. Verify `frontend/public/_redirects` made it into the build.

**Backup task fails with "gnupg not found"**
`gnupg` apt package not in the Dockerfile. Add `RUN apt-get update && apt-get install -y gnupg`.

---

## What this runbook deliberately doesn't cover

POC-grade, not enterprise. The following are explicit non-goals — call them out to anyone who asks if this is "production-ready":

- **CI/CD beyond auto-deploy.** Railway auto-deploys on push to `main`. No staging environment. No automated test gate before deploy (your local pytest run is the gate).
- **Multi-region.** Railway is single-region (US-East). Hetzner is single-region (match it). EU customers see ~100ms extra latency.
- **Blue/green deploys, zero-downtime migrations.** Deploys cause a ~5 sec gap.
- **SOC2, HIPAA, PCI.** Not even close.
- **Multi-node Postgres / read replicas.** Single Railway Postgres instance.
- **Ollama HA.** One Hetzner box. If it dies, LLM features go down (the rule-based fallback still works because `LLM_ENABLED` would need to be flipped to keep the API up — consider making the fallback automatic on Ollama timeout if this matters).
- **Customer data export.** Add an "export my data" endpoint when the first customer asks.
- **Email notifications.** No transactional email is wired up. If the product needs it (password reset, alerts), add Postmark or Resend later.
- **Penetration test.** Worth doing before more than ~10 paying customers.

---

If something in this runbook doesn't match what you find in the dashboards (Railway/Cloudflare/Hetzner UIs change), search their docs for the closest equivalent setting. The concepts are stable, the buttons move.
