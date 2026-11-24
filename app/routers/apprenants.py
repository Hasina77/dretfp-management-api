import io
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status, Depends
from sqlmodel import Session, select, func
from pydantic import BaseModel
from typing import List, Optional
from app.database.config import get_db_session
from app.database.models import Apprenant, Matiere, Note, Examen
import re
import unicodedata
import openpyxl
from fastapi import UploadFile, File, Form, HTTPException, Depends, status

from app.database import models
from datetime import datetime
from fastapi.responses import StreamingResponse
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT


router = APIRouter()

class ApprenantExcelIn(BaseModel):
    im_apprenant: str  
    nom_apprenant: str
    prenom_apprenant: Optional[str] = ""
    date_naiss: str
    lieu_naiss: str
    examen_id: str
    etablissement_id: int   
    secteur_id: int        
    filiere_id: int        
    metier_id: int         
    session: int
    mention: str
    progression: Optional[str] = "AUCUNE_DEMANDE"

class PaquetImportExcel(BaseModel):
    apprenants: List[ApprenantExcelIn]


class ApprenantCreate(BaseModel):
    im_apprenant: str
    nom_apprenant: str
    prenom_apprenant: Optional[str] = ""
    date_naiss: str
    lieu_naiss: str
    examen_id: str
    session: int
    mention: str
    etablissement_id: int
    secteur_id: int
    filiere_id: int
    metier_id: int
    progression: Optional[str] = "AUCUNE_DEMANDE"

class NoteItemIn(BaseModel):
    id_matiere: int
    note_sur_20: float

class ReleveNotesIn(BaseModel):
    id_apprenant: int
    notes: List[NoteItemIn]



@router.get("/liste", response_model=List[Apprenant])
def lister_tous_les_apprenants(db: Session = Depends(get_db_session)):
    requete_sql = select(Apprenant).order_by(Apprenant.id_apprenant.desc())
    return db.exec(requete_sql).all()

@router.post("/import-bulk", status_code=status.HTTP_201_CREATED)
def importer_masse_excel(paquet: PaquetImportExcel, db: Session = Depends(get_db_session)):
    if not paquet.apprenants:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="⚠️ Le fichier Excel ou le lot transmis ne contient aucune ligne valide."
        )
    
    compteur_insertions = 0
    compteur_doublons = 0
    liste_matricules_doublons = []

    for élève in paquet.apprenants:
        im_propre = str(élève.im_apprenant).strip().upper()
        
        pattern_matricule = r"^.{3}-\d{4}-.{3}$"
        if not re.match(pattern_matricule, im_propre):
            continue

        critere_unicite = select(Apprenant).where(Apprenant.im_apprenant == im_propre)
        apprenant_existant = db.exec(critere_unicite).first()

        if apprenant_existant:
            compteur_doublons += 1
            liste_matricules_doublons.append(im_propre)
            continue 

        nouvel_apprenant = Apprenant(
            im_apprenant=im_propre,
            nom_apprenant=str(élève.nom_apprenant).strip().upper(), 
            prenom_apprenant=str(élève.prenom_apprenant).strip() if élève.prenom_apprenant else "",
            date_naiss=str(élève.date_naiss).strip(),
            lieu_naiss=str(élève.lieu_naiss).strip().upper() if élève.lieu_naiss else "INCONNU",
            
            examen_id=int(élève.examen_id) if str(élève.examen_id).isdigit() else 1,
            etablissement_id=int(élève.etablissement_id) if élève.etablissement_id else 1,
            secteur_id=int(élève.secteur_id) if élève.secteur_id else 1,
            filiere_id=int(élève.filiere_id) if élève.filiere_id else 1,
            metier_id=int(élève.metier_id) if élève.metier_id else 1,
            
            session=int(élève.session) if élève.session else 2026,
            mention="",
            progression=str(élève.progression).strip() if élève.progression else "AUCUNE_DEMANDE"
        )
        
        db.add(nouvel_apprenant)
        compteur_insertions += 1

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"❌ Erreur lors du commit bulk Excel dans MySQL : {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Impossible de valider l'écriture de masse dans WampServer : {str(e)}"
        )

    return {
        "status": "success",
        "message": "Traitement du fichier Excel achevé avec succès !",
        "statistiques": {
            "total_lignes_traitees": len(paquet.apprenants),
            "enregistrements_bdd": compteur_insertions,
            "doublons_ignores": compteur_doublons
        },
        "details_doublons": list(set(liste_matricules_doublons))
    }
    

@router.post("/creer", status_code=status.HTTP_201_CREATED)
def creer_nouvel_apprenant(apprenant_in: ApprenantCreate, db: Session = Depends(get_db_session)):
    
    im_propre = str(apprenant_in.im_apprenant).strip().upper()
    
    pattern_matricule = r"^.{3}-\d{4}-.{3}$"
    
    if not re.match(pattern_matricule, im_propre):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"❌ Structure invalide : Le matricule '{im_propre}' ne respecte pas le format obligatoire XXX-0000-XXX (4 chiffres au milieu)."
        )

    existe_deja = db.exec(select(Apprenant).where(Apprenant.im_apprenant == im_propre)).first()
    if existe_deja:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="⚠️ Un apprenant possède déjà ce numéro d'immatriculation (IM) dans le registre."
        )

    nouvel_apprenant = Apprenant(
        im_apprenant=im_propre,  
        nom_apprenant=str(apprenant_in.nom_apprenant).strip().upper(),
        prenom_apprenant=str(apprenant_in.prenom_apprenant).strip() if apprenant_in.prenom_apprenant else "",
        date_naiss=apprenant_in.date_naiss,
        lieu_naiss=str(apprenant_in.lieu_naiss).strip().upper() if apprenant_in.lieu_naiss else "INCONNU",
        examen_id=str(apprenant_in.examen_id).strip().upper() if apprenant_in.examen_id else "CAP",
        session=int(apprenant_in.session) if apprenant_in.session else 2026,
        mention="",
        etablissement_id=apprenant_in.etablissement_id,
        secteur_id=apprenant_in.secteur_id,
        filiere_id=apprenant_in.filiere_id,
        metier_id=apprenant_in.metier_id,
        progression=str(apprenant_in.progression).strip() if apprenant_in.progression else "AUCUNE_DEMANDE"
    )
    
    try:
        db.add(nouvel_apprenant)
        db.commit()
        db.refresh(nouvel_apprenant)
        
        return {
            "status": "success",
            "message": "Candidat enregistré avec succès dans la base décentralisée !",
            "data": nouvel_apprenant
        }
    except Exception as e:
        db.rollback()
        print(f"❌ Échec d'écriture MySQL de l'apprenant : {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur fatale d'écriture BDD : {str(e)}"
        )
    
    
