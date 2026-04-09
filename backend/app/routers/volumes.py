import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.cost_model import CostModel
from app.models.actual_volume import ActualVolume
from app.models.team import TeamMembership
from app.routers.auth import get_current_user
from app.schemas.actual_volume import ActualVolumeOut, ActualVolumeCreate
from app.services.file_parser import parse_volume_upload
from app.services.audit import log_event

router = APIRouter()


def require_model_access(db: Session, user: User, cm: CostModel):
    membership = db.query(TeamMembership).filter(
        TeamMembership.user_id == user.id,
        TeamMembership.team_id == cm.team_id,
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this team")


@router.get("/{cost_model_id}", response_model=list[ActualVolumeOut])
def get_volumes(
    cost_model_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cm = db.query(CostModel).filter(CostModel.id == cost_model_id).first()
    if not cm:
        raise HTTPException(status_code=404, detail="Cost model not found")
    require_model_access(db, current_user, cm)
    return (
        db.query(ActualVolume)
        .filter(ActualVolume.cost_model_id == cost_model_id)
        .order_by(ActualVolume.year, ActualVolume.quarter)
        .all()
    )


@router.post("/{cost_model_id}/upload")
async def upload_volumes(
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
    rows = parse_volume_upload(content, filename)

    count = 0
    for row in rows:
        existing = db.query(ActualVolume).filter(
            ActualVolume.cost_model_id == cost_model_id,
            ActualVolume.year == row["year"],
            ActualVolume.quarter == row["quarter"],
        ).first()

        if existing:
            existing.volume = row["volume"]
            existing.unit = row.get("unit", "kg")
            existing.uploaded_by = current_user.id
            existing.source_file = filename
        else:
            av = ActualVolume(
                cost_model_id=cost_model_id,
                uploaded_by=current_user.id,
                year=row["year"],
                quarter=row["quarter"],
                volume=row["volume"],
                unit=row.get("unit", "kg"),
                source_file=filename,
            )
            db.add(av)
        count += 1

    db.commit()
    log_event(db, cm.team_id, current_user.id, "create", "actual_volume", str(cost_model_id),
              new_value={"rows_processed": count, "filename": filename})
    db.commit()
    return {"status": "uploaded", "rows_processed": count, "filename": filename}


@router.put("/{cost_model_id}/{year}/{quarter}", response_model=ActualVolumeOut)
def update_volume(
    cost_model_id: uuid.UUID,
    year: int,
    quarter: int,
    data: ActualVolumeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cm = db.query(CostModel).filter(CostModel.id == cost_model_id).first()
    if not cm:
        raise HTTPException(status_code=404, detail="Cost model not found")
    require_model_access(db, current_user, cm)

    existing = db.query(ActualVolume).filter(
        ActualVolume.cost_model_id == cost_model_id,
        ActualVolume.year == year,
        ActualVolume.quarter == quarter,
    ).first()

    if existing:
        existing.volume = data.volume
        existing.unit = data.unit
        existing.uploaded_by = current_user.id
    else:
        existing = ActualVolume(
            cost_model_id=cost_model_id,
            uploaded_by=current_user.id,
            year=data.year,
            quarter=data.quarter,
            volume=data.volume,
            unit=data.unit,
        )
        db.add(existing)

    db.commit()
    db.refresh(existing)
    return existing


@router.delete("/{cost_model_id}/{year}/{quarter}")
def delete_volume(
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

    vol = db.query(ActualVolume).filter(
        ActualVolume.cost_model_id == cost_model_id,
        ActualVolume.year == year,
        ActualVolume.quarter == quarter,
    ).first()

    if not vol:
        raise HTTPException(status_code=404, detail="Volume not found")

    db.delete(vol)
    db.commit()
    return {"status": "deleted"}
