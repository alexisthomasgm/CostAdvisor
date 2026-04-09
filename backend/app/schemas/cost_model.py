import uuid
from datetime import datetime
from pydantic import BaseModel, field_validator, computed_field


class FormulaComponentItem(BaseModel):
    label: str
    commodity_name: str | None = None  # resolved to commodity_id on backend
    weight: float


class FormulaVersionCreate(BaseModel):
    base_price: float
    base_year: int
    base_quarter: int
    margin_type: str = "pct"  # 'pct', 'fixed', 'unknown'
    margin_value: float | None = None
    components: list[FormulaComponentItem]
    notes: str | None = None

    @field_validator("base_price")
    @classmethod
    def base_price_positive(cls, v):
        if v <= 0:
            raise ValueError("Base price must be positive")
        return v

    @field_validator("components")
    @classmethod
    def at_least_one_component(cls, v):
        if not v:
            raise ValueError("At least one formula component is required")
        return v

    @field_validator("margin_type")
    @classmethod
    def valid_margin_type(cls, v):
        if v not in ("pct", "fixed", "unknown"):
            raise ValueError("margin_type must be 'pct', 'fixed', or 'unknown'")
        return v


class CostModelCreate(BaseModel):
    product_id: uuid.UUID
    supplier_id: int | None = None
    destination_country: str | None = None
    region: str = "Europe"
    currency: str = "USD"
    formula: FormulaVersionCreate


class CostModelUpdate(BaseModel):
    supplier_id: int | None = None
    destination_country: str | None = None
    region: str | None = None
    currency: str | None = None


# --- Output schemas ---

class FormulaComponentOut(BaseModel):
    id: int
    label: str
    commodity_id: int | None
    commodity_name: str | None = None
    weight: float

    model_config = {"from_attributes": True}


class FormulaVersionOut(BaseModel):
    id: int
    base_price: float
    base_year: int
    base_quarter: int
    margin_type: str
    margin_value: float | None
    notes: str | None
    created_at: datetime
    updated_at: datetime | None = None
    components: list[FormulaComponentOut] = []

    @computed_field
    @property
    def quarter_label(self) -> str:
        return f"Q{self.base_quarter}-{self.base_year}"

    model_config = {"from_attributes": True}


class CostModelOut(BaseModel):
    id: uuid.UUID
    team_id: uuid.UUID
    product_id: uuid.UUID
    supplier_id: int | None
    destination_country: str | None
    region: str
    currency: str
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime
    formula_versions: list[FormulaVersionOut] = []

    # Flattened product info for convenience
    product_name: str | None = None
    product_reference: str | None = None
    product_unit: str | None = None
    product_active_content: float | None = None
    supplier_name: str | None = None

    model_config = {"from_attributes": True}
