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
from fastapi import UploadFile, File, Form

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
            mention=None,
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
        mention=None,
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
    
@router.delete("/supprimer/{id_apprenant}", status_code=status.HTTP_200_OK)
def supprimer_apprenant_du_registre(id_apprenant: int, db: Session = Depends(get_db_session)):
    apprenant_cible = db.get(Apprenant, id_apprenant)
    
    if not apprenant_cible:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="⚠️ Impossible de supprimer : Cet apprenant n'existe pas dans la base de données."
        )
    
    db.delete(apprenant_cible)
    db.commit()
    
    return {
        "status": "success",
        "message": f"L'apprenant {apprenant_cible.nom_apprenant} a été effacé définitivement."
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
