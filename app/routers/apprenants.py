from fastapi import APIRouter, HTTPException, status, Depends
from sqlmodel import Session, select
from pydantic import BaseModel, Field
from typing import List, Optional
from app.database.config import get_db_session
from app.database.models import Apprenant

router = APIRouter()

# 1. Schéma de validation Pydantic (Dictionnaire de données strict pour l'entrée Excel)
class ApprenantExcelIn(BaseModel):
    im_apprenant: int
    nom_apprenant: str
    prenom_apprenant: Optional[str] = ""
    date_naiss: str
    lieu_naiss: str
    examen_id: str
    etablissement_id: str
    secteur_id: Optional[str] = "Industriel"
    filiere_id: str
    metier_id: Optional[str] = ""
    session: int
    mention: str
    progression: Optional[str] = "AUCUNE_DEMANDE"

class PaquetImportExcel(BaseModel):
    apprenants: List[ApprenantExcelIn]

# ==============================================================================
# 🚀 ROUTE PRINCIPALE : INSERTION DE MASSE DEPUIS EXCEL ET TERRAIN
# ==============================================================================
@router.post("/import-bulk", status_code=status.HTTP_201_CREATED)
def importer_masse_excel(paquet: PaquetImportExcel, db: Session = Depends(get_db_session)):
    # Vérification de sécurité élémentaire
    if not paquet.apprenants:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="⚠️ Le fichier Excel ou le lot transmis ne contient aucune ligne valide."
        )
    
    compteur_insertions = 0
    compteur_doublons = 0
    liste_matricules_doublons = []

    # Parcours ligne par ligne du tableau envoyé par React
    for élève in paquet.apprenants:
        # Vérification d'unicité : Est-ce que ce numéro IM existe déjà dans la table apprenants ?
        critere_unicite = select(Apprenant).where(Apprenant.im_apprenant == élève.im_apprenant)
        apprenant_existant = db.exec(critere_unicite).first()

        if apprenant_existant:
            compteur_doublons += 1
            liste_matricules_doublons.append(élève.im_apprenant)
            continue # Règle de gestion : On ignore le doublon et on passe au suivant sans bloquer le script

        # Cartographie et conversion du schéma Pydantic vers le modèle SQLModel
        nouvel_apprenant = Apprenant(
            im_apprenant=élève.im_apprenant,
            nom_apprenant=élève.nom_apprenant.upper(), # Forcer le nom en majuscule pour la propreté en BDD
            prenom_apprenant=élève.prenom_apprenant,
            date_naiss=élève.date_naiss,
            lieu_naiss=élève.lieu_naiss,
            examen_id=élève.examen_id.upper(),
            etablissement_id=élève.etablissement_id,
            secteur_id=élève.secteur_id,
            filiere_id=élève.filiere_id,
            metier_id=élève.metier_id,
            session=élève.session,
            mention=élève.mention,
            progression=élève.progression
        )
        
        db.add(nouvel_apprenant)
        compteur_insertions += 1

    # Validation de la transaction et écriture physique dans dretfp_central_db.sqlite
    db.commit()

    return {
        "status": "success",
        "message": "Traitement du fichier Excel achevé avec succès !",
        "statistiques": {
            "total_lignes_traitees": len(paquet.apprenants),
            "enregistrements_bdd": compteur_insertions,
            "doublons_ignores": compteur_doublons
        },
        "details_doublons": liste_matricules_doublons
    }

# ==============================================================================
# 📋 ROUTE SECONDAIRE : LIRE LE REGISTRE CENTRALISÉ (Pour alimenter ton grand tableau React)
# ==============================================================================
@router.get("/liste", response_model=List[Apprenant])
def lister_tous_les_apprenants(db: Session = Depends(get_db_session)):
    # Récupère l'intégralité du registre trié par ID décroissant (les plus récents en premier)
    requete_sql = select(Apprenant).order_by(Apprenant.id_apprenant.desc())
    return db.exec(requete_sql).all()
