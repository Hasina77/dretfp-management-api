from fastapi import APIRouter, Depends, status
from sqlmodel import Session, select
from pydantic import BaseModel
from typing import List, Optional
from app.database.config import get_db_session
from app.database.models import HistoriqueEvenement

router = APIRouter()

class HistoriqueCreate(BaseModel):
    acteur: str
    role_acteur: str
    action_effectuee: str
    details: Optional[str] = None

@router.get("/liste", status_code=status.HTTP_200_OK)
def lister_historique(db: Session = Depends(get_db_session)):
    statement = select(HistoriqueEvenement).order_by(HistoriqueEvenement.date_evenement.desc())
    return db.exec(statement).all()

@router.post("/ajouter", status_code=status.HTTP_201_CREATED)
def enregistrer_evenement(event_in: HistoriqueCreate, db: Session = Depends(get_db_session)):
    nouvel_event = HistoriqueEvenement(**event_in.dict())
    db.add(nouvel_event)
    db.commit()
    return {"status": "logged"}
