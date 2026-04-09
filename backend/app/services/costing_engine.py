"""
Core costing engine: should-cost, evolution, squeeze/desqueeze, and brief calculations.
"""
from sqlalchemy.orm import Session

from app.models.cost_model import CostModel
from app.models.price_data import ActualPrice
from app.models.actual_volume import ActualVolume
from app.services.data_resolver import get_single_index_value
from app.services.volume_projector import project_volumes
from app.services.narrative import generate_narrative
from app.services.fx_converter import convert_price
from app.services.unit_converter import convert_unit, convert_price_per_unit
from app.schemas.costing import (
    ShouldCostResult, EvolutionRequest, EvolutionResult, EvolutionPeriod, ComponentInfo,
    SqueezeRequest, SqueezeResult, SqueezePeriod,
    BriefRequest, BriefResult, BriefDriver,
    PriceChangeRequest, PriceChangeResult, PriceChangeComponent,
)

# ── Period helpers ─────────────────────────────────────────────

MONTH_NAMES = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


def generate_periods(
    from_year: int, from_quarter: int,
    to_year: int, to_quarter: int,
    granularity: str = "quarterly",
) -> list[tuple[int, int, int | None, str]]:
    """
    Generate period list as [(year, quarter, month_or_none, label), ...].
    """
    periods = []
    y, q = from_year, from_quarter
    while (y, q) <= (to_year, to_quarter):
        if granularity == "monthly":
            for m_offset in range(3):
                month = (q - 1) * 3 + m_offset + 1
                label = f"{MONTH_NAMES[month - 1]}-{str(y)[-2:]}"
                periods.append((y, q, month, label))
        else:
            label = f"Q{q}-{str(y)[-2:]}"
            periods.append((y, q, None, label))
        q += 1
        if q > 4:
            q = 1
            y += 1
    return periods


def _get_period_formula(cost_model: CostModel, year: int, quarter: int):
    """Get the formula version active for a given period."""
    return cost_model.formula_for_period(year, quarter)


def _available_index_range(db: Session, cost_model: CostModel):
    """Find the min/max (year, quarter) of index data available for this model's components."""
    from app.models.index_data import IndexValue

    # Gather commodity_ids from ALL formula versions (union)
    commodity_ids = set()
    for fv in cost_model.formula_versions:
        for c in fv.components:
            if c.commodity_id:
                commodity_ids.add(c.commodity_id)

    if not commodity_ids:
        return None, None, None, None

    from sqlalchemy import func
    row = db.query(
        func.min(IndexValue.year * 10 + IndexValue.quarter),
        func.max(IndexValue.year * 10 + IndexValue.quarter),
    ).filter(IndexValue.commodity_id.in_(commodity_ids)).first()

    if not row or row[0] is None:
        return None, None, None, None

    min_yq, max_yq = row
    return min_yq // 10, min_yq % 10, max_yq // 10, max_yq % 10


def _default_period_range(db: Session, cost_model: CostModel):
    """Determine a sensible default period range from available index data.
    Defaults to the last 8 quarters of available data."""
    min_y, min_q, max_y, max_q = _available_index_range(db, cost_model)
    if max_y is None:
        fv = cost_model.current_formula
        if not fv:
            return 2023, 1, 2025, 4
        return max(fv.base_year - 1, 2020), 1, fv.base_year + 2, 4

    # Go 7 quarters back from the latest available quarter (8 quarters total)
    to_year, to_quarter = max_y, max_q
    from_year, from_quarter = max_y, max_q
    for _ in range(7):
        from_quarter -= 1
        if from_quarter < 1:
            from_quarter = 4
            from_year -= 1

    # Clamp to available data start
    if (from_year, from_quarter) < (min_y, min_q):
        from_year, from_quarter = min_y, min_q

    return from_year, from_quarter, to_year, to_quarter


# ── Conversion helpers ────────────────────────────────────────

def _apply_fx(db: Session, value: float, from_ccy: str, to_ccy: str | None, year: int, quarter: int) -> float:
    if not to_ccy or to_ccy == from_ccy:
        return value
    return convert_price(db, value, from_ccy, to_ccy, year, quarter)


