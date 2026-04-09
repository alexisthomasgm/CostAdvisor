# CostAdvisor — Deployment Runbook

This is the complete walkthrough from your laptop to a hosted website. Follow it top to bottom in order. Every step that requires your hands on a keyboard or a console is here. Any step marked with a clipboard 📋 is something only you can do (signup, click, payment, OAuth console).

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
                              └─────────────┘    └─────▲─────────┘
                                                       │
                                          ┌────────────┴────────┐
                                          │ Railway: Worker svc │
                                          │ celery worker+beat  │
                                          └─────────────────────┘

LLM in production: NONE running. Redis cache is pre-warmed before each demo
from your laptop running Ollama locally. See Phase 10.
```

**Total monthly cost target:** ~$5–15 once Railway's free trial credit runs out, plus ~$10/year for the domain.

---

## What's already done in the codebase

These changes were made during deployment prep — you don't need to redo them:

### Code fixes
- `backend/app/config.py` — added `environment` and `llm_enabled` settings
- `backend/app/routers/auth.py` — login cookie now uses `secure=True`/`samesite=none` in production
- `backend/app/routers/admin.py` — same fix for impersonation cookies
- `backend/app/services/ollama.py` — respects `LLM_ENABLED=false` (cache-only mode)
- `backend/celeryconfig.py` — fixed beat schedule to use proper `crontab()` (was a latent bug — bare dict schedules don't work)
- `backend/app/tasks/__init__.py` — added `autodiscover_tasks` so the worker finds task modules
- `backend/alembic.ini` — removed hardcoded dev DB URL (`alembic/env.py` already overrides at runtime)
- `frontend/src/api.js` — `baseURL` now reads `VITE_API_BASE_URL` env var

### Files created
- `backend/Dockerfile` — production-ready, honors Railway's `$PORT`, runs as non-root
- `backend/.dockerignore` — keeps secrets, venv, and licensed `*.xlsx` out of the image
- `backend/scripts/warm_cache.py` — the LLM cache warm-up script (Phase 10)
- `backend/.env.example` — sanitized template (real Google secret was scrubbed)
- `frontend/.env.example` — documents `VITE_API_BASE_URL`
- `frontend/public/_redirects` — Cloudflare Pages SPA fallback so direct URLs to `/admin`, `/login` etc. don't 404
- `.gitignore` (repo root) — covers `.env`, `venv/`, `node_modules/`, `*.xlsx`, etc.

### Things deliberately left alone
- The Google OAuth client secret is **not rotated** (your call, given the file has never been pushed). It still lives in your local `backend/.env`. The `.env.example` placeholder is safe to commit.
- `vite.config.js` proxy still points at localhost — that's fine; the proxy is dev-only, never bundled.
- No CI/CD, no monitoring, no Sentry. Add later.

---

## Accounts you need (one-time setup)

📋 Create accounts at all of these before starting. All have free signup:

| Service | Used for | Cost |
|---|---|---|
| **GitHub** | Source repo (private) | Free |
| **Cloudflare** | DNS, domain registration, frontend hosting (Pages) | Free, ~$10/yr for the domain |
| **Railway** | Backend API, worker, Postgres, Redis | $5 free trial credit, then ~$5–15/mo |
| **Google Cloud Console** | OAuth credentials | Free, you already have this |

---

## Phase 0 — Local sanity check (10 min)

📋 Before touching anything else, verify the local app still runs after the code changes I made.

```bash
cd /home/alexis/costadvisor

# 1. Make sure Postgres + Redis are running locally
pg_isready
redis-cli ping   # should print PONG

# 2. Run migrations against your local DB (in case schema drifted)
cd backend
source venv/bin/activate
alembic upgrade head

# 3. Start the local stack
cd ..
./start.sh
```

**Verify:**
- Backend logs show no startup errors
- `http://localhost:8000/health` returns `{"status":"ok"}`
- `http://localhost:8000/docs` loads (FastAPI swagger)
- `http://localhost:5173` loads the React app
- Click "Login," go through Google OAuth, end up logged in
- You can see your data (cost models, indexes, etc.)

