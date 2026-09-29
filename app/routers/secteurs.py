from fastapi import APIRouter, Depends, status, HTTPException
from sqlmodel import Session, select
from typing import List, Optional
from app.database.config import get_db_session
from app.database.models import Secteur
from pydantic import BaseModel

router = APIRouter()

class SecteurCreate(BaseModel):
    nom_secteur: Optional[str] = "Nouveau Secteur"
    etablissement_id: Optional[int] = 1
    description_sec: Optional[str] = ""

@router.get("/liste", response_model=List[Secteur])
def lister_tous_les_secteurs(db: Session = Depends(get_db_session)):
    liste_secteurs = db.exec(select(Secteur)).all()
    
    for sec in liste_secteurs:
        if hasattr(sec, "centre_id") and not getattr(sec, "etablissement_id", None):
            sec.etablissement_id = sec.centre_id
            
    return liste_secteurs

@router.post("/creer", status_code=status.HTTP_201_CREATED)
def creer_nouveau_secteur(secteur_in: SecteurCreate, db: Session = Depends(get_db_session)):
    nouveau_secteur = Secteur(
        nom_secteur=secteur_in.nom_secteur,
        etablissement_id=secteur_in.etablissement_id,
        description_sec=secteur_in.description_sec
    )
    
    db.add(nouveau_secteur)
    db.commit()
    db.refresh(nouveau_secteur)
    
    return {
        "status": "success",
        "message": "Nouveau secteur enregistré avec succès !",
        "data": nouveau_secteur
    }

@router.put("/modifier/{id_secteur}", status_code=status.HTTP_200_OK)
def modifier_secteur_technologique(id_secteur: int, secteur_in: SecteurCreate, db: Session = Depends(get_db_session)):
    secteur_cible = db.get(Secteur, id_secteur)
    
    if not secteur_cible:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="⚠️ Erreur : Ce secteur technologique est introuvable."
        )
    
    secteur_cible.nom_secteur = secteur_in.nom_secteur
    secteur_cible.etablissement_id = int(secteur_in.etablissement_id)
    secteur_cible.description_sec = secteur_in.description_sec
    
    db.add(secteur_cible)
    db.commit()
    
    db.expire(secteur_cible) 
    secteur_mis_a_jour = db.get(Secteur, id_secteur)
    
    return {
        "status": "success",
        "message": "Le secteur a été mis à jour avec succès !",
        "data": secteur_mis_a_jour
    }

@router.delete("/supprimer/{id_secteur}", status_code=status.HTTP_200_OK)
def supprimer_secteur_technologique(id_secteur: int, db: Session = Depends(get_db_session)):
    secteur_cible = db.get(Secteur, id_secteur)
    
    if not secteur_cible:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="⚠️ Ce secteur technologique est introuvable."
        )
        
    db.delete(secteur_cible)
    db.commit()
    
    return {
        "status": "success", 
        "message": "Le secteur a été supprimé avec succès."
    }
