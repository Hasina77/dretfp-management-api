from fastapi import APIRouter, HTTPException, status, Depends
from sqlmodel import Session, select, func
from pydantic import BaseModel
from typing import List, Optional
from app.database.config import get_db_session
from app.database.models import Apprenant
import re

router = APIRouter()

class ApprenantExcelIn(BaseModel):
    im_apprenant: str  
    nom_apprenant: str
    prenom_apprenant: Optional[str] = ""
    date_naiss: str
    lieu_naiss: str
    examen_id: str
    etablissement_id: int   
    secteur_id: int        
    filiere_id: int        
    metier_id: int         
    session: int
    mention: str
    progression: Optional[str] = "AUCUNE_DEMANDE"

class PaquetImportExcel(BaseModel):
    apprenants: List[ApprenantExcelIn]


class ApprenantCreate(BaseModel):
    im_apprenant: str
    nom_apprenant: str
    prenom_apprenant: Optional[str] = ""
    date_naiss: str
    lieu_naiss: str
    examen_id: str
    session: int
    mention: str
    etablissement_id: int
    secteur_id: int
    filiere_id: int
    metier_id: int
    progression: Optional[str] = "AUCUNE_DEMANDE"

@router.get("/liste", response_model=List[Apprenant])
def lister_tous_les_apprenants(db: Session = Depends(get_db_session)):
    requete_sql = select(Apprenant).order_by(Apprenant.id_apprenant.desc())
    return db.exec(requete_sql).all()

@router.post("/import-bulk", status_code=status.HTTP_201_CREATED)
def importer_masse_excel(paquet: PaquetImportExcel, db: Session = Depends(get_db_session)):
    if not paquet.apprenants:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="⚠️ Le fichier Excel ou le lot transmis ne contient aucune ligne valide."
        )
    
    compteur_insertions = 0
    compteur_doublons = 0
    liste_matricules_doublons = []

    for élève in paquet.apprenants:
        im_propre = str(élève.im_apprenant).strip().upper()
        
        pattern_matricule = r"^.{3}-\d{4}-.{3}$"
        if not re.match(pattern_matricule, im_propre):
            continue

        critere_unicite = select(Apprenant).where(Apprenant.im_apprenant == im_propre)
        apprenant_existant = db.exec(critere_unicite).first()

        if apprenant_existant:
            compteur_doublons += 1
            liste_matricules_doublons.append(im_propre)
            continue 

        nouvel_apprenant = Apprenant(
            im_apprenant=im_propre,
            nom_apprenant=str(élève.nom_apprenant).strip().upper(), 
            prenom_apprenant=str(élève.prenom_apprenant).strip() if élève.prenom_apprenant else "",
            date_naiss=str(élève.date_naiss).strip(),
            lieu_naiss=str(élève.lieu_naiss).strip().upper() if élève.lieu_naiss else "INCONNU",
            
            examen_id=int(élève.examen_id) if str(élève.examen_id).isdigit() else 1,
            etablissement_id=int(élève.etablissement_id) if élève.etablissement_id else 1,
            secteur_id=int(élève.secteur_id) if élève.secteur_id else 1,
            filiere_id=int(élève.filiere_id) if élève.filiere_id else 1,
            metier_id=int(élève.metier_id) if élève.metier_id else 1,
            
            session=int(élève.session) if élève.session else 2026,
            mention=str(élève.mention).strip() if élève.mention else "Passable",
            progression=str(élève.progression).strip() if élève.progression else "AUCUNE_DEMANDE"
        )
        
        db.add(nouvel_apprenant)
        compteur_insertions += 1

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"❌ Erreur lors du commit bulk Excel dans MySQL : {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Impossible de valider l'écriture de masse dans WampServer : {str(e)}"
        )

    return {
        "status": "success",
        "message": "Traitement du fichier Excel achevé avec succès !",
        "statistiques": {
            "total_lignes_traitees": len(paquet.apprenants),
            "enregistrements_bdd": compteur_insertions,
            "doublons_ignores": compteur_doublons
        },
        "details_doublons": list(set(liste_matricules_doublons))
    }
    