def _apply_unit(value: float, from_unit: str, to_unit: str | None) -> float:
    """Convert a price-per-unit value between units."""
    if not to_unit or to_unit == from_unit:
        return value
    try:
        return convert_price_per_unit(value, from_unit, to_unit)
    except ValueError:
        return value


def _output_ccy(model_ccy: str, display_ccy: str | None) -> str:
    return display_ccy if display_ccy else model_ccy


def _output_unit(model_unit: str, display_unit: str | None) -> str:
    return display_unit if display_unit else model_unit


# ── Margin helpers ─────────────────────────────────────────────

def _apply_margin(indexed_cost: float, margin_type: str, margin_value: float | None,
                  base_price: float | None = None) -> tuple[float, float]:
    """
    Apply margin to indexed cost. Returns (should_cost, margin_amount).
    """
    if margin_value is not None:
        margin_value = float(margin_value)
    if base_price is not None:
        base_price = float(base_price)

    if margin_type == "pct" and margin_value is not None:
        pct = margin_value / 100.0
        if pct >= 1.0:
            pct = 0.0
        should_cost = indexed_cost / (1 - pct)
        return should_cost, should_cost - indexed_cost

    elif margin_type == "fixed" and margin_value is not None:
        should_cost = indexed_cost + margin_value
        return should_cost, margin_value

    elif margin_type == "unknown" and base_price is not None:
        margin = base_price - indexed_cost
        should_cost = indexed_cost + margin
        return should_cost, margin

    return indexed_cost, 0.0


# ── Should-Cost ────────────────────────────────────────────────

def calculate_should_cost(
    db: Session,
    cost_model: CostModel,
    target_year: int | None = None,
    target_quarter: int | None = None,
) -> ShouldCostResult:
    # Use period-aware formula selection
    if target_year and target_quarter:
        fv = _get_period_formula(cost_model, target_year, target_quarter)
    else:
        fv = cost_model.current_formula

    if not fv:
        return ShouldCostResult(
            should_cost=0, cost_before_margin=0, margin_amount=0,
            rm_cost=0, ovc_cost=0, per_active_unit=None,
            currency=cost_model.currency, unit=cost_model.product.unit,
        )

    base_price = float(fv.base_price)
    region = cost_model.region
    ref_year = fv.base_year
    ref_quarter = fv.base_quarter
    active = float(cost_model.product.active_content or 1)

    t_year = target_year or ref_year
    t_quarter = target_quarter or ref_quarter

    indexed_cost = _compute_indexed_cost(
        db, fv, cost_model, region, ref_year, ref_quarter, t_year, t_quarter, base_price
    )

    should_cost, margin_amount = _apply_margin(
        indexed_cost, fv.margin_type, fv.margin_value, base_price
    )

    return ShouldCostResult(
        should_cost=round(should_cost, 4),
        cost_before_margin=round(indexed_cost, 4),
        margin_amount=round(margin_amount, 4),
        rm_cost=0,
        ovc_cost=0,
        per_active_unit=round(should_cost / active, 4) if active else None,
        currency=cost_model.currency,
        unit=cost_model.product.unit,
    )


# ── Evolution ──────────────────────────────────────────────────

