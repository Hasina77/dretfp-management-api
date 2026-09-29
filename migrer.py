import sys
import os
import urllib.parse

os.environ["PYTHONIOENCODING"] = "utf-8"
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlmodel import create_engine, SQLModel
from app.database.models import Apprenant, Secteur, Filiere, Metier

mot_de_passe_brut = "ton_mot_de_passe" 

mot_de_passe_encode = urllib.parse.quote_plus(mot_de_passe_brut)

DATABASE_URL = f"postgresql://postgres:{mot_de_passe_encode}@localhost:5432/dretfp_db"

print("🔗 1. Tentative de connexion à PostgreSQL...")
engine = create_engine(DATABASE_URL, echo=False)

print("⚡ 2. Gravure des tables en cours...")
try:
    SQLModel.metadata.create_all(engine)
    print("\n✅ EXPÉDITION RÉUSSIE ! Vos 7 tables sont désormais créées dans PostgreSQL.")
except Exception as e:
    print("\n❌ ERREUR DE CONNEXION DÉTECTÉE !")
    print("👉 Raisons possibles :")
    print("1. Le mot de passe écrit à la ligne 16 est incorrect.")
    print("2. La base de données 'dretfp_db' n'a pas été créée dans pgAdmin.")
    print("3. Le serveur PostgreSQL est éteint sur votre ordinateur.")