def supprimer_notes_lies_apprenant(id_apprenant: int, db: Session):
    notes_a_supprimer = db.exec(
        select(Note).where(Note.id_apprenant == id_apprenant)
    ).all()
    for note in notes_a_supprimer:
        db.delete(note)


@router.delete("/supprimer/{id_apprenant}", status_code=status.HTTP_200_OK)
def supprimer_apprenant_du_registre(id_apprenant: int, db: Session = Depends(get_db_session)):
    apprenant_cible = db.get(Apprenant, id_apprenant)
    
    if not apprenant_cible:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="⚠️ Impossible de supprimer : Cet apprenant n'existe pas dans la base de données."
        )
    im_cible = str(
        getattr(apprenant_cible, "im_apprenant", "") 
        or getattr(apprenant_cible, "im", "") 
        or getattr(apprenant_cible, "matricule", "")
    ).strip().upper()

    DemandeModel = getattr(models, "Demande", None)
    if DemandeModel and im_cible:
        demandes_app = db.exec(
            select(DemandeModel).where(DemandeModel.im_apprenant == im_cible)
        ).all()

        titres_termines = {"ATTESTATION": False, "RELEVE": False, "DIPLOME": False}
        statuts_valides = {"TERMINER", "TERMINÉ", "OBTENU"}

        for d in demandes_app:
            doc = str(getattr(d, "type_document", "") or getattr(d, "document", "")).upper()
            st = str(getattr(d, "statut", "")).upper()
            if st in statuts_valides:
                if "ATTESTATION" in doc:
                    titres_termines["ATTESTATION"] = True
                elif "RELEVE" in doc or "NOTE" in doc:
                    titres_termines["RELEVE"] = True
                elif "DIPLOME" in doc:
                    titres_termines["DIPLOME"] = True

        if not all(titres_termines.values()):
            manquants = [k for k, v in titres_termines.items() if not v]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"⛔ Suppression bloquée : Les 3 demandes (Attestation, Relevé de notes, Diplôme) doivent être au statut 'Terminé' avant de supprimer cet apprenant. Manquant(s) : {', '.join(manquants)}."
            )

    supprimer_notes_lies_apprenant(id_apprenant, db)
    db.delete(apprenant_cible)
    db.commit()
    
    return {
        "status": "success",
        "message": f"L'apprenant {apprenant_cible.nom_apprenant} et ses notes associées ont été effacés définitivement."
    }



@router.put("/modifier/{im_apprenant}", status_code=status.HTTP_200_OK)
def modifier_renseignements_apprenant(im_apprenant: str, apprenant_in: ApprenantCreate, db: Session = Depends(get_db_session)):
    apprenant_cible = db.exec(select(Apprenant).where(Apprenant.im_apprenant == im_apprenant)).first()
    
    if not apprenant_cible:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="⚠️ Impossible de modifier : Cet apprenant n'existe pas dans le registre."
        )
    
    apprenant_cible.nom_apprenant = apprenant_in.nom_apprenant.upper()
    apprenant_cible.prenom_apprenant = apprenant_in.prenom_apprenant
    apprenant_cible.date_naiss = apprenant_in.date_naiss
    apprenant_cible.lieu_naiss = apprenant_in.lieu_naiss
    apprenant_cible.examen_id = apprenant_in.examen_id.upper()
    apprenant_cible.session = apprenant_in.session
    # ❌ Ancienne ligne à supprimer ou commenter :
    # apprenant_cible.mention = apprenant_in.mention
    # ✅ La mention est désormais protégée et gérée uniquement par l'importation des notes
    apprenant_cible.etablissement_id = apprenant_in.etablissement_id
    apprenant_cible.secteur_id = apprenant_in.secteur_id
    apprenant_cible.filiere_id = apprenant_in.filiere_id
    apprenant_cible.metier_id = apprenant_in.metier_id
    
    db.add(apprenant_cible)
    db.commit()
    db.refresh(apprenant_cible)
    
    return {"status": "success", "message": "Mise à jour SQLite validée !"}

@router.get("/notifications-attente", status_code=status.HTTP_200_OK)
def compter_notifications_apprenants_en_attente(db: Session = Depends(get_db_session)):
    """
    Retourne le nombre total d'apprenants envoyés à distance par 
    les chefs de centre sur le terrain et en attente de validation.
    """
    requete = select(func.count(Apprenant.id_apprenant)).where(
        Apprenant.progression == "EN_ATTENTE_VALIDATION"
    )
    total_en_attente = db.exec(requete).one()
    
    return {
        "notifications_count": total_en_attente,
        "statut": "success"
    }


