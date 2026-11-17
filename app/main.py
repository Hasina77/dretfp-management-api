import os
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select
from contextlib import asynccontextmanager
from pydantic import BaseModel
from typing import Optional
from fastapi import Depends, HTTPException
from app.database.config import get_db_session
from app.database.models import ChefCentre, DocumentCentre
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from app.routers import (
    auth, 
    demandes, 
    examens, 
    apprenants, 
    etablissements, 
    secteurs, 
    filieres, 
    metiers,
    chefs,
    historique 
)

from app.database.config import init_db_tables


class ChefCentreUpdate(BaseModel):
    nom_chefcentre: Optional[str] = None
    prenom_chefcentre: Optional[str] = None
    mail_chefcentre: Optional[str] = None
    tel_chefcentre: Optional[str] = None
    username: Optional[str] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("📡 Connexion au serveur local de la DRETFP Amoron'i Mania en cours...")
    init_db_tables() 
    print("🚀 Base de données MySQL (phpMyAdmin) initialisée et connectée avec succès !")
    yield
    print(" Arrêt du serveur de la DRETFP.")

app = FastAPI(
    title="API Système d'Information Intégré - DRETFP",
    description="Backend robuste pour la gestion décentralisée des examens, nomenclatures et demandes de titres.",
    version="1.0.0",
    lifespan=lifespan
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
    allow_origins=["*"],     
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
app.include_router(chefs.router, prefix="/api/chefs-centre", tags=["Chefs de Centre"])
app.include_router(historique.router, prefix="/api/historique", tags=["Historique"])



@app.put("/api/chefs-centre/{id_chefcentre}")
def update_chef_centre(id_chefcentre: int, data: ChefCentreUpdate, db: Session = Depends(get_db_session)):
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

@app.get("/api/documents/notifications-attente", tags=["Documents"])
def verifier_notifications_documents(db: Session = Depends(get_db_session)):
    docs = db.exec(select(DocumentCentre)).all()
    # Regroupe le nombre de documents par établissement
    compteur_par_etab = {}
    for d in docs:
        compteur_par_etab[d.id_etablissement] = compteur_par_etab.get(d.id_etablissement, 0) + 1
    return {
        "total": len(docs),
        "par_etablissement": compteur_par_etab
    }

@app.get("/api/documents/{id_etablissement}", tags=["Documents"])
def lister_documents_par_centre(id_etablissement: int, db: Session = Depends(get_db_session)):
    statement = select(DocumentCentre).where(
        DocumentCentre.id_etablissement == id_etablissement
    ).order_by(DocumentCentre.date_envoi.desc())
    return db.exec(statement).all()