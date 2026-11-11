from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlmodel import Session, select
from app.database.config import get_db_session
from app.database.models import UtilisateurAdministration, CompteChefTerrain, ChefCentre
from app.core.security import get_password_hash, verify_password, create_access_token
from typing import List, Optional

router = APIRouter()

class UserRegister(BaseModel):
    email: EmailStr
    password: str

class ChefRegisterIn(BaseModel):
    username: str
    email: EmailStr
    password: str    

class UserOut(BaseModel):
    id_admin: Optional[int] = None
    email_professionnel: str
    role_applicatif: str

class AdminResetIn(BaseModel):
    email: EmailStr
    new_password: str
    secret_key: str


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register_admin(user_in: UserRegister, db: Session = Depends(get_db_session)):
    statement = select(UtilisateurAdministration).where(UtilisateurAdministration.email_professionnel == user_in.email)
    existing_user = db.exec(statement).first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="⚠️ Erreur : Un compte administrateur existe déjà avec cette adresse e-mail professionnelle."
        )
    
    hashed_password = get_password_hash(user_in.password)
    
    nouvel_admin = UtilisateurAdministration(
        email_professionnel=user_in.email,
        password_hashed=hashed_password,
        role_applicatif="ADMIN_DRETFP"
    )
    
    db.add(nouvel_admin)
    db.commit()
    db.refresh(nouvel_admin)
    
    return {
        "status": "success",
        "message": "Compte d'administration centrale créé avec succès !",
        "email": nouvel_admin.email_professionnel
    }

@router.post("/register-chef", status_code=status.HTTP_201_CREATED)
def inscrire_compte_chef_de_centre(info_in: ChefRegisterIn, db: Session = Depends(get_db_session)):
    username_nettoye = info_in.username.strip().lower()
    
    chef_officiel = db.exec(select(ChefCentre).where(ChefCentre.username == username_nettoye)).first()
    if not chef_officiel:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="❌ Accès refusé : Votre identifiant officiel n'est pas répertorié par la DRETFP. Contactez votre Direction."
        )
    
    compte_existant = db.exec(select(CompteChefTerrain).where(CompteChefTerrain.email_liaison == info_in.email)).first()
    if compte_existant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="⚠️ Un compte de gestion de terrain est déjà associé à cette adresse e-mail."
        )
    
    nouveau_chef = CompteChefTerrain(
        username_officiel=username_nettoye,
        email_liaison=info_in.email,
        password_hashed=get_password_hash(info_in.password), 
        etablissement_id=chef_officiel.id_etablissement,
        role_applicatif="AGENT_CENTRE"
    )
    
    db.add(nouveau_chef)
    db.commit()
    return {"status": "success", "message": "Fiche de poste activée avec succès ! Votre espace terrain est opérationnel."}

@router.post("/login")
def login_user(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db_session)):
    identifiant = form_data.username.strip()
    
    admin_user = db.exec(select(UtilisateurAdministration).where(UtilisateurAdministration.email_professionnel == identifiant)).first()
    
    if admin_user and verify_password(form_data.password, admin_user.password_hashed):
        token = create_access_token(subject=admin_user.email_professionnel, role=admin_user.role_applicatif)
        return {
            "access_token": token,
            "token_type": "bearer",
            "role": admin_user.role_applicatif,
            "centre_affectation": None
        }
        
    chef_user = db.exec(select(CompteChefTerrain).where(CompteChefTerrain.email_liaison == identifiant)).first()
    if not chef_user:
        chef_user = db.exec(select(CompteChefTerrain).where(CompteChefTerrain.username_officiel == identifiant.lower())).first()
        
    if chef_user and verify_password(form_data.password, chef_user.password_hashed):
        token = create_access_token(subject=chef_user.email_liaison, role=chef_user.role_applicatif)
        return {
            "access_token": token,
            "token_type": "bearer",
            "role": chef_user.role_applicatif,
            "centre_affectation": str(chef_user.etablissement_id)
        }
        
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Identifiants incorrects ou rôle non homologué sur les serveurs de la DRETFP."
    )

@router.get("/utilisateurs", response_model=List[UserOut], status_code=status.HTTP_200_OK)
def lister_tous_les_utilisateurs_bureau(db: Session = Depends(get_db_session)):
    """
    Récupère exclusivement la liste des comptes rattachés au corps
    d'administration centrale de la DRETFP Amoron'i Mania.
    """
    requete_sql = select(UtilisateurAdministration).order_by(UtilisateurAdministration.id_admin.desc())
    liste_utilisateurs = db.exec(requete_sql).all()
    
    return liste_utilisateurs


@router.post("/reset-admin-password", status_code=status.HTTP_200_OK)
def reinitialiser_mot_de_passe_admin(data: AdminResetIn, db: Session = Depends(get_db_session)):
    if data.secret_key != "DRETFP_AMORONIMANIA_2026":
        raise HTTPException(status_code=403, detail="Clé de sécurité de la Direction invalide.")
        
    admin = db.exec(select(UtilisateurAdministration).where(UtilisateurAdministration.email_professionnel == data.email)).first()
    if not admin:
        raise HTTPException(status_code=404, detail="Aucun compte administrateur trouvé avec cet e-mail.")
        
    admin.password_hashed = get_password_hash(data.new_password)
    db.add(admin)
    db.commit()
    return {"status": "success", "message": "Mot de passe administrateur réinitialisé avec succès."}