def trouver_id_examen_apprenant(apprenant: Apprenant, db: Session) -> Optional[int]:
    id_ex = getattr(apprenant, "examen_id", None) or getattr(apprenant, "id_examen", None)
    if id_ex is not None:
        return int(id_ex)
    
    nom_ex = getattr(apprenant, "nom_examen", None) or getattr(apprenant, "examen", None)
    if nom_ex:
        nom_propre = str(nom_ex).strip().lower()
        tous_examens = db.exec(select(Examen)).all()
        for ex in tous_examens:
            titre_ex = str(getattr(ex, "nom_exam", "") or getattr(ex, "nom_examen", "")).strip().lower()
            if titre_ex == nom_propre:
                return getattr(ex, "id_examen", None) or getattr(ex, "id", None)
    return None


@router.get("/{id_apprenant}/releve-notes", status_code=status.HTTP_200_OK)
def obtenir_releve_notes(id_apprenant: int, db: Session = Depends(get_db_session)):
    apprenant = db.get(Apprenant, id_apprenant)
    if not apprenant:
        raise HTTPException(status_code=404, detail="Apprenant introuvable.")

    id_exam_cible = trouver_id_examen_apprenant(apprenant, db)
    matieres = db.exec(
        select(Matiere).where(Matiere.id_examen == id_exam_cible)
    ).all() if id_exam_cible else []

    notes_existantes = db.exec(
        select(Note).where(Note.id_apprenant == id_apprenant)
    ).all()
    map_notes = {n.id_matiere: n.note_sur_20 for n in notes_existantes}

    lignes_bulletin = []
    total_points = 0.0
    total_coeffs = 0

    for m in matieres:
        note_val = map_notes.get(m.id_matiere, 0.0)
        points = note_val * m.coefficient
        total_points += points
        total_coeffs += m.coefficient

        lignes_bulletin.append({
            "id_matiere": m.id_matiere,
            "nom_matiere": m.nom_matiere,
            "type_epreuve": m.type_epreuve,
            "coefficient": m.coefficient,
            "note_sur_20": note_val,
            "note_ponderee": round(points, 2)
        })

    moyenne = round(total_points / total_coeffs, 2) if total_coeffs > 0 else 0.0

    if moyenne >= 16:
        mention = "TRÈS BIEN"
    elif moyenne >= 14:
        mention = "BIEN"
    elif moyenne >= 12:
        mention = "ASSEZ BIEN"
    elif moyenne >= 10:
        mention = "PASSABLE"
    else:
        mention = "AJOURNÉ"

    return {
        "apprenant": apprenant,
        "lignes": lignes_bulletin,
        "total_points": round(total_points, 2),
        "total_coefficients": total_coeffs,
        "moyenne_generale": moyenne,
        "mention_calculee": mention
    }

@router.post("/enregistrer-releve", status_code=status.HTTP_200_OK)
def enregistrer_releve_notes(data: ReleveNotesIn, db: Session = Depends(get_db_session)):
    apprenant = db.get(Apprenant, data.id_apprenant)
    if not apprenant:
        raise HTTPException(status_code=404, detail="Apprenant introuvable.")

    for item in data.notes:
        if item.note_sur_20 < 0 or item.note_sur_20 > 20:
            raise HTTPException(status_code=400, detail="Les notes doivent être comprises entre 0 et 20.")

        note_existante = db.exec(
            select(Note).where(
                Note.id_apprenant == data.id_apprenant,
                Note.id_matiere == item.id_matiere
            )
        ).first()

        if note_existante:
            note_existante.note_sur_20 = item.note_sur_20
            db.add(note_existante)
        else:
            nouvelle_note = Note(
                id_apprenant=data.id_apprenant,
                id_matiere=item.id_matiere,
                note_sur_20=item.note_sur_20
            )
            db.add(nouvelle_note)

    db.commit()

    bilan = obtenir_releve_notes(data.id_apprenant, db)
    if hasattr(apprenant, "mention"):
        apprenant.mention = bilan["mention_calculee"]
    if hasattr(apprenant, "moyenne"):
        apprenant.moyenne = bilan["moyenne_generale"]
    db.add(apprenant)
    db.commit()

    return {"status": "success", "bilan": bilan}




def normaliser_texte(texte: str) -> str:
    if not texte:
        return ""
    sans_accents = ''.join(
        c for c in unicodedata.normalize('NFD', str(texte))
        if unicodedata.category(c) != 'Mn'
    )
    propre = sans_accents.strip().lower()
    return propre[:-1] if propre.endswith('s') and len(propre) > 3 else propre

