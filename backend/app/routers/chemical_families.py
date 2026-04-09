from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.chemical_family import ChemicalFamily
from app.routers.auth import get_current_user
from app.schemas.chemical_family import ChemicalFamilyCreate, ChemicalFamilyOut

router = APIRouter()


def require_super_admin(user: User):
    if not user.is_super_admin:
        raise HTTPException(status_code=403, detail="Super admin required")


@router.get("/", response_model=list[ChemicalFamilyOut])
def list_families(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return db.query(ChemicalFamily).order_by(ChemicalFamily.name).all()


@router.post("/", response_model=ChemicalFamilyOut, status_code=201)
def create_family(
    data: ChemicalFamilyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_super_admin(current_user)
    family = ChemicalFamily(
        name=data.name,
        custom_attribute_schema=data.custom_attribute_schema,
    )
    db.add(family)
    db.commit()
    db.refresh(family)
    return family


@router.delete("/{family_id}")
def delete_family(
    family_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_super_admin(current_user)
    family = db.query(ChemicalFamily).filter(ChemicalFamily.id == family_id).first()
    if not family:
        raise HTTPException(status_code=404, detail="Chemical family not found")
    db.delete(family)
    db.commit()
    return {"status": "deleted"}
