from fastapi import APIRouter, Depends, status, HTTPException
from sqlmodel import Session, select, delete
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
from app.database.config import get_db_session
from app.database.models import HistoriqueEvenement

router = APIRouter()

class HistoriqueCreate(BaseModel):
    acteur: str
    role_acteur: str
    action_effectuee: str
    details: Optional[str] = None

class SuppressionLotIn(BaseModel):
    ids: List[int]

@router.get("/liste", status_code=status.HTTP_200_OK)
def lister_historique(db: Session = Depends(get_db_session)):
    date_limite = datetime.utcnow() - timedelta(days=90)
    requete_purge = delete(HistoriqueEvenement).where(HistoriqueEvenement.date_evenement < date_limite)
    db.exec(requete_purge)
    db.commit()

    statement = select(HistoriqueEvenement).order_by(HistoriqueEvenement.date_evenement.desc())
    return db.exec(statement).all()

@router.post("/ajouter", status_code=status.HTTP_201_CREATED)
def enregistrer_evenement(event_in: HistoriqueCreate, db: Session = Depends(get_db_session)):
    nouvel_event = HistoriqueEvenement(**event_in.dict())
    db.add(nouvel_event)
    db.commit()
    return {"status": "logged"}

@router.post("/supprimer-selection", status_code=status.HTTP_200_OK)
def supprimer_historique_selectionne(data: SuppressionLotIn, db: Session = Depends(get_db_session)):
    if not data.ids:
        raise HTTPException(status_code=400, detail="Aucun élément sélectionné.")
        
    requete_suppression = delete(HistoriqueEvenement).where(HistoriqueEvenement.id_historique.in_(data.ids))
    db.exec(requete_suppression)
    db.commit()
    return {"status": "deleted", "count": len(data.ids)}
