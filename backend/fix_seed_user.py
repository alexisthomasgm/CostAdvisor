"""
Instead of deleting the seed user, update their google_id
so Google OAuth login matches the existing row.

We need your real Google sub ID. We'll fetch it from Google's API
using the OAuth flow. But easier: just set a placeholder and let
the callback update it. Actually easiest: just remove the unique
constraint conflict by updating the fake google_id to something
that won't clash, then let the login create a new user.

Simplest fix: update the seed user's google_id and email so they
don't conflict with the real login.
"""
from sqlalchemy import text
from app.database import engine

with engine.begin() as conn:
    # Rename the seed user so it doesn't conflict with real Google login
    conn.execute(text("""
        UPDATE users
        SET google_id = 'seed-placeholder',
            email = 'seed-user@placeholder.local'
        WHERE id = 'd9cbd7a9-93ca-4400-a204-7f9ceaa87a23'
    """))

print("Done - seed user moved out of the way")
