import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, HttpUrl


class CommodityIndexOut(BaseModel):
    id: int
    name: str
    unit: str | None
    currency: str | None = None
    category: str | None = None
    source_url: str | None = None
    scrape_enabled: bool

    model_config = {"from_attributes": True}


class IndexValueOut(BaseModel):
    commodity_id: int
    commodity_name: str | None = None
    region: str
    year: int
    quarter: int
    value: float | None = None
    source: str  # 'scraped', 'team_override', 'team_blank'
    scraped_value: float | None = None
    override_id: int | None = None
    override_by: str | None = None
    override_at: str | None = None
    global_scraper: str | None = None  # e.g. "INSEE" if commodity has a built-in scraper
    global_scrape_at: str | None = None  # ISO timestamp of last global scrape

    model_config = {"from_attributes": True}


class IndexValueFilter(BaseModel):
    """Query params for filtering index values."""
    region: str | None = None
    commodity_name: str | None = None
    year: int | None = None
    quarter: int | None = None


# --- Override request schemas ---


class CellOverrideRequest(BaseModel):
    team_id: uuid.UUID
    commodity_id: int
    region: str
    year: int
    quarter: int
    value: float


class BulkOverrideRequest(BaseModel):
    team_id: uuid.UUID
    commodity_id: int
    region: str
    value: float
    periods: list[dict]  # [{"year": 2025, "quarter": 1}, ...]


# --- TeamIndexSource schemas ---


class TeamIndexSourceCreate(BaseModel):
    team_id: uuid.UUID
    commodity_id: int
    region: str
    source_type: Literal["manual", "scrape_url", "upload"]
    scrape_url: str | None = None
    scrape_config: dict | None = None

    model_config = {"from_attributes": True}


class TeamIndexSourceOut(BaseModel):
    id: int
    team_id: uuid.UUID
    commodity_id: int
    region: str
    source_type: str
    scrape_url: str | None
    scrape_config: dict | None
    source_file: str | None
    created_by: uuid.UUID
    updated_at: datetime
    commodity_name: str | None = None
    last_scrape_status: str | None = None  # "ok" | "error" | null
    last_scrape_at: str | None = None

    model_config = {"from_attributes": True}


class ScrapeNowResult(BaseModel):
    source_id: int
    status: str  # "ok" | "error"
    value: float | None = None
    error: str | None = None
    detected_source: str | None = None  # "INSEE" | "generic"


# --- Filter options ---


class FilterOptionsOut(BaseModel):
    products: list[dict]  # [{"id": "uuid", "name": "..."}]
    suppliers: list[dict]  # [{"id": 1, "name": "..."}]
    regions: list[str]
    materials: list[str]


# --- Portfolio impact ---


class IndexImpactItem(BaseModel):
    cost_model_id: uuid.UUID
    product_name: str
    supplier_name: str | None = None
    region: str
    component_label: str
    weight: float
    base_index_value: float | None = None
    current_index_value: float | None = None
    index_change_pct: float | None = None
    cost_impact_pct: float | None = None  # weight * index_change_pct


class IndexImpactResponse(BaseModel):
    commodity_id: int
    commodity_name: str
    unit: str | None = None
    currency: str | None = None
    source_url: str | None = None
    impacts: list[IndexImpactItem]