@router.post("/importer-notes-excel", status_code=status.HTTP_200_OK)
async def importer_notes_depuis_excel(
    id_examen: int = Form(...),
    fichier: UploadFile = File(...),
    db: Session = Depends(get_db_session)
):
    try:
        if not fichier.filename.endswith((".xlsx", ".xls")):
            raise HTTPException(status_code=400, detail="Veuillez sélectionner un fichier Excel (.xlsx).")

        contenu = await fichier.read()
        wb = openpyxl.load_workbook(io.BytesIO(contenu), data_only=True)
        feuille = wb.active

        toutes_lignes = list(feuille.iter_rows(values_only=True))
        if not toutes_lignes:
            raise HTTPException(status_code=400, detail="Le fichier Excel est vide.")

        index_entete = 0
        for idx, row in enumerate(toutes_lignes[:10]):
            if row and len(row) > 0 and row[0] is not None:
                c0 = normaliser_texte(row[0])
                if any(mot in c0 for mot in ["matricule", "im", "inscription", "numero"]):
                    index_entete = idx
                    break

        entetes = [str(cell).strip() if cell is not None else "" for cell in toutes_lignes[index_entete]]

        matieres_examen = db.exec(select(Matiere).where(Matiere.id_examen == id_examen)).all()
        if not matieres_examen:
            raise HTTPException(status_code=400, detail="Aucune matière configurée pour cet examen.")

        map_matieres_par_nom = {normaliser_texte(m.nom_matiere): m for m in matieres_examen}

        colonnes_matieres = {}
        for idx_col in range(3, len(entetes)):
            nom_col_norm = normaliser_texte(entetes[idx_col])
            if nom_col_norm in map_matieres_par_nom:
                colonnes_matieres[idx_col] = map_matieres_par_nom[nom_col_norm]

        if not colonnes_matieres:
            noms_attendus = ", ".join([m.nom_matiere for m in matieres_examen])
            noms_trouves = ", ".join([e for e in entetes[3:] if e])
            raise HTTPException(
                status_code=400,
                detail=f"Colonnes non reconnues.\n• Attendues : [{noms_attendus}]\n• Lues dans Excel : [{noms_trouves}]"
            )

        tous_apprenants = db.exec(select(Apprenant)).all()
        apprenants_exam = [
            app for app in tous_apprenants 
            if trouver_id_examen_apprenant(app, db) == id_examen
        ]

        nb_importes = 0
        lignes_ignorees = []

        for num_ligne, row in enumerate(toutes_lignes[index_entete + 1:], start=index_entete + 2):
            if not row or len(row) == 0 or row[0] is None or str(row[0]).strip() == "":
                continue

            im_excel = str(row[0]).strip().upper()
            nom_excel = str(row[1]).strip().upper() if len(row) > 1 and row[1] is not None else ""
            prenom_excel = str(row[2]).strip().lower() if len(row) > 2 and row[2] is not None else ""

            candidat_trouve = None
            for app in apprenants_exam:
                im_base = str(
                    getattr(app, "im", None) 
                    or getattr(app, "im_apprenant", None) 
                    or getattr(app, "matricule", None) 
                    or getattr(app, "numero_inscription", "")
                ).strip().upper()
                
                nom_base = str(
                    getattr(app, "nom", None) 
                    or getattr(app, "nom_apprenant", "")
                ).strip().upper()
                
                prenom_base = str(
                    getattr(app, "prenom", None) 
                    or getattr(app, "prenom_apprenant", None) 
                    or getattr(app, "prenoms", "")
                ).strip().lower()

                if im_base == im_excel and nom_base == nom_excel and prenom_base == prenom_excel:
                    candidat_trouve = app
                    break

            if not candidat_trouve:
                lignes_ignorees.append(f"Ligne {num_ligne} ({im_excel} - {nom_excel} {prenom_excel}) : non trouvé dans l'examen sélectionné.")
                continue

            id_app = getattr(candidat_trouve, "id_apprenant", None) or getattr(candidat_trouve, "id", None)
            for idx_col, matiere_obj in colonnes_matieres.items():
                val_brute = row[idx_col] if idx_col < len(row) else None
                if val_brute is None or str(val_brute).strip() == "":
                    continue

                note_float = float(str(val_brute).replace(",", "."))
                if note_float < 0 or note_float > 20:
                    continue

                note_existante = db.exec(
                    select(Note).where(
                        Note.id_apprenant == id_app,
                        Note.id_matiere == matiere_obj.id_matiere
                    )
                ).first()

                if note_existante:
                    note_existante.note_sur_20 = note_float
                    db.add(note_existante)
                else:
                    db.add(Note(
                        id_apprenant=id_app,
                        id_matiere=matiere_obj.id_matiere,
                        note_sur_20=note_float
                    ))

            db.commit()

            bilan = obtenir_releve_notes(id_app, db)
            if hasattr(candidat_trouve, "mention"):
                candidat_trouve.mention = bilan["mention_calculee"]
            if hasattr(candidat_trouve, "moyenne"):
                candidat_trouve.moyenne = bilan["moyenne_generale"]
            db.add(candidat_trouve)
            db.commit()
            db.refresh(candidat_trouve)

            nb_importes += 1


        return {
            "status": "success",
            "nb_importes": nb_importes,
            "nb_ignores": len(lignes_ignorees),
            "details_ignores": lignes_ignorees
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ Erreur Python lors de l'importation Excel des notes : {e}")
        raise HTTPException(status_code=500, detail=f"Erreur serveur : {str(e)}")


@router.get("/avec-notes/ids", status_code=status.HTTP_200_OK)
def lister_ids_apprenants_avec_notes(db: Session = Depends(get_db_session)):
    """
    Retourne la liste des identifiants des apprenants ayant déjà des notes importées.
    """
    ids = db.exec(select(Note.id_apprenant).distinct()).all()
    return list(ids)




class RelevesGroupesIn(BaseModel):
    ids_apprenants: List[int]

def construire_elements_releve(id_apprenant: int, db: Session, styles_dict: dict) -> list:
    bilan = obtenir_releve_notes(id_apprenant, db)
    apprenant = bilan["apprenant"]
    lignes = bilan["lignes"]

    if not lignes:
        return []

    nom_complet = f"{getattr(apprenant, 'nom', '') or getattr(apprenant, 'nom_apprenant', '')} {getattr(apprenant, 'prenom', '') or getattr(apprenant, 'prenom_apprenant', '')}".strip()
    matricule = str(getattr(apprenant, "im", "") or getattr(apprenant, "im_apprenant", "") or getattr(apprenant, "matricule", "N/A")).strip()

    date_naiss_brute = getattr(apprenant, "date_naissance", None) or getattr(apprenant, "date_naiss", None)
    if hasattr(date_naiss_brute, "strftime"):
        date_naiss_str = date_naiss_brute.strftime("%d/%m/%Y")
    else:
        date_naiss_str = str(date_naiss_brute or "").strip()

    lieu_naiss_str = str(getattr(apprenant, "lieu_naissance", None) or getattr(apprenant, "lieu_naiss", None) or "").strip()

    if date_naiss_str and lieu_naiss_str:
        date_lieu_naissance = f"{date_naiss_str} à {lieu_naiss_str}"
    elif date_naiss_str:
        date_lieu_naissance = date_naiss_str
    elif lieu_naiss_str:
        date_lieu_naissance = f"à {lieu_naiss_str}"
    else:
        date_lieu_naissance = "Non spécifié"

    nom_examen = getattr(apprenant, "nom_examen", None) or getattr(apprenant, "nom_exam", None) or getattr(apprenant, "examen", None)
    if not nom_examen:
        id_ex = trouver_id_examen_apprenant(apprenant, db)
        ExamenModel = getattr(models, "Examen", None)
        if id_ex and ExamenModel:
            exam_obj = db.get(ExamenModel, id_ex)
            if exam_obj:
                nom_examen = getattr(exam_obj, "nom_exam", None) or getattr(exam_obj, "nom_examen", None)
    nom_examen = str(nom_examen or "Non spécifié")

    centre = (
        getattr(apprenant, "centre_examen", None)
        or getattr(apprenant, "etablissement", None)
        or getattr(apprenant, "nom_etablissement", None)
        or getattr(apprenant, "centre", None)
    )
    if not centre:
        id_etab = getattr(apprenant, "etablissement_id", None) or getattr(apprenant, "id_etablissement", None)
        EtabModel = getattr(models, "Etablissement", None)
        if id_etab and EtabModel:
            etab_obj = db.get(EtabModel, id_etab)
            if etab_obj:
                centre = getattr(etab_obj, "nom_etablissement", None) or getattr(etab_obj, "nom", None)

    DemandeModel = getattr(models, "Demande", None)
    if not centre and matricule != "N/A" and DemandeModel and hasattr(DemandeModel, "im_apprenant"):
        demande_obj = db.exec(select(DemandeModel).where(DemandeModel.im_apprenant == matricule)).first()
        if demande_obj:
            centre = getattr(demande_obj, "centre_examen", None) or getattr(demande_obj, "centre", None)

    centre = str(centre or "Non spécifié")

    session_exam = (
        getattr(apprenant, "session", None)
        or getattr(apprenant, "session_examen", None)
        or getattr(apprenant, "annee_scolaire", None)
        or getattr(apprenant, "annee", None)
    )
    if not session_exam and matricule != "N/A" and DemandeModel and hasattr(DemandeModel, "im_apprenant"):
        demande_obj = db.exec(select(DemandeModel).where(DemandeModel.im_apprenant == matricule)).first()
        if demande_obj:
            session_exam = getattr(demande_obj, "session", None) or getattr(demande_obj, "annee", None)

    session_exam = str(session_exam or datetime.now().year)

    page_elements = []

    page_elements.append(Paragraph(
        "REPOBLIKAN'I MADAGASIKARA<br/>Fitiavana - Tanindrazana - Fandrosoana<br/>"
        "--------------------<br/>"
        "MINISTÈRE DE L'ENSEIGNEMENT TECHNIQUE ET DE LA FORMATION PROFESSIONNELLE<br/>"
        "DIRECTION RÉGIONALE DE L'ENSEIGNEMENT TECHNIQUE ET DE LA FORMATION PROFESSIONNELLE<br/>"
        "AMORON'I MANIA (DRETFP)",
        styles_dict["entete"]
    ))
    page_elements.append(Spacer(1, 10))
    page_elements.append(Paragraph("RELEVÉ DE NOTES OFFICIEL", styles_dict["titre"]))

    bloc_identite = Paragraph(
        f"<b>Numéro d'Inscription :</b> {matricule}<br/>"
        f"<b>Nom et Prénoms :</b> {nom_complet}<br/>"
        f"<b>Date et lieu de naissance :</b> {date_lieu_naissance}<br/>"
        f"<b>Examen :</b> {nom_examen}<br/>"
        f"<b>Centre d'Examen :</b> {centre}<br/>"
        f"<b>Session :</b> {session_exam}<br/>"
        f"<b>Date d'édition :</b> {datetime.now().strftime('%d/%m/%Y')}",
        styles_dict["info"]
    )

    table_header_candidat = Table([[bloc_identite]], colWidths=[525])
    table_header_candidat.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOX', (0, 0), (-1, -1), 0.8, colors.HexColor('#dadce0')),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
        ('PADDING', (0, 0), (-1, -1), 10),
    ]))
    page_elements.append(table_header_candidat)
    page_elements.append(Spacer(1, 18))

    donnees_tableau = [
        ["Matière / Épreuve", "Coeff.", "Note / 20", "Points"]
    ]

    for l in lignes:
        donnees_tableau.append([
            l["nom_matiere"],
            str(l["coefficient"]),
            f"{l['note_sur_20']:.2f}",
            f"{l['note_ponderee']:.2f}"
        ])

    donnees_tableau.append([
        "TOTAL GÉNÉRAL", str(bilan["total_coefficients"]), "—", f"{bilan['total_points']:.2f}"
    ])
    donnees_tableau.append([
        "MOYENNE GÉNÉRALE", "", f"{bilan['moyenne_generale']:.2f} / 20", bilan["mention_calculee"]
    ])

    table_notes = Table(donnees_tableau, colWidths=[255, 70, 100, 100])
    nb_lignes_total = len(donnees_tableau)

    table_notes.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#002f6c')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),
        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.6, colors.HexColor('#bdc1c6')),
        ('PADDING', (0, 0), (-1, -1), 7),
        ('BACKGROUND', (0, nb_lignes_total - 2), (-1, nb_lignes_total - 2), colors.HexColor('#f1f3f4')),
        ('FONTNAME', (0, nb_lignes_total - 2), (-1, nb_lignes_total - 2), 'Helvetica-Bold'),
        ('BACKGROUND', (0, nb_lignes_total - 1), (-1, nb_lignes_total - 1), colors.HexColor('#e8f0fe')),
        ('TEXTCOLOR', (0, nb_lignes_total - 1), (-1, nb_lignes_total - 1), colors.HexColor('#002f6c')),
        ('FONTNAME', (0, nb_lignes_total - 1), (-1, nb_lignes_total - 1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, nb_lignes_total - 1), (-1, nb_lignes_total - 1), 11),
    ]))

    page_elements.append(table_notes)
    page_elements.append(Spacer(1, 25))

    page_elements.append(Paragraph(
        f"Fait à Ambositra, le {datetime.now().strftime('%d/%m/%Y')}<br/><br/>"
        "<b>Le Directeur Régional de l'Enseignement Technique<br/>et de la Formation Professionnelle</b>",
        styles_dict["pied"]
    ))

    return page_elements