If anything fails here, fix it before proceeding. **Do not move on with broken local state.**

---

## Phase 1 — Git + GitHub (5 min)

📋 The repo is currently not under version control.

```bash
cd /home/alexis/costadvisor

# Initialize git (the .gitignore already exists — created during prep)
git init
git branch -M main

# CRITICAL: verify nothing sensitive will be tracked
git status
```

**Look at the output. The following files should NOT appear in untracked files:**
- `backend/.env`
- `backend/venv/` (or any file under it)
- `frontend/node_modules/` (or any file under it)
- `jacobi_demo_data.xlsx`
- `backend/__pycache__/` or any `*.pyc`
- `backend/celerybeat-schedule`

If any of those show up, **stop** and fix the `.gitignore` before committing. Common reason: a typo in the gitignore pattern or you ran `git add -f` somewhere.

```bash
# Stage everything not gitignored
git add .
git status   # one more sanity check
git commit -m "Initial commit: deployment-ready"
```

📋 On GitHub:
1. Click **+ → New repository**
2. Name it `costadvisor` (or whatever you like)
3. **Visibility: Private**
4. Do NOT initialize with README/license/.gitignore — your repo already has files
5. Click "Create"

```bash
# Push (replace YOURNAME with your GitHub username)
git remote add origin git@github.com:YOURNAME/costadvisor.git
git push -u origin main
```

**Verify:**
- The repo on GitHub shows your files
- Click into `backend/` and confirm there's no `.env` file visible (only `.env.example`)
- `jacobi_demo_data.xlsx` should also not be there

If `.env` made it into the commit somehow: `git rm --cached backend/.env`, commit, push. The secret is technically in history at that point; if you care, force a history rewrite with `git filter-repo` (instructions on the filter-repo docs page).

---

## Phase 2 — Domain (can be done in parallel with Phase 3)

📋 You said the domain is WIP. Two options:

**Option A — buy at Cloudflare Registrar.** Cheapest, no markup. Cloudflare Dashboard → Domain Registration → Register Domains → search → buy. ~$10/yr. Auto-creates the DNS zone.

**Option B — you already have a domain elsewhere.** Add it to Cloudflare:
1. Cloudflare Dashboard → Add a Site → enter the domain
2. Free plan
3. Copy the two Cloudflare nameservers it shows you
4. Go to your current registrar (Porkbun/Namecheap/whoever) → change nameservers to those two
5. Wait 5–60 min for propagation

**You don't need to point any DNS records yet** — we'll do that in Phase 9. For now you just need the domain in Cloudflare so it's ready.

Pick a subdomain plan now so Phase 4 and 8 are unambiguous:
- Frontend: `https://yourdomain.com` (root)
- API: `https://api.yourdomain.com`

Write these down. You'll type them into Railway and Cloudflare Pages soon.

---

## Phase 3 — Railway: project + Postgres + Redis (5 min)

📋 In Railway:

1. **New Project → Empty Project**. Name it `costadvisor`.
2. Inside the project: **+ New → Database → Add PostgreSQL**. Wait a few seconds for it to provision.
3. **+ New → Database → Add Redis**. Same.

You now have two managed data services. Railway has automatically created `DATABASE_URL` and `REDIS_URL` reference variables you can wire into other services.

**Verify:**
- Click the Postgres service → Variables tab → see `DATABASE_URL` populated
- Click the Redis service → Variables tab → see `REDIS_URL` populated

Don't touch them. We'll reference them from the API and Worker services in the next phase.

---

## Phase 4 — Railway: API service (10 min)

📋 In the same Railway project:

