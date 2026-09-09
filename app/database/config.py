import os
from sqlmodel import SQLModel, create_engine, Session

# 1. Définition du chemin de la base de données (SQLite en local pour le dev)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'dretfp_central_db.sqlite')}"

# 2. Création du moteur de connexion (Engine)
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# 3. Fonction pour initialiser la base de données (Crée les tables si elles n'existent pas)
def init_db_tables():
    SQLModel.metadata.create_workbook = SQLModel.metadata.create_all(engine)

# 4. Dépendance FastAPI pour ouvrir/fermer une session propre à chaque requête API
def get_db_session():
    with Session(engine) as session:
        yield session
