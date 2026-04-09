import uuid
from datetime import datetime
from pydantic import BaseModel


class AuditLogOut(BaseModel):
    id: int
    team_id: uuid.UUID
    user_id: uuid.UUID
    user_email: str | None = None
    event_type: str
    entity_type: str
    entity_id: str
    previous_value: dict | None
    new_value: dict | None
    timestamp: datetime

    model_config = {"from_attributes": True}
