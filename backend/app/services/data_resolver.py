"""
Data resolver: implements the override hierarchy.
Priority: team override > scraped value > fallback.
"""
import uuid
from sqlalchemy.orm import Session
from sqlalchemy import text, and_, or_

from app.models.index_data import CommodityIndex, IndexValue, IndexOverride
from app.models.user import User
from app.schemas.index_data import IndexValueOut
from app.services.scraper import SCRAPER_REGISTRY, SCRAPER_SOURCE_LABELS


def resolve_index_values(
    db: Session,
    team_id: uuid.UUID,
    region: str | None = None,
    commodity_name: str | None = None,
    year: int | None = None,
    quarter: int | None = None,
    commodity_ids: set[int] | None = None,
    from_year: int | None = None,
    from_quarter: int | None = None,
    to_year: int | None = None,
    to_quarter: int | None = None,
) -> list[IndexValueOut]:
    """
    Get index values with team overrides applied.
    Returns a flat list of values, with override values replacing scraped values where they exist.
    Enriched with scraped_value, override_id, override_by, override_at.
    """
    # Build set of commodity names that have built-in scrapers
    scraped_commodities = set(SCRAPER_REGISTRY.keys())

    # Build base query for scraped values
    query = (
        db.query(
            IndexValue.commodity_id,
            CommodityIndex.name.label("commodity_name"),
            IndexValue.region,
            IndexValue.year,
            IndexValue.quarter,
            IndexValue.value,
            IndexValue.scraped_at,
        )
        .join(CommodityIndex, CommodityIndex.id == IndexValue.commodity_id)
    )

    if region:
        query = query.filter(IndexValue.region == region)
    if commodity_name:
        query = query.filter(CommodityIndex.name == commodity_name)
    if year:
        query = query.filter(IndexValue.year == year)
    if quarter:
        query = query.filter(IndexValue.quarter == quarter)

    # Product/supplier filter: restrict to specific commodity IDs
    if commodity_ids is not None:
        if not commodity_ids:
            return []  # No matching commodities
        query = query.filter(IndexValue.commodity_id.in_(commodity_ids))

    # Time range filter
    if from_year is not None and from_quarter is not None:
        query = query.filter(or_(
            IndexValue.year > from_year,
            and_(IndexValue.year == from_year, IndexValue.quarter >= from_quarter),
        ))
    if to_year is not None and to_quarter is not None:
        query = query.filter(or_(
            IndexValue.year < to_year,
            and_(IndexValue.year == to_year, IndexValue.quarter <= to_quarter),
        ))

    scraped = query.all()

    # Build dict of overrides for this team, storing full objects + user display name
    override_query = (
        db.query(IndexOverride, User.display_name)
        .outerjoin(User, User.id == IndexOverride.uploaded_by)
        .filter(IndexOverride.team_id == team_id)
    )
    if region:
        override_query = override_query.filter(IndexOverride.region == region)
    if year:
        override_query = override_query.filter(IndexOverride.year == year)
    if quarter:
        override_query = override_query.filter(IndexOverride.quarter == quarter)

    overrides = {}
    for o, display_name in override_query.all():
        key = (o.commodity_id, o.region, o.year, o.quarter)
        overrides[key] = (o, display_name)

    # Merge: override wins
    results = []
    for row in scraped:
        key = (row.commodity_id, row.region, row.year, row.quarter)
        override_entry = overrides.get(key)

        # Determine global scraper info for this commodity
        gs = SCRAPER_SOURCE_LABELS.get(row.commodity_name) if row.commodity_name in scraped_commodities else None
        gs_at = row.scraped_at.isoformat() if row.scraped_at else None

        if override_entry:
            o, display_name = override_entry
            results.append(IndexValueOut(
                commodity_id=row.commodity_id,
                commodity_name=row.commodity_name,
                region=row.region,
                year=row.year,
                quarter=row.quarter,
                value=float(o.value) if o.value is not None else None,
                source="team_blank" if o.value is None else "team_override",
                scraped_value=float(row.value),
                override_id=o.id,
                override_by=display_name,
                override_at=o.uploaded_at.isoformat() if o.uploaded_at else None,
                global_scraper=gs,
                global_scrape_at=gs_at,
            ))
        else:
            results.append(IndexValueOut(
                commodity_id=row.commodity_id,
                commodity_name=row.commodity_name,
                region=row.region,
                year=row.year,
                quarter=row.quarter,
                value=float(row.value),
                source="scraped",
                scraped_value=float(row.value),
                global_scraper=gs,
                global_scrape_at=gs_at,
            ))

    return results


def get_single_index_value(
    db: Session,
    team_id: uuid.UUID,
    commodity_id: int,
    region: str,
    year: int,
    quarter: int,
) -> float | None:
    """Get a single resolved index value (override > scraped)."""
    # Check override first (exact region, then GLOBAL fallback)
    override = db.query(IndexOverride).filter(
        IndexOverride.team_id == team_id,
        IndexOverride.commodity_id == commodity_id,
        IndexOverride.region == region,
        IndexOverride.year == year,
        IndexOverride.quarter == quarter,
    ).first()

    if not override and region != "GLOBAL":
        override = db.query(IndexOverride).filter(
            IndexOverride.team_id == team_id,
            IndexOverride.commodity_id == commodity_id,
            IndexOverride.region == "GLOBAL",
            IndexOverride.year == year,
            IndexOverride.quarter == quarter,
        ).first()

    if override:
        # Null override = intentional blank (team source doesn't cover this period)
        return float(override.value) if override.value is not None else None

    # Fall back to scraped
    iv = db.query(IndexValue).filter(
        IndexValue.commodity_id == commodity_id,
        IndexValue.region == region,
        IndexValue.year == year,
        IndexValue.quarter == quarter,
    ).first()

    if iv:
        return float(iv.value)

    # Fall back to GLOBAL region if region-specific value not found
    if region != "GLOBAL":
        iv = db.query(IndexValue).filter(
            IndexValue.commodity_id == commodity_id,
            IndexValue.region == "GLOBAL",
            IndexValue.year == year,
            IndexValue.quarter == quarter,
        ).first()
        if iv:
            return float(iv.value)

    # Fall back to any region that has data for this commodity/period
    iv = db.query(IndexValue).filter(
        IndexValue.commodity_id == commodity_id,
        IndexValue.year == year,
        IndexValue.quarter == quarter,
    ).first()
    if iv:
        return float(iv.value)

    # Temporal fallback: carry forward the most recent available value.
    # This handles cases where the requested period (e.g. a future reference
    # quarter) doesn't have data yet — use the latest known value instead of
    # returning None (which would flatten all ratios to 1.0).
    from sqlalchemy import or_, and_
    iv = db.query(IndexValue).filter(
        IndexValue.commodity_id == commodity_id,
        or_(
            IndexValue.year < year,
            and_(IndexValue.year == year, IndexValue.quarter <= quarter),
        ),
    ).order_by(
        IndexValue.year.desc(),
        IndexValue.quarter.desc(),
    ).first()
    if iv:
        return float(iv.value)

    return None
