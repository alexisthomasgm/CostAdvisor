import uuid
from datetime import datetime
from pydantic import BaseModel


class ActualPriceOut(BaseModel):
    id: int
    cost_model_id: uuid.UUID
    year: int
    quarter: int
    price: float
    source_file: str | None
    uploaded_at: datetime

    model_config = {"from_attributes": True}


class ActualPriceCreate(BaseModel):
    year: int
    quarter: int
    price: float


class UploadPreview(BaseModel):
    rows: list[ActualPriceCreate]
    filename: str
    row_count: int
