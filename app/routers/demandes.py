from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

router = APIRouter()

# 1. Modèle Pydantic pour valider la création d'une demande (Table demandes_diplomes)
class DemandeCreate(BaseModel):
    type_document: str # 'ATTESTATION' ou 'DIPLOME'
    numero_matricule: str
    annee_session: int
    canal_demande: str # 'EN_LIGNE' ou 'AU_GUICHET'

# Modèle pour afficher le résultat propre
class DemandeResponse(BaseModel):
    id: int
    type_document: str
    numero_matricule: str
    annee_session: int
    canal_demande: str
    statut: str # 'EN_ATTENTE', 'VALIDE'
    date_demande: str

# Base de données temporaire pour faire fonctionner ton interface immédiatement
DB_DEMANDES_SIMULEES = [
    {"id": 101, "type_document": "ATTESTATION", "numero_matricule": "MAT-2025-004", "annee_session": 2025, "canal_demande": "EN_LIGNE", "statut": "VALIDE", "date_demande": "15/08/2026"},
    {"id": 102, "type_document": "DIPLOME", "numero_matricule": "MAT-2025-089", "annee_session": 2025, "canal_demande": "EN_LIGNE", "statut": "EN_ATTENTE", "date_demande": "03/09/2026"}
]

# 2. Route pour récupérer toutes les demandes (Utile pour le Dashboard Admin)
@router.get("/liste", response_model=List[DemandeResponse])
def obtenir_toutes_les_demandes():
    return DB_DEMANDES_SIMULEES

# 3. Route pour créer une nouvelle demande (Depuis React)
@router.post("/creer", status_code=status.HTTP_201_CREATED)
def creer_nouvelle_demande(demande: DemandeCreate):
    # Logique d'ingénierie logicielle : Génération de l'objet métier
    nouvelle_demande = {
        "id": len(DB_DEMANDES_SIMULEES) + 1,
        "type_document": demande.type_document,
        "numero_matricule": demande.numero_matricule,
        "annee_session": demande.annee_session,
        "canal_demande": demande.canal_demande,
        "statut": "EN_ATTENTE", # Par défaut
        "date_demande": datetime.now().strftime("%d/%m/%Y")
    }
    
    # Enregistrement simulé
    DB_DEMANDES_SIMULEES.append(nouvelle_demande)
    return {"message": "Demande enregistrée avec succès !", "demande": nouvelle_demande}
