import os
import shutil
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select, func
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from app.database.config import get_db_session
from app.database.models import ChefCentre, Etablissement, CompteChefTerrain, DocumentCentre
from datetime import datetime
from fastapi import UploadFile, File, Form
from app.database.models import DocumentCentre

router = APIRouter()


class ChefCentreCreate(BaseModel):
    nom_chefcentre: str
    prenom_chefcentre: Optional[str] = None
    username: str
    tel_chefcentre: Optional[str] = None
    mail_chefcentre: Optional[EmailStr] = None
    id_etablissement: int


class ChefCentreResponse(BaseModel):
    id_chefcentre: int
    nom_chefcentre: str
    prenom_chefcentre: Optional[str]
    username: str
    tel_chefcentre: Optional[str]
    mail_chefcentre: Optional[str]
    id_etablissement: int
    est_connecte: bool = False
    a_envoye_donnees: bool = False      
    nb_apprenants_envoyes: int = 0     

    class Config:
        from_attributes = True


class ChefCentreUpdateIn(BaseModel):
    nom_chefcentre: Optional[str] = None
    prenom_chefcentre: Optional[str] = None
    mail_chefcentre: Optional[str] = None
    tel_chefcentre: Optional[str] = None
    username: Optional[str] = None


@router.post("/enregistrer", response_model=ChefCentreResponse, status_code=status.HTTP_201_CREATED)
def enregistrer_chef_centre(chef_in: ChefCentreCreate, db: Session = Depends(get_db_session)):
    username_propre = chef_in.username.strip().lower()
    nom_propre = chef_in.nom_chefcentre.strip().upper()
    prenom_propre = chef_in.prenom_chefcentre.strip() if chef_in.prenom_chefcentre else None

    username_existant = db.exec(select(ChefCentre).where(ChefCentre.username == username_propre)).first()
    if username_existant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"⚠️ Conflit : Le nom d'utilisateur '{username_propre}' est déjà attribué."
        )

    etablissement_existant = db.get(Etablissement, chef_in.id_etablissement)
    if not etablissement_existant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"❌ L'établissement ID {chef_in.id_etablissement} n'existe pas."
        )

    nouveau_chef = ChefCentre(
        nom_chefcentre=nom_propre,
        prenom_chefcentre=prenom_propre,
        username=username_propre,
        tel_chefcentre=chef_in.tel_chefcentre.strip() if chef_in.tel_chefcentre else None,
        mail_chefcentre=chef_in.mail_chefcentre.strip() if chef_in.mail_chefcentre else None,
        id_etablissement=chef_in.id_etablissement
    )

    try:
        db.add(nouveau_chef)
        db.commit()
        db.refresh(nouveau_chef)
        return nouveau_chef
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'insertion : {str(e)}")


@router.get("/liste", response_model=List[ChefCentreResponse], status_code=status.HTTP_200_OK)
def lister_tous_les_chefs_de_centre(db: Session = Depends(get_db_session)):
    chefs = db.exec(select(ChefCentre).order_by(ChefCentre.id_chefcentre.desc())).all()

    comptes_actifs = db.exec(select(CompteChefTerrain.username_officiel)).all()
    usernames_connectes = {u.strip().lower() for u in comptes_actifs if u}

    tous_documents = db.exec(select(DocumentCentre)).all()

    resultat = []
    for chef in chefs:
        chef_dict = chef.dict()
        chef_dict["est_connecte"] = (chef.username.strip().lower() in usernames_connectes)

        nb_docs = sum(
            1 for app in tous_documents 
            if getattr(app, "etablissement_id", None) == chef.id_etablissement 
            or getattr(app, "centre_id", None) == chef.id_etablissement
        )

        chef_dict["nb_apprenants_envoyes"] = nb_docs
        chef_dict["a_envoye_donnees"] = (nb_docs > 0)
        resultat.append(chef_dict)

    return resultat