@router.get("/{id_apprenant}/releve-notes/pdf", status_code=status.HTTP_200_OK)
def generer_releve_notes_pdf(id_apprenant: int, db: Session = Depends(get_db_session)):
    styles = getSampleStyleSheet()
    styles_dict = {
        "entete": ParagraphStyle('Entete', parent=styles['Normal'], alignment=TA_CENTER, fontSize=10, leading=13, fontName='Helvetica-Bold'),
        "titre": ParagraphStyle('Titre', parent=styles['Title'], alignment=TA_CENTER, fontSize=15, textColor=colors.HexColor('#002f6c'), spaceBefore=10, spaceAfter=14),
        "info": ParagraphStyle('Info', parent=styles['Normal'], fontSize=10, leading=15),
        "pied": ParagraphStyle('Pied', parent=styles['Normal'], alignment=TA_RIGHT, fontSize=10, leading=14)
    }

    elements = construire_elements_releve(id_apprenant, db, styles_dict)
    if not elements:
        raise HTTPException(
            status_code=400,
            detail="Aucune matière ou note enregistrée pour ce candidat. Importez d'abord les notes."
        )

    apprenant = db.get(Apprenant, id_apprenant)
    matricule = str(getattr(apprenant, "im", "") or getattr(apprenant, "im_apprenant", "") or getattr(apprenant, "matricule", "candidat")).strip()

    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=A4, rightMargin=35, leftMargin=35, topMargin=30, bottomMargin=30)
    doc.build(elements)
    pdf_buffer.seek(0)

    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="Releve_Notes_{matricule}.pdf"'}
    )