@router.post("/creer", status_code=status.HTTP_201_CREATED)
def creer_nouvel_apprenant(apprenant_in: ApprenantCreate, db: Session = Depends(get_db_session)):
    
    im_propre = str(apprenant_in.im_apprenant).strip().upper()
    
    pattern_matricule = r"^.{3}-\d{4}-.{3}$"
    
    if not re.match(pattern_matricule, im_propre):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"❌ Structure invalide : Le matricule '{im_propre}' ne respecte pas le format obligatoire XXX-0000-XXX (4 chiffres au milieu)."
        )

    existe_deja = db.exec(select(Apprenant).where(Apprenant.im_apprenant == im_propre)).first()
    if existe_deja:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="⚠️ Un apprenant possède déjà ce numéro d'immatriculation (IM) dans le registre."
        )

    nouvel_apprenant = Apprenant(
        im_apprenant=im_propre,  
        nom_apprenant=str(apprenant_in.nom_apprenant).strip().upper(),
        prenom_apprenant=str(apprenant_in.prenom_apprenant).strip() if apprenant_in.prenom_apprenant else "",
        date_naiss=apprenant_in.date_naiss,
        lieu_naiss=str(apprenant_in.lieu_naiss).strip().upper() if apprenant_in.lieu_naiss else "INCONNU",
        examen_id=str(apprenant_in.examen_id).strip().upper() if apprenant_in.examen_id else "CAP",
        session=int(apprenant_in.session) if apprenant_in.session else 2026,
        mention=str(apprenant_in.mention).strip() if apprenant_in.mention else "Passable",
        etablissement_id=apprenant_in.etablissement_id,
        secteur_id=apprenant_in.secteur_id,
        filiere_id=apprenant_in.filiere_id,
        metier_id=apprenant_in.metier_id,
        progression=str(apprenant_in.progression).strip() if apprenant_in.progression else "AUCUNE_DEMANDE"
    )
    
    try:
        db.add(nouvel_apprenant)
        db.commit()
        db.refresh(nouvel_apprenant)
        
        return {
            "status": "success",
            "message": "Candidat enregistré avec succès dans la base décentralisée !",
            "data": nouvel_apprenant
        }
    except Exception as e:
        db.rollback()
        print(f"❌ Échec d'écriture MySQL de l'apprenant : {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur fatale d'écriture BDD : {str(e)}"
        )
    
@router.delete("/supprimer/{id_apprenant}", status_code=status.HTTP_200_OK)
def supprimer_apprenant_du_registre(id_apprenant: int, db: Session = Depends(get_db_session)):
    apprenant_cible = db.get(Apprenant, id_apprenant)
    
    if not apprenant_cible:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="⚠️ Impossible de supprimer : Cet apprenant n'existe pas dans la base de données."
        )
    
    db.delete(apprenant_cible)
    db.commit()
    
    return {
        "status": "success",
        "message": f"L'apprenant {apprenant_cible.nom_apprenant} a été effacé définitivement."
    }

@router.put("/modifier/{im_apprenant}", status_code=status.HTTP_200_OK)
def modifier_renseignements_apprenant(im_apprenant: str, apprenant_in: ApprenantCreate, db: Session = Depends(get_db_session)):
    apprenant_cible = db.exec(select(Apprenant).where(Apprenant.im_apprenant == im_apprenant)).first()
    
    if not apprenant_cible:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="⚠️ Impossible de modifier : Cet apprenant n'existe pas dans le registre."
        )
    
    apprenant_cible.nom_apprenant = apprenant_in.nom_apprenant.upper()
    apprenant_cible.prenom_apprenant = apprenant_in.prenom_apprenant
    apprenant_cible.date_naiss = apprenant_in.date_naiss
    apprenant_cible.lieu_naiss = apprenant_in.lieu_naiss
    apprenant_cible.examen_id = apprenant_in.examen_id.upper()
    apprenant_cible.session = apprenant_in.session
    apprenant_cible.mention = apprenant_in.mention
    apprenant_cible.etablissement_id = apprenant_in.etablissement_id
    apprenant_cible.secteur_id = apprenant_in.secteur_id
    apprenant_cible.filiere_id = apprenant_in.filiere_id
    apprenant_cible.metier_id = apprenant_in.metier_id
    
    db.add(apprenant_cible)
    db.commit()
    db.refresh(apprenant_cible)
    
    return {"status": "success", "message": "Mise à jour SQLite validée !"}

@router.get("/notifications-attente", status_code=status.HTTP_200_OK)
def compter_notifications_apprenants_en_attente(db: Session = Depends(get_db_session)):
    """
    Retourne le nombre total d'apprenants envoyés à distance par 
    les chefs de centre sur le terrain et en attente de validation.
    """
    requete = select(func.count(Apprenant.id_apprenant)).where(
        Apprenant.progression == "EN_ATTENTE_VALIDATION"
    )
    total_en_attente = db.exec(requete).one()
    
    return {
        "notifications_count": total_en_attente,
        "statut": "success"
    }