from fastapi import APIRouter, HTTPException, status, Depends
from sqlmodel import Session, select, text
from pydantic import BaseModel
from typing import List, Optional, Any 
from datetime import datetime
from app.database.config import get_db_session
from app.database.models import DemandeTitre, Apprenant
from sqlalchemy import inspect
import re 

router = APIRouter()

class DemandeCreate(BaseModel):
    im_apprenant: Any
    nom_complet: Any
    type_document: Any
    centre_examen: Optional[Any] = ""
    statut: Optional[Any] = "EN_COURS"

class DemandeTransfertIn(BaseModel):
    im_apprenant: Any
    nom_apprenant: Any
    prenom_apprenant: Optional[Any] = ""
    session: Any
    type_document: Any
    statut: Optional[Any] = "EN_COURS"

@router.get("/liste")
def lister_toutes_les_demandes_de_titres(db: Session = Depends(get_db_session)):
    try:
        inspect_query = text("SHOW COLUMNS FROM demandes_titres")
        resultats_colonnes = db.execute(inspect_query).all()
        colonnes_existantes = [col[0] for col in resultats_colonnes]

        champs_souhaites = ["id_demande", "im_apprenant", "nom_complet", "session", "type_document", "statut", "centre_examen", "date_depot"]
        champs_valides = [c for c in champs_souhaites if c in colonnes_existantes]
        
        champs_sql = ", ".join(champs_valides)
        ordre_tri = "ORDER BY id_demande DESC" if "id_demande" in colonnes_existantes else ""
        
        query_brute = text(f"SELECT {champs_sql} FROM demandes_titres {ordre_tri}")
        resultat = db.execute(query_brute).mappings().all()
        
        return [dict(row) for row in resultat]
        
    except Exception as e:
        print(f"❌ Erreur lecture catalogue : {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"⚠️ Erreur de chargement du registre MySQL : {str(e)}"
        )
    
@router.post("/creer", status_code=status.HTTP_201_CREATED)
def creer_nouvelle_demande_administrative(demande_in: DemandeCreate, db: Session = Depends(get_db_session)):
    
    im_propre = str(demande_in.im_apprenant).strip()
    type_propre = str(demande_in.type_document).strip().upper()
    nom_propre = str(demande_in.nom_complet).strip().upper()
    centre_propre = str(demande_in.centre_examen).strip().upper() if demande_in.centre_examen else "CENTRE REGIONAL"

    try:
        verif_query = text("SELECT id_demande FROM demandes_titres WHERE im_apprenant = :im AND type_document = :type_doc")
        existe = db.execute(verif_query, {"im": im_propre, "type_doc": type_propre}).first()
        
        if existe:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"⚠️ Un dossier de type {type_propre} existe déjà pour ce candidat."
            )
    except HTTPException:
        raise
    except Exception as e:
        print(f"⚠️ Alerte anti-doublon ignorée (Table en cours de migration) : {e}")

    try:
        inspect_query = text("DESCRIBE demandes_titres")
        resultats_les_colonnes = db.execute(inspect_query).all()
        
        colonnes_reelles = [str(row[0]).lower().strip() for row in resultats_les_colonnes]
        
        toutes_les_valeurs = {
            "im_apprenant": im_propre,
            "nom_complet": nom_propre,
            "type_document": type_propre,
            "centre_examen": centre_propre,
            "statut": str(demande_in.statut).strip().upper() if hasattr(demande_in, 'statut') and demande_in.statut else "EN_TRAITEMENT",
            "date_depot": datetime.now().strftime("%d/%m/%Y")
        }
        colonnes_finales = [c for c in toutes_les_valeurs.keys() if c.lower().strip() in colonnes_reelles]
        
        if not colonnes_finales:
            raise Exception("Aucune correspondance de colonne trouvée dans ta table demandes_titres.")

        champs_sql = ", ".join(colonnes_finales)
        parametres_sql = ", ".join([f":{c}" for c in colonnes_finales])
        
        requete_brute = text(f"INSERT INTO demandes_titres ({champs_sql}) VALUES ({parametres_sql})")
        params_execution = {c: toutes_les_valeurs[c] for c in colonnes_finales}
        
        db.execute(requete_brute, params_execution)
        
        try:
            statement_apprenant = select(Apprenant).where(Apprenant.im_apprenant == im_propre)
            apprenant_concerne = db.exec(statement_apprenant).first()
            if apprenant_concerne:
                apprenant_concerne.progression = "EN_COURS"
                db.add(apprenant_concerne)
        except Exception as app_err:
            print(f"⚠️ Ignoré : Mise à jour progression apprenant : {app_err}")

        db.commit()
        return {"status": "success", "message": "Demande enregistrée avec succès dans MySQL !"}
        
    except Exception as e:
        db.rollback()
        print(f"❌ Défaillance lors de l'insertion MySQL : {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur d'écriture BDD : {str(e)}"
        )
     
