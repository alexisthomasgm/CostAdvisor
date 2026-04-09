import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.scenario import CostScenario
from app.models.team import TeamMembership
from app.routers.auth import get_current_user
from app.schemas.scenario import ScenarioCreate, ScenarioOut

router = APIRouter()


@router.get("/", response_model=list[ScenarioOut])
def list_scenarios(
    team_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return system scenarios + team-specific scenarios."""
    query = db.query(CostScenario).filter(
        (CostScenario.is_system == True) |  # noqa: E712
        (CostScenario.team_id == team_id)
    )
    return query.all()


@router.post("/", response_model=ScenarioOut, status_code=201)
def create_scenario(
    team_id: uuid.UUID,
    data: ScenarioCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    scenario = CostScenario(
        name=data.name,
        description=data.description,
        is_system=False,
        team_id=team_id,
        breakdown=data.breakdown,
    )
    db.add(scenario)
    db.commit()
    db.refresh(scenario)
    return scenario


@router.delete("/{scenario_id}")
def delete_scenario(
    scenario_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    scenario = db.query(CostScenario).filter(CostScenario.id == scenario_id).first()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    if scenario.is_system:
        raise HTTPException(status_code=400, detail="Cannot delete system scenarios")
    db.delete(scenario)
    db.commit()
    return {"status": "deleted"}