def calculate_evolution(
    db: Session,
    cost_model: CostModel,
    request: EvolutionRequest,
) -> EvolutionResult:
    fv = cost_model.current_formula
    use_active = request.formula_mode != "versioned"
    model_ccy = cost_model.currency
    model_unit = cost_model.product.unit
    out_ccy = _output_ccy(model_ccy, request.display_currency)
    out_unit = _output_unit(model_unit, request.display_unit)

    if not fv:
        return EvolutionResult(
            product_name=cost_model.product.name,
            supplier_name=cost_model.supplier.name if cost_model.supplier else None,
            reference_cost=0, region=cost_model.region,
            currency=out_ccy, unit=out_unit,
            periods=[],
        )

    base_price = float(fv.base_price)
    region = cost_model.region

    ref_year = request.reference_year or fv.base_year
    ref_quarter = request.reference_quarter or fv.base_quarter

    if request.from_year and request.from_quarter and request.to_year and request.to_quarter:
        from_y, from_q = request.from_year, request.from_quarter
        to_y, to_q = request.to_year, request.to_quarter
    else:
        from_y, from_q, to_y, to_q = _default_period_range(db, cost_model)

    periods = generate_periods(from_y, from_q, to_y, to_q, request.granularity)

    actuals = {}
    for ap in db.query(ActualPrice).filter(ActualPrice.cost_model_id == cost_model.id).all():
        actuals[(ap.year, ap.quarter)] = float(ap.price)

    # Convert reference cost for display (use current/latest formula)
    ref_cost_display = _apply_unit(
        _apply_fx(db, base_price, model_ccy, out_ccy, ref_year, ref_quarter),
        model_unit, out_unit
    )

    # Build component info list for display.
    # In versioned mode, collect the union of labels across all formula versions
    # so every period's component costs can be matched by the frontend.
    if use_active:
        comp_info = [
            ComponentInfo(label=c.label, commodity_name=c.commodity.name if c.commodity else None)
            for c in fv.components
        ]
    else:
        seen = set()
        comp_info = []
        for ver in cost_model.formula_versions:
            for c in ver.components:
                if c.label not in seen:
                    seen.add(c.label)
                    comp_info.append(ComponentInfo(
                        label=c.label,
                        commodity_name=c.commodity.name if c.commodity else None,
                    ))

    periods_out = []
    for year, quarter, month, label in periods:
        # Period-aware: get the formula for this specific period
        period_fv = fv if use_active else _get_period_formula(cost_model, year, quarter)
        period_base_price = float(period_fv.base_price)
        period_ref_year = period_fv.base_year
        period_ref_quarter = period_fv.base_quarter

        indexed_cost = _compute_indexed_cost(
            db, period_fv, cost_model, region,
            period_ref_year, period_ref_quarter, year, quarter, period_base_price
        )

        # Compute per-component costs using period formula
        comp_base = _component_base(period_base_price, period_fv.margin_type, period_fv.margin_value)
        comp_costs = {}
        for comp in period_fv.components:
            weight = float(comp.weight)
            if comp.commodity_id:
                ref_val = get_single_index_value(
                    db, cost_model.team_id, comp.commodity_id, region, period_ref_year, period_ref_quarter
                )
                cur_val = get_single_index_value(
                    db, cost_model.team_id, comp.commodity_id, region, year, quarter
                )
                ratio = (cur_val / ref_val) if (ref_val and cur_val) else 1.0
            else:
                ratio = 1.0
            comp_cost = comp_base * weight * ratio
            comp_cost = _apply_unit(_apply_fx(db, comp_cost, model_ccy, out_ccy, year, quarter), model_unit, out_unit)
            comp_costs[comp.label] = round(comp_cost, 4)

        theoretical, _ = _apply_margin(indexed_cost, period_fv.margin_type, period_fv.margin_value, period_base_price)

        actual = actuals.get((year, quarter))

        # Apply FX and unit conversions
        theoretical = _apply_unit(_apply_fx(db, theoretical, model_ccy, out_ccy, year, quarter), model_unit, out_unit)
        if actual is not None:
            actual = _apply_unit(_apply_fx(db, actual, model_ccy, out_ccy, year, quarter), model_unit, out_unit)

        gap = (actual - theoretical) if actual is not None else None
        bp_display = _apply_unit(_apply_fx(db, period_base_price, model_ccy, out_ccy, year, quarter), model_unit, out_unit)
        gap_pct = (gap / bp_display * 100) if (gap is not None and bp_display) else None

        periods_out.append(EvolutionPeriod(
            period=label,
            year=year,
            quarter=quarter,
            month=month,
            theoretical=round(theoretical, 4),
            actual=round(actual, 4) if actual is not None else None,
            gap=round(gap, 4) if gap is not None else None,
            gap_pct=round(gap_pct, 2) if gap_pct is not None else None,
            component_costs=comp_costs,
        ))

    avail_min_y, avail_min_q, avail_max_y, avail_max_q = _available_index_range(db, cost_model)

    return EvolutionResult(
        product_name=cost_model.product.name,
        supplier_name=cost_model.supplier.name if cost_model.supplier else None,
        reference_cost=round(ref_cost_display, 4),
        region=region,
        currency=out_ccy,
        unit=out_unit,
        periods=periods_out,
        components=comp_info,
        available_from_year=avail_min_y,
        available_from_quarter=avail_min_q,
        available_to_year=avail_max_y,
        available_to_quarter=avail_max_q,
    )


