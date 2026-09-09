from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth
from app.routers import demandes
from app.routers import examens
from app.database.config import init_db_tables
from app.routers import apprenants
from app.routers import etablissements






# 1. Initialisation de l'application FastAPI avec titres institutionnels pour Swagger
app = FastAPI(
    title="API Système d'Information Intégré - DRETFP",
    description="Backend robuste pour la gestion décentralisée des examens et demandes de titres.",
    version="1.0.0"
)

@app.on_event("startup")
def on_startup():
    init_db_tables() # Génère les tables de manière automatisée au lancement
    print("🚀 Base de données DRETFP initialisée avec succès !")


# 2. Configuration du CORS (Indispensable pour autoriser React à appeler FastAPI)
origins = [
    "http://localhost:5173", # L'adresse par défaut de ton serveur React
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Autorise toutes les méthodes (GET, POST, PUT, DELETE)
    allow_headers=["*"], # Autorise tous les en-têtes (y compris le Token JWT)
)

# 3. Route de test de base (Health Check)
@app.get("/", tags=["Système"])
def read_root():
    return {
        "status": "online",
        "message": "Bienvenue sur le serveur central de la DRETFP",
        "documentation": "/docs"
    }


app.include_router(auth.router, prefix="/api/auth", tags=["Authentification"])
app.include_router(examens.router, prefix="/api/examens", tags=["Examens Terrain"])
app.include_router(demandes.router, prefix="/api/demandes", tags=["Demandes Titres"])
app.include_router(apprenants.router, prefix="/api/apprenants", tags=["Registre Apprenants"])
app.include_router(etablissements.router, prefix="/api/etablissements", tags=["Gestion Établissements"])

