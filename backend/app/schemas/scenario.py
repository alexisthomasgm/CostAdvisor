from pydantic import BaseModel
import uuid


class ScenarioCreate(BaseModel):
    name: str
    description: str | None = None
    breakdown: dict  # {"Raw Materials": 0.68, ...}


class ScenarioOut(BaseModel):
    id: int
    name: str
    description: str | None
    is_system: bool
    team_id: uuid.UUID | None
    breakdown: dict

    model_config = {"from_attributes": True}