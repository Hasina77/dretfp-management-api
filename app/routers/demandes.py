from fastapi import APIRouter, HTTPException, status, Depends
from sqlmodel import Session, select
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from app.database.config import get_db_session
from app.database.models import DemandeTitre  # Votre modèle existant avec im_apprenant, nom_complet, etc.

router = APIRouter()
# 1. Modèle Pydantic pour valider la création d'une demande depuis React
class DemandeCreate(BaseModel):
    im_apprenant: int
    nom_complet: str
    type_document: str  # 'ATTESTATION' ou 'DIPLOME'
    centre_examen: str

# ==============================================================================
# 📋 1. ROUTE POUR RÉCUPÉRER TOUTES LES DEMANDES (Pour alimenter ton tableau React)
# ==============================================================================
@router.get("/liste", response_model=List[DemandeTitre])
def lister_tous_les_titres(db: Session = Depends(get_db_session)):
    return db.exec(select(DemandeTitre).order_by(DemandeTitre.id_demande.desc())).all()

# ==============================================================================
# 🚀 2. ROUTE POUR CRÉER ET COPIER LES RENSEIGNEMENTS EN BDD (Action Demande)
# ==============================================================================
@router.post("/creer", status_code=status.HTTP_201_CREATED)
def creer_nouvelle_demande(demande_in: DemandeCreate, db: Session = Depends(get_db_session)):
    # Création de l'instance SQLModel connectée à votre table réelle
    nouvelle_demande = DemandeTitre(
        im_apprenant=demande_in.im_apprenant,
        nom_complet=demande_in.nom_complet,
        type_document=demande_in.type_document,
        centre_examen=demande_in.centre_examen,
        statut="EN_ATTENTE",  # Configuration initiale obligatoire exigée : "En attente"
        date_depot=datetime.now().strftime("%d/%m/%Y")
    )
    
    db.add(nouvelle_demande)
    db.commit()
    db.refresh(nouvelle_demande)
    
    return {
        "status": "success",
        "message": "La demande a bien été copiée dans le registre des demandes !",
        "data": nouvelle_demande
    }

# ==============================================================================
# ⚖️ 3. ROUTE POUR LE BOUTON TRAITER : CHANGEMENT DE STATUT VERS "VALIDE"
# ==============================================================================
@router.put("/valider/{id_demande}", status_code=status.HTTP_200_OK)
def valider_demande_titre(id_demande: int, db: Session = Depends(get_db_session)):
    # Recherche physique du titre dans le fichier SQLite
    demande_cible = db.get(DemandeTitre, id_demande)
    
    if not demande_cible:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="⚠️ Erreur : Cette demande de titre est introuvable ou inexistante."
        )
    
    # Mutation de l'état de l'objet métier
    demande_cible.statut = "VALIDE"
    
    db.add(demande_cible)
    db.commit()
    db.refresh(demande_cible)
    
    return {
        "status": "success",
        "message": "Le statut a été mis à jour et validé avec succès !",
        "data": demande_cible
    }
