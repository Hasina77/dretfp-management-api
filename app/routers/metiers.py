from fastapi import APIRouter, Depends, status, HTTPException
from sqlmodel import Session, select
from typing import List, Optional
from app.database.config import get_db_session
from app.database.models import Metier
from pydantic import BaseModel

router = APIRouter()

class MetierCreate(BaseModel):
    nom_metier: str
    filiere_id: int
    description_met: Optional[str] = ""

@router.get("/liste", response_model=List[Metier])
def lister_tous_les_metiers(db: Session = Depends(get_db_session)):
    return db.exec(select(Metier)).all()

@router.post("/creer", status_code=status.HTTP_201_CREATED)
def creer_nouveau_metier(metier_in: MetierCreate, db: Session = Depends(get_db_session)):
    nouveau_metier = Metier(
        nom_metier=metier_in.nom_metier,
        filiere_id=metier_in.filiere_id,
        description_met=metier_in.description_met
    )
    db.add(nouveau_metier)
    db.commit()
    db.refresh(nouveau_metier)
    return {"status": "success", "data": nouveau_metier}

@router.put("/modifier/{id_metier}", status_code=status.HTTP_200_OK)
def modifier_metier_specifique(id_metier: int, metier_in: MetierCreate, db: Session = Depends(get_db_session)):
    metier_cible = db.get(Metier, id_metier)
    
    if not metier_cible:
        raise HTTPException(status_code=404, detail="⚠️ Ce métier est introuvable.")
        
    metier_cible.nom_metier = metier_in.nom_metier
    metier_cible.filiere_id = metier_in.filiere_id
    metier_cible.description_met = metier_in.description_met
    
    db.add(metier_cible)
    db.commit()
    db.refresh(metier_cible)
    return {"status": "success", "message": "Métier mis à jour avec succès !"}

@router.delete("/supprimer/{id_metier}", status_code=status.HTTP_200_OK)
def supprimer_metier_specifique(id_metier: int, db: Session = Depends(get_db_session)):
    metier_cible = db.get(Metier, id_metier)
    if not metier_cible:
        raise HTTPException(status_code=404, detail="Métier introuvable.")
    db.delete(metier_cible)
    db.commit()
    return {"status": "success", "message": "Métier effacé de SQLite."}