@router.put("/{id_chefcentre}", status_code=status.HTTP_200_OK)
def modifier_chef_centre_partiel(id_chefcentre: int, data: ChefCentreUpdateIn, db: Session = Depends(get_db_session)):
    chef = db.get(ChefCentre, id_chefcentre)
    if not chef:
        raise HTTPException(status_code=404, detail="Chef de centre introuvable.")

    if data.nom_chefcentre is not None:
        chef.nom_chefcentre = data.nom_chefcentre.strip().upper()
    if data.prenom_chefcentre is not None:
        chef.prenom_chefcentre = data.prenom_chefcentre.strip()
    if data.mail_chefcentre is not None:
        chef.mail_chefcentre = data.mail_chefcentre.strip()
    if data.tel_chefcentre is not None:
        chef.tel_chefcentre = data.tel_chefcentre.strip()
    if data.username is not None:
        chef.username = data.username.strip().lower()

    try:
        db.add(chef)
        db.commit()
        db.refresh(chef)
        return {"status": "success", "chef": chef}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erreur lors de la sauvegarde : {str(e)}")


@router.delete("/{id_chefcentre}", status_code=status.HTTP_200_OK)
@router.delete("/supprimer/{id_chefcentre}", status_code=status.HTTP_200_OK)
def revoquer_chef_de_centre(id_chefcentre: int, db: Session = Depends(get_db_session)):
    chef_cible = db.get(ChefCentre, id_chefcentre)
    if not chef_cible:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="⚠️ Révocation impossible : Ce responsable est introuvable."
        )

    try:
        try:
            from app.database.models import CompteChefTerrain
            compte_terrain = db.exec(
                select(CompteChefTerrain).where(CompteChefTerrain.username_officiel == chef_cible.username)
            ).first()
            if compte_terrain:
                db.delete(compte_terrain)
        except Exception:
            pass

        db.delete(chef_cible)
        db.commit()
        return {
            "status": "success",
            "message": f"Le chef de centre {chef_cible.nom_chefcentre} a été révoqué avec succès."
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erreur lors de la révocation : {str(e)}")


import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import BackgroundTasks

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "fanomezankasinahasiniaina13@gmail.com" 
SMTP_PASSWORD = "dpliljuolwkzyhxt"      

class EnvoiAccesIn(BaseModel):
    destinataire: EmailStr
    nom_complet: str
    username: str
    telephone: Optional[str] = None

def tache_envoi_email_chef(destinataire: str, nom_complet: str, username: str):
    msg = MIMEMultipart()
    msg['From'] = f"DRETFP Amoron'i Mania <{SMTP_USER}>"
    msg['To'] = destinataire
    msg['Subject'] = "Vos identifiants d'accès — Portail Chef de Centre DRETFP"

    corps = f"""Bonjour M./Mme {nom_complet},

La Direction Régionale de l'Enseignement Technique et de la Formation Professionnelle (DRETFP) Amoron'i Mania vous transmet vos accès officiels au portail de saisie :

- Identifiant (Username) : {username}
- Lien d'accès : https://onrender.com

Veuillez vous connecter pour activer votre espace et gérer les fiches de vos candidats.

Cordialement,
L'Administration Centrale DRETFP Amoron'i Mania."""
    
    msg.attach(MIMEText(corps, 'plain', 'utf-8'))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
    except Exception as e:
        print(f"Erreur SMTP lors de l'envoi à {destinataire} : {e}")

@router.post("/envoyer-acces-email", status_code=status.HTTP_200_OK)
def envoyer_acces_par_email(data: EnvoiAccesIn):
    msg = MIMEMultipart()
    msg['From'] = f"DRETFP Amoron'i Mania <{SMTP_USER}>"
    msg['To'] = data.destinataire
    msg['Subject'] = "Vos identifiants d'accès — Portail Chef de Centre DRETFP"

    corps = f"""Bonjour M./Mme {data.nom_complet},

La Direction Régionale de l'Enseignement Technique et de la Formation Professionnelle (DRETFP) Amoron'i Mania vous transmet vos accès officiels au portail de saisie :

- Identifiant : {data.username}
- Lien d'accès : https://dretfp-amoronimania-chef-de-centre.onrender.com

Cordialement,
L'Administration Centrale DRETFP Amoron'i Mania."""
    
    msg.attach(MIMEText(corps, 'plain', 'utf-8'))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=15)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        return {"status": "success", "message": f"E-mail envoyé avec succès à {data.destinataire}"}
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Échec de l'envoi (vérifiez la connexion Internet du serveur) : {str(e)}"
        )


