import uuid
from datetime import datetime
from pydantic import BaseModel


class SupplierCreate(BaseModel):
    name: str
    country: str | None = None


class SupplierOut(BaseModel):
    id: int
    team_id: uuid.UUID
    name: str
    country: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
