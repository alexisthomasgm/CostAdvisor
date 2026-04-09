import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.cost_model import CostModel
from app.models.price_data import ActualPrice
from app.models.actual_volume import ActualVolume
from app.models.team import TeamMembership
from app.routers.auth import get_current_user
from app.services.costing_engine import calculate_should_cost
from app.services.fx_converter import convert_price

router = APIRouter()


class PortfolioModelSummary(BaseModel):
    cost_model_id: uuid.UUID
    product_name: str
    product_reference: str | None
    supplier_name: str | None
    destination_country: str | None
    region: str
    currency: str
    current_should_cost: float
    latest_actual_price: float | None
    gap: float | None
    gap_pct: float | None
    cumulative_impact: float | None
    flag_index_moved: bool
    flag_price_drift: bool


class PortfolioKPIs(BaseModel):
    total_exposure: float
    models_flagged: int
    largest_single_exposure: float
    largest_exposure_model_id: uuid.UUID | None


class PortfolioResponse(BaseModel):
    models: list[PortfolioModelSummary]
    kpis: PortfolioKPIs


@router.get("/summary", response_model=PortfolioResponse)
def portfolio_summary(
    team_id: uuid.UUID,
    reporting_currency: str = "USD",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.is_super_admin:
        membership = db.query(TeamMembership).filter(
            TeamMembership.user_id == current_user.id,
            TeamMembership.team_id == team_id,
        ).first()
        if not membership:
            raise HTTPException(status_code=403, detail="Not a member of this team")

    cost_models = db.query(CostModel).filter(CostModel.team_id == team_id).all()

    summaries = []
    total_exposure = 0.0
    largest_exposure = 0.0
    largest_exposure_id = None
    models_flagged = 0

    for cm in cost_models:
        fv = cm.current_formula
        if not fv:
            continue

        # Compute current should-cost
        sc_result = calculate_should_cost(db, cm)
        current_sc = sc_result.should_cost

        # Get latest actual price
        latest_price = (
            db.query(ActualPrice)
            .filter(ActualPrice.cost_model_id == cm.id)
            .order_by(ActualPrice.year.desc(), ActualPrice.quarter.desc())
            .first()
        )
        latest_actual = float(latest_price.price) if latest_price else None

        gap = (latest_actual - current_sc) if latest_actual is not None else None
        base_price = float(fv.base_price)
        gap_pct = (gap / base_price * 100) if (gap is not None and base_price) else None

        # Calculate cumulative impact if volumes exist
        cumulative_impact = None
        volumes = db.query(ActualVolume).filter(ActualVolume.cost_model_id == cm.id).all()
        if volumes and gap is not None:
            total_vol = sum(float(v.volume) for v in volumes)
            cumulative_impact = gap * total_vol

        # Flags
        flag_price_drift = abs(gap_pct) > 10 if gap_pct is not None else False
        flag_index_moved = False

        # Check if indices moved >5% since base date without new formula version
        if fv.components:
            from app.services.data_resolver import get_single_index_value
            for comp in fv.components:
                if comp.commodity_id:
                    ref_val = get_single_index_value(
                        db, cm.team_id, comp.commodity_id, cm.region,
                        fv.base_year, fv.base_quarter
                    )
                    # Check most recent quarter
                    from app.services.costing_engine import _default_period_range
                    _, _, to_y, to_q = _default_period_range(db, cm)
                    cur_val = get_single_index_value(
                        db, cm.team_id, comp.commodity_id, cm.region, to_y, to_q
                    )
                    if ref_val and cur_val:
                        change = abs(cur_val / ref_val - 1)
                        if change > 0.05:
                            flag_index_moved = True
                            break

        if flag_price_drift or flag_index_moved:
            models_flagged += 1

        exposure = abs(cumulative_impact) if cumulative_impact is not None else (abs(gap) if gap else 0)

        # Convert exposure to reporting currency for aggregation
        fx_exposure = exposure
        if cm.currency != reporting_currency and exposure > 0:
            try:
                from app.services.costing_engine import _default_period_range
                _, _, to_y, to_q = _default_period_range(db, cm)
                fx_exposure = convert_price(db, exposure, cm.currency, reporting_currency, to_y, to_q)
            except Exception:
                fx_exposure = exposure

        total_exposure += fx_exposure
        if fx_exposure > largest_exposure:
            largest_exposure = exposure
            largest_exposure_id = cm.id

        summaries.append(PortfolioModelSummary(
            cost_model_id=cm.id,
            product_name=cm.product.name,
            product_reference=cm.product.formula,
            supplier_name=cm.supplier.name if cm.supplier else None,
            destination_country=cm.destination_country,
            region=cm.region,
            currency=cm.currency,
            current_should_cost=round(current_sc, 4),
            latest_actual_price=round(latest_actual, 4) if latest_actual else None,
            gap=round(gap, 4) if gap is not None else None,
            gap_pct=round(gap_pct, 2) if gap_pct is not None else None,
            cumulative_impact=round(cumulative_impact, 2) if cumulative_impact is not None else None,
            flag_index_moved=flag_index_moved,
            flag_price_drift=flag_price_drift,
        ))

    # Sort by exposure descending
    summaries.sort(key=lambda s: abs(s.cumulative_impact or s.gap or 0), reverse=True)

    return PortfolioResponse(
        models=summaries,
        kpis=PortfolioKPIs(
            total_exposure=round(total_exposure, 2),
            models_flagged=models_flagged,
            largest_single_exposure=round(largest_exposure, 2),
            largest_exposure_model_id=largest_exposure_id,
        ),
    )
