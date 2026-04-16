"""Create the seed team and user for Jacobi data."""
from sqlalchemy import text
from app.database import engine

TEAM_ID = "1db4d50c-b2c5-496b-8450-bf12b31484c0"
USER_ID = "d9cbd7a9-93ca-4400-a204-7f9ceaa87a23"

with engine.begin() as conn:
    # Temporarily defer the FK constraint so we can insert user then team
    conn.execute(text("SET CONSTRAINTS ALL DEFERRED"))

    # Insert user first (no team FK on users table)
    conn.execute(text("""
        INSERT INTO users (id, google_id, email, display_name, created_at, is_super_admin)
        VALUES (:uid, 'seed-google-id', 'alexis@staminachem.com', 'Alexis Thomas', NOW(), true)
        ON CONFLICT (id) DO NOTHING
    """), {"uid": USER_ID})

    # Insert team with created_by pointing to user
    conn.execute(text("""
        INSERT INTO teams (id, name, created_by, created_at)
        VALUES (:tid, 'Jacobi', :uid, NOW())
        ON CONFLICT (id) DO NOTHING
    """), {"tid": TEAM_ID, "uid": USER_ID})

    # Add team membership
    conn.execute(text("""
        INSERT INTO team_memberships (user_id, team_id, role, joined_at)
        VALUES (:uid, :tid, 'owner', NOW())
        ON CONFLICT DO NOTHING
    """), {"uid": USER_ID, "tid": TEAM_ID})

print("Done: team + user created")
