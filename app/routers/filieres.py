from fastapi import APIRouter, Depends, status, HTTPException
from sqlmodel import Session, select
from typing import List, Optional
from app.database.config import get_db_session
from app.database.models import Filiere
from pydantic import BaseModel

router = APIRouter()
class FiliereCreate(BaseModel):
    nom_filiere: str
    secteur_id: int
    description_fil: Optional[str] = ""

@router.get("/liste", response_model=List[Filiere])
def lister_toutes_les_filieres(db: Session = Depends(get_db_session)):
    return db.exec(select(Filiere)).all()

@router.post("/creer", status_code=status.HTTP_201_CREATED)
def creer_nouvelle_filiere(filiere_in: FiliereCreate, db: Session = Depends(get_db_session)):
    nouvelle_filiere = Filiere(
        nom_filiere=filiere_in.nom_filiere,
        secteur_id=filiere_in.secteur_id,
        description_fil=filiere_in.description_fil
    )
    db.add(nouvelle_filiere)
    db.commit()
    db.refresh(nouvelle_filiere)
    return {"status": "success", "data": nouvelle_filiere}

@router.put("/modifier/{id_filiere}", status_code=status.HTTP_200_OK)
def modifier_filiere_technique(id_filiere: int, filiere_in: FiliereCreate, db: Session = Depends(get_db_session)):
    filiere_cible = db.get(Filiere, id_filiere)
    
    if not filiere_cible:
        raise HTTPException(status_code=404, detail="⚠️ Cette filière est introuvable.")
        
    filiere_cible.nom_filiere = filiere_in.nom_filiere
    filiere_cible.secteur_id = filiere_in.secteur_id
    filiere_cible.description_fil = filiere_in.description_fil
    
    db.add(filiere_cible)
    db.commit()
    db.refresh(filiere_cible)
    return {"status": "success", "message": "Filière mise à jour !"}

@router.delete("/supprimer/{id_filiere}", status_code=status.HTTP_200_OK)
def supprimer_filiere_technique(id_filiere: int, db: Session = Depends(get_db_session)):
    filiere_cible = db.get(Filiere, id_filiere)
    
    if not filiere_cible:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="⚠️ Cette filière technique est introuvable."
        )
        
    db.delete(filiere_cible)
    db.commit()
    
    return {
        "status": "success", 
        "message": "La filière a été supprimée avec succès."
      }

