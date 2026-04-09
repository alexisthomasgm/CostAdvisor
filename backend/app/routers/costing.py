import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.cost_model import CostModel
from app.models.team import TeamMembership
from app.routers.auth import get_current_user
from app.schemas.costing import (
    ShouldCostRequest, ShouldCostResult,
    EvolutionRequest, EvolutionResult,
    SqueezeRequest, SqueezeResult,
    BriefRequest, BriefResult,
    PriceChangeRequest, PriceChangeResult,
)
from app.services.costing_engine import (
    calculate_should_cost, calculate_evolution,
    calculate_squeeze, calculate_brief,
    calculate_price_change,
)

router = APIRouter()


def require_model_access(db: Session, user: User, cm: CostModel):
    membership = db.query(TeamMembership).filter(
        TeamMembership.user_id == user.id,
        TeamMembership.team_id == cm.team_id,
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this team")


@router.post("/should-cost", response_model=ShouldCostResult)
def should_cost(
    data: ShouldCostRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cm = db.query(CostModel).filter(CostModel.id == data.cost_model_id).first()
    if not cm:
        raise HTTPException(status_code=404, detail="Cost model not found")
    require_model_access(db, current_user, cm)

    return calculate_should_cost(
        db=db,
        cost_model=cm,
        target_year=data.target_year,
        target_quarter=data.target_quarter,
    )


@router.post("/evolution", response_model=EvolutionResult)
def evolution(
    data: EvolutionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cm = db.query(CostModel).filter(CostModel.id == data.cost_model_id).first()
    if not cm:
        raise HTTPException(status_code=404, detail="Cost model not found")
    require_model_access(db, current_user, cm)

    return calculate_evolution(db=db, cost_model=cm, request=data)


@router.post("/squeeze", response_model=SqueezeResult)
def squeeze(
    data: SqueezeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cm = db.query(CostModel).filter(CostModel.id == data.cost_model_id).first()
    if not cm:
        raise HTTPException(status_code=404, detail="Cost model not found")
    require_model_access(db, current_user, cm)

    return calculate_squeeze(db=db, cost_model=cm, request=data)


@router.post("/brief", response_model=BriefResult)
async def brief(
    data: BriefRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cm = db.query(CostModel).filter(CostModel.id == data.cost_model_id).first()
    if not cm:
        raise HTTPException(status_code=404, detail="Cost model not found")
    require_model_access(db, current_user, cm)

    result = calculate_brief(db=db, cost_model=cm, request=data)

    # Attempt LLM-enhanced narrative (falls back to rule-based)
    from app.services.narrative import generate_enhanced_narrative

    result.narrative = await generate_enhanced_narrative(
        product_name=result.product_name,
        supplier_name=result.supplier_name,
        drivers=[d.model_dump() for d in result.drivers],
        gap=result.gap,
        gap_pct=result.gap_pct,
        total_impact=result.total_impact,
        currency=result.currency,
        period_label=result.period_label,
        num_periods=len(result.evolution),
    )
    return result


@router.post("/price-change", response_model=PriceChangeResult)
def price_change(
    data: PriceChangeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cm = db.query(CostModel).filter(CostModel.id == data.cost_model_id).first()
    if not cm:
        raise HTTPException(status_code=404, detail="Cost model not found")
    require_model_access(db, current_user, cm)

    return calculate_price_change(db=db, cost_model=cm, request=data)