# ── Squeeze / Desqueeze ───────────────────────────────────────

def calculate_squeeze(
    db: Session,
    cost_model: CostModel,
    request: SqueezeRequest,
) -> SqueezeResult:
    fv = cost_model.current_formula
    model_ccy = cost_model.currency
    model_unit = cost_model.product.unit
    out_ccy = _output_ccy(model_ccy, request.display_currency)
    out_unit = _output_unit(model_unit, request.display_unit)

    if not fv:
        return SqueezeResult(
            product_name=cost_model.product.name,
            supplier_name=cost_model.supplier.name if cost_model.supplier else None,
            reference_cost=0, region=cost_model.region,
            currency=out_ccy, unit=out_unit,
            periods=[], cumulative_impact=0, total_volume=0,
        )

    base_price = float(fv.base_price)
    region = cost_model.region
    ref_year = request.reference_year or fv.base_year
    ref_quarter = request.reference_quarter or fv.base_quarter

    if request.from_year and request.from_quarter and request.to_year and request.to_quarter:
        from_y, from_q = request.from_year, request.from_quarter
        to_y, to_q = request.to_year, request.to_quarter
    else:
        from_y, from_q, to_y, to_q = _default_period_range(db, cost_model)

    periods = generate_periods(from_y, from_q, to_y, to_q, request.granularity)

    actuals = {}
    for ap in db.query(ActualPrice).filter(ActualPrice.cost_model_id == cost_model.id).all():
        actuals[(ap.year, ap.quarter)] = float(ap.price)

    raw_volumes = {}
    for av in db.query(ActualVolume).filter(ActualVolume.cost_model_id == cost_model.id).all():
        raw_volumes[(av.year, av.quarter)] = float(av.volume)

    period_keys = [(y, q) for y, q, _, _ in periods]
    volume_data = project_volumes(raw_volumes, request.volume_projection, period_keys)

    ref_cost_display = _apply_unit(
        _apply_fx(db, base_price, model_ccy, out_ccy, ref_year, ref_quarter),
        model_unit, out_unit
    )

    cumulative = 0.0
    total_volume = 0.0
    periods_out = []

    for year, quarter, month, label in periods:
        # Period-aware formula selection
        period_fv = _get_period_formula(cost_model, year, quarter)
        period_base_price = float(period_fv.base_price)
        period_ref_year = period_fv.base_year
        period_ref_quarter = period_fv.base_quarter

        indexed_cost = _compute_indexed_cost(
            db, period_fv, cost_model, region,
            period_ref_year, period_ref_quarter, year, quarter, period_base_price
        )

        if request.include_margin:
            theoretical, _ = _apply_margin(indexed_cost, period_fv.margin_type, period_fv.margin_value, period_base_price)
        else:
            theoretical = indexed_cost

        actual = actuals.get((year, quarter))

        theoretical = _apply_unit(_apply_fx(db, theoretical, model_ccy, out_ccy, year, quarter), model_unit, out_unit)
        if actual is not None:
            actual = _apply_unit(_apply_fx(db, actual, model_ccy, out_ccy, year, quarter), model_unit, out_unit)

        gap = (actual - theoretical) if actual is not None else None
        bp_display = _apply_unit(_apply_fx(db, period_base_price, model_ccy, out_ccy, year, quarter), model_unit, out_unit)
        gap_pct = (gap / bp_display * 100) if (gap is not None and bp_display) else None

        vol, vol_projected = volume_data.get((year, quarter), (0.0, True))
        # Convert volume units if needed
        if vol and out_unit and out_unit != model_unit:
            try:
                vol = convert_unit(vol, model_unit, out_unit)
            except ValueError:
                pass
        impact = gap * vol if gap is not None else None
        if impact is not None:
            cumulative += impact
        total_volume += vol

        periods_out.append(SqueezePeriod(
            period=label,
            year=year,
            quarter=quarter,
            month=month,
            theoretical=round(theoretical, 4),
            actual=round(actual, 4) if actual is not None else None,
            gap=round(gap, 4) if gap is not None else None,
            gap_pct=round(gap_pct, 2) if gap_pct is not None else None,
            volume=round(vol, 4),
            volume_projected=vol_projected,
            impact=round(impact, 2) if impact is not None else None,
            cumulative_impact=round(cumulative, 2),
        ))

    return SqueezeResult(
        product_name=cost_model.product.name,
        supplier_name=cost_model.supplier.name if cost_model.supplier else None,
        reference_cost=round(ref_cost_display, 4),
        region=region,
        currency=out_ccy,
        unit=out_unit,
        periods=periods_out,
        cumulative_impact=round(cumulative, 2),
        total_volume=round(total_volume, 4),
    )


