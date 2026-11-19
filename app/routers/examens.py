from fastapi import APIRouter, Depends, status, HTTPException
from sqlmodel import Session, select
from pydantic import BaseModel
from typing import List, Optional, Any
from app.database.config import get_db_session
from app.database.models import Examen, Matiere

router = APIRouter()

class ExamenCreate(BaseModel):
    nom_exam: Any 
    description_exam: Optional[Any] = ""

class MatiereCreateIn(BaseModel):
    id_examen: int
    nom_matiere: str
    coefficient: int = 1
    type_epreuve: str = "Écrite"

class MatiereUpdateIn(BaseModel):
    nom_matiere: Optional[str] = None
    coefficient: Optional[int] = None
    type_epreuve: Optional[str] = None



@router.post("/creer", status_code=status.HTTP_201_CREATED)
def creer_nouvel_examen(examen_in: ExamenCreate, db: Session = Depends(get_db_session)):
    
    nom_nettoye = str(examen_in.nom_exam).strip()
    desc_nettoye = str(examen_in.description_exam).strip() if examen_in.description_exam else ""

    if not nom_nettoye:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="⚠️ Le nom de l'examen ne peut pas être vide."
        )
    
    statement = select(Examen).where(Examen.nom_exam == nom_nettoye)
    existe_deja = db.exec(statement).first()
    
    if existe_deja:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"⚠️ L'examen '{nom_nettoye}' est déjà enregistré dans le système."
        )

    nouvel_examen = Examen(
        nom_exam=nom_nettoye,
        description_exam=desc_nettoye
    )
    
    db.add(nouvel_examen)
    db.commit()
    db.refresh(nouvel_examen)
    
    return {
        "status": "success",
        "message": "Nouvel examen enregistré avec succès !",
        "data": nouvel_examen
    }

@router.get("/liste", response_model=List[Examen])
def lister_tous_les_examens(db: Session = Depends(get_db_session)):
    return db.exec(select(Examen).order_by(Examen.id_examen.desc())).all()


@router.put("/modifier/{id_examen}", status_code=status.HTTP_200_OK)
def modifier_examen(id_examen: int, examen_in: ExamenCreate, db: Session = Depends(get_db_session)):
    
    examen_cible = db.get(Examen, id_examen)
    if not examen_cible:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="⚠️ Erreur : Cet examen est introuvable."
        )
        
    nom_nettoye = str(examen_in.nom_exam).strip()
    desc_nettoye = str(examen_in.description_exam).strip() if examen_in.description_exam else ""

    examen_cible.nom_exam = nom_nettoye
    examen_cible.description_exam = desc_nettoye
    
    db.add(examen_cible)
    db.commit()
    db.expire(examen_cible)
    examen_mis_a_jour = db.get(Examen, id_examen)
    
    return {
        "status": "success",
        "message": "L'examen a été mis à jour avec succès !",
        "data": examen_mis_a_jour
    }


@router.delete("/supprimer/{id_examen}", status_code=status.HTTP_200_OK)
def supprimer_examen(id_examen: int, db: Session = Depends(get_db_session)):
    
    examen_cible = db.get(Examen, id_examen)
    if not examen_cible:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="⚠️ Erreur : Cet examen n'existe pas ou a déjà été supprimé."
        )
        
    db.delete(examen_cible)
    db.commit()
    
    return {
        "status": "success",
        "message": f"L'examen '{examen_cible.nom_exam}' a été retiré définitivement."
    }


@router.get("/{id_examen}/matieres", status_code=status.HTTP_200_OK)
def lister_matieres_examen(id_examen: int, db: Session = Depends(get_db_session)):
    statement = select(Matiere).where(Matiere.id_examen == id_examen).order_by(Matiere.id_matiere.asc())
    return db.exec(statement).all()

@router.post("/matieres/ajouter", status_code=status.HTTP_201_CREATED)
def ajouter_matiere_examen(data: MatiereCreateIn, db: Session = Depends(get_db_session)):
    nouvelle_matiere = Matiere(
        id_examen=data.id_examen,
        nom_matiere=data.nom_matiere.strip(),
        coefficient=data.coefficient,
        type_epreuve=data.type_epreuve
    )
    db.add(nouvelle_matiere)
    db.commit()
    db.refresh(nouvelle_matiere)
    return nouvelle_matiere

@router.delete("/matieres/{id_matiere}", status_code=status.HTTP_200_OK)
def supprimer_matiere_examen(id_matiere: int, db: Session = Depends(get_db_session)):
    matiere = db.get(Matiere, id_matiere)
    if not matiere:
        raise HTTPException(status_code=404, detail="Matière introuvable.")
    db.delete(matiere)
    db.commit()
    return {"status": "success"}


@router.put("/matieres/{id_matiere}", status_code=status.HTTP_200_OK)
def modifier_matiere_examen(id_matiere: int, data: MatiereUpdateIn, db: Session = Depends(get_db_session)):
    matiere = db.get(Matiere, id_matiere)
    if not matiere:
        raise HTTPException(status_code=404, detail="Matière introuvable.")

    if data.nom_matiere is not None:
        matiere.nom_matiere = data.nom_matiere.strip()
    if data.coefficient is not None:
        matiere.coefficient = data.coefficient
    if data.type_epreuve is not None:
        matiere.type_epreuve = data.type_epreuve

    db.add(matiere)
    db.commit()
    db.refresh(matiere)
    return matiere