@router.post("/releves-notes/pdf-groupe", status_code=status.HTTP_200_OK)
def generer_releves_notes_pdf_groupe(data: RelevesGroupesIn, db: Session = Depends(get_db_session)):
    if not data.ids_apprenants:
        raise HTTPException(status_code=400, detail="Aucun candidat sélectionné.")

    styles = getSampleStyleSheet()
    styles_dict = {
        "entete": ParagraphStyle('Entete', parent=styles['Normal'], alignment=TA_CENTER, fontSize=10, leading=13, fontName='Helvetica-Bold'),
        "titre": ParagraphStyle('Titre', parent=styles['Title'], alignment=TA_CENTER, fontSize=15, textColor=colors.HexColor('#002f6c'), spaceBefore=10, spaceAfter=14),
        "info": ParagraphStyle('Info', parent=styles['Normal'], fontSize=10, leading=15),
        "pied": ParagraphStyle('Pied', parent=styles['Normal'], alignment=TA_RIGHT, fontSize=10, leading=14)
    }

    tous_elements = []
    nb_pages = 0

    for id_app in data.ids_apprenants:
        elements_candidat = construire_elements_releve(id_app, db, styles_dict)
        if not elements_candidat:
            continue

        if nb_pages > 0:
            tous_elements.append(PageBreak())

        tous_elements.extend(elements_candidat)
        nb_pages += 1

    if nb_pages == 0:
        raise HTTPException(status_code=400, detail="Aucun des candidats sélectionnés n'a de notes enregistrées.")

    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=A4,
        rightMargin=35,
        leftMargin=35,
        topMargin=30,
        bottomMargin=30
    )
    doc.build(tous_elements)
    pdf_buffer.seek(0)

    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="Releves_Notes_Groupes.pdf"'}
    )



class SuppressionSessionNotesIn(BaseModel):
    ids_apprenants: List[int]

@router.post("/notes/supprimer-session", status_code=status.HTTP_200_OK)
def supprimer_notes_session(data: SuppressionSessionNotesIn, db: Session = Depends(get_db_session)):
    if not data.ids_apprenants:
        raise HTTPException(status_code=400, detail="Aucun candidat dans cette session.")

    nb_notes_supprimees = 0
    for id_app in data.ids_apprenants:
        notes_app = db.exec(select(Note).where(Note.id_apprenant == id_app)).all()
        for n in notes_app:
            db.delete(n)
            nb_notes_supprimees += 1

        apprenant = db.get(Apprenant, id_app)
        if apprenant:
            if hasattr(apprenant, "mention"):
                apprenant.mention = None
            if hasattr(apprenant, "moyenne"):
                apprenant.moyenne = None
            db.add(apprenant)

    db.commit()
    return {
        "status": "success",
        "nb_notes_supprimees": nb_notes_supprimees,
        "nb_apprenants_maj": len(data.ids_apprenants)
    }