# ── Negotiation Brief ─────────────────────────────────────────

def calculate_brief(
    db: Session,
    cost_model: CostModel,
    request: BriefRequest,
) -> BriefResult:
    fv = cost_model.current_formula
    model_ccy = cost_model.currency
    model_unit = cost_model.product.unit
    out_ccy = _output_ccy(model_ccy, request.display_currency)
    out_unit = _output_unit(model_unit, request.display_unit)

    if not fv:
        return BriefResult(
            product_name=cost_model.product.name,
            supplier_name=cost_model.supplier.name if cost_model.supplier else None,
            destination_country=cost_model.destination_country,
            currency=out_ccy, unit=out_unit,
            current_should_cost=0, current_actual_price=None,
            gap=None, gap_pct=None, total_impact=None,
            period_label="", evolution=[], narrative="No formula defined.",
            drivers=[],
        )

    base_price = float(fv.base_price)
    region = cost_model.region
    ref_year = fv.base_year
    ref_quarter = fv.base_quarter

    if request.from_year and request.from_quarter and request.to_year and request.to_quarter:
        from_y, from_q = request.from_year, request.from_quarter
        to_y, to_q = request.to_year, request.to_quarter
    else:
        from_y, from_q, to_y, to_q = _default_period_range(db, cost_model)

    periods = generate_periods(from_y, from_q, to_y, to_q, "quarterly")

    actuals = {}
    for ap in db.query(ActualPrice).filter(ActualPrice.cost_model_id == cost_model.id).all():
        actuals[(ap.year, ap.quarter)] = float(ap.price)

    raw_volumes = {}
    for av in db.query(ActualVolume).filter(ActualVolume.cost_model_id == cost_model.id).all():
        raw_volumes[(av.year, av.quarter)] = float(av.volume)

    evo_periods = []
    for year, quarter, month, label in periods:
        # Use the current formula for all periods (matches Evolution's default
        # "active" mode) so both pages produce identical theoretical lines.
        period_fv = fv
        period_base_price = base_price
        period_ref_year = ref_year
        period_ref_quarter = ref_quarter

        indexed_cost = _compute_indexed_cost(
            db, period_fv, cost_model, region,
            period_ref_year, period_ref_quarter, year, quarter, period_base_price
        )
        theoretical, _ = _apply_margin(indexed_cost, period_fv.margin_type, period_fv.margin_value, period_base_price)
        actual = actuals.get((year, quarter))

        theoretical = _apply_unit(_apply_fx(db, theoretical, model_ccy, out_ccy, year, quarter), model_unit, out_unit)
        if actual is not None:
            actual = _apply_unit(_apply_fx(db, actual, model_ccy, out_ccy, year, quarter), model_unit, out_unit)

        gap = (actual - theoretical) if actual is not None else None
        bp_display = _apply_unit(_apply_fx(db, period_base_price, model_ccy, out_ccy, year, quarter), model_unit, out_unit)
        gap_pct = (gap / bp_display * 100) if (gap is not None and bp_display) else None

        evo_periods.append(EvolutionPeriod(
            period=label, year=year, quarter=quarter, month=month,
            theoretical=round(theoretical, 4),
            actual=round(actual, 4) if actual is not None else None,
            gap=round(gap, 4) if gap is not None else None,
            gap_pct=round(gap_pct, 2) if gap_pct is not None else None,
        ))

    last_period = evo_periods[-1] if evo_periods else None
    current_sc = last_period.theoretical if last_period else 0
    current_actual = last_period.actual if last_period else None
    current_gap = last_period.gap if last_period else None
    current_gap_pct = last_period.gap_pct if last_period else None

    total_impact = None
    if raw_volumes:
        total_impact = 0.0
        for ep in evo_periods:
            vol = raw_volumes.get((ep.year, ep.quarter), 0)
            if ep.gap is not None:
                total_impact += ep.gap * vol

    # Compute drivers using latest formula
    last_y, last_q = periods[-1][0], periods[-1][1]
    comp_base = _component_base(base_price, fv.margin_type, fv.margin_value)
    drivers = []
    for comp in fv.components:
        weight = float(comp.weight)
        idx_name = None
        idx_change_pct = 0.0
        ratio = 1.0

        if comp.commodity_id:
            ref_val = get_single_index_value(
                db, cost_model.team_id, comp.commodity_id, region, ref_year, ref_quarter
            )
            cur_val = get_single_index_value(
                db, cost_model.team_id, comp.commodity_id, region, last_y, last_q
            )
            if ref_val is not None and cur_val is not None and ref_val != 0:
                ratio = cur_val / ref_val
                idx_change_pct = (ratio - 1) * 100
            if comp.commodity:
                idx_name = comp.commodity.name

        contribution = _apply_unit(
            _apply_fx(db, comp_base * weight * (idx_change_pct / 100), model_ccy, out_ccy, last_y, last_q),
            model_unit, out_unit
        )
        comp_cost = _apply_unit(
            _apply_fx(db, comp_base * weight * ratio, model_ccy, out_ccy, last_y, last_q),
            model_unit, out_unit
        )
        direction = "up" if idx_change_pct > 1 else "down" if idx_change_pct < -1 else "flat"

        drivers.append(BriefDriver(
            component_label=comp.label,
            index_name=idx_name,
            index_change_pct=round(idx_change_pct, 2),
            contribution_to_gap=round(contribution, 4),
            component_cost=round(comp_cost, 4),
            direction=direction,
        ))

    drivers.sort(key=lambda d: abs(d.component_cost), reverse=True)

    period_label = f"{periods[0][3]} to {periods[-1][3]}" if periods else ""

    narrative = generate_narrative(
        product_name=cost_model.product.name,
        supplier_name=cost_model.supplier.name if cost_model.supplier else None,
        drivers=[d.model_dump() for d in drivers],
        gap=current_gap,
        gap_pct=current_gap_pct,
        total_impact=total_impact,
        currency=out_ccy,
        period_label=period_label,
        num_periods=len(periods),
    )

    return BriefResult(
        product_name=cost_model.product.name,
        supplier_name=cost_model.supplier.name if cost_model.supplier else None,
        destination_country=cost_model.destination_country,
        currency=out_ccy,
        unit=out_unit,
        current_should_cost=current_sc,
        current_actual_price=current_actual,
        gap=current_gap,
        gap_pct=current_gap_pct,
        total_impact=round(total_impact, 2) if total_impact is not None else None,
        period_label=period_label,
        evolution=evo_periods,
        narrative=narrative,
        drivers=drivers,
    )


