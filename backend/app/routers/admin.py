import uuid
from fastapi import APIRouter, Depends, HTTPException, Response, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.user import User
from app.models.team import Team, TeamMembership
from app.config import get_settings
from app.routers.auth import get_current_user, create_jwt
from app.schemas.user import UserOut
from app.services.audit import log_event

router = APIRouter()
settings = get_settings()


def require_super_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_super_admin:
        raise HTTPException(status_code=403, detail="Super admin required")
    return current_user


class UserAdminOut(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str | None
    avatar_url: str | None
    is_super_admin: bool
    created_at: str
    last_login_at: str | None
    teams: list[dict]

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    display_name: str | None = None
    is_super_admin: bool | None = None


@router.get("/users", response_model=list[UserAdminOut])
def list_all_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    users = db.query(User).order_by(User.created_at).all()
    result = []
    for u in users:
        teams = []
        for m in u.memberships:
            team = db.query(Team).filter(Team.id == m.team_id).first()
            teams.append({
                "team_id": str(m.team_id),
                "team_name": team.name if team else "Unknown",
                "role": m.role,
            })
        result.append(UserAdminOut(
            id=u.id,
            email=u.email,
            display_name=u.display_name,
            avatar_url=u.avatar_url,
            is_super_admin=u.is_super_admin,
            created_at=u.created_at.isoformat() if u.created_at else "",
            last_login_at=u.last_login_at.isoformat() if u.last_login_at else None,
            teams=teams,
        ))
    return result


@router.put("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: uuid.UUID,
    data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if data.display_name is not None:
        user.display_name = data.display_name
    if data.is_super_admin is not None:
        user.is_super_admin = data.is_super_admin

    db.commit()
    db.refresh(user)
    return user


@router.post("/impersonate/{user_id}")
def impersonate(
    user_id: uuid.UUID,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """Start impersonating another user. Stores admin token in a separate cookie."""
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    # Save admin's own token so we can restore later
    admin_token = create_jwt(current_user.id)
    target_token = create_jwt(target.id)

    is_prod = settings.environment != "development"
    cookie_samesite = "none" if is_prod else "lax"

    response.set_cookie(
        key="ca_admin_token",
        value=admin_token,
        httponly=True,
        secure=is_prod,
        samesite=cookie_samesite,
        max_age=3600 * 24,
    )
    response.set_cookie(
        key="ca_token",
        value=target_token,
        httponly=True,
        secure=is_prod,
        samesite=cookie_samesite,
        max_age=3600 * 24,
    )
    # Readable by JS so the frontend can show the impersonation bar
    response.set_cookie(
        key="ca_impersonating",
        value="1",
        httponly=False,
        secure=is_prod,
        samesite=cookie_samesite,
        max_age=3600 * 24,
    )

    return {
        "status": "impersonating",
        "target_email": target.email,
        "target_name": target.display_name,
    }


@router.post("/stop-impersonate")
def stop_impersonate(
    request: Request,
    response: Response,
):
    """Stop impersonating and restore the admin's own session."""
    admin_token = request.cookies.get("ca_admin_token")
    if not admin_token:
        raise HTTPException(status_code=400, detail="Not currently impersonating")

    is_prod = settings.environment != "development"
    response.set_cookie(
        key="ca_token",
        value=admin_token,
        httponly=True,
        secure=is_prod,
        samesite="none" if is_prod else "lax",
        max_age=3600 * 24,
    )
    response.delete_cookie("ca_admin_token")
    response.delete_cookie("ca_impersonating")

    return {"status": "restored"}


class SetTeamRequest(BaseModel):
    team_id: uuid.UUID
    role: str = "member"


@router.post("/users/{user_id}/set-team")
def set_user_team(
    user_id: uuid.UUID,
    data: SetTeamRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """Replace all of a user's team memberships with a single team assignment."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    team = db.query(Team).filter(Team.id == data.team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    # Remove existing memberships
    db.query(TeamMembership).filter(TeamMembership.user_id == user_id).delete()

    # Add new membership
    m = TeamMembership(user_id=user_id, team_id=data.team_id, role=data.role)
    db.add(m)
    log_event(db, data.team_id, current_user.id, "set_team", "user", str(user_id),
              new_value={"team": team.name, "role": data.role})
    db.commit()

    return {"status": "ok", "team_name": team.name}


@router.post("/users/{user_id}/add-team")
def add_user_to_team(
    user_id: uuid.UUID,
    data: SetTeamRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """Add a user to an additional team without removing existing memberships."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    team = db.query(Team).filter(Team.id == data.team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    existing = db.query(TeamMembership).filter(
        TeamMembership.user_id == user_id,
        TeamMembership.team_id == data.team_id,
    ).first()
    if existing:
        existing.role = data.role
    else:
        db.add(TeamMembership(user_id=user_id, team_id=data.team_id, role=data.role))

    log_event(db, data.team_id, current_user.id, "add_team", "user", str(user_id),
              new_value={"team": team.name, "role": data.role})
    db.commit()
    return {"status": "ok", "team_name": team.name}


@router.delete("/users/{user_id}/teams/{team_id}")
def remove_user_from_team(
    user_id: uuid.UUID,
    team_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    """Remove a user from a specific team."""
    m = db.query(TeamMembership).filter(
        TeamMembership.user_id == user_id,
        TeamMembership.team_id == team_id,
    ).first()
    if not m:
        raise HTTPException(status_code=404, detail="Membership not found")
    log_event(db, team_id, current_user.id, "remove_team", "user", str(user_id),
              previous_value={"team_id": str(team_id), "role": m.role})
    db.delete(m)
    db.commit()
    return {"status": "removed"}


@router.get("/teams", response_model=list[dict])
def list_all_teams(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_super_admin),
):
    teams = db.query(Team).order_by(Team.created_at).all()
    result = []
    for t in teams:
        members = db.query(TeamMembership).filter(TeamMembership.team_id == t.id).all()
        result.append({
            "id": str(t.id),
            "name": t.name,
            "created_at": t.created_at.isoformat() if t.created_at else "",
            "member_count": len(members),
            "members": [
                {
                    "user_id": str(m.user_id),
                    "role": m.role,
                    "email": m.user.email if m.user else None,
                }
                for m in members
            ],
        })
    return result