import requests

WHATSAPP_API_URL = "https://ultramsg.com"
WHATSAPP_TOKEN = "VOTRE_TOKEN_API_WHATSAPP"

@router.post("/envoyer-acces-whatsapp", status_code=status.HTTP_200_OK)
def envoyer_acces_par_whatsapp(data: EnvoiAccesIn):
    if not data.telephone:
        raise HTTPException(status_code=400, detail="Numéro de téléphone manquant.")

    tel_propre = data.telephone.replace(" ", "").lstrip("+")
    if tel_propre.startswith("0"):
        tel_propre = f"261{tel_propre[1:]}"
    elif not tel_propre.startswith("261"):
        tel_propre = f"261{tel_propre}"

    message_wa = (
        f"🏛️ *DRETFP AMORON'I MANIA*\n\n"
        f"Bonjour *M./Mme {data.nom_complet}*,\n"
        f"Voici votre identifiant officiel pour accéder au portail Chef de Centre :\n\n"
        f"🔑 *Identifiant :* {data.username}\n"
        f"🌐 *Lien :* https://onrender.com\n\n"
        f"Cordialement,\nLa Direction Régionale."
    )

    try:
        reponse = requests.post(
            WHATSAPP_API_URL,
            data={"token": WHATSAPP_TOKEN, "to": f"+{tel_propre}", "body": message_wa},
            timeout=10
        )
        if reponse.status_code == 200:
            return {"status": "success", "message": f"Message WhatsApp envoyé automatiquement au +{tel_propre}"}
        raise HTTPException(status_code=502, detail="Échec de la passerelle WhatsApp.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur d'envoi WhatsApp : {str(e)}")



UPLOAD_DIR = "uploads/documents_centres"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/envoyer-document", status_code=status.HTTP_201_CREATED)
async def recevoir_document_chef(
    id_etablissement: int = Form(...),
    chef_username: str = Form(...),
    fichier: UploadFile = File(...),
    db: Session = Depends(get_db_session)
):
    try:
        ext = os.path.splitext(fichier.filename)[1].lower()
        if ext not in [".xlsx", ".xls", ".doc", ".docx", ".pdf"]:
            raise HTTPException(
                status_code=400, 
                detail="Format non autorisé. Seuls Excel, Word et PDF sont acceptés."
            )

        nom_unique = f"{id_etablissement}_{int(datetime.utcnow().timestamp())}_{fichier.filename}"
        chemin_complet = os.path.join(UPLOAD_DIR, nom_unique)

        with open(chemin_complet, "wb") as buffer:
            shutil.copyfileobj(fichier.file, buffer)

        nouveau_doc = DocumentCentre(
            id_etablissement=id_etablissement,
            chef_username=chef_username,
            nom_fichier=fichier.filename,
            type_fichier=ext.replace(".", "").upper(),
            chemin_stockage=f"/uploads/documents_centres/{nom_unique}"
        )
        db.add(nouveau_doc)
        db.commit()
        db.refresh(nouveau_doc)
        return {"status": "success", "document": nouveau_doc}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ Erreur upload document : {e}")
        raise HTTPException(status_code=500, detail=f"Erreur serveur : {str(e)}")
    

@router.get("/documents/{id_etablissement}", status_code=status.HTTP_200_OK)
def lister_documents_etablissement(id_etablissement: int, db: Session = Depends(get_db_session)):
    statement = select(DocumentCentre).where(
        DocumentCentre.id_etablissement == id_etablissement
    ).order_by(DocumentCentre.date_envoi.desc())
    return db.exec(statement).all()