# ── Price Change Analysis ─────────────────────────────────────

def calculate_price_change(
    db: Session,
    cost_model: CostModel,
    request: PriceChangeRequest,
) -> PriceChangeResult:
    """Compute the fair price change between two periods based on component index movements."""
    # Use period-aware formula for both from and to periods
    from_fv = _get_period_formula(cost_model, request.from_year, request.from_quarter)
    to_fv = _get_period_formula(cost_model, request.to_year, request.to_quarter)

    if not from_fv or not to_fv:
        return PriceChangeResult(
            product_name=cost_model.product.name,
            supplier_name=cost_model.supplier.name if cost_model.supplier else None,
            currency=cost_model.currency,
            unit=cost_model.product.unit,
            base_price=0,
            from_label=f"Q{request.from_quarter}-{str(request.from_year)[-2:]}",
            to_label=f"Q{request.to_quarter}-{str(request.to_year)[-2:]}",
            fair_change_pct=0,
            fair_new_price=0,
            margin_weight=0,
            components=[],
        )

    # Use the to-period formula for the analysis
    fv = to_fv
    base_price = float(fv.base_price)
    region = cost_model.region

    # Compute margin weight
    comp_base = _component_base(base_price, fv.margin_type, fv.margin_value)
    margin_weight = (base_price - comp_base) / base_price if base_price else 0

    components = []
    total_fair_change = 0.0

    for comp in fv.components:
        weight = float(comp.weight)
        # Weight relative to full price (not just component pool)
        full_weight = weight * (1 - margin_weight)

        idx_start = None
        idx_end = None
        idx_change_pct = 0.0

        if comp.commodity_id:
            ref_val = get_single_index_value(
                db, cost_model.team_id, comp.commodity_id, region,
                request.from_year, request.from_quarter,
            )
            cur_val = get_single_index_value(
                db, cost_model.team_id, comp.commodity_id, region,
                request.to_year, request.to_quarter,
            )
            if ref_val:
                idx_start = ref_val
            if cur_val:
                idx_end = cur_val
            if ref_val and cur_val:
                idx_change_pct = (cur_val / ref_val - 1) * 100

        contribution = full_weight * idx_change_pct
        total_fair_change += contribution

        components.append(PriceChangeComponent(
            label=comp.label,
            index_name=comp.commodity.name if comp.commodity else None,
            weight=round(full_weight * 100, 2),
            index_start=round(idx_start, 4) if idx_start else None,
            index_end=round(idx_end, 4) if idx_end else None,
            index_change_pct=round(idx_change_pct, 2),
            contribution_pct=round(contribution, 2),
        ))

    fair_new_price = base_price * (1 + total_fair_change / 100)

    return PriceChangeResult(
        product_name=cost_model.product.name,
        supplier_name=cost_model.supplier.name if cost_model.supplier else None,
        currency=cost_model.currency,
        unit=cost_model.product.unit,
        base_price=round(base_price, 4),
        from_label=f"Q{request.from_quarter}-{str(request.from_year)[-2:]}",
        to_label=f"Q{request.to_quarter}-{str(request.to_year)[-2:]}",
        fair_change_pct=round(total_fair_change, 2),
        fair_new_price=round(fair_new_price, 4),
        margin_weight=round(margin_weight * 100, 2),
        components=components,
    )


