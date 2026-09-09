from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import List
from datetime import datetime

router = APIRouter()

# 1. Modèle Pydantic pour valider une note d'examen individuelle (Table notes_examens)
class NoteExamenModel(BaseModel):
    numero_matricule: str
    intitule_examen: str
    note_obtenue: float
    session_annee: int

# 2. Modèle pour le paquet de notes envoyé lors de la synchronisation de la PWA
class SyncPaquetModel(BaseModel):
    notes: List[NoteExamenModel]

# Base de données simulée pour stocker les notes reçues
DB_NOTES_CENTRALISEES = []

# 3. Route standard : Enregistrement d'une note unique (Mode connecté direct)
@router.post("/creer", status_code=status.HTTP_201_CREATED)
def enregistrer_note_directe(note: NoteExamenModel):
    # Logique d'ingénierie logicielle : Attribution automatique de la mention
    mention = "ADMIS" if note.note_obtenue >= 10.0 else "AJOURNE"
    
    nouvelle_note = {
        **note.model_dump(),
        "mention": mention,
        "date_reception": datetime.now().strftime("%d/%m/%Y à %H:%M")
    }
    
    DB_NOTES_CENTRALISEES.append(nouvelle_note)
    return {"status": "success", "message": "Note transmise directement au serveur central.", "data": nouvelle_note}

# 4. Route clé du mémoire : Synchronisation en lot (Mode déconnecté PWA)
@router.post("/sync", status_code=status.HTTP_200_OK)
def synchroniser_notes_terrain(paquet: SyncPaquetModel):
    if not paquet.notes:
        raise HTTPException(status_code=400, detail="Le paquet de synchronisation est vide.")
    
    notes_traitees = []
    
    # Parcours du lot de données stockées localement par IndexedDB
    for note in paquet.notes:
        mention = "ADMIS" if note.note_obtenue >= 10.0 else "AJOURNE"
        note_complete = {
            **note.model_dump(),
            "mention": mention,
            "date_reception": datetime.now().strftime("%d/%m/%Y à %H:%M")
        }
        DB_NOTES_CENTRALISEES.append(note_complete)
        notes_traitees.append(note_complete)
        
    return {
        "status": "success",
        "message": f"Algorithme de synchronisation exécuté : {len(notes_traitees)} note(s) intégrée(s) avec succès.",
        "total_enregistre": len(DB_NOTES_CENTRALISEES)
    }

# 5. Route de consultation (Pour vérifier que les notes sont bien arrivées)
@router.get("/liste")
def lister_toutes_les_notes():
    return DB_NOTES_CENTRALISEES
