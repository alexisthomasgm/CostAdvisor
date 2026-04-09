import uuid
from datetime import datetime
from pydantic import BaseModel, EmailStr


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str | None
    avatar_url: str | None
    is_super_admin: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class UserWithTeams(UserOut):
    memberships: list["TeamMembershipOut"] = []


# Avoid circular import
from app.schemas.team import TeamMembershipOut  # noqa: E402
UserWithTeams.model_rebuild()