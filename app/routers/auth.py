from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlmodel import Session, select
from app.database.config import get_db_session
from app.database.models import User, ChefCentre
from app.core.security import get_password_hash, verify_password, create_access_token
from typing import List, Optional

router = APIRouter()

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    role: str
    centre_affectation: str

class ChefRegisterIn(BaseModel):
    username: str
    email: EmailStr
    password: str    

@router.post("/register", status_code=status.HTTP_201_CREATED)
def register_user(user_in: UserRegister, db: Session = Depends(get_db_session)):
    statement = select(User).where(User.email == user_in.email)
    existing_user = db.exec(statement).first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="⚠️ Erreur : Un compte utilisateur existe déjà avec cette adresse e-mail."
        )
    
    hashed_password = get_password_hash(user_in.password)
    
    nouvel_utilisateur = User(
        email=user_in.email,
        password_hashed=hashed_password,
        role=user_in.role,
        centre_affectation=user_in.centre_affectation
    )
    
    db.add(nouvel_utilisateur)
    db.commit()
    db.refresh(nouvel_utilisateur)
    
    return {
        "status": "success",
        "message": f"Compte créé avec succès pour le rôle {user_in.role} !",
        "email": nouvel_utilisateur.email
    }

@router.post("/login")
def login_user(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db_session)):
    statement = select(User).where(User.email == form_data.username)
    user = db.exec(statement).first()
    
    if not user or not verify_password(form_data.password, user.password_hashed):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants officiels ou mot de passe DRETFP incorrects."
        )
    
    token = create_access_token(subject=user.email, role=user.role)
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user.role,
        "centre_affectation": user.centre_affectation
    }
class UserOut(BaseModel):
    id_user: Optional[int] = None
    email: str
    role: str
    centre_affectation: str
    date_creation: Optional[str] = None

@router.get("/utilisateurs", response_model=List[UserOut], status_code=status.HTTP_200_OK)
def lister_tous_les_utilisateurs(db: Session = Depends(get_db_session)):
    """
    Récupère la liste de tous les comptes (Admins et Chefs de Centre) 
    inscrits dans la base de données centrale .
    """
    requete_sql = select(User).order_by(User.id_user.desc())
    liste_utilisateurs = db.exec(requete_sql).all()
    
    return liste_utilisateurs

@router.post("/register-chef", status_code=status.HTTP_201_CREATED)
def inscrire_compte_chef_de_centre(info_in: ChefRegisterIn, db: Session = Depends(get_db_session)):
    # 1. Vérifier si le username est répertorié dans la liste officielle des chefs de centre
    chef_officiel = db.exec(select(ChefCentre).where(ChefCentre.username == info_in.username)).first()
    if not chef_officiel:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="❌ Accès refusé : Vous n'êtes pas autorisé à créer un compte. Contactez l'administrateur de la DRETFP."
        )
    
    # 2. Vérifier si un compte d'accès utilisateur existe déjà pour cet e-mail
    compte_existant = db.exec(select(User).where(User.email == info_in.email)).first()
    if compte_existant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="⚠️ Un compte utilisateur est déjà associé à cette adresse e-mail."
        )
    
    # 3. Création du compte utilisateur rattaché avec le rôle AGENT_CENTRE
    nouvel_utilisateur = User(
        email=info_in.email,
        password_hashed=get_password_hash(info_in.password), # Ta fonction crypto existante
        role="AGENT_CENTRE",
        centre_affectation=str(chef_officiel.id_etablissement)
    )
    
    db.add(nouvel_utilisateur)
    db.commit()
    return {"status": "success", "message": "Compte de Chef de Centre créé avec succès !"}