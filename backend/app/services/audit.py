"""Audit trail logging service."""
import uuid
from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog


def log_event(
    db: Session,
    team_id: uuid.UUID,
    user_id: uuid.UUID,
    event_type: str,
    entity_type: str,
    entity_id: str,
    previous_value: dict | None = None,
    new_value: dict | None = None,
):
    entry = AuditLog(
        team_id=team_id,
        user_id=user_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=str(entity_id),
        previous_value=previous_value,
        new_value=new_value,
    )
    db.add(entry)