1. **+ New → GitHub Repo → select `costadvisor`**. Authorize Railway to access the repo if prompted.
2. Railway will detect the repo. After it spins up the service:
   - Click the new service → **Settings**
   - **Service Name:** `api`
   - **Root Directory:** `backend` ← important, otherwise Railway will look for a Dockerfile at the repo root
   - **Builder:** Dockerfile (Railway should auto-detect `backend/Dockerfile`)
3. Go to **Variables** tab and add (use "+ New Variable"):

| Name | Value |
|---|---|
| `ENVIRONMENT` | `production` |
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` (Railway reference syntax) |
| `REDIS_URL` | `${{Redis.REDIS_URL}}` |
| `JWT_SECRET` | run `python -c "import secrets; print(secrets.token_urlsafe(48))"` and paste the output |
| `JWT_ALGORITHM` | `HS256` |
| `JWT_EXPIRY_HOURS` | `72` |
| `GOOGLE_CLIENT_ID` | (from your existing `backend/.env`) |
| `GOOGLE_CLIENT_SECRET` | (from your existing `backend/.env`) |
| `APP_URL` | `https://yourdomain.com` (the root domain you picked) |
| `API_URL` | `https://api.yourdomain.com` |
| `LLM_ENABLED` | `false` (cache-only mode — Phase 10 populates the cache) |
| `OLLAMA_URL` | `http://disabled` (placeholder; with LLM_ENABLED=false this is never called) |
| `OLLAMA_MODEL` | `llama3.2:3b` (must match what you'll run locally during warm-up) |

4. **Networking** tab → **Generate Domain**. Railway gives you something like `costadvisor-api-production-XXXX.up.railway.app`. Copy it — you'll use it temporarily until DNS is wired.

5. The service should rebuild and deploy automatically. Watch the **Deployments** tab for the build log. First build takes ~3–5 min.

**Verify:**
- Build logs show no errors
- Deployment is "Active"
- `https://<railway-generated-url>/health` returns `{"status":"ok"}`
- `https://<railway-generated-url>/docs` loads the FastAPI swagger

If the build fails: read the log carefully. Common issues:
- "No such file requirements.txt" → Root Directory not set to `backend`
- "psycopg2 fails to install" → unlikely; we use `psycopg2-binary`
- DB connection error at startup → `DATABASE_URL` reference variable not wired correctly

---

## Phase 5 — Railway: Worker service (5 min)

📋 The same backend image runs as a Celery worker with a different start command.

1. In the Railway project: **+ New → GitHub Repo → costadvisor** (yes, the same repo again — Railway supports multiple services pointing at one repo).
2. **Settings:**
   - **Service Name:** `worker`
   - **Root Directory:** `backend`
   - **Builder:** Dockerfile
   - **Custom Start Command:** `celery -A app.tasks worker --beat --loglevel=info`
3. **Variables** — copy the same set as the API service. Easiest way: in the Variables tab, click "Raw Editor" on the api service, copy everything, paste into the worker service. The worker needs `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET` (used by some scheduled tasks), all the index API keys, and the LLM vars too.
4. **Networking:** the worker has no public HTTP — leave it private. No domain needed.

**Verify:**
- Build succeeds
- Deploy logs show Celery banner: `celery@<hostname> v5.4.0`
- "Loading" + "ready" messages, then idle (waiting for tasks)
- No tracebacks

If you see `KeyError: 'celeryconfig'` → the worker is running from the wrong directory; double-check Root Directory is `backend`.

---

## Phase 6 — Migrations + initial data (10 min)

📋 The Postgres is empty. You need to:
1. Run Alembic migrations to create the schema
2. Get demo data into it (your seed scripts)

### Run migrations

In Railway, click the **api** service → **... menu → "Run a command"** (or use the Railway CLI: `railway run alembic upgrade head` from your laptop with the project linked). Run:

```
alembic upgrade head
```

You should see Alembic apply each migration. Verify by checking the Postgres service → Data tab; tables should now exist.

### Seed the data — privacy-conscious approach

The seed scripts read `jacobi_demo_data.xlsx`, which contains licensed data. **You don't want that file inside Railway's container.** Better approach: seed locally, then dump and restore.

**On your laptop:**

```bash
cd /home/alexis/costadvisor/backend
source venv/bin/activate

# Make sure your local DB has fresh data (run seed scripts against local Postgres)
python seed_jacobi.py
python seed_jacobi_purchases.py
python seed_jacobi_formulas.py

# Dump your local DB
pg_dump -h localhost -U costadvisor -d costadvisor \
  --no-owner --no-acl --clean --if-exists \
  > /tmp/costadvisor_seed.sql
```

**Push to Railway's Postgres.** Get the connection details: in Railway, click the Postgres service → Connect tab → copy the "Postgres Connection URL" (looks like `postgresql://postgres:xxxxx@xxxxx.railway.app:1234/railway`).

```bash
# Restore (replace with the URL from Railway Connect tab)
psql 'postgresql://postgres:xxxxx@xxxxx.railway.app:1234/railway' < /tmp/costadvisor_seed.sql
```

**Verify:**
- No errors during restore (warnings about "role does not exist" are fine — that's why we used `--no-owner`)
- In Railway Postgres → Data tab, you should see rows in your tables

---

## Phase 7 — Google OAuth: add the production redirect URI (3 min)

📋 Currently your OAuth client only allows `http://localhost:8000/auth/callback`. Production needs the deployed URL added.

1. Go to https://console.cloud.google.com/apis/credentials
2. Click your OAuth 2.0 Client ID (the one whose ID matches your `GOOGLE_CLIENT_ID`)
3. Under **Authorized redirect URIs** → **Add URI**:
   - `https://api.yourdomain.com/auth/callback`
   - **Also temporarily add** `https://<railway-generated-url>/auth/callback` so you can test before DNS propagates
4. Under **Authorized JavaScript origins** → **Add URI**:
   - `https://yourdomain.com`
5. **Save**

**Important:** Google OAuth changes can take up to 5 minutes to propagate. If your first login attempt gets `redirect_uri_mismatch`, wait and try again.

---

## Phase 8 — Cloudflare Pages: deploy the frontend (10 min)

📋 In Cloudflare Dashboard:

1. **Workers & Pages → Create application → Pages → Connect to Git**
2. Authorize Cloudflare to read your GitHub
3. Pick the `costadvisor` repo
4. Set up build:
   - **Project name:** `costadvisor`
   - **Production branch:** `main`
   - **Framework preset:** Vite (auto-detected probably)
   - **Build command:** `npm run build`
   - **Build output directory:** `dist`
   - **Root directory (advanced):** `frontend`
5. **Environment variables (advanced):**
   - `VITE_API_BASE_URL` = `https://api.yourdomain.com`
6. **Save and Deploy**

First build takes ~2 min. Cloudflare gives you a `costadvisor.pages.dev` URL.

**Verify:**
- Build succeeds
- The pages.dev URL loads the React app
- The login page renders correctly
- DON'T try to log in yet — the OAuth redirect points at `api.yourdomain.com` which doesn't resolve until Phase 9

---

## Phase 9 — DNS wiring (5 min + propagation)

📋 In Cloudflare → DNS → Records, add two records:

| Type | Name | Target | Proxy |
|---|---|---|---|
| `CNAME` | `@` (root) | `costadvisor.pages.dev` | Proxied (orange cloud) |
| `CNAME` | `api` | `costadvisor-api-production-xxxx.up.railway.app` | Proxied (orange cloud) |

(Adjust the targets to your actual generated URLs.)

**Important about the API CNAME and Railway:** Railway's free tier requires you to add the custom domain in Railway too. In Railway, go to the **api** service → **Settings → Networking → Custom Domain → Add Domain → `api.yourdomain.com`**. Railway will give you a verification record. If it asks for a CNAME target, that's the same Railway hostname you already used.

For the root domain on Cloudflare Pages:
- In Cloudflare Pages → your project → Custom domains → Set up custom domain → `yourdomain.com`
- Cloudflare auto-handles this since the domain is in the same Cloudflare account

DNS propagation usually completes in 1–5 minutes inside Cloudflare's network.

**Verify:**
- `https://yourdomain.com` loads the React app
- `https://api.yourdomain.com/health` returns `{"status":"ok"}`
- Both have valid HTTPS certificates (Cloudflare auto-provisions)

---

## Phase 10 — Pre-warm the LLM cache (20 min)

📋 This is the trick that makes the demo fully private and fast at $0/mo.

### One-time setup on your laptop

```bash
# Install Ollama if you don't have it
curl -fsSL https://ollama.com/install.sh | sh

# Start Ollama (leave running in a terminal)
ollama serve

# In another terminal: pull the model
ollama pull llama3.2:3b
```

The 3B model is ~2 GB on disk and runs decently on CPU. Chosen because it's small enough to be fast for the warm-up loop. You can use a bigger model if you want better output, but the cache key is hashed from the model name — **whatever you pull here MUST match `OLLAMA_MODEL` in Railway**.

### Configure your local backend to write into Railway's Redis

In `backend/.env` (your local file, never committed), temporarily add/change:

```
LLM_ENABLED=true
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b
REDIS_URL=<paste the Railway Redis URL from the Railway dashboard, "Connect" tab>
```

### Run the warm-up

```bash
# Restart your local backend so it picks up the new env vars
cd /home/alexis/costadvisor
./start.sh
```

In a browser, open `http://localhost:5173`, log in via Google OAuth.

In DevTools → Application → Cookies → http://localhost:5173, find the `ca_token` cookie and copy its **Value** (a long JWT string starting with `ey...`).

In a third terminal:

```bash
cd /home/alexis/costadvisor/backend
source venv/bin/activate
SESSION_TOKEN='paste-the-jwt-here' python scripts/warm_cache.py
```

Watch the output. Every brief and index analysis will print `OK` or `FAIL`. First-time generations take ~10–20 sec each on CPU. Total warm-up time depends on how much data you have — could be 5–30 min.

**Verify:**
- Most lines print `OK`
- A handful of `FAIL` lines for things with no data is normal (e.g., a cost model with no period data yet)
- No tracebacks

### Restore your local `.env`

After warm-up completes, change `backend/.env` back to local settings:

```
LLM_ENABLED=true
OLLAMA_URL=http://localhost:11434
REDIS_URL=redis://localhost:6379/0
```

Restart your local backend so it stops poking at the Railway Redis.

---

## Phase 11 — Production smoke test (10 min)

📋 The whole point of this phase is to catch demo-breakers BEFORE the audience sees them. Do every step.

1. **Open `https://yourdomain.com` in a fresh incognito window** (no cookies from prior testing)
2. **Click Login.** Should redirect to Google's consent screen, then back to `https://yourdomain.com` logged in
3. **Look at DevTools → Application → Cookies.** You should see `ca_token` set on `api.yourdomain.com`, with `Secure: true`, `SameSite: None`, `HttpOnly: true`
4. **Refresh the page.** You should stay logged in (proves the cookie is being sent on subsequent requests)
5. **Click through every screen** the demo will show. Specifically:
   - Generate a brief — verify the narrative is the LLM-enhanced one (not the rule-based fallback). If it's the rule-based one, the cache miss happened, meaning your warm-up didn't cover this exact request → re-run warm-up against the same period selection
   - Open a commodity index → click "AI analysis" → verify you get a real explanation, not "AI analysis is currently unavailable"
6. **Log in as a SECOND Google account** in another incognito window. Verify you don't see the first user's data. (This is your minimum viable tenancy test.)
7. **Log out, log back in.** Verify the session cycle works.

If any of this fails, see the **Troubleshooting** section at the bottom.

---

## Phase 12 — Demo day morning checklist

📋 Run through this an hour before the presentation:

- [ ] Visit `https://yourdomain.com/health`-equivalent (the API one): `https://api.yourdomain.com/health`. Should be `{"status":"ok"}`.
- [ ] Log in fresh (incognito window). Should succeed without prompts beyond Google's consent.
- [ ] Click through the exact demo flow you'll show. Every LLM response should appear instantly (cache hit). Any slow / fallback response = cache miss → bad sign.
- [ ] Check Railway dashboard: api service "Active", worker service "Active", no recent error spikes.
- [ ] Confirm your demo Google account is still logged in, OR have the credentials handy.
- [ ] Have a backup browser tab open with the local dev environment running, just in case.
- [ ] Make sure your laptop is on power, wifi is solid, Do Not Disturb is on.

---

## Post-demo TODO (do these the week after)

These are explicitly out of scope for the demo but important before any real customer touches the system. Listing them so they don't fall on the floor:

1. **Tenancy audit.** Walk every query in `backend/app/routers/` and `backend/app/services/` and verify each touches tenant data only after filtering by `team_id` or `user_id`. There's no automated test for this — it's read-the-code work. Then add a few integration tests that log in as Tenant A and try to access Tenant B's resources (should 403 / 404, not return data).
2. **Postgres Row-Level Security (RLS) as a backstop.** Even after the audit, add RLS policies on the team-scoped tables so a future query bug can't accidentally leak across tenants. This is the difference between "we tried to be careful" and "the database physically refuses to leak."
3. **Real backups.** Railway backs up Postgres but you want your own copy for licensed data. Set up a nightly `pg_dump` to a Backblaze B2 bucket (encrypted), and **test the restore process** at least once.
4. **Audit log.** You already have an `audit_log` model. Make sure every write that touches tenant data goes through `log_event()`.
5. **Decide self-hosted SLM strategy.** If the LLM features are going to be load-bearing, provision a Hetzner CCX13 (~$13/mo) running Ollama, set `LLM_ENABLED=true` and `OLLAMA_URL=http://<that-server>:11434`. Use a Tailscale tunnel between Railway and the Hetzner box so the Ollama port isn't on the public internet.
6. **Move secrets out of `backend/.env` on your laptop** to a password manager. Keep `.env` for placeholder values only.
7. **Rotate the Google OAuth client secret** and the JWT secret as a hygienic baseline. Rotation is free, hygiene matters.
8. **Daily scraping schedule.** Currently set to weekly Mondays in `celeryconfig.py`. Change `crontab(hour=6, minute=0, day_of_week=1)` → `crontab(hour=6, minute=0)` (every day at 06:00) once the worker is stable.
9. **Monitoring.** Add UptimeRobot (free) pinging `https://api.yourdomain.com/health` every 5 min. Add Sentry (free hobby tier) for error tracking once you have actual users.

---

## Environment variable reference

Complete list of every env var the app reads, where to set it, and what it should be in each environment.

| Variable | Local dev (`backend/.env`) | Production (Railway) | Notes |
|---|---|---|---|
| `ENVIRONMENT` | `development` (or unset) | `production` | Controls cookie security flags |
| `DATABASE_URL` | local Postgres URL | `${{Postgres.DATABASE_URL}}` | Railway reference variable |
| `REDIS_URL` | `redis://localhost:6379/0` | `${{Redis.REDIS_URL}}` | |
| `GOOGLE_CLIENT_ID` | from Google Console | same | |
| `GOOGLE_CLIENT_SECRET` | from Google Console | same | |
| `JWT_SECRET` | any random string | `secrets.token_urlsafe(48)` output | NEVER reuse the dev one |
| `JWT_ALGORITHM` | `HS256` | `HS256` | |
| `JWT_EXPIRY_HOURS` | `72` | `72` | |
| `APP_URL` | `http://localhost:5173` | `https://yourdomain.com` | Used for CORS + OAuth redirect |
| `API_URL` | `http://localhost:8000` | `https://api.yourdomain.com` | Used to build OAuth callback URL |
| `LLM_ENABLED` | `true` | `false` | False = cache-only mode for demo |
| `OLLAMA_URL` | `http://localhost:11434` | `http://disabled` | Never called when LLM_ENABLED=false |
| `OLLAMA_MODEL` | `llama3.2:3b` | `llama3.2:3b` | MUST match between dev and prod for cache keys to align |
| `OLLAMA_TIMEOUT` | `60` | `60` | |
| `EIA_API_KEY` | optional | optional | EIA scraper, demo doesn't need it |
| `FRED_API_KEY` | optional | optional | FRED scraper, demo doesn't need it |
| `VITE_API_BASE_URL` (frontend) | unset (uses Vite proxy) | `https://api.yourdomain.com` (Cloudflare Pages env) | Set in Pages dashboard |

---

## Troubleshooting

**Login redirects to Google then back to a 400 / "redirect_uri_mismatch"**
The redirect URI you registered in Google Console doesn't exactly match what the app sent. Check exact protocol (`https://`), exact domain, no trailing slash. Add the missing variant in Google Console and wait 5 min for propagation.

**Login appears to succeed (Google consent screen → back to your app), but you're immediately redirected to login again**
The cookie was set but isn't being sent on subsequent requests. Causes:
- `ENVIRONMENT` not set to `production` in Railway → cookie has `secure=False` → browser drops it on HTTPS
- Frontend and API are on completely different parent domains AND your CORS / cookie config doesn't allow cross-site cookies. With the current code, `samesite=None + secure=True` is set in production, which works cross-site.
- `withCredentials: true` missing on the axios client (already set in `frontend/src/api.js`)

**CORS error in browser console**
`APP_URL` env var on the API service doesn't exactly match the frontend's actual URL. Must include protocol, no trailing slash. Update in Railway, redeploy.

**Build fails on Railway with "No such file requirements.txt"**
Service Root Directory not set to `backend`. Fix in Settings → Source.

**Worker service crashes with "ModuleNotFoundError: No module named 'celeryconfig'"**
Worker is being run from the wrong directory. Confirm Root Directory = `backend`. The Dockerfile sets `WORKDIR /app` and copies the backend contents into it, so `celeryconfig` lives at `/app/celeryconfig.py` and is importable.

**LLM responses in production are the rule-based fallback, not the cached LLM ones**
Cache miss. Either:
- Warm-up didn't run successfully (re-check `warm_cache.py` output)
- `OLLAMA_MODEL` differs between warm-up and Railway (cache key includes the model name)
- Redis was emptied / TTL expired (cache TTL is 7 days)
- Warm-up wrote to a *different* Redis than Railway uses (double-check the `REDIS_URL` you set during warm-up)

**Page reload on `/admin` returns a 404**
SPA fallback not configured on Cloudflare Pages. The `frontend/public/_redirects` file should fix this — verify it made it into the build.

**`alembic upgrade head` fails with "could not connect to server"**
You're running it from your laptop without the right `DATABASE_URL`. Easiest fix: run via Railway's "Run a command" UI on the api service, or use `railway run alembic upgrade head` after `railway link`.

---

## What this runbook deliberately doesn't cover

- **Custom CI/CD.** Railway auto-deploys on push to `main`. That's all you need for now.
- **Staging environments.** One env until there's a reason for two.
- **Containerized frontend.** Cloudflare Pages builds React directly; you don't need `Dockerfile.frontend` for production. It can stay in the repo for docker-compose dev workflows.
- **Multi-region deployment.** Railway is single-region. Latency from Canada/EU to Railway's US-East is ~100ms. Acceptable for a demo. For real users worldwide, that's a Phase 2 migration to Fly.io or similar.
- **Blue/green deploys, zero-downtime migrations.** Deploys cause a ~5 sec gap. Schedule deploys when no demo is running.

---

If something in this runbook doesn't match what you find in the dashboards (Railway/Cloudflare UIs change), search their docs for the closest equivalent setting. The concepts are stable, the buttons move.
