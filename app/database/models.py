from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime

# ==========================================
# 🗄️ TABLE 1 : REGISTRE CENTRAL DES APPRENANTS (Alimentée par l'import Excel)
# ==========================================
class Apprenant(SQLModel, table=True):
    __tablename__ = "apprenants"

    id_apprenant: Optional[int] = Field(default=None, primary_key=True)
    im_apprenant: int = Field(unique=True, index=True) # Numéro Matricule unique
    nom_apprenant: str
    prenom_apprenant: str
    date_naiss: str
    lieu_naiss: str
    examen_id: str          # ex: 'CAP', 'BEP', 'BT'
    etablissement_id: str   # ex: 'Lycée Technique Fianarantsoa'
    secteur_id: str         # ex: 'Industriel', 'Artisanat'
    filiere_id: str         # ex: 'Génie Logiciel'
    metier_id: str          # ex: 'Développeur'
    session: int            # ex: 2026
    mention: str            # ex: 'Très Bien'
    progression: str = Field(default="AUCUNE_DEMANDE") # Suivi du statut administratif

# ==========================================
# 📜 TABLE 2 : FLUX DES DEMANDES DE TITRES (Alimentée par l'élève en ligne ou guichet)
# ==========================================
class DemandeTitre(SQLModel, table=True):
    __tablename__ = "demandes_titres"

    id_demande: Optional[int] = Field(default=None, primary_key=True)
    
    # 🔒 CLÉ ÉTRANGÈRE : Relie la demande au matricule de l'apprenant dans la BDD
    im_apprenant: int = Field(foreign_key="apprenants.im_apprenant", index=True)
    
    nom_complet: str        # Copie du Nom + Prénom pour l'affichage rapide
    type_document: str      # 'ATTESTATION' ou 'DIPLOME'
    centre_examen: str
    date_depot: str = Field(default_factory=lambda: datetime.now().strftime("%d/%m/%Y"))
    statut: str = Field(default="EN_ATTENTE") # 'EN_ATTENTE', 'VALIDE'

# ==========================================
# 🔐 TABLE 3 : SÉCURITÉ ET UTILISATEURS (ADMINS & CHEFS DE CENTRE)
# ==========================================
class User(SQLModel, table=True):
    __tablename__ = "users"

    id_user: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True) # Identifiant de connexion unique
    password_hashed: str                        # Mot de passe chiffré (Bcrypt)
    role: str                                   # 'ADMIN_DRETFP' ou 'AGENT_CENTRE'
    centre_affectation: Optional[str] = Field(default=None) # ex: 'Lycée Technique Fianarantsoa'
    date_creation: str = Field(default_factory=lambda: datetime.now().strftime("%d/%m/%Y à %H:%M"))

# ==========================================
# 🏢 TABLE 4 : RÉPERTOIRE DES ÉTABLISSEMENTS (CENTRES D'EXAMEN)
# ==========================================
class Etablissement(SQLModel, table=True):
    __tablename__ = "etablissements"

    id_centre: Optional[int] = Field(default=None, primary_key=True)
    code_centre: str = Field(unique=True, index=True) # ex: 'CENTRE-FIANAR-01'
    nom_etablissement: str                            # ex: 'Lycée Technique Fianarantsoa'
    localisation_district: str                        # ex: 'Fianarantsoa I'
    contact: str                                      # ex: '+261 34 00 123 45'
    email: str                                        # ex: 'lt.fianar@dretfp.mg'
    statut: str = Field(default="Actif")
    date_enregistrement: str = Field(default_factory=lambda: datetime.now().strftime("%d/%m/%Y à %H:%M"))