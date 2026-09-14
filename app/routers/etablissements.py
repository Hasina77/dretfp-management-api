from fastapi import APIRouter, HTTPException, status, Depends
from sqlmodel import Session, select
from pydantic import BaseModel, EmailStr
from typing import List
from app.database.config import get_db_session
from app.database.models import Etablissement
import re # À ajouter tout en haut du fichier pour les expressions régulière

router = APIRouter()

# Schéma de validation Pydantic pour l'entrée React
class EtablissementCreate(BaseModel):
    code_centre: str
    nom_etablissement: str
    localisation_district: str
    contact: str
    email: EmailStr

# 🚀 ROUTE AVEC DOUBLE CONTRÔLE D'UNICITÉ MULTI-CHAMPS (Niveau Master 2)
@router.post("/creer", status_code=status.HTTP_201_CREATED)
def creer_etablissement(centre_in: EtablissementCreate, db: Session = Depends(get_db_session)):
    
    # 🧼 Nettoyage du numéro reçu (on retire les espaces)
    contact_nettoye = re.sub(r'\s+', '', centre_in.contact)
    
    # 🔬 Vérification du format strict : +261 suivi de 9 chiffres
    if not re.match(r'^\+261\d{9}$', contact_nettoye):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="⚠️ Ce numéro n'existe pas à Madagascar. Le format doit comporter strictement 9 chiffres après +261."
        )

    # 1. Requête SQL pour chercher si l'un de ces trois champs uniques est déjà pris
    statement = select(Etablissement).where(
        (Etablissement.code_centre == centre_in.code_centre) |
        (Etablissement.contact == centre_in.contact) |
        (Etablissement.email == centre_in.email)
    )
    conflit_existant = db.exec(statement).first()
    
    if examen_conflit := conflit_existant: # Si conflit détecté
        if examen_conflit.code_centre == centre_in.code_centre:
            erreur_detail = f"⚠️ Erreur : Le Code de centre '{centre_in.code_centre}' est déjà utilisé."
        elif examen_conflit.contact == centre_in.contact:
            erreur_detail = f"⚠️ Erreur : Le numéro de Contact '{centre_in.contact}' appartient déjà à un autre établissement."
        else:
            erreur_detail = f"⚠️ Erreur : L'adresse E-mail '{centre_in.email}' est déjà attribuée."
            
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=erreur_detail)
        
    # Enregistrement définitif
    nouvel_etablissement = Etablissement(**centre_in.model_dump())
    db.add(nouvel_etablissement)
    db.commit()
    db.refresh(nouvel_etablissement)
    
    return {"status": "success", "message": "Établissement enregistré avec succès !"}


# 2. 📋 ROUTE POUR RÉCUPÉRER LE RÉPERTOIRE (Pour rafraîchir ton tableau React)
@router.get("/liste", response_model=List[Etablissement])
def lister_tous_les_etablissements(db: Session = Depends(get_db_session)):
    return db.exec(select(Etablissement).order_by(Etablissement.id_centre.desc())).all()

# ✏️ ROUTE DE MODIFICATION COMPLÈTE AVEC SÉCURITÉ ET INTÉGRITÉ MULTI-CHAMPS
@router.put("/modifier/{id_centre}")
def modifier_etablissement(id_centre: int, centre_modifie: EtablissementCreate, db: Session = Depends(get_db_session)):
    
    # 1. Recherche de l'établissement existant à modifier
    etablissement_cible = db.get(Etablissement, id_centre)
    if not etablissement_cible:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="⚠️ Erreur : Établissement introuvable dans le répertoire central."
        )

    # 2. Contrôle d'unicité multicritère : Vérifie si les nouvelles valeurs ne créent pas de conflit avec UN AUTRE établissement
    statement = select(Etablissement).where(
        ((Etablissement.code_centre == centre_modifie.code_centre) |
         (Etablissement.contact == centre_modifie.contact) |
         (Etablissement.email == centre_modifie.email)) &
        (Etablissement.id_centre != id_centre) # Indispensable pour s'exclure soi-même de la vérification !
    )
    conflit_existant = db.exec(statement).first()
    
    if conflit_existant:
        if conflit_existant.code_centre == centre_modifie.code_centre:
            erreur_detail = f"⚠️ Erreur : Le Code de centre '{centre_modifie.code_centre}' est déjà attribué à un autre établissement."
        elif conflit_existant.contact == centre_modifie.contact:
            erreur_detail = f"⚠️ Erreur : Le numéro de Contact '{centre_modifie.contact}' appartient déjà à un autre établissement."
        else:
            erreur_detail = f"⚠️ Erreur : L'adresse E-mail '{centre_modifie.email}' est déjà utilisée."
            
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=erreur_detail)

    # 3. Mappage et affectation dynamique des données validées
    etablissement_cible.code_centre = centre_modifie.code_centre
    etablissement_cible.nom_etablissement = centre_modifie.nom_etablissement
    etablissement_cible.localisation_district = centre_modifie.localisation_district
    etablissement_cible.contact = centre_modifie.contact
    etablissement_cible.email = centre_modifie.email

    # 4. Enregistrement persistant dans la base SQLite
    db.add(etablissement_cible)
    db.commit()
    db.refresh(etablissement_cible)

    return {
        "status": "success",
        "message": "Fiche établissement mise à jour avec succès !",
        "data": etablissement_cible
    }

# 🗑️ ROUTE POUR SUPPRIMER DÉFINITIVEMENT UN ÉTABLISSEMENT
@router.delete("/supprimer/{id_centre}", status_code=status.HTTP_200_OK)
def supprimer_etablissement(id_centre: int, db: Session = Depends(get_db_session)):
    
    # 1. Recherche de l'établissement dans la base SQLite
    etablissement_cible = db.get(Etablissement, id_centre)
    
    # 2. Si l'établissement n'existe pas, on renvoie une erreur 404
    if not etablissement_cible:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="⚠️ Erreur : Cet établissement n'existe pas ou a déjà été supprimé."
        )
        
    # 3. Suppression physique de la ligne dans la base de données
    db.delete(etablissement_cible)
    db.commit()
    
    return {
        "status": "success",
        "message": f"L'établissement '{etablissement_cible.nom_etablissement}' a été retiré définitivement du répertoire officiel."
    }
