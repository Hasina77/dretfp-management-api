from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlmodel import Session, select
from app.database.config import get_db_session
from app.database.models import User
from app.core.security import get_password_hash, verify_password, create_access_token
from typing import List, Optional

router = APIRouter()

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    role: str
    centre_affectation: str

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