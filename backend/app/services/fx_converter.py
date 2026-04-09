"""FX rate lookup and currency conversion."""
from sqlalchemy.orm import Session

from app.models.fx_rate import FxRate


def get_fx_rate(
    db: Session,
    from_ccy: str,
    to_ccy: str,
    year: int,
    quarter: int,
) -> float | None:
    """Look up FX rate from the fx_rates table. Returns None if not found."""
    if from_ccy == to_ccy:
        return 1.0

    rate = db.query(FxRate).filter(
        FxRate.from_currency == from_ccy,
        FxRate.to_currency == to_ccy,
        FxRate.year == year,
        FxRate.quarter == quarter,
    ).first()

    if rate:
        return float(rate.rate)

    # Try the inverse
    inverse = db.query(FxRate).filter(
        FxRate.from_currency == to_ccy,
        FxRate.to_currency == from_ccy,
        FxRate.year == year,
        FxRate.quarter == quarter,
    ).first()

    if inverse and float(inverse.rate) != 0:
        return 1.0 / float(inverse.rate)

    return None


def convert_price(
    db: Session,
    value: float,
    from_ccy: str,
    to_ccy: str,
    year: int,
    quarter: int,
) -> float:
    """Convert a price from one currency to another. Returns original if no rate found."""
    rate = get_fx_rate(db, from_ccy, to_ccy, year, quarter)
    if rate is None:
        return value
    return value * rate
