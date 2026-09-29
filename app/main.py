from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import SQLModel

from app.routers import (
    auth, 
    demandes, 
    examens, 
    apprenants, 
    etablissements, 
    secteurs, 
    filieres, 
    metiers
)

from app.database.config import init_db_tables, engine

app = FastAPI(
    title="API Système d'Information Intégré - DRETFP",
    description="Backend robuste pour la gestion décentralisée des examens, nomenclatures et demandes de titres.",
    version="1.0.0"
)

@app.on_event("startup")
def on_startup():
    init_db_tables() 
    print("🚀 Base de données PostgreSQL DRETFP initialisée et connectée avec succès !")

origins = [
    "http://localhost:5173",    
    "http://127.0.0.1:5173",
    "http://localhost",
    "http://127.0.0.1"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,     
    allow_credentials=True,   
    allow_methods=["*"],         
    allow_headers=["*"],
)
@app.get("/", tags=["Système"])
def read_root():
    return {
        "status": "online",
        "message": "Bienvenue sur le serveur central de la DRETFP",
        "documentation": "/docs"
    }

app.include_router(auth.router, prefix="/api/auth", tags=["Authentification"])
app.include_router(examens.router, prefix="/api/examens", tags=["Gestion Examens"])
app.include_router(demandes.router, prefix="/api/demandes", tags=["Demandes Titres"])
app.include_router(apprenants.router, prefix="/api/apprenants", tags=["Gestion Apprenants"])
app.include_router(etablissements.router, prefix="/api/etablissements", tags=["Gestion Établissements"])
app.include_router(secteurs.router, prefix="/api/secteurs", tags=["Gestion Secteurs"])
app.include_router(filieres.router, prefix="/api/filieres", tags=["Gestion Filières"])
app.include_router(metiers.router, prefix="/api/metiers", tags=["Gestion Métiers"])
