import asyncio
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.index_data import (
    CommodityIndex, IndexValue, IndexOverride, TeamIndexSource,
)
from app.models.cost_model import CostModel, FormulaVersion, FormulaComponent
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.team import TeamMembership
from app.routers.auth import get_current_user
from app.schemas.index_data import (
    CommodityIndexOut, IndexValueOut,
    TeamIndexSourceCreate, TeamIndexSourceOut, ScrapeNowResult,
    CellOverrideRequest, BulkOverrideRequest,
    FilterOptionsOut, IndexImpactItem, IndexImpactResponse,
)
from app.services.data_resolver import resolve_index_values
from app.services.file_parser import parse_index_upload
from app.services.scraper import GenericWebScraper, smart_scrape, smart_scrape_all, detect_source_type, ScrapedDataPoint
from app.services.audit import log_event

router = APIRouter()


def require_super_admin(user: User):
    if not user.is_super_admin:
        raise HTTPException(status_code=403, detail="Super admin required")


def require_team_access(db: Session, user: User, team_id: uuid.UUID):
    if user.is_super_admin:
        return
    membership = db.query(TeamMembership).filter(
        TeamMembership.user_id == user.id,
        TeamMembership.team_id == team_id,
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this team")


@router.get("/", response_model=list[CommodityIndexOut])
def list_commodities(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(CommodityIndex).order_by(CommodityIndex.name).all()


@router.get("/values", response_model=list[IndexValueOut])
def get_index_values(
    team_id: uuid.UUID,
    region: str | None = Query(None),
    commodity_name: str | None = Query(None),
    year: int | None = Query(None),
    quarter: int | None = Query(None),
    product_id: uuid.UUID | None = Query(None),
    supplier_id: int | None = Query(None),
    from_year: int | None = Query(None),
    from_quarter: int | None = Query(None),
    to_year: int | None = Query(None),
    to_quarter: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_team_access(db, current_user, team_id)
    # Resolve commodity IDs for product/supplier filter
    commodity_ids = None
    if product_id or supplier_id:
        commodity_ids = _resolve_commodity_ids(db, team_id, product_id, supplier_id)

    return resolve_index_values(
        db=db,
        team_id=team_id,
        region=region,
        commodity_name=commodity_name,
        year=year,
        quarter=quarter,
        commodity_ids=commodity_ids,
        from_year=from_year,
        from_quarter=from_quarter,
        to_year=to_year,
        to_quarter=to_quarter,
    )


@router.post("/upload")
async def upload_global_indexes(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload global index data (super admin only). Writes to index_values table."""
    require_super_admin(current_user)

    content = await file.read()
    filename = file.filename or "upload"
    rows = parse_index_upload(content, filename)

    count = 0
    for row in rows:
        commodity = db.query(CommodityIndex).filter(
            CommodityIndex.name == row["material"]
        ).first()
        if not commodity:
            continue

        existing = db.query(IndexValue).filter(
            IndexValue.commodity_id == commodity.id,
            IndexValue.region == row["region"],
            IndexValue.year == row["year"],
            IndexValue.quarter == row["quarter"],
        ).first()

        if existing:
            existing.value = row["value"]
            existing.source = "admin_upload"
        else:
            iv = IndexValue(
                commodity_id=commodity.id,
                region=row["region"],
                year=row["year"],
                quarter=row["quarter"],
                value=row["value"],
                source="admin_upload",
            )
            db.add(iv)
        count += 1

    log_event(db, uuid.UUID("00000000-0000-0000-0000-000000000000"), current_user.id,
              "upload", "global_indexes", filename, new_value={"rows": count})
    db.commit()
    return {"status": "uploaded", "rows_processed": count, "filename": filename}


@router.post("/overrides")
async def upload_index_overrides(
    team_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload team-specific index overrides."""
    require_team_access(db, current_user, team_id)
    content = await file.read()
    filename = file.filename or "upload"
    rows = parse_index_upload(content, filename)

    count = 0
    for row in rows:
        commodity = db.query(CommodityIndex).filter(
            CommodityIndex.name == row["material"]
        ).first()
        if not commodity:
            continue

        existing = db.query(IndexOverride).filter(
            IndexOverride.team_id == team_id,
            IndexOverride.commodity_id == commodity.id,
            IndexOverride.region == row["region"],
            IndexOverride.year == row["year"],
            IndexOverride.quarter == row["quarter"],
        ).first()

        if existing:
            existing.value = row["value"]
            existing.uploaded_by = current_user.id
            existing.source_file = filename
        else:
            override = IndexOverride(
                team_id=team_id,
                commodity_id=commodity.id,
                region=row["region"],
                year=row["year"],
                quarter=row["quarter"],
                value=row["value"],
                uploaded_by=current_user.id,
                source_file=filename,
            )
            db.add(override)
        count += 1

    log_event(db, team_id, current_user.id, "upload", "index_overrides", filename,
              new_value={"rows": count})
    db.commit()
    return {"status": "uploaded", "rows_processed": count, "filename": filename}


# --- Cell-level and bulk override endpoints ---


@router.put("/overrides/cell", response_model=IndexValueOut)
def cell_override(
    body: CellOverrideRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upsert a single cell override. Returns the updated enriched IndexValueOut."""
    require_team_access(db, current_user, body.team_id)
    # Verify commodity exists
    commodity = db.query(CommodityIndex).filter(
        CommodityIndex.id == body.commodity_id
    ).first()
    if not commodity:
        raise HTTPException(status_code=404, detail="Commodity not found")

    now = datetime.now(timezone.utc)

    existing = db.query(IndexOverride).filter(
        IndexOverride.team_id == body.team_id,
        IndexOverride.commodity_id == body.commodity_id,
        IndexOverride.region == body.region,
        IndexOverride.year == body.year,
        IndexOverride.quarter == body.quarter,
    ).first()

    if existing:
        existing.value = body.value
        existing.uploaded_by = current_user.id
        existing.source_file = "inline_edit"
        existing.uploaded_at = now
        override = existing
    else:
        override = IndexOverride(
            team_id=body.team_id,
            commodity_id=body.commodity_id,
            region=body.region,
            year=body.year,
            quarter=body.quarter,
            value=body.value,
            uploaded_by=current_user.id,
            source_file="inline_edit",
            uploaded_at=now,
        )
        db.add(override)
        db.flush()

    # Get the scraped value for this cell
    iv = db.query(IndexValue).filter(
        IndexValue.commodity_id == body.commodity_id,
        IndexValue.region == body.region,
        IndexValue.year == body.year,
        IndexValue.quarter == body.quarter,
    ).first()

    log_event(db, body.team_id, current_user.id, "override", "index_cell",
              f"{commodity.name}/{body.region}/Q{body.quarter}-{body.year}",
              new_value={"value": body.value})
    db.commit()

    return IndexValueOut(
        commodity_id=body.commodity_id,
        commodity_name=commodity.name,
        region=body.region,
        year=body.year,
        quarter=body.quarter,
        value=float(body.value),
        source="team_override",
        scraped_value=float(iv.value) if iv else None,
        override_id=override.id,
        override_by=current_user.display_name,
        override_at=now.isoformat(),
    )


@router.put("/overrides/bulk")
def bulk_override(
    body: BulkOverrideRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Apply a value to multiple periods for a commodity+region."""
    require_team_access(db, current_user, body.team_id)
    commodity = db.query(CommodityIndex).filter(
        CommodityIndex.id == body.commodity_id
    ).first()
    if not commodity:
        raise HTTPException(status_code=404, detail="Commodity not found")

    now = datetime.now(timezone.utc)
    count = 0

    for period in body.periods:
        yr = period.get("year")
        qtr = period.get("quarter")
        if yr is None or qtr is None:
            continue

        existing = db.query(IndexOverride).filter(
            IndexOverride.team_id == body.team_id,
            IndexOverride.commodity_id == body.commodity_id,
            IndexOverride.region == body.region,
            IndexOverride.year == yr,
            IndexOverride.quarter == qtr,
        ).first()

        if existing:
            existing.value = body.value
            existing.uploaded_by = current_user.id
            existing.source_file = "bulk_edit"
            existing.uploaded_at = now
        else:
            db.add(IndexOverride(
                team_id=body.team_id,
                commodity_id=body.commodity_id,
                region=body.region,
                year=yr,
                quarter=qtr,
                value=body.value,
                uploaded_by=current_user.id,
                source_file="bulk_edit",
                uploaded_at=now,
            ))
        count += 1

    log_event(db, body.team_id, current_user.id, "override", "index_bulk",
              f"{commodity.name}/{body.region}",
              new_value={"value": body.value, "periods": count})
    db.commit()
    return {"status": "ok", "cells_updated": count}


@router.delete("/overrides/bulk")
def delete_overrides_bulk(
    team_id: uuid.UUID,
    commodity_id: int,
    region: str,
    year: int | None = Query(None),
    quarter: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reset overrides. With year+quarter: single cell. Without: all for commodity+region+team."""
    require_team_access(db, current_user, team_id)
    query = db.query(IndexOverride).filter(
        IndexOverride.team_id == team_id,
        IndexOverride.commodity_id == commodity_id,
        IndexOverride.region == region,
    )

    if year is not None and quarter is not None:
        query = query.filter(
            IndexOverride.year == year,
            IndexOverride.quarter == quarter,
        )

    count = query.count()
    query.delete(synchronize_session=False)

    log_event(db, team_id, current_user.id, "delete", "index_overrides",
              f"commodity={commodity_id}/region={region}",
              new_value={"deleted": count})
    db.commit()
    return {"status": "deleted", "count": count}


@router.delete("/overrides/{override_id}")
def delete_override(
    override_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    override = db.query(IndexOverride).filter(IndexOverride.id == override_id).first()
    if not override:
        raise HTTPException(status_code=404, detail="Override not found")
    require_team_access(db, current_user, override.team_id)
    log_event(db, override.team_id, current_user.id, "delete", "index_override", str(override_id),
              previous_value={
                  "commodity_id": override.commodity_id,
                  "region": override.region,
                  "year": override.year,
                  "quarter": override.quarter,
                  "value": float(override.value) if override.value is not None else None,
              })
    db.delete(override)
    db.commit()
    return {"status": "deleted"}


# --- TeamIndexSource CRUD ---


@router.get("/sources", response_model=list[TeamIndexSourceOut])
def list_team_sources(
    team_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all configured index sources for a team, enriched with commodity name and scrape status."""
    require_team_access(db, current_user, team_id)
    sources = (
        db.query(TeamIndexSource)
        .filter(TeamIndexSource.team_id == team_id)
        .order_by(TeamIndexSource.commodity_id, TeamIndexSource.region)
        .all()
    )

    results = []
    for s in sources:
        # Get commodity name
        commodity = db.query(CommodityIndex).filter(
            CommodityIndex.id == s.commodity_id
        ).first()

        # Derive last scrape status from most recent IndexOverride with scrape: source_file
        last_scrape = (
            db.query(IndexOverride)
            .filter(
                IndexOverride.team_id == s.team_id,
                IndexOverride.commodity_id == s.commodity_id,
                IndexOverride.region == s.region,
                IndexOverride.source_file.like("scrape:%"),
            )
            .order_by(IndexOverride.uploaded_at.desc())
            .first()
        )

        results.append(TeamIndexSourceOut(
            id=s.id,
            team_id=s.team_id,
            commodity_id=s.commodity_id,
            region=s.region,
            source_type=s.source_type,
            scrape_url=s.scrape_url,
            scrape_config=s.scrape_config,
            source_file=s.source_file,
            created_by=s.created_by,
            updated_at=s.updated_at,
            commodity_name=commodity.name if commodity else None,
            last_scrape_status="ok" if last_scrape else None,
            last_scrape_at=last_scrape.uploaded_at.isoformat() if last_scrape else None,
        ))

    return results


@router.post("/sources", response_model=TeamIndexSourceOut)
async def create_or_update_team_source(
    body: TeamIndexSourceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create or update a team index source configuration.

    When source_type is scrape_url, automatically triggers a scrape on save:
    clears old overrides, populates all returned periods, interpolates gaps,
    and blanks periods outside the new source's range.
    """
    require_team_access(db, current_user, body.team_id)
    if body.source_type == "scrape_url" and not body.scrape_url:
        raise HTTPException(
            status_code=422, detail="scrape_url required when source_type is scrape_url"
        )

    # Verify commodity exists
    commodity = db.query(CommodityIndex).filter(
        CommodityIndex.id == body.commodity_id
    ).first()
    if not commodity:
        raise HTTPException(status_code=404, detail="Commodity not found")

    existing = db.query(TeamIndexSource).filter(
        TeamIndexSource.team_id == body.team_id,
        TeamIndexSource.commodity_id == body.commodity_id,
        TeamIndexSource.region == body.region,
    ).first()

    if existing:
        existing.source_type = body.source_type
        existing.scrape_url = body.scrape_url
        existing.scrape_config = body.scrape_config
        existing.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)
        source = existing
    else:
        source = TeamIndexSource(
            team_id=body.team_id,
            commodity_id=body.commodity_id,
            region=body.region,
            source_type=body.source_type,
            scrape_url=body.scrape_url,
            scrape_config=body.scrape_config,
            created_by=current_user.id,
        )
        db.add(source)
        db.commit()
        db.refresh(source)

    # Auto-scrape on save for scrape_url sources
    if body.source_type == "scrape_url" and body.scrape_url:
        try:
            await _scrape_and_replace_overrides(db, source, current_user)
        except Exception:
            pass  # scrape failure shouldn't block saving the source config

    return TeamIndexSourceOut(
        id=source.id,
        team_id=source.team_id,
        commodity_id=source.commodity_id,
        region=source.region,
        source_type=source.source_type,
        scrape_url=source.scrape_url,
        scrape_config=source.scrape_config,
        source_file=source.source_file,
        created_by=source.created_by,
        updated_at=source.updated_at,
        commodity_name=commodity.name,
    )


@router.delete("/sources/{source_id}")
def delete_team_source(
    source_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a team index source configuration."""
    source = db.query(TeamIndexSource).filter(TeamIndexSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    require_team_access(db, current_user, source.team_id)
    db.query(IndexOverride).filter(
        IndexOverride.team_id == source.team_id,
        IndexOverride.commodity_id == source.commodity_id,
        IndexOverride.region == source.region,
    ).delete()
    db.delete(source)
    db.commit()
    return {"status": "deleted"}


@router.get("/detect-source")
def detect_source(
    url: str = Query(...),
    current_user: User = Depends(get_current_user),
):
    """Detect the source type for a URL (e.g. INSEE IDBANK detection)."""
    source_type, idbank = detect_source_type(url)
    return {"detected_source": source_type, "idbank": idbank}


@router.post("/sources/{source_id}/scrape-now", response_model=ScrapeNowResult)
async def scrape_now(
    source_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Trigger an immediate scrape for a team source. Uses smart dispatch for known URL patterns."""
    source = db.query(TeamIndexSource).filter(TeamIndexSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    require_team_access(db, current_user, source.team_id)
    if source.source_type != "scrape_url":
        raise HTTPException(status_code=400, detail="Source is not a scrape_url type")
    if not source.scrape_url:
        raise HTTPException(status_code=400, detail="No scrape URL configured")

    try:
        latest_value, detected = await _scrape_and_replace_overrides(db, source, current_user)
    except Exception as exc:
        return ScrapeNowResult(source_id=source_id, status="error", error=str(exc))

    return ScrapeNowResult(source_id=source_id, status="ok", value=latest_value, detected_source=detected)


async def _scrape_and_replace_overrides(
    db: Session,
    source: TeamIndexSource,
    current_user: User,
) -> tuple[float, str]:
    """Scrape all available data, clear old overrides, insert new ones with
    linear interpolation for gaps between scraped periods.

    Returns (latest_value, detected_source).
    Raises on scrape failure or empty data.
    """
    points, detected = await smart_scrape_all(source.scrape_url, source.scrape_config)
    if not points:
        raise ValueError("No data returned from source")

    # Sort by time and interpolate gaps between scraped data points
    points.sort(key=lambda p: (p.year, p.quarter))
    filled = []
    for i, point in enumerate(points):
        filled.append(point)
        if i + 1 < len(points):
            nxt = points[i + 1]
            # Walk quarter-by-quarter between this point and the next
            y, q = point.year, point.quarter
            gaps = []
            while True:
                q += 1
                if q > 4:
                    q = 1
                    y += 1
                if (y, q) == (nxt.year, nxt.quarter):
                    break
                gaps.append((y, q))
            # Linearly interpolate across the gap
            for j, (gy, gq) in enumerate(gaps):
                frac = (j + 1) / (len(gaps) + 1)
                interp = point.value + frac * (nxt.value - point.value)
                filled.append(ScrapedDataPoint(
                    region=source.region,
                    year=gy,
                    quarter=gq,
                    value=round(interp, 4),
                ))

    # Build set of periods covered by the new source
    now = datetime.now(timezone.utc)
    filled_periods = {(p.year, p.quarter) for p in filled}

    # Find all base source periods for this commodity+region that the new
    # source does NOT cover — these need null overrides to blank them out.
    base_periods = db.query(IndexValue.year, IndexValue.quarter).filter(
        IndexValue.commodity_id == source.commodity_id,
        IndexValue.region == source.region,
    ).all()

    # Clear all existing overrides for this team/commodity/region
    db.query(IndexOverride).filter(
        IndexOverride.team_id == source.team_id,
        IndexOverride.commodity_id == source.commodity_id,
        IndexOverride.region == source.region,
    ).delete()

    # Insert overrides for scraped + interpolated periods
    latest_value = None
    for point in filled:
        db.add(IndexOverride(
            team_id=source.team_id,
            commodity_id=source.commodity_id,
            region=source.region,
            year=point.year,
            quarter=point.quarter,
            value=point.value,
            uploaded_by=current_user.id,
            source_file=f"scrape:{source.scrape_url}",
        ))
        latest_value = point.value

    # Insert null overrides to blank out base periods not in the new source
    for year, quarter in base_periods:
        if (year, quarter) not in filled_periods:
            db.add(IndexOverride(
                team_id=source.team_id,
                commodity_id=source.commodity_id,
                region=source.region,
                year=year,
                quarter=quarter,
                value=None,
                uploaded_by=current_user.id,
                source_file=f"scrape:{source.scrape_url}",
            ))

    log_event(db, source.team_id, current_user.id, "scrape", "team_index_source", str(source.id),
              new_value={
                  "scrape_url": source.scrape_url,
                  "commodity_id": source.commodity_id,
                  "region": source.region,
                  "points_written": len(filled),
                  "latest_value": latest_value,
              })
    db.commit()
    return latest_value, detected


# --- Helper: resolve commodity IDs from product/supplier ---


def _resolve_commodity_ids(
    db: Session,
    team_id: uuid.UUID,
    product_id: uuid.UUID | None = None,
    supplier_id: int | None = None,
) -> set[int]:
    """Get the set of commodity_ids used by a product's or supplier's cost models."""
    query = (
        db.query(FormulaComponent.commodity_id)
        .join(FormulaVersion, FormulaVersion.id == FormulaComponent.formula_version_id)
        .join(CostModel, CostModel.id == FormulaVersion.cost_model_id)
        .filter(
            CostModel.team_id == team_id,
            FormulaComponent.commodity_id.isnot(None),
        )
    )
    if product_id:
        query = query.filter(CostModel.product_id == product_id)
    if supplier_id:
        query = query.filter(CostModel.supplier_id == supplier_id)

    return {row[0] for row in query.distinct().all()}


# --- Filter options endpoint ---


@router.get("/filter-options", response_model=FilterOptionsOut)
def get_filter_options(
    team_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return filter dropdown options for the indexes page."""
    require_team_access(db, current_user, team_id)
    products = (
        db.query(Product.id, Product.name)
        .filter(Product.team_id == team_id)
        .order_by(Product.name)
        .all()
    )
    suppliers = (
        db.query(Supplier.id, Supplier.name)
        .filter(Supplier.team_id == team_id)
        .order_by(Supplier.name)
        .all()
    )
    regions = (
        db.query(IndexValue.region)
        .distinct()
        .order_by(IndexValue.region)
        .all()
    )
    materials = (
        db.query(CommodityIndex.name)
        .order_by(CommodityIndex.name)
        .all()
    )

    return FilterOptionsOut(
        products=[{"id": str(p.id), "name": p.name} for p in products],
        suppliers=[{"id": s.id, "name": s.name} for s in suppliers],
        regions=[r[0] for r in regions],
        materials=[m[0] for m in materials],
    )


# --- Portfolio impact endpoint ---


@router.get("/{commodity_id}/impact", response_model=IndexImpactResponse)
def get_index_impact(
    commodity_id: int,
    team_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the portfolio impact of an index: which products use it and how much it's changed."""
    require_team_access(db, current_user, team_id)
    from app.services.data_resolver import get_single_index_value

    commodity = db.query(CommodityIndex).filter(CommodityIndex.id == commodity_id).first()
    if not commodity:
        raise HTTPException(status_code=404, detail="Commodity not found")

    # Subquery: earliest formula version per cost model (first baseline)
    # Using the earliest base period gives a meaningful index change over time,
    # rather than comparing the latest version's base period to current (which
    # is often the same quarter, yielding 0% change).
    from sqlalchemy import func
    earliest_fv = (
        db.query(
            FormulaVersion.cost_model_id,
            func.min(FormulaVersion.id).label("min_fv_id"),
        )
        .group_by(FormulaVersion.cost_model_id)
        .subquery()
    )

    # Find formula components from the earliest version of each cost model
    components = (
        db.query(
            FormulaComponent,
            FormulaVersion,
            CostModel,
            Product.name.label("product_name"),
            Supplier.name.label("supplier_name"),
        )
        .join(FormulaVersion, FormulaVersion.id == FormulaComponent.formula_version_id)
        .join(CostModel, CostModel.id == FormulaVersion.cost_model_id)
        .join(earliest_fv, earliest_fv.c.min_fv_id == FormulaVersion.id)
        .join(Product, Product.id == CostModel.product_id)
        .outerjoin(Supplier, Supplier.id == CostModel.supplier_id)
        .filter(
            FormulaComponent.commodity_id == commodity_id,
            CostModel.team_id == team_id,
        )
        .all()
    )

    impacts = []
    now = datetime.now(timezone.utc)
    current_year = now.year
    current_quarter = (now.month - 1) // 3 + 1

    for comp, fv, cm, product_name, supplier_name in components:
        # Get base period index value
        base_val = get_single_index_value(
            db, team_id, commodity_id, cm.region,
            fv.base_year, fv.base_quarter,
        )
        # Get current period index value
        current_val = get_single_index_value(
            db, team_id, commodity_id, cm.region,
            current_year, current_quarter,
        )

        change_pct = None
        impact_pct = None
        if base_val and current_val and base_val != 0:
            change_pct = round((current_val / base_val - 1) * 100, 2)
            impact_pct = round(float(comp.weight) * change_pct, 2)

        impacts.append(IndexImpactItem(
            cost_model_id=cm.id,
            product_name=product_name,
            supplier_name=supplier_name,
            region=cm.region,
            component_label=comp.label,
            weight=float(comp.weight),
            base_index_value=base_val,
            current_index_value=current_val,
            index_change_pct=change_pct,
            cost_impact_pct=impact_pct,
        ))

    return IndexImpactResponse(
        commodity_id=commodity_id,
        commodity_name=commodity.name,
        unit=commodity.unit,
        currency=commodity.currency,
        source_url=commodity.source_url,
        impacts=impacts,
    )
