from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime

class Apprenant(SQLModel, table=True):
    __tablename__ = "apprenants"

    id_apprenant: Optional[int] = Field(default=None, primary_key=True)
    im_apprenant: int = Field(unique=True, index=True)
    nom_apprenant: str
    prenom_apprenant: str
    date_naiss: str
    lieu_naiss: str
    examen_id: str 
    etablissement_id: str
    secteur_id: str
    filiere_id: str 
    metier_id: str  
    session: int  
    mention: str   
    progression: str = Field(default="AUCUNE_DEMANDE") 

class DemandeTitre(SQLModel, table=True):
    __tablename__ = "demandes_titres"
    
    id_demande: Optional[int] = Field(default=None, primary_key=True)
    im_apprenant: str
    nom_complet: str 
    session: int
    type_document: str 
    statut: str 


class User(SQLModel, table=True):
    __tablename__ = "users"

    id_user: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True) 
    password_hashed: str                        
    role: str                                  
    centre_affectation: Optional[str] = Field(default=None) 
    date_creation: str = Field(default_factory=lambda: datetime.now().strftime("%d/%m/%Y à %H:%M"))


class Etablissement(SQLModel, table=True):
    __tablename__ = "etablissements"

    id_centre: Optional[int] = Field(default=None, primary_key=True)
    code_centre: str = Field(unique=True, index=True) 
    nom_etablissement: str                            
    localisation_district: str                        
    contact: str                                      
    email: str                                        
    statut: str = Field(default="Actif")
    date_enregistrement: str = Field(default_factory=lambda: datetime.now().strftime("%d/%m/%Y à %H:%M"))

class Secteur(SQLModel, table=True):
    __tablename__ = "secteurs"

    id_secteur: Optional[int] = Field(default=None, primary_key=True)
    nom_secteur: str
    etablissement_id: int = Field(index=True)
    description_sec: Optional[str] = None



class Filiere(SQLModel, table=True):
    __tablename__ = "filieres"

    id_filiere: Optional[int] = Field(default=None, primary_key=True)
    nom_filiere: str
    description_fil: Optional[str] = None
    secteur_id: int = Field(index=True) 


class Metier(SQLModel, table=True):
    __tablename__ = "metiers"

    id_metier: Optional[int] = Field(default=None, primary_key=True)
    nom_metier: str
    description_met: Optional[str] = None
    filiere_id: int = Field(index=True) 

class Examen(SQLModel, table=True):
    __tablename__ = "examens"
    
    id_examen: Optional[int] = Field(default=None, primary_key=True)
    nom_exam: str
    description_exam: Optional[str] = None  