# ── Shared helpers ─────────────────────────────────────────────

def _component_base(base_price: float, margin_type: str, margin_value: float | None) -> float:
    """Compute the cost pool (base_price minus margin).
    Component weights sum to 1.0 and represent the composition of this pool,
    not the full price. Margin is re-applied separately by _apply_margin."""
    if margin_type == "pct" and margin_value is not None:
        pct = float(margin_value) / 100.0
        if pct >= 1.0:
            pct = 0.0
        return base_price * (1 - pct)
    elif margin_type == "fixed" and margin_value is not None:
        return base_price - float(margin_value)
    return base_price


def _compute_indexed_cost(
    db: Session,
    fv,
    cost_model: CostModel,
    region: str,
    ref_year: int,
    ref_quarter: int,
    target_year: int,
    target_quarter: int,
    base_price: float,
) -> float:
    """Compute the indexed cost for a given period using the formula components."""
    comp_base = _component_base(base_price, fv.margin_type, fv.margin_value)
    indexed_cost = 0.0
    for comp in fv.components:
        weight = float(comp.weight)
        if comp.commodity_id:
            ref_val = get_single_index_value(
                db, cost_model.team_id, comp.commodity_id, region, ref_year, ref_quarter
            )
            cur_val = get_single_index_value(
                db, cost_model.team_id, comp.commodity_id, region, target_year, target_quarter
            )
            ratio = (cur_val / ref_val) if (ref_val and cur_val) else 1.0
        else:
            ratio = 1.0
        indexed_cost += comp_base * weight * ratio
    return indexed_cost