class AttestationsGroupesIn(BaseModel):
    ids_apprenants: List[int]


from reportlab.lib.pagesizes import A4, landscape

def dessiner_bordure_attestation(canvas, doc):
    canvas.saveState()
    largeur, hauteur = landscape(A4) 

    marge_ext = 20
    canvas.setStrokeColor(colors.HexColor('#002f6c'))
    canvas.setLineWidth(2.4)
    canvas.rect(marge_ext, marge_ext, largeur - 2 * marge_ext, hauteur - 2 * marge_ext)

    marge_int = 26
    canvas.setStrokeColor(colors.HexColor('#5f6368'))
    canvas.setLineWidth(0.8)
    canvas.rect(marge_int, marge_int, largeur - 2 * marge_int, hauteur - 2 * marge_int)

    taille_coin = 8
    canvas.setFillColor(colors.HexColor('#002f6c'))
    coins = [
        (marge_ext, hauteur - marge_ext - taille_coin),
        (largeur - marge_ext - taille_coin, hauteur - marge_ext - taille_coin),
        (marge_ext, marge_ext),
        (largeur - marge_ext - taille_coin, marge_ext)
    ]
    for cx, cy in coins:
        canvas.rect(cx, cy, taille_coin, taille_coin, fill=1, stroke=0)

    canvas.restoreState()



def construire_elements_attestation(id_apprenant: int, db: Session) -> list:
    apprenant = db.get(Apprenant, id_apprenant)
    if not apprenant:
        return []

    nom_complet = f"{getattr(apprenant, 'nom_apprenant', '') or getattr(apprenant, 'nom', '')} {getattr(apprenant, 'prenom_apprenant', '') or getattr(apprenant, 'prenom', '')}".strip()
    matricule = str(getattr(apprenant, "im_apprenant", "") or getattr(apprenant, "im", "") or getattr(apprenant, "matricule", "N/A")).strip()

    date_naiss_brute = getattr(apprenant, "date_naiss", None) or getattr(apprenant, "date_naissance", None)
    date_naiss_str = date_naiss_brute.strftime("%d/%m/%Y") if hasattr(date_naiss_brute, "strftime") else str(date_naiss_brute or "").strip()
    lieu_naiss_str = str(getattr(apprenant, "lieu_naiss", None) or getattr(apprenant, "lieu_naissance", None) or "").strip()
    date_lieu_naissance = f"{date_naiss_str} à {lieu_naiss_str}".strip(" à") if (date_naiss_str or lieu_naiss_str) else "Non spécifié"

    nom_examen = getattr(apprenant, "nom_exam", None) or getattr(apprenant, "nom_examen", None) or getattr(apprenant, "examen", None)
    if not nom_examen:
        id_ex = getattr(apprenant, "examen_id", None) or getattr(apprenant, "id_examen", None)
        ExamenModel = getattr(models, "Examen", None)
        if id_ex and ExamenModel:
            exam_obj = db.get(ExamenModel, id_ex)
            if exam_obj:
                nom_examen = getattr(exam_obj, "nom_exam", None) or getattr(exam_obj, "nom_examen", None)
    nom_examen = str(nom_examen or "Non spécifié").upper()

    nom_secteur = getattr(apprenant, "secteur", None)
    id_sec = getattr(apprenant, "secteur_id", None) or getattr(apprenant, "id_secteur", None)
    sec_obj = None
    SecteurModel = getattr(models, "Secteur", None)
    if id_sec and SecteurModel:
        sec_obj = db.get(SecteurModel, id_sec)
        if sec_obj and not nom_secteur:
            nom_secteur = getattr(sec_obj, "nom_secteur", None)
    nom_secteur = str(nom_secteur or "Non spécifié").upper()

    centre = getattr(apprenant, "etablissement", None) or getattr(apprenant, "centre_examen", None)
    if not centre:
        id_etab = getattr(apprenant, "etablissement_id", None) or (getattr(sec_obj, "etablissement_id", None) if sec_obj else None)
        EtabModel = getattr(models, "Etablissement", None)
        if id_etab and EtabModel:
            etab_obj = db.get(EtabModel, id_etab)
            if etab_obj:
                centre = getattr(etab_obj, "nom_etablissement", None) or getattr(etab_obj, "nom", None)
    centre = str(centre or "Non spécifié").upper()

    nom_filiere = getattr(apprenant, "filiere", None)
    id_fil = getattr(apprenant, "filiere_id", None)
    FiliereModel = getattr(models, "Filiere", None)
    if not nom_filiere and id_fil and FiliereModel:
        fil_obj = db.get(FiliereModel, id_fil)
        if fil_obj:
            nom_filiere = getattr(fil_obj, "nom_filiere", None)

    nom_metier = getattr(apprenant, "metier", None)
    id_met = getattr(apprenant, "metier_id", None)
    MetierModel = getattr(models, "Metier", None)
    if not nom_metier and id_met and MetierModel:
        met_obj = db.get(MetierModel, id_met)
        if met_obj:
            nom_metier = getattr(met_obj, "nom_metier", None)

    filiere_metier = " / ".join([x for x in [str(nom_filiere or "").upper(), str(nom_metier or "").upper()] if x]) or "Non spécifié"
    session_exam = str(getattr(apprenant, "session", None) or datetime.now().year)
    mention = str(getattr(apprenant, "mention", None) or "PASSABLE").upper()

    styles = getSampleStyleSheet()
    style_entete = ParagraphStyle('EnteteAtt', parent=styles['Normal'], alignment=TA_CENTER, fontSize=9.5, leading=11.5, fontName='Helvetica-Bold')
    style_num = ParagraphStyle('NumAtt', parent=styles['Normal'], alignment=TA_CENTER, fontSize=10.5, spaceBefore=6, spaceAfter=4)
    style_titre = ParagraphStyle('TitreAtt', parent=styles['Title'], alignment=TA_CENTER, fontSize=16, fontName='Times-Bold', textColor=colors.HexColor('#002f6c'), spaceBefore=2, spaceAfter=10)
    style_corps = ParagraphStyle('CorpsAtt', parent=styles['Normal'], alignment=TA_LEFT, fontSize=11, leading=18, fontName='Times-Roman')
    style_avis = ParagraphStyle('AvisAtt', parent=styles['Normal'], alignment=TA_LEFT, fontSize=8.5, leading=11, fontName='Helvetica')
    style_sign = ParagraphStyle('SignAtt', parent=styles['Normal'], alignment=TA_CENTER, fontSize=9.5, leading=13, fontName='Helvetica')

    elements = []

    elements.append(Paragraph(
        "REPOBLIKAN'I MADAGASIKARA<br/>"
        "<i>Fitiavana – Tanindrazana – Fandrosoana</i><br/>"
        "***********<br/>"
        "MINISTERE DE L'ENSEIGNEMENT TECHNIQUE ET DE LA FORMATION PROFESSIONNELLE<br/>"
        "***************<br/>"
        "SECRETARIAT GENERAL<br/>"
        "***************<br/>"
        "DIRECTION REGIONALE DE L'ENSEIGNEMENT TECHNIQUE ET DE LA FORMATION PROFESSIONNELLE<br/>"
        "AMORON'I MANIA",
        style_entete
    ))

    elements.append(Paragraph(f"N° D'INSCRIPTION : <b>{matricule}</b>", style_num))
    elements.append(Paragraph("<u>ATTESTATION DE REUSSITE</u>", style_titre))

    elements.append(Paragraph(
        f"LE DIRECTEUR REGIONAL DE L'ENSEIGNEMENT TECHNIQUE ET DE LA FORMATION PROFESSIONNELLE, atteste que :<br/>"
        f"Nom : <b>{nom_complet}</b><br/>" 
        f"Né(e) le : <b>{date_lieu_naissance}</b><br/>"
        f"A subi avec succès l'Examen du : <b>{nom_examen}</b><br/>"
        f"Centre : <b>{centre}</b><br/>" 
        f"Secteur : <b>{nom_secteur}</b><br/>"
        f"Filière/Métier : <b>{filiere_metier}</b><br/>"
        f"Session du : <b>{session_exam}</b><br/>"
        f"Mention : <b>{mention}</b>",
        style_corps
    ))

    elements.append(Spacer(1, 18))

    bloc_avis = Paragraph(
        "<b><center>AVIS IMPORTANT</center></b><br/>"
        "Il ne peut être délivré qu'une seule attestation de réussite.<br/>"
        "L'intéressé(e) doit en faire autant de copies qu'il lui est<br/>"
        "nécessaire et les certifier conformes à l'original.",
        style_avis
    )
    table_avis = Table([[bloc_avis]], colWidths=[310])
    table_avis.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('PADDING', (0, 0), (-1, -1), 8),
    ]))

    bloc_signature = Paragraph(
        f"Fait à Ambositra, le {datetime.now().strftime('%d/%m/%Y')}<br/><br/>"
        "<b>P. LE DIRECTEUR REGIONAL DE L'ENSEIGNEMENT TECHNIQUE<br/>"
        "ET DE LA FORMATION PROFESSIONNELLE</b><br/><br/><br/>"
        "<i>Par délégation</i>",
        style_sign
    )

    table_pied = Table([[table_avis, bloc_signature]], colWidths=[330, 420])
    table_pied.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(table_pied)

    return elements




