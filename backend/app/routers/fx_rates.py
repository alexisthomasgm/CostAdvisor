from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.fx_rate import FxRate
from app.routers.auth import get_current_user
from app.schemas.fx_rate import FxRateOut
from app.services.file_parser import parse_fx_upload

router = APIRouter()


def require_super_admin(user: User):
    if not user.is_super_admin:
        raise HTTPException(status_code=403, detail="Super admin required")


@router.get("/", response_model=list[FxRateOut])
def list_fx_rates(
    from_currency: str | None = Query(None),
    to_currency: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(FxRate)
    if from_currency:
        query = query.filter(FxRate.from_currency == from_currency)
    if to_currency:
        query = query.filter(FxRate.to_currency == to_currency)
    return query.order_by(FxRate.year, FxRate.quarter).all()


@router.post("/upload")
async def upload_fx_rates(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_super_admin(current_user)

    content = await file.read()
    filename = file.filename or "upload"
    rows = parse_fx_upload(content, filename)

    count = 0
    for row in rows:
        existing = db.query(FxRate).filter(
            FxRate.from_currency == row["from_currency"],
            FxRate.to_currency == row["to_currency"],
            FxRate.year == row["year"],
            FxRate.quarter == row["quarter"],
        ).first()

        if existing:
            existing.rate = row["rate"]
            existing.uploaded_by = current_user.id
        else:
            fx = FxRate(
                from_currency=row["from_currency"],
                to_currency=row["to_currency"],
                year=row["year"],
                quarter=row["quarter"],
                rate=row["rate"],
                uploaded_by=current_user.id,
            )
            db.add(fx)
        count += 1

    db.commit()
    return {"status": "uploaded", "rows_processed": count, "filename": filename}
