from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from app.database.config import get_db_session
from app.database.models import ChefCentre, Etablissement

router = APIRouter()


class ChefCentreCreate(BaseModel):
    nom_chefcentre: str
    prenom_chefcentre: Optional[str] = None
    username: str
    tel_chefcentre: Optional[str] = None
    mail_chefcentre: Optional[EmailStr] = None
    id_etablissement: int

class ChefCentreResponse(BaseModel):
    id_chefcentre: int
    nom_chefcentre: str
    prenom_chefcentre: Optional[str]
    username: str
    tel_chefcentre: Optional[str]
    mail_chefcentre: Optional[str]
    id_etablissement: int

class ChefCentreUpdateIn(BaseModel):
    nom_chefcentre: Optional[str] = None
    prenom_chefcentre: Optional[str] = None
    mail_chefcentre: Optional[str] = None
    tel_chefcentre: Optional[str] = None
    username: Optional[str] = None

class Config:
    from_attributes = True



@router.post("/enregistrer", response_model=ChefCentreResponse, status_code=status.HTTP_201_CREATED)
def enregistrer_chef_centre(chef_in: ChefCentreCreate, db: Session = Depends(get_db_session)):
    """
    Enregistre un nouveau Chef de Centre dans le système après vérification des contraintes d'intégrité.
    """
    username_propre = chef_in.username.strip().lower()
    nom_propre = chef_in.nom_chefcentre.strip().upper()
    prenom_propre = chef_in.prenom_chefcentre.strip() if chef_in.prenom_chefcentre else None

    critere_unicite = select(ChefCentre).where(ChefCentre.username == username_propre)
    username_existant = db.exec(critere_unicite).first()
    if username_existant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"⚠️ Conflit : Le nom d'utilisateur '{username_propre}' est déjà attribué à un autre responsable."
        )

    etablissement_existant = db.get(Etablissement, chef_in.id_etablissement)
    if not etablissement_existant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"❌ Erreur référentielle : L'établissement avec l'identifiant ID {chef_in.id_etablissement} n'existe pas."
        )

    nouveau_chef = ChefCentre(
        nom_chefcentre=nom_propre,
        prenom_chefcentre=prenom_propre,
        username=username_propre,
        tel_chefcentre=chef_in.tel_chefcentre.strip() if chef_in.tel_chefcentre else None,
        mail_chefcentre=chef_in.mail_chefcentre.strip() if chef_in.mail_chefcentre else None,
        id_etablissement=chef_in.id_etablissement
    )

    try:
        db.add(nouveau_chef)
        db.commit()
        db.refresh(nouveau_chef)
        return nouveau_chef
    except Exception as e:
        db.rollback()
        print(f"❌ Échec d'écriture MySQL pour ChefCentre : {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur fatale lors de l'insertion en base de données : {str(e)}"
        )


@router.get("/liste", response_model=List[ChefCentreResponse], status_code=status.HTTP_200_OK)
def lister_tous_les_chefs_de_centre(db: Session = Depends(get_db_session)):
    """
    Récupère le registre complet de tous les chefs de centre par ordre décroissant d'inscription.
    """
    requete_sql = select(ChefCentre).order_by(ChefCentre.id_chefcentre.desc())
    return db.exec(requete_sql).all()


@router.put("/modifier/{id_chefcentre}", response_model=ChefCentreResponse, status_code=status.HTTP_200_OK)
def modifier_fiche_chef_centre(id_chefcentre: int, chef_in: ChefCentreCreate, db: Session = Depends(get_db_session)):
    """
    Met à jour l'ensemble des données d'un chef de centre identifié par sa clé primaire.
    """
    chef_cible = db.get(ChefCentre, id_chefcentre)
    if not chef_cible:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="⚠️ Modification impossible : Ce chef de centre est introuvable dans le répertoire."
        )

    username_propre = chef_in.username.strip().lower()
    conflit_username = db.exec(
        select(ChefCentre).where(ChefCentre.username == username_propre, ChefCentre.id_chefcentre != id_chefcentre)
    ).first()
    if conflit_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"⚠️ Le nom d'utilisateur '{username_propre}' appartient déjà à un autre compte."
        )

    etablissement_existant = db.get(Etablissement, chef_in.id_etablissement)
    if not etablissement_existant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"❌ Établissement d'affectation ID {chef_in.id_etablissement} inexistant."
        )

    chef_cible.nom_chefcentre = chef_in.nom_chefcentre.strip().upper()
    chef_cible.prenom_chefcentre = chef_in.prenom_chefcentre.strip() if chef_in.prenom_chefcentre else None
    chef_cible.username = username_propre
    chef_cible.tel_chefcentre = chef_in.tel_chefcentre.strip() if chef_in.tel_chefcentre else None
    chef_cible.mail_chefcentre = chef_in.mail_chefcentre.strip() if chef_in.mail_chefcentre else None
    chef_cible.id_etablissement = chef_in.id_etablissement

    try:
        db.add(chef_cible)
        db.commit()
        db.refresh(chef_cible)
        return chef_cible
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la mise à jour des données : {str(e)}"
        )


@router.delete("/supprimer/{id_chefcentre}", status_code=status.HTTP_200_OK)
def revoquer_chef_de_centre(id_chefcentre: int, db: Session = Depends(get_db_session)):
    """
    Supprime définitivement un chef de centre du registre de l'administration régionale.
    """
    chef_cible = db.get(ChefCentre, id_chefcentre)
    if not chef_cible:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="⚠️ Révocation impossible : Ce responsable n'existe pas ou a déjà été retiré du système."
        )

    try:
        db.delete(chef_cible)
        db.commit()
        return {
            "status": "success",
            "message": f"Le chef de centre {chef_cible.nom_chefcentre} a été révoqué et effacé du registre avec succès."
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur serveur lors de la suppression de la fiche de poste : {str(e)}"
        )


@router.put("/chefs-centre/{id_chefcentre}", status_code=status.HTTP_200_OK)
def modifier_chef_centre(id_chefcentre: int, data: ChefCentreUpdateIn, db: Session = Depends(get_db_session)):
    chef = db.get(ChefCentre, id_chefcentre)
    if not chef:
        raise HTTPException(status_code=404, detail="Chef de centre introuvable.")

    if data.nom_chefcentre is not None:
        chef.nom_chefcentre = data.nom_chefcentre.strip()
    if data.prenom_chefcentre is not None:
        chef.prenom_chefcentre = data.prenom_chefcentre.strip()
    if data.mail_chefcentre is not None:
        chef.mail_chefcentre = data.mail_chefcentre.strip()
    if data.tel_chefcentre is not None:
        chef.tel_chefcentre = data.tel_chefcentre.strip()
    if data.username is not None:
        chef.username = data.username.strip()

    db.add(chef)
    db.commit()
    db.refresh(chef)
    return {"status": "success", "chef": chef}
