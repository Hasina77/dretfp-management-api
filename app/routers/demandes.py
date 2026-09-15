from fastapi import APIRouter, HTTPException, status, Depends
from sqlmodel import Session, select
from pydantic import BaseModel
from typing import List
from datetime import datetime
from app.database.config import get_db_session
from app.database.models import DemandeTitre

router = APIRouter()

class DemandeCreate(BaseModel):
    im_apprenant: int
    nom_complet: str
    type_document: str
    centre_examen: str

# 📋 1. RÉCUPÉRER TOUTES LES DEMANDES
@router.get("/liste", response_model=List[DemandeTitre])
def lister_tous_les_titres(db: Session = Depends(get_db_session)):
    return db.exec(select(DemandeTitre).order_by(DemandeTitre.id_demande.desc())).all()

# 🚀 2. CREATION DU DOSSIER (Statut initial : EN_ATTENTE)
@router.post("/creer", status_code=status.HTTP_201_CREATED)
def creer_nouvelle_demande(demande_in: DemandeCreate, db: Session = Depends(get_db_session)):
    nouvelle_demande = DemandeTitre(
        im_apprenant=demande_in.im_apprenant,
        nom_complet=demande_in.nom_complet,
        type_document=demande_in.type_document,
        centre_examen=demande_in.centre_examen,
        statut="EN_ATTENTE",  # Reste bloqué dans "Liste des Demandes" au début
        date_depot=datetime.now().strftime("%d/%m/%Y")
    )
    db.add(nouvelle_demande)
    db.commit()
    db.refresh(nouvelle_demande)
    return {"status": "success", "data": nouvelle_demande}

# ⚖️ 3. ACTION DU BOUTON "TRAITRE" : TRANSFERT VERS LA LISTE DES TRAITEMENTS (Statut : EN_COURS)
@router.put("/envoyer-au-traitement/{id_demande}", status_code=status.HTTP_200_OK)
def envoyer_au_traitement_regional(id_demande: int, db: Session = Depends(get_db_session)):
    demande = db.get(DemandeTitre, id_demande)
    if not demande:
        raise HTTPException(status_code=404, detail="Demande introuvable.")
    
    demande.statut = "EN_COURS"  # Fait basculer le dossier vers les sous-onglets de traitement
    db.add(demande)
    db.commit()
    db.refresh(demande)
    return {"status": "success", "message": "Dossier envoyé à la liste de traitement.", "data": demande}

# ✒️ 4. ACTION DE SIGNATURE FINALE DANS LA LISTE DES TRAITEMENTS (Statut : VALIDE)
@router.put("/finaliser-signature/{id_demande}", status_code=status.HTTP_200_OK)
def finaliser_signature_titre(id_demande: int, db: Session = Depends(get_db_session)):
    demande = db.get(DemandeTitre, id_demande)
    if not demande:
        raise HTTPException(status_code=404, detail="Demande introuvable.")
    
    demande.statut = "VALIDE"  # Clôture définitivement le processus
    db.add(demande)
    db.commit()
    db.refresh(demande)
    return {"status": "success", "message": "Document officiellement signé et validé !"}