@router.put("/envoyer-au-traitement/{id_demande}", status_code=status.HTTP_200_OK)
def envoyer_au_traitement_regional(id_demande: int, db: Session = Depends(get_db_session)):
    demande = db.get(DemandeTitre, id_demande)
    if not demande:
        raise HTTPException(status_code=404, detail="Demande introuvable.")
    
    demande.statut = "EN_COURS" 
    db.add(demande)
    db.commit()
    db.refresh(demande)
    return {"status": "success", "message": "Dossier envoyé à la liste de traitement.", "data": demande}


@router.put("/finaliser-signature/{id_demande}", status_code=status.HTTP_200_OK)
def finaliser_signature_titre(id_demande: int, db: Session = Depends(get_db_session)):
    demande = db.get(DemandeTitre, id_demande)
    if not demande:
        raise HTTPException(status_code=404, detail="Demande introuvable.")
    
    demande.statut = "TERMINER"  
    db.add(demande)
    db.commit()
    db.refresh(demande)
    return {"status": "success", "message": "Document officiellement imprimé et validé !"}



@router.delete("/supprimer/{id_demande}", status_code=status.HTTP_200_OK)
def supprimer_demande_titre(id_demande: int, db: Session = Depends(get_db_session)):
    demande = db.get(DemandeTitre, id_demande)
    if not demande:
        raise HTTPException(status_code=404, detail="Demande introuvable.")
    
    if demande.statut == "EN_ATTENTE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="⚠️ Action refusée : Impossible de supprimer une demande qui n'a pas encore été traitée."
        )
        
    db.delete(demande)
    db.commit()
    return {"status": "success", "message": "Demande supprimée définitivement de la base !"}


@router.put("/annuler/{id_demande}", status_code=status.HTTP_200_OK)
def annuler_demande_titre(id_demande: int, db: Session = Depends(get_db_session)):
    demande = db.get(DemandeTitre, id_demande)
    if not demande:
        raise HTTPException(status_code=404, detail="Demande introuvable.")
    
    if demande.statut == "VALIDE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="⚠️ Action refusée : Impossible d'annuler une demande déjà validée et signée officiellement."
        )
        
    demande.statut = "EN_ATTENTE" 
    db.add(demande)
    db.commit()
    db.refresh(demande)
    return {"status": "success", "message": "La demande a été réinitialisée au statut En attente.", "data": demande}

@router.post("/creer-depuis-enligne", status_code=status.HTTP_201_CREATED)
def creer_demande_depuis_flux_enligne(demande_in: DemandeTransfertIn, db: Session = Depends(get_db_session)):
    
    statement_doublon = select(DemandeTitre).where(
        (DemandeTitre.im_apprenant == demande_in.im_apprenant) & 
        (DemandeTitre.type_document == demande_in.type_document)
    )
    deja_transferee = db.exec(statement_doublon).first()
    
    if deja_transferee:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"⚠️ Le dossier de type {demande_in.type_document} pour le matricule {demande_in.im_apprenant} a déjà été actionné au Guichet."
        )

    prenom_part = f" {demande_in.prenom_apprenant}" if demande_in.prenom_apprenant else ""
    nom_complet_calcule = f"{demande_in.nom_apprenant.upper()}{prenom_part}"

    nouvelle_demande = DemandeTitre(
        im_apprenant=demande_in.im_apprenant,
        nom_complet=nom_complet_calcule,
        nom_apprenant=demande_in.nom_apprenant.upper(), 
        prenom_apprenant=demande_in.prenom_apprenant,
        session=demande_in.session,
        type_document=demande_in.type_document.upper(),
        statut=demande_in.statut.upper()
    )
    if hasattr(nouvelle_demande, "nom_complet"):
        setattr(nouvelle_demande, "nom_complet", nom_complet_calcule)
        
    db.add(nouvelle_demande)
    
    statement_apprenant = select(Apprenant).where(Apprenant.im_apprenant == demande_in.im_apprenant)
    apprenant_concerne = db.exec(statement_apprenant).first()
    if apprenant_concerne:
        apprenant_concerne.progression = demande_in.statut.upper()
        db.add(apprenant_concerne)

    db.commit()
    db.refresh(nouvelle_demande)
    return {"status": "success", "data": nouvelle_demande}

