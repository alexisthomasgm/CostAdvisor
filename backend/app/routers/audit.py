import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.audit_log import AuditLog
from app.models.team import TeamMembership
from app.routers.auth import get_current_user
from app.schemas.audit_log import AuditLogOut

router = APIRouter()


@router.get("/", response_model=list[AuditLogOut])
def list_audit_logs(
    team_id: uuid.UUID,
    entity_type: str | None = Query(None),
    entity_id: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Check access
    if not current_user.is_super_admin:
        membership = db.query(TeamMembership).filter(
            TeamMembership.user_id == current_user.id,
            TeamMembership.team_id == team_id,
        ).first()
        if not membership:
            raise HTTPException(status_code=403, detail="Not a member of this team")

    query = db.query(AuditLog).filter(AuditLog.team_id == team_id)

    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    if entity_id:
        query = query.filter(AuditLog.entity_id == entity_id)

    logs = (
        query
        .order_by(AuditLog.timestamp.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    results = []
    for log in logs:
        user = log.user
        results.append(AuditLogOut(
            id=log.id,
            team_id=log.team_id,
            user_id=log.user_id,
            user_email=user.email if user else None,
            event_type=log.event_type,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            previous_value=log.previous_value,
            new_value=log.new_value,
            timestamp=log.timestamp,
        ))
    return results
