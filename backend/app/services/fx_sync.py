"""
Sync FX-category commodity index values into the fx_rates table.

After FX exchange rate indexes (EUR/USD, GBP/EUR, etc.) are scraped,
this module copies their values into the fx_rates table so the cost
engine and portfolio calculations can use them for currency conversion.
"""
from sqlalchemy.orm import Session

from app.models.index_data import CommodityIndex, IndexValue
from app.models.fx_rate import FxRate


# Map commodity name to (from_currency, to_currency)
_FX_PAIR_MAP = {
    "EUR/USD": ("EUR", "USD"),
    "GBP/EUR": ("GBP", "EUR"),
    "CNY/EUR": ("CNY", "EUR"),
    "JPY/EUR": ("JPY", "EUR"),
    "IDR/EUR": ("IDR", "EUR"),
    "PHP/EUR": ("PHP", "EUR"),
}


def sync_fx_rates(db: Session) -> int:
    """
    Copy FX-category index values into the fx_rates table.
    Returns the number of rows upserted.
    """
    # Get all FX-category commodities
    fx_commodities = (
        db.query(CommodityIndex)
        .filter(CommodityIndex.category == "FX")
        .all()
    )

    count = 0
    for commodity in fx_commodities:
        pair = _FX_PAIR_MAP.get(commodity.name)
        if not pair:
            continue
        from_ccy, to_ccy = pair

        # Get all index values for this FX commodity
        values = (
            db.query(IndexValue)
            .filter(IndexValue.commodity_id == commodity.id)
            .all()
        )

        for iv in values:
            existing = db.query(FxRate).filter(
                FxRate.from_currency == from_ccy,
                FxRate.to_currency == to_ccy,
                FxRate.year == iv.year,
                FxRate.quarter == iv.quarter,
            ).first()

            if existing:
                existing.rate = iv.value
            else:
                db.add(FxRate(
                    from_currency=from_ccy,
                    to_currency=to_ccy,
                    year=iv.year,
                    quarter=iv.quarter,
                    rate=iv.value,
                    # Use a system UUID for automated syncs
                    uploaded_by="00000000-0000-0000-0000-000000000000",
                ))
            count += 1

    db.commit()
    return count
