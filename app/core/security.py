from datetime import datetime, timedelta
from typing import Any, Union
from passlib.context import CryptContext
import jwt

# 1. Configuration du hachage des mots de passe (Algorithme Bcrypt)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Clé secrète de signature (À changer en production, indispensable pour ton mémoire)
SECRET_KEY = "DRETFP_SUPER_SECRET_KEY_M2_GENIE_LOGICIEL"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480 # Le jeton dure 8 heures (une journée de travail d'agent)

# 2. Fonction pour hacher un mot de passe (Sécurisation de la table users)
def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

# 3. Fonction pour vérifier si un mot de passe saisi correspond au hachage en BDD
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

# 4. Fonction pour générer le jeton JWT sécurisé après la connexion
def create_access_token(subject: Union[str, Any], role: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # Le payload contient les informations d'autorisation de l'utilisateur
    to_encode = {
        "exp": expire, 
        "sub": str(subject),
        "role": role
    }
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
