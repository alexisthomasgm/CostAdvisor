import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.product import Product
from app.models.team import TeamMembership
from app.routers.auth import get_current_user
from app.schemas.product import ProductCreate, ProductUpdate, ProductOut
from app.services.audit import log_event

router = APIRouter()


def require_team_access(db: Session, user: User, team_id: uuid.UUID):
    membership = db.query(TeamMembership).filter(
        TeamMembership.user_id == user.id,
        TeamMembership.team_id == team_id,
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this team")


@router.get("/", response_model=list[ProductOut])
def list_products(
    team_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_team_access(db, current_user, team_id)
    return db.query(Product).filter(Product.team_id == team_id).all()


@router.post("/", response_model=ProductOut, status_code=201)
def create_product(
    team_id: uuid.UUID,
    data: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_team_access(db, current_user, team_id)
    product = Product(
        team_id=team_id,
        created_by=current_user.id,
        name=data.name,
        formula=data.formula,
        active_content=data.active_content,
        unit=data.unit,
        chemical_family_id=data.chemical_family_id,
        custom_attributes=data.custom_attributes,
    )
    db.add(product)
    log_event(db, team_id, current_user.id, "create", "product", str(product.id),
              new_value={"name": data.name, "formula": data.formula, "unit": data.unit})
    db.commit()
    db.refresh(product)
    return product


@router.get("/{product_id}", response_model=ProductOut)
def get_product(
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    require_team_access(db, current_user, product.team_id)
    return product


@router.put("/{product_id}", response_model=ProductOut)
def update_product(
    product_id: uuid.UUID,
    data: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    require_team_access(db, current_user, product.team_id)

    prev = {"name": product.name, "formula": product.formula, "unit": product.unit}
    for field in ["name", "formula", "active_content", "unit", "chemical_family_id", "custom_attributes"]:
        val = getattr(data, field, None)
        if val is not None:
            setattr(product, field, val)

    log_event(db, product.team_id, current_user.id, "update", "product", str(product.id),
              previous_value=prev, new_value={"name": product.name, "formula": product.formula, "unit": product.unit})
    db.commit()
    db.refresh(product)
    return product


@router.delete("/{product_id}")
def delete_product(
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    require_team_access(db, current_user, product.team_id)
    log_event(db, product.team_id, current_user.id, "delete", "product", str(product.id),
              previous_value={"name": product.name})
    db.delete(product)
    db.commit()
    return {"status": "deleted"}
