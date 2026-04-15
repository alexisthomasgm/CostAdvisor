"""Account self-service: currently just DELETE /api/account."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.database import get_db, bypass_rls_var
from app.models.team import Team, TeamMembership
from app.models.user import User
from app.routers.auth import get_current_user
from app.services.audit import log_event

router = APIRouter()


@router.delete("/")
def delete_account(
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete the current user. Hard-delete any team where they are the
    sole member (cascade wipes all team-scoped data). For shared teams, only
    remove the user's membership."""
    # Account deletion crosses team boundaries for this user: they may be the
    # sole member of one team and a co-member of another. We need to see both
    # sets regardless of RLS.
    bypass_rls_var.set(True)

    memberships = (
        db.query(TeamMembership)
        .filter(TeamMembership.user_id == current_user.id)
        .all()
    )

    for m in memberships:
        member_count = (
            db.query(TeamMembership)
            .filter(TeamMembership.team_id == m.team_id)
            .count()
        )
        # Log against the team before it goes away (or before the membership does)
        log_event(
            db, m.team_id, current_user.id,
            "account_delete", "user", str(current_user.id),
            previous_value={"email": current_user.email, "role": m.role,
                            "sole_member": member_count == 1},
        )
        if member_count == 1:
            team = db.query(Team).filter(Team.id == m.team_id).first()
            if team:
                db.delete(team)  # CASCADE wipes memberships, products, cost_models, etc.
        else:
            db.delete(m)

    current_user.deleted_at = datetime.now(timezone.utc)
    # Null out the google_id so the same Google account can sign up fresh
    # later if desired, without colliding on the unique constraint.
    current_user.google_id = f"deleted:{current_user.id}"
    current_user.email = f"deleted+{current_user.id}@invalid.local"

    db.commit()

    response.delete_cookie("ca_token")
    return {"status": "deleted"}
