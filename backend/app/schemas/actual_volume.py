import uuid
from datetime import datetime
from pydantic import BaseModel


class ActualVolumeCreate(BaseModel):
    year: int
    quarter: int
    volume: float
    unit: str = "kg"


class ActualVolumeOut(BaseModel):
    id: int
    cost_model_id: uuid.UUID
    year: int
    quarter: int
    volume: float
    unit: str
    source_file: str | None
    uploaded_at: datetime

    model_config = {"from_attributes": True}
