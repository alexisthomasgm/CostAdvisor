"""AI-powered analysis endpoints (Ollama local LLM)."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.routers.auth import get_current_user
from app.models.user import User
from app.services.ollama import ollama_generate

router = APIRouter()

INDEX_SYSTEM_PROMPT = (
    "You are a commodity market analyst for a procurement team. "
    "Your primary job is to explain WHY a commodity index moved the way it did — "
    "identify the macro-economic, geopolitical, supply-chain, or seasonal factors "
    "that drove the price change. Use your knowledge of commodity markets to give "
    "a concrete, specific explanation (not generic). "
    "Then briefly note what this means for procurement costs going forward. "
    "Be concise (4-6 sentences), use the specific numbers provided. "
    "Do not use markdown formatting, bullet points, or headers."
)


# --- Schemas ---

class IndexPeriod(BaseModel):
    year: int
    quarter: int
    value: float | None = None


class IndexImpact(BaseModel):
    product_name: str
    supplier_name: str | None = None
    weight: float
    index_change_pct: float
    cost_impact_pct: float


class IndexAnalysisRequest(BaseModel):
    commodity_id: int
    commodity_name: str
    region: str | None = None
    category: str | None = None
    unit: str | None = None
    currency: str | None = None
    periods: list[IndexPeriod] = []
    impacts: list[IndexImpact] = []


class IndexAnalysisResponse(BaseModel):
    analysis: str
    source: str  # "llm" or "unavailable"


# --- Endpoint ---

@router.post("/index-analysis", response_model=IndexAnalysisResponse)
async def index_analysis(
    body: IndexAnalysisRequest,
    current_user: User = Depends(get_current_user),
):
    prompt = _build_index_prompt(body)
    result = await ollama_generate(prompt, system=INDEX_SYSTEM_PROMPT)

    if result:
        return IndexAnalysisResponse(analysis=result, source="llm")

    return IndexAnalysisResponse(
        analysis="AI analysis is currently unavailable. Please ensure the local LLM service is running.",
        source="unavailable",
    )


def _build_index_prompt(body: IndexAnalysisRequest) -> str:
    parts = [
        f"Index: {body.commodity_name}",
    ]
    if body.category:
        parts[0] += f" ({body.category})"
    if body.region:
        parts.append(f"Region: {body.region}")
    if body.unit or body.currency:
        parts.append(f"Unit: {body.unit or 'N/A'}, Currency: {body.currency or 'N/A'}")

    # Price history
    valid_periods = [p for p in body.periods if p.value is not None]
    if valid_periods:
        parts.append("\nPrice history (quarterly):")
        for p in valid_periods:
            parts.append(f"  Q{p.quarter} {p.year}: {p.value}")

        # Compute overall change for context
        first_val = valid_periods[0].value
        last_val = valid_periods[-1].value
        if first_val and last_val and first_val != 0:
            overall_pct = (last_val / first_val - 1) * 100
            parts.append(f"\nOverall change: {overall_pct:+.1f}% over {len(valid_periods)} quarters")

    # Portfolio exposure
    if body.impacts:
        parts.append("\nPortfolio exposure:")
        for imp in body.impacts:
            supplier = f" ({imp.supplier_name})" if imp.supplier_name else ""
            parts.append(
                f"  - {imp.product_name}{supplier}: "
                f"{imp.weight * 100:.1f}% weight, "
                f"index changed {imp.index_change_pct:+.1f}%, "
                f"cost impact {imp.cost_impact_pct:+.1f}%"
            )

    parts.append(
        "\nExplain why this commodity index moved the way it did. "
        "What specific macro-economic, geopolitical, supply/demand, or seasonal factors "
        "caused these price changes? Be concrete — name real-world events or market dynamics, "
        "not generic statements. Then briefly note what the procurement team should expect next "
        "and how significant the portfolio exposure is."
    )

    return "\n".join(parts)
