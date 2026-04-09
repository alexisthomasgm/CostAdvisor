import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.product import Product
from app.models.cost_model import CostModel, FormulaVersion, FormulaComponent
from app.models.index_data import CommodityIndex
from app.models.team import TeamMembership
from app.routers.auth import get_current_user
from app.schemas.cost_model import (
    CostModelCreate, CostModelUpdate, CostModelOut,
    FormulaVersionCreate, FormulaVersionOut,
)
from app.services.audit import log_event

router = APIRouter()


def resolve_commodity_id(db: Session, name: str) -> int | None:
    if not name:
        return None
    commodity = db.query(CommodityIndex).filter(CommodityIndex.name == name).first()
    return commodity.id if commodity else None


def require_team_access(db: Session, user: User, team_id: uuid.UUID):
    membership = db.query(TeamMembership).filter(
        TeamMembership.user_id == user.id,
        TeamMembership.team_id == team_id,
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this team")


def _build_cost_model_out(cm: CostModel) -> CostModelOut:
    out = CostModelOut.model_validate(cm)
    out.product_name = cm.product.name if cm.product else None
    out.product_reference = cm.product.formula if cm.product else None
    out.product_unit = cm.product.unit if cm.product else None
    out.product_active_content = cm.product.active_content if cm.product else None
    out.supplier_name = cm.supplier.name if cm.supplier else None
    return out


@router.get("/", response_model=list[CostModelOut])
def list_cost_models(
    team_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_team_access(db, current_user, team_id)
    models = db.query(CostModel).filter(CostModel.team_id == team_id).all()
    return [_build_cost_model_out(cm) for cm in models]


@router.post("/", response_model=CostModelOut, status_code=201)
def create_cost_model(
    team_id: uuid.UUID,
    data: CostModelCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_team_access(db, current_user, team_id)

    # Verify product exists and belongs to team
    product = db.query(Product).filter(Product.id == data.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if product.team_id != team_id:
        raise HTTPException(status_code=403, detail="Product does not belong to this team")

    cm = CostModel(
        team_id=team_id,
        product_id=data.product_id,
        supplier_id=data.supplier_id,
        destination_country=data.destination_country,
        region=data.region,
        currency=data.currency,
        created_by=current_user.id,
    )
    db.add(cm)
    db.flush()

    # Create first formula version
    fv = FormulaVersion(
        cost_model_id=cm.id,
        base_price=data.formula.base_price,
        base_year=data.formula.base_year,
        base_quarter=data.formula.base_quarter,
        margin_type=data.formula.margin_type,
        margin_value=data.formula.margin_value,
        notes=data.formula.notes,
    )
    db.add(fv)
    db.flush()

    for comp in data.formula.components:
        fc = FormulaComponent(
            formula_version_id=fv.id,
            label=comp.label,
            commodity_id=resolve_commodity_id(db, comp.commodity_name),
            weight=comp.weight,
        )
        db.add(fc)

    db.commit()
    db.refresh(cm)
    log_event(db, team_id, current_user.id, "create", "cost_model", str(cm.id),
              new_value={"product_id": str(data.product_id), "region": data.region, "currency": data.currency})
    db.commit()
    return _build_cost_model_out(cm)


@router.get("/{cost_model_id}", response_model=CostModelOut)
def get_cost_model(
    cost_model_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cm = db.query(CostModel).filter(CostModel.id == cost_model_id).first()
    if not cm:
        raise HTTPException(status_code=404, detail="Cost model not found")
    require_team_access(db, current_user, cm.team_id)
    return _build_cost_model_out(cm)


@router.put("/{cost_model_id}", response_model=CostModelOut)
def update_cost_model(
    cost_model_id: uuid.UUID,
    data: CostModelUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cm = db.query(CostModel).filter(CostModel.id == cost_model_id).first()
    if not cm:
        raise HTTPException(status_code=404, detail="Cost model not found")
    require_team_access(db, current_user, cm.team_id)

    changes = {}
    for field in ["supplier_id", "destination_country", "region", "currency"]:
        val = getattr(data, field, None)
        if val is not None:
            changes[field] = {"old": str(getattr(cm, field)), "new": str(val)}
            setattr(cm, field, val)

    db.commit()
    db.refresh(cm)
    if changes:
        log_event(db, cm.team_id, current_user.id, "update", "cost_model", str(cm.id), new_value=changes)
        db.commit()
    return _build_cost_model_out(cm)


@router.delete("/{cost_model_id}")
def delete_cost_model(
    cost_model_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cm = db.query(CostModel).filter(CostModel.id == cost_model_id).first()
    if not cm:
        raise HTTPException(status_code=404, detail="Cost model not found")
    require_team_access(db, current_user, cm.team_id)
    team_id = cm.team_id
    log_event(db, team_id, current_user.id, "delete", "cost_model", str(cm.id),
              previous_value={"product_id": str(cm.product_id), "region": cm.region})
    db.delete(cm)
    db.commit()
    return {"status": "deleted"}


@router.post("/{cost_model_id}/renegotiate", response_model=FormulaVersionOut, status_code=201)
def renegotiate(
    cost_model_id: uuid.UUID,
    data: FormulaVersionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upsert a formula version for a quarter. If one exists for the same quarter, update in place."""
    cm = db.query(CostModel).filter(CostModel.id == cost_model_id).first()
    if not cm:
        raise HTTPException(status_code=404, detail="Cost model not found")
    require_team_access(db, current_user, cm.team_id)

    # Check if a version exists for this quarter
    existing = db.query(FormulaVersion).filter(
        FormulaVersion.cost_model_id == cost_model_id,
        FormulaVersion.base_year == data.base_year,
        FormulaVersion.base_quarter == data.base_quarter,
    ).first()

    if existing:
        # Update in place
        existing.base_price = data.base_price
        existing.margin_type = data.margin_type
        existing.margin_value = data.margin_value
        existing.notes = data.notes
        existing.updated_at = datetime.now(timezone.utc)

        # Delete old components, create new ones
        db.query(FormulaComponent).filter(
            FormulaComponent.formula_version_id == existing.id
        ).delete()

        for comp in data.components:
            fc = FormulaComponent(
                formula_version_id=existing.id,
                label=comp.label,
                commodity_id=resolve_commodity_id(db, comp.commodity_name),
                weight=comp.weight,
            )
            db.add(fc)

        db.commit()
        db.refresh(existing)
        log_event(db, cm.team_id, current_user.id, "update", "formula_version", str(existing.id),
                  new_value={"cost_model_id": str(cost_model_id),
                             "quarter": f"Q{data.base_quarter}-{data.base_year}",
                             "base_price": str(existing.base_price), "margin_type": existing.margin_type})
        db.commit()
        return existing
    else:
        # New quarter — create new version
        fv = FormulaVersion(
            cost_model_id=cost_model_id,
            base_price=data.base_price,
            base_year=data.base_year,
            base_quarter=data.base_quarter,
            margin_type=data.margin_type,
            margin_value=data.margin_value,
            notes=data.notes,
        )
        db.add(fv)
        db.flush()

        for comp in data.components:
            fc = FormulaComponent(
                formula_version_id=fv.id,
                label=comp.label,
                commodity_id=resolve_commodity_id(db, comp.commodity_name),
                weight=comp.weight,
            )
            db.add(fc)

        db.commit()
        db.refresh(fv)
        log_event(db, cm.team_id, current_user.id, "create", "formula_version", str(fv.id),
                  new_value={"cost_model_id": str(cost_model_id),
                             "quarter": f"Q{data.base_quarter}-{data.base_year}",
                             "base_price": str(fv.base_price), "margin_type": fv.margin_type})
        db.commit()
        return fv


@router.get("/{cost_model_id}/versions", response_model=list[FormulaVersionOut])
def list_versions(
    cost_model_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cm = db.query(CostModel).filter(CostModel.id == cost_model_id).first()
    if not cm:
        raise HTTPException(status_code=404, detail="Cost model not found")
    require_team_access(db, current_user, cm.team_id)
    return (
        db.query(FormulaVersion)
        .filter(FormulaVersion.cost_model_id == cost_model_id)
        .order_by(FormulaVersion.base_year.desc(), FormulaVersion.base_quarter.desc())
        .all()
    )


@router.delete("/{cost_model_id}/versions/{version_id}")
def delete_version(
    cost_model_id: uuid.UUID,
    version_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cm = db.query(CostModel).filter(CostModel.id == cost_model_id).first()
    if not cm:
        raise HTTPException(status_code=404, detail="Cost model not found")
    require_team_access(db, current_user, cm.team_id)

    fv = db.query(FormulaVersion).filter(
        FormulaVersion.id == version_id,
        FormulaVersion.cost_model_id == cost_model_id,
    ).first()
    if not fv:
        raise HTTPException(status_code=404, detail="Formula version not found")

    # Don't allow deleting the last version
    count = db.query(FormulaVersion).filter(
        FormulaVersion.cost_model_id == cost_model_id,
    ).count()
    if count <= 1:
        raise HTTPException(status_code=400, detail="Cannot delete the only formula version")

    log_event(db, cm.team_id, current_user.id, "delete", "formula_version", str(fv.id),
              previous_value={"quarter": f"Q{fv.base_quarter}-{fv.base_year}", "base_price": str(fv.base_price)})
    db.delete(fv)
    db.commit()
    return {"status": "deleted"}


@router.post("/{cost_model_id}/clone", response_model=CostModelOut, status_code=201)
def clone_cost_model(
    cost_model_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    original = db.query(CostModel).filter(CostModel.id == cost_model_id).first()
    if not original:
        raise HTTPException(status_code=404, detail="Cost model not found")
    require_team_access(db, current_user, original.team_id)

    clone = CostModel(
        team_id=original.team_id,
        product_id=original.product_id,
        supplier_id=original.supplier_id,
        destination_country=original.destination_country,
        region=original.region,
        currency=original.currency,
        created_by=current_user.id,
    )
    db.add(clone)
    db.flush()

    # Clone the current formula version
    current_fv = original.current_formula
    if current_fv:
        fv = FormulaVersion(
            cost_model_id=clone.id,
            base_price=current_fv.base_price,
            base_year=current_fv.base_year,
            base_quarter=current_fv.base_quarter,
            margin_type=current_fv.margin_type,
            margin_value=current_fv.margin_value,
        )
        db.add(fv)
        db.flush()

        for comp in current_fv.components:
            fc = FormulaComponent(
                formula_version_id=fv.id,
                label=comp.label,
                commodity_id=comp.commodity_id,
                weight=comp.weight,
            )
            db.add(fc)

    db.commit()
    db.refresh(clone)
    return _build_cost_model_out(clone)