@router.post("/recevoir-enligne", status_code=status.HTTP_201_CREATED)
def recevoir_demande_depuis_portail_public(demande_in: DemandeTransfertIn, db: Session = Depends(get_db_session)):
    
    im_propre = str(demande_in.im_apprenant).strip()
    nom_saisi = str(demande_in.nom_apprenant).strip().upper()

    query_apprenant = text("""
        SELECT etablissement_id, nom_apprenant, prenom_apprenant 
        FROM apprenants 
        WHERE im_apprenant = :im
    """)
    apprenant_profil = db.execute(query_apprenant, {"im": im_propre}).first()
    if not apprenant_profil:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"❌ Rejet : Le numéro matricule '{im_propre}' n'existe pas dans le registre officiel des diplômés."
        )

    try:
        profil_dict = apprenant_profil._asdict()
        id_etablissement_candidat = profil_dict.get("etablissement_id")
        nom_reel_bdd = str(profil_dict.get("nom_apprenant", "")).strip().upper()
        prenom_eleve_brut = str(profil_dict.get("prenom_apprenant", "")).strip()
    except Exception:
        id_etablissement_candidat = apprenant_profil[0]
        nom_reel_bdd = str(apprenant_profil[1]).strip().upper()
        prenom_eleve_brut = str(apprenant_profil[2]).strip() if apprenant_profil[2] else ""

    if nom_saisi not in nom_reel_bdd and nom_reel_bdd not in nom_saisi:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="❌ Rejet : Les renseignements fournis (Nom et Matricule) ne correspondent à aucun profil valide."
        )

    type_propre = str(demande_in.type_document).strip().upper()
    verif_query = text("SELECT id_demande FROM demandes_titres WHERE im_apprenant = :im AND type_document = :type_doc")
    existe = db.execute(verif_query, {"im": im_propre, "type_doc": type_propre}).first()
    
    if existe:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="⚠️ Une demande en ligne pour ce titre est déjà enregistrée et en cours d'instruction."
        )

    prenom_part = f" {prenom_eleve_brut}" if prenom_eleve_brut else ""
    nom_complet_calcule = f"{nom_reel_bdd}{prenom_part}".strip().upper()

    nom_vrai_centre = None
    if id_etablissement_candidat:
        try:
            query_etab = text("""
                SELECT nom_etablissement 
                FROM etablissements 
                WHERE id_etablissement = :id_etab
            """)
            etab_db = db.execute(query_etab, {"id_etab": id_etablissement_candidat}).first()
            if etab_db:
                try:
                    nom_vrai_centre = str(etab_db._asdict().get("nom_etablissement")).strip().upper()
                except Exception:
                    nom_vrai_centre = str(etab_db[0]).strip().upper()
        except Exception as etab_err:
            print(f"⚠️ Erreur recherche établissement : {etab_err}")

    if not nom_vrai_centre:
        nom_vrai_centre = "CENTRE REGIONAL DRETFP"

    try:
        import sqlalchemy
        inspecteur = sqlalchemy.inspect(db.bind)
        colonnes_reelles = [col["name"].lower().strip() for col in inspecteur.get_columns("demandes_titres")]
        
        valeurs_possibles = {
            "im_apprenant": im_propre,
            "nom_complet": nom_complet_calcule,
            "session": int(demande_in.session) if demande_in.session else 2026,
            "type_document": type_propre,
            "centre_examen": nom_vrai_centre,
            "statut": "EN_ATTENTE",
            "date_depot": datetime.now().strftime("%d/%m/%Y")
        }
        
        colonnes_finales = [c for c in valeurs_possibles.keys() if c.lower().strip() in colonnes_reelles]
        champs_sql = ", ".join(colonnes_finales)
        parametres_sql = ", ".join([f":{c}" for c in colonnes_finales])
        
        requete_brute = text(f"INSERT INTO demandes_titres ({champs_sql}) VALUES ({parametres_sql})")
        params_execution = {c: valeurs_possibles[c] for c in colonnes_finales}
        
        db.execute(requete_brute, params_execution)
        db.commit()
        return {"status": "success", "message": f"Demande en ligne validée avec succès pour l'établissement : {nom_vrai_centre}"}
        
    except Exception as e:
        db.rollback()
        print(f"❌ Défaillance critique lors du stockage de la demande en ligne : {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur d'écriture BDD : {str(e)}"
        )

