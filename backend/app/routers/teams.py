import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.team import Team, TeamMembership
from app.routers.auth import get_current_user
from app.schemas.team import TeamCreate, TeamOut, TeamMemberOut, InviteRequest, RoleUpdate

router = APIRouter()


def require_team_role(db: Session, user: User, team_id: uuid.UUID, roles: list[str]) -> TeamMembership:
    """Check that user has one of the required roles on the team."""
    membership = db.query(TeamMembership).filter(
        TeamMembership.user_id == user.id,
        TeamMembership.team_id == team_id,
    ).first()
    if not membership or membership.role not in roles:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return membership


@router.post("/", response_model=TeamOut)
def create_team(
    data: TeamCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    team = Team(name=data.name, created_by=current_user.id)
    db.add(team)
    db.flush()
    membership = TeamMembership(user_id=current_user.id, team_id=team.id, role="owner")
    db.add(membership)
    db.commit()
    db.refresh(team)
    return team


@router.get("/", response_model=list[TeamOut])
def list_teams(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    team_ids = [m.team_id for m in current_user.memberships]
    return db.query(Team).filter(Team.id.in_(team_ids)).all()


@router.get("/{team_id}", response_model=TeamOut)
def get_team(
    team_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_team_role(db, current_user, team_id, ["owner", "admin", "member"])
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


@router.get("/{team_id}/members", response_model=list[TeamMemberOut])
def list_members(
    team_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_team_role(db, current_user, team_id, ["owner", "admin", "member"])
    memberships = db.query(TeamMembership).filter(TeamMembership.team_id == team_id).all()
    result = []
    for m in memberships:
        user = db.query(User).filter(User.id == m.user_id).first()
        result.append(TeamMemberOut(
            user_id=m.user_id,
            role=m.role,
            joined_at=m.joined_at,
            email=user.email if user else None,
            display_name=user.display_name if user else None,
        ))
    return result


@router.post("/{team_id}/invite")
def invite_member(
    team_id: uuid.UUID,
    data: InviteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_team_role(db, current_user, team_id, ["owner", "admin"])
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found. They must log in at least once first.")

    existing = db.query(TeamMembership).filter(
        TeamMembership.user_id == user.id,
        TeamMembership.team_id == team_id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="User already on team")

    membership = TeamMembership(user_id=user.id, team_id=team_id, role="member")
    db.add(membership)
    db.commit()
    return {"status": "invited", "email": data.email}


@router.patch("/{team_id}/members/{user_id}")
def update_member_role(
    team_id: uuid.UUID,
    user_id: uuid.UUID,
    data: RoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_team_role(db, current_user, team_id, ["owner"])
    if data.role not in ("admin", "member"):
        raise HTTPException(status_code=400, detail="Invalid role")
    membership = db.query(TeamMembership).filter(
        TeamMembership.user_id == user_id,
        TeamMembership.team_id == team_id,
    ).first()
    if not membership:
        raise HTTPException(status_code=404, detail="Membership not found")
    membership.role = data.role
    db.commit()
    return {"status": "updated"}


@router.delete("/{team_id}/members/{user_id}")
def remove_member(
    team_id: uuid.UUID,
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_team_role(db, current_user, team_id, ["owner", "admin"])
    membership = db.query(TeamMembership).filter(
        TeamMembership.user_id == user_id,
        TeamMembership.team_id == team_id,
    ).first()
    if not membership:
        raise HTTPException(status_code=404, detail="Membership not found")
    if membership.role == "owner":
        raise HTTPException(status_code=400, detail="Cannot remove team owner")
    db.delete(membership)
    db.commit()
    return {"status": "removed"}