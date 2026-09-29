import urllib.parse
from sqlmodel import create_engine, SQLModel, Session

UTILISATEUR = "root"
MOT_DE_PASSE_BRUT = "" 
NOM_BASE_DE_DONNEES = "dretfp_db"

mot_de_passe_encode = urllib.parse.quote_plus(MOT_DE_PASSE_BRUT)

if mot_de_passe_encode:
    DATABASE_URL = f"mysql+pymysql://{UTILISATEUR}:{mot_de_passe_encode}@localhost:3306/{NOM_BASE_DE_DONNEES}"
else:
    DATABASE_URL = f"mysql+pymysql://{UTILISATEUR}@localhost:3306/{NOM_BASE_DE_DONNEES}"

engine = create_engine(DATABASE_URL, echo=False)

def init_db_tables():
    print("📡 Connexion au serveur local MySQL (phpMyAdmin) en cours...")
    from app.database.models import Apprenant, Secteur, Filiere, Metier, Etablissement, DemandeTitre
    
    SQLModel.metadata.create_all(engine)
    print("✅ Toutes les tables de nomenclatures et de registres ont été injectées avec succès dans MySQL !")


def get_db_session():
    with Session(engine) as session:
        yield session
