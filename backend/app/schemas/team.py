import uuid
from datetime import datetime
from pydantic import BaseModel


class TeamCreate(BaseModel):
    name: str


class TeamOut(BaseModel):
    id: uuid.UUID
    name: str
    created_by: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class TeamMembershipOut(BaseModel):
    team_id: uuid.UUID
    role: str
    joined_at: datetime
    team: TeamOut | None = None

    model_config = {"from_attributes": True}


class TeamMemberOut(BaseModel):
    user_id: uuid.UUID
    role: str
    joined_at: datetime
    email: str | None = None
    display_name: str | None = None

    model_config = {"from_attributes": True}


class InviteRequest(BaseModel):
    email: str


class RoleUpdate(BaseModel):
    role: str  # 'admin' or 'member'