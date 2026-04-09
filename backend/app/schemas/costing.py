import uuid
from pydantic import BaseModel


class ShouldCostRequest(BaseModel):
    cost_model_id: uuid.UUID
    target_year: int | None = None
    target_quarter: int | None = None
    display_currency: str | None = None
    display_unit: str | None = None


class ShouldCostResult(BaseModel):
    should_cost: float
    cost_before_margin: float
    margin_amount: float
    rm_cost: float
    ovc_cost: float
    per_active_unit: float | None
    currency: str
    unit: str


class EvolutionRequest(BaseModel):
    cost_model_id: uuid.UUID
    reference_year: int | None = None
    reference_quarter: int | None = None
    from_year: int | None = None
    from_quarter: int | None = None
    to_year: int | None = None
    to_quarter: int | None = None
    granularity: str = "quarterly"  # 'quarterly' or 'monthly'
    formula_mode: str = "active"  # 'active' or 'versioned'
    display_currency: str | None = None
    display_unit: str | None = None


class EvolutionPeriod(BaseModel):
    period: str  # 'Q1-23' or 'Jan-24'
    year: int
    quarter: int
    month: int | None = None  # set for monthly granularity
    theoretical: float
    actual: float | None
    gap: float | None
    gap_pct: float | None
    component_costs: dict[str, float] | None = None  # label -> cost for that period


class ComponentInfo(BaseModel):
    label: str
    commodity_name: str | None


class EvolutionResult(BaseModel):
    product_name: str
    supplier_name: str | None
    reference_cost: float
    region: str
    currency: str
    unit: str
    periods: list[EvolutionPeriod]
    components: list[ComponentInfo] = []
    available_from_year: int | None = None
    available_from_quarter: int | None = None
    available_to_year: int | None = None
    available_to_quarter: int | None = None


class SqueezeRequest(BaseModel):
    cost_model_id: uuid.UUID
    reference_year: int | None = None
    reference_quarter: int | None = None
    from_year: int | None = None
    from_quarter: int | None = None
    to_year: int | None = None
    to_quarter: int | None = None
    granularity: str = "quarterly"
    include_margin: bool = True
    volume_projection: str = "flat"  # 'flat' or 'seasonal'
    display_currency: str | None = None
    display_unit: str | None = None


class SqueezePeriod(BaseModel):
    period: str
    year: int
    quarter: int
    month: int | None = None
    theoretical: float
    actual: float | None
    gap: float | None
    gap_pct: float | None
    volume: float | None
    volume_projected: bool = False
    impact: float | None  # gap * volume
    cumulative_impact: float


class SqueezeResult(BaseModel):
    product_name: str
    supplier_name: str | None
    reference_cost: float
    region: str
    currency: str
    unit: str
    periods: list[SqueezePeriod]
    cumulative_impact: float
    total_volume: float


class BriefRequest(BaseModel):
    cost_model_id: uuid.UUID
    from_year: int | None = None
    from_quarter: int | None = None
    to_year: int | None = None
    to_quarter: int | None = None
    display_currency: str | None = None
    display_unit: str | None = None


class BriefDriver(BaseModel):
    component_label: str
    index_name: str | None
    index_change_pct: float
    contribution_to_gap: float
    component_cost: float  # absolute cost contribution to theoretical price
    direction: str  # 'up', 'down', 'flat'


class BriefResult(BaseModel):
    product_name: str
    supplier_name: str | None
    destination_country: str | None
    currency: str
    unit: str
    current_should_cost: float
    current_actual_price: float | None
    gap: float | None
    gap_pct: float | None
    total_impact: float | None
    period_label: str
    evolution: list[EvolutionPeriod]
    narrative: str
    drivers: list[BriefDriver]


# ── Price Change Analysis ─────────────────────────────────────

class PriceChangeRequest(BaseModel):
    cost_model_id: uuid.UUID
    from_year: int
    from_quarter: int
    to_year: int
    to_quarter: int


class PriceChangeComponent(BaseModel):
    label: str
    index_name: str | None
    weight: float
    index_start: float | None
    index_end: float | None
    index_change_pct: float
    contribution_pct: float  # weight * index_change_pct


class PriceChangeResult(BaseModel):
    product_name: str
    supplier_name: str | None
    currency: str
    unit: str
    base_price: float
    from_label: str
    to_label: str
    fair_change_pct: float
    fair_new_price: float
    margin_weight: float
    components: list[PriceChangeComponent]