@router.put("/imprimer/{id_demande}", status_code=status.HTTP_200_OK)
def valider_et_cloturer_impression_titre(id_demande: int, db: Session = Depends(get_db_session)):
    try:
        verif_query = text("SELECT im_apprenant FROM demandes_titres WHERE id_demande = :id_dem")
        demande_existante = db.execute(verif_query, {"id_dem": id_demande}).first()
        
        if not demande_existante:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="⚠️ Erreur : Cette demande est introuvable dans le répertoire."
            )
            
        im_candidat = demande_existante[0]

        maj_statut_query = text("""
            UPDATE demandes_titres 
            SET statut = 'TERMINER' 
            WHERE id_demande = :id_dem
        """)
        db.execute(maj_statut_query, {"id_dem": id_demande})

        try:
            maj_apprenant_query = text("""
                UPDATE apprenants 
                SET progression = 'TERMINER' 
                WHERE im_apprenant = :im
            """)
            db.execute(maj_apprenant_query, {"im": im_candidat})
        except Exception as app_err:
            print(f"⚠️ Ignoré : Progression apprenant non supportée : {app_err}")

        db.commit()
        return {"status": "success", "message": "Statut de l'impression synchronisé avec succès !"}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ Crash d'impression BDD : {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur serveur MySQL lors de l'impression : {str(e)}"
        )
    
@router.put("/modifier/{id_demande}", status_code=status.HTTP_200_OK)
def modifier_statut_ou_contenu_demande(id_demande: int, demande_in: DemandeCreate, db: Session = Depends(get_db_session)):
    try:
        verif_query = text("SELECT id_demande FROM demandes_titres WHERE id_demande = :id_dem")
        existe = db.execute(verif_query, {"id_dem": id_demande}).first()
        
        if not existe:
            raise HTTPException(status_code=404, detail="⚠️ Cette demande n'existe pas dans MySQL.")

        maj_query = text("""
            UPDATE demandes_titres 
            SET statut = :statut,
                nom_complet = :nom,
                centre_examen = :centre
            WHERE id_demande = :id_dem
        """)
        
        db.execute(maj_query, {
            "statut": str(demande_in.statut).strip().upper() if demande_in.statut else "OBTENU",
            "nom": str(demande_in.nom_complet).strip().upper(),
            "centre": str(demande_in.centre_examen).strip().upper() if demande_in.centre_examen else "LTP AMBOSITRA",
            "id_dem": id_demande
        })

        try:
            maj_app_query = text("""
                UPDATE apprenants 
                SET progression = :statut
                WHERE im_apprenant = :im
            """)
            db.execute(maj_app_query, {
                "statut": str(demande_in.statut).strip().upper() if demande_in.statut else "OBTENU",
                "im": str(demande_in.im_apprenant).strip()
            })
        except Exception as app_err:
            print(f"⚠️ Progression apprenant non mise à jour : {app_err}")

        db.commit()
        return {"status": "success", "message": "Demande mise à jour avec succès dans MySQL !"}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ Crash PUT modifier_demande : {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur serveur d'écriture : {str(e)}"
        )
        
@router.put("/changer-statut-diplome/{id_demande}", status_code=status.HTTP_200_OK)
def changer_statut_exclusif_diplome(id_demande: int, statut_cible: str, db: Session = Depends(get_db_session)):
    try:
        statut_propre = str(statut_cible).strip().upper()
        
        verif_query = text("SELECT im_apprenant FROM demandes_titres WHERE id_demande = :id_dem")
        existe = db.execute(verif_query, {"id_dem": id_demande}).first()
        
        if not existe:
            raise HTTPException(status_code=404, detail="⚠️ Demande introuvable dans MySQL.")
            
        im_candidat = existe[0]

        maj_query = text("""
            UPDATE demandes_titres 
            SET statut = :statut 
            WHERE id_demande = :id_dem
        """)
        db.execute(maj_query, {"statut": statut_propre, "id_dem": id_demande})

        try:
            maj_app_query = text("""
                UPDATE apprenants 
                SET progression = :statut 
                WHERE im_apprenant = :im
            """)
            db.execute(maj_app_query, {"statut": statut_propre, "im": im_candidat})
        except Exception as app_err:
            print(f"⚠️ Ignoré : Synchronisation progression apprenant : {app_err}")

        db.commit()
        return {"status": "success", "message": f"Statut basculé vers {statut_propre} avec succès !"}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ Défaillance PUT changer-statut-diplome : {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur d'écriture MySQL : {str(e)}"
        )

@router.post("/recevoir-enligne", status_code=status.HTTP_201_CREATED)
def recevoir_demande_depuis_portail_public(demande_in: DemandeTransfertIn, db: Session = Depends(get_db_session)):
    
    im_propre = str(demande_in.im_apprenant).strip().upper()
    nom_saisi = str(demande_in.nom_apprenant).strip().upper()

    pattern_matricule = r"^.{3}-\d{4}-.{3}$"
    
    if not re.match(pattern_matricule, im_propre):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="❌ Rejet : Le format du numéro matricule est invalide. Structure exigée : XXX-0000-XXX (4 chiffres au milieu)."
        )
