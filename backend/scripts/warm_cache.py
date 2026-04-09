#!/usr/bin/env python
"""
Warm the LLM cache with deterministic responses for the demo.

Why this exists
---------------
For privacy reasons we don't run a live LLM in production. Instead we run Ollama
LOCALLY before the demo and pre-populate the *production* Redis cache with the
responses. The cache has a 7-day TTL, so one warm-up covers a week of demos.

How to run
----------
1. Start Ollama locally and pull the model production will use:
       ollama serve
       ollama pull llama3.2:3b   # or whatever you set OLLAMA_MODEL to

2. Configure your local backend to point at the *production* Redis and the
   *local* Ollama. Easiest way: temporarily edit backend/.env (or export):
       REDIS_URL=<your Railway Redis URL>
       LLM_ENABLED=true
       OLLAMA_URL=http://localhost:11434
       OLLAMA_MODEL=llama3.2:3b

   IMPORTANT: OLLAMA_MODEL must match what you'll set in Railway. The cache key
   is hashed from the model name, so a mismatch means cache misses in production.

3. Start the local backend:  uvicorn app.main:app --port 8000

4. Open the local frontend (npm run dev) and log in via Google OAuth.
   In your browser DevTools → Application → Cookies → http://localhost:5173,
   copy the value of the `ca_token` cookie.

5. Run this script:
       SESSION_TOKEN='<paste-jwt-here>' python backend/scripts/warm_cache.py

   First run will be slow (CPU LLM). Watch for ✓ marks.

6. After it finishes, set in Railway:
       LLM_ENABLED=false
       OLLAMA_URL=http://disabled
   The production app will now serve from Redis cache only.

What it does
------------
For every team your account belongs to:
  - lists every cost model and warms a /api/costing/brief for two period windows
  - lists every commodity index and warms /api/ai/index-analysis with its values

Re-runs are safe — cache hits are skipped, only misses call Ollama.
"""

import os
import sys
from datetime import datetime

import httpx

BACKEND = os.environ.get("BACKEND_URL", "http://localhost:8000")
TOKEN = os.environ.get("SESSION_TOKEN")

if not TOKEN:
    sys.stderr.write(
        "ERROR: SESSION_TOKEN env var is required.\n"
        "  Log in to the local frontend, copy the value of the `ca_token` cookie,\n"
        "  then re-run with: SESSION_TOKEN='<value>' python backend/scripts/warm_cache.py\n"
    )
    sys.exit(1)

HEADERS = {"Cookie": f"ca_token={TOKEN}"}
TIMEOUT = httpx.Timeout(300.0, connect=10.0)


def warm_briefs(client: httpx.Client, team_id: str, team_name: str) -> None:
    print(f"\n[{team_name}] Listing cost models...")
    resp = client.get("/api/cost-models/", params={"team_id": team_id})
    if resp.status_code != 200:
        print(f"  ! Failed to list cost models: {resp.status_code} {resp.text[:200]}")
        return

    cost_models = resp.json() or []
    print(f"  {len(cost_models)} cost model(s) found")

    now = datetime.now()
    cur_year = now.year
    cur_q = max(1, (now.month - 1) // 3 + 1)

    # Warm a couple of period windows so demo navigation is mostly covered
    period_windows = [
        (cur_year - 1, 1, cur_year, cur_q),
        (cur_year - 2, 1, cur_year, cur_q),
    ]

    for cm in cost_models:
        cm_id = cm.get("id")
        cm_name = cm.get("name") or str(cm_id)
        if not cm_id:
            continue
        for fy, fq, ty, tq in period_windows:
            body = {
                "cost_model_id": cm_id,
                "from_year": fy,
                "from_quarter": fq,
                "to_year": ty,
                "to_quarter": tq,
            }
            r = client.post("/api/costing/brief", json=body)
            label = f"{cm_name} ({fy}Q{fq}->{ty}Q{tq})"
            if r.status_code == 200:
                print(f"  OK   Brief: {label}")
            else:
                print(f"  FAIL Brief: {label} ({r.status_code} {r.text[:120]})")


def warm_index_analyses(client: httpx.Client, team_id: str, team_name: str) -> None:
    print(f"\n[{team_name}] Listing commodity indexes...")
    list_resp = client.get("/api/indexes/")
    if list_resp.status_code != 200:
        print(f"  ! Failed to list indexes: {list_resp.status_code}")
        return
    commodities = list_resp.json() or []
    print(f"  {len(commodities)} commodity index(es) found")

    for c in commodities:
        c_id = c.get("id")
        c_name = c.get("name") or str(c_id)
        c_region = c.get("region")
        c_category = c.get("category")
        c_unit = c.get("unit")
        c_currency = c.get("currency")

        # Fetch the time series scoped to this team
        vals_resp = client.get(
            "/api/indexes/values",
            params={"team_id": team_id, "commodity_name": c_name},
        )
        if vals_resp.status_code != 200:
            print(f"  FAIL values for {c_name}: {vals_resp.status_code}")
            continue
        values = vals_resp.json() or []

        # Reshape to {year, quarter, value}
        periods = []
        for v in values:
            y = v.get("year")
            q = v.get("quarter")
            val = v.get("value")
            if y is not None and q is not None:
                periods.append({"year": y, "quarter": q, "value": val})

        if not periods:
            print(f"  SKIP {c_name}: no period data")
            continue

        body = {
            "commodity_id": c_id,
            "commodity_name": c_name,
            "region": c_region,
            "category": c_category,
            "unit": c_unit,
            "currency": c_currency,
            "periods": periods,
            "impacts": [],
        }
        r = client.post("/api/ai/index-analysis", json=body)
        if r.status_code == 200:
            print(f"  OK   Index analysis: {c_name}")
        else:
            print(f"  FAIL Index analysis: {c_name} ({r.status_code} {r.text[:120]})")


def main() -> None:
    print(f"Backend: {BACKEND}")
    with httpx.Client(base_url=BACKEND, headers=HEADERS, timeout=TIMEOUT) as client:
        me = client.get("/auth/me")
        if me.status_code != 200:
            print(f"! /auth/me failed ({me.status_code}). Is your SESSION_TOKEN correct?")
            sys.exit(1)
        user = me.json()
        print(f"Logged in as: {user.get('email')}")

        teams = user.get("teams") or []
        if not teams:
            print("! No teams found. Make sure your account belongs to at least one team with data.")
            sys.exit(1)

        for team in teams:
            tid = team.get("team_id") or team.get("id")
            tname = team.get("team_name") or team.get("name") or str(tid)
            if not tid:
                continue
            warm_briefs(client, tid, tname)
            warm_index_analyses(client, tid, tname)

        print("\nDone. Cache populated. Re-running this script is safe (cache hits are skipped).")


if __name__ == "__main__":
    main()
