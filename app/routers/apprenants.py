from fastapi import APIRouter, HTTPException, status, Depends
from sqlmodel import Session, select
from pydantic import BaseModel
from typing import List, Optional
from app.database.config import get_db_session
from app.database.models import Apprenant

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
        critere_unicite = select(Apprenant).where(Apprenant.im_apprenant == élève.im_apprenant)
        apprenant_existant = db.exec(critere_unicite).first()

        if apprenant_existant:
            compteur_doublons += 1
            liste_matricules_doublons.append(élève.im_apprenant)
            continue 

        nouvel_apprenant = Apprenant(
            im_apprenant=élève.im_apprenant,
            nom_apprenant=élève.nom_apprenant.upper(), 
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

@router.post("/creer", status_code=status.HTTP_201_CREATED)
def creer_nouvel_apprenant(apprenant_in: ApprenantCreate, db: Session = Depends(get_db_session)):
    existe_deja = db.exec(select(Apprenant).where(Apprenant.im_apprenant == apprenant_in.im_apprenant)).first()
    if existe_deja:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="⚠️ Un apprenant possède déjà ce numéro d'immatriculation (IM) dans le registre."
        )

    nouvel_apprenant = Apprenant(
        im_apprenant=apprenant_in.im_apprenant,
        nom_apprenant=apprenant_in.nom_apprenant,
        prenom_apprenant=apprenant_in.prenom_apprenant,
        date_naiss=apprenant_in.date_naiss,
        lieu_naiss=apprenant_in.lieu_naiss,
        examen_id=apprenant_in.examen_id,
        session=apprenant_in.session,
        mention=apprenant_in.mention,
        etablissement_id=apprenant_in.etablissement_id,
        secteur_id=apprenant_in.secteur_id,
        filiere_id=apprenant_in.filiere_id,
        metier_id=apprenant_in.metier_id,
        progression=apprenant_in.progression
    )
    
    db.add(nouvel_apprenant)
    db.commit()
    db.refresh(nouvel_apprenant)
    
    return {
        "status": "success",
        "message": "Candidat enregistré avec succès dans la base décentralisée !",
        "data": nouvel_apprenant
    }
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

