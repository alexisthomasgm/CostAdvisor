from datetime import datetime
from pydantic import BaseModel


class FxRateOut(BaseModel):
    id: int
    from_currency: str
    to_currency: str
    year: int
    quarter: int
    rate: float
    uploaded_at: datetime

    model_config = {"from_attributes": True}