@router.get("/{id_apprenant}/attestation/pdf", status_code=status.HTTP_200_OK)
def generer_attestation_pdf(id_apprenant: int, db: Session = Depends(get_db_session)):
    elements = construire_elements_attestation(id_apprenant, db)
    if not elements:
        raise HTTPException(status_code=404, detail="Apprenant introuvable pour l'attestation.")

    apprenant = db.get(Apprenant, id_apprenant)
    matricule = str(getattr(apprenant, "im_apprenant", "") or getattr(apprenant, "im", "candidat")).strip()

    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=landscape(A4),
        rightMargin=45,
        leftMargin=45,
        topMargin=35,
        bottomMargin=32
    )
    doc.build(
        elements,
        onFirstPage=dessiner_bordure_attestation,
        onLaterPages=dessiner_bordure_attestation
    )
    pdf_buffer.seek(0)

    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="Attestation_{matricule}.pdf"'}
    )


@router.post("/attestations/pdf-groupe", status_code=status.HTTP_200_OK)
def generer_attestations_pdf_groupe(data: AttestationsGroupesIn, db: Session = Depends(get_db_session)):
    if not data.ids_apprenants:
        raise HTTPException(status_code=400, detail="Aucun candidat sélectionné.")

    tous_elements = []
    nb_pages = 0
    for id_app in data.ids_apprenants:
        el = construire_elements_attestation(id_app, db)
        if not el:
            continue
        if nb_pages > 0:
            tous_elements.append(PageBreak())
        tous_elements.extend(el)
        nb_pages += 1

    if nb_pages == 0:
        raise HTTPException(status_code=404, detail="Aucune attestation générable.")

    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=landscape(A4),
        rightMargin=45,
        leftMargin=45,
        topMargin=35,
        bottomMargin=32
    )
    doc.build(
        tous_elements,
        onFirstPage=dessiner_bordure_attestation,
        onLaterPages=dessiner_bordure_attestation
    )
    pdf_buffer.seek(0)

    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="Attestations_Groupees.pdf"'}
    )
