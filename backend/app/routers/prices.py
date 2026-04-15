import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.cost_model import CostModel
from app.models.price_data import ActualPrice
from app.models.team import TeamMembership
from app.routers.auth import get_current_user
from app.schemas.price_data import ActualPriceOut, ActualPriceCreate
from app.services.file_parser import parse_price_upload
from app.services.audit import log_event

router = APIRouter()


def require_model_access(db: Session, user: User, cm: CostModel):
    membership = db.query(TeamMembership).filter(
        TeamMembership.user_id == user.id,
        TeamMembership.team_id == cm.team_id,
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this team")


@router.get("/{cost_model_id}", response_model=list[ActualPriceOut])
def get_actual_prices(
    cost_model_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cm = db.query(CostModel).filter(CostModel.id == cost_model_id).first()
    if not cm:
        raise HTTPException(status_code=404, detail="Cost model not found")
    require_model_access(db, current_user, cm)
    prices = (
        db.query(ActualPrice)
        .filter(ActualPrice.cost_model_id == cost_model_id)
        .order_by(ActualPrice.year, ActualPrice.quarter)
        .all()
    )
    return [ActualPriceOut.model_validate(p) for p in prices]


@router.post("/{cost_model_id}/upload")
async def upload_prices(
    cost_model_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cm = db.query(CostModel).filter(CostModel.id == cost_model_id).first()
    if not cm:
        raise HTTPException(status_code=404, detail="Cost model not found")
    require_model_access(db, current_user, cm)

    content = await file.read()
    filename = file.filename or "upload"
    rows = parse_price_upload(content, filename)

    count = 0
    for row in rows:
        existing = db.query(ActualPrice).filter(
            ActualPrice.cost_model_id == cost_model_id,
            ActualPrice.year == row["year"],
            ActualPrice.quarter == row["quarter"],
        ).first()

        if existing:
            existing.price = row["price"]
            existing.uploaded_by = current_user.id
            existing.source_file = filename
        else:
            ap = ActualPrice(
                cost_model_id=cost_model_id,
                uploaded_by=current_user.id,
                year=row["year"],
                quarter=row["quarter"],
                price=row["price"],
                source_file=filename,
            )
            db.add(ap)
        count += 1

    db.commit()
    log_event(db, cm.team_id, current_user.id, "create", "price_data", str(cost_model_id),
              new_value={"rows_processed": count, "filename": filename})
    db.commit()
    return {"status": "uploaded", "rows_processed": count, "filename": filename}


@router.put("/{cost_model_id}/{year}/{quarter}", response_model=ActualPriceOut)
def update_price(
    cost_model_id: uuid.UUID,
    year: int,
    quarter: int,
    data: ActualPriceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cm = db.query(CostModel).filter(CostModel.id == cost_model_id).first()
    if not cm:
        raise HTTPException(status_code=404, detail="Cost model not found")
    require_model_access(db, current_user, cm)

    existing = db.query(ActualPrice).filter(
        ActualPrice.cost_model_id == cost_model_id,
        ActualPrice.year == year,
        ActualPrice.quarter == quarter,
    ).first()

    previous = float(existing.price) if existing else None
    if existing:
        existing.price = data.price
        existing.uploaded_by = current_user.id
    else:
        existing = ActualPrice(
            cost_model_id=cost_model_id,
            uploaded_by=current_user.id,
            year=data.year,
            quarter=data.quarter,
            price=data.price,
        )
        db.add(existing)

    log_event(db, cm.team_id, current_user.id, "update", "price_data", str(cost_model_id),
              previous_value={"year": year, "quarter": quarter, "price": previous} if previous is not None else None,
              new_value={"year": year, "quarter": quarter, "price": float(data.price)})
    db.commit()
    db.refresh(existing)
    return ActualPriceOut.model_validate(existing)


@router.delete("/{cost_model_id}/{year}/{quarter}")
def delete_price(
    cost_model_id: uuid.UUID,
    year: int,
    quarter: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cm = db.query(CostModel).filter(CostModel.id == cost_model_id).first()
    if not cm:
        raise HTTPException(status_code=404, detail="Cost model not found")
    require_model_access(db, current_user, cm)

    price = db.query(ActualPrice).filter(
        ActualPrice.cost_model_id == cost_model_id,
        ActualPrice.year == year,
        ActualPrice.quarter == quarter,
    ).first()

    if not price:
        raise HTTPException(status_code=404, detail="Price not found")

    log_event(db, cm.team_id, current_user.id, "delete", "price_data", str(cost_model_id),
              previous_value={"year": year, "quarter": quarter, "price": float(price.price)})
    db.delete(price)
    db.commit()
    return {"status": "deleted"}
