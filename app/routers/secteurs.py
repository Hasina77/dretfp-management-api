from fastapi import APIRouter, Depends, status, HTTPException
from sqlmodel import Session, select
from typing import List, Optional
from app.database.config import get_db_session
from app.database.models import Secteur, EtablissementSecteur
from pydantic import BaseModel

router = APIRouter()


class SecteurCreate(BaseModel):
    nom_secteur: Optional[str] = "Nouveau Secteur"
    etablissement_id: Optional[int] = None
    etablissements_ids: Optional[List[int]] = []
    description_sec: Optional[str] = ""


class SecteurOut(BaseModel):
    id_secteur: int
    nom_secteur: str
    etablissement_id: Optional[int] = None
    etablissements_ids: List[int] = []
    description_sec: Optional[str] = None


def synchroniser_liaisons_secteur(id_secteur: int, ids_etabs: List[int], db: Session):
    anciennes = db.exec(
        select(EtablissementSecteur).where(EtablissementSecteur.id_secteur == id_secteur)
    ).all()
    for lien in anciennes:
        db.delete(lien)

    for id_etab in set(ids_etabs):
        if id_etab:
            db.add(EtablissementSecteur(id_etablissement=int(id_etab), id_secteur=id_secteur))


@router.get("/liste", response_model=List[SecteurOut])
def lister_tous_les_secteurs(db: Session = Depends(get_db_session)):
    liste_secteurs = db.exec(select(Secteur)).all()
    tous_liens = db.exec(select(EtablissementSecteur)).all()

    map_etabs_par_secteur = {}
    for lien in tous_liens:
        map_etabs_par_secteur.setdefault(lien.id_secteur, []).append(lien.id_etablissement)

    resultat = []
    for sec in liste_secteurs:
        ids_lies = list(map_etabs_par_secteur.get(sec.id_secteur, []))
        if sec.etablissement_id and sec.etablissement_id not in ids_lies:
            ids_lies.insert(0, sec.etablissement_id)

        resultat.append(
            SecteurOut(
                id_secteur=sec.id_secteur,
                nom_secteur=sec.nom_secteur,
                etablissement_id=ids_lies[0] if len(ids_lies) > 0 else sec.etablissement_id,
                etablissements_ids=ids_lies,
                description_sec=sec.description_sec
            )
        )

    return resultat



@router.post("/creer", status_code=status.HTTP_201_CREATED)
def creer_nouveau_secteur(secteur_in: SecteurCreate, db: Session = Depends(get_db_session)):
    nom_propre = (secteur_in.nom_secteur or "").strip()
    if not nom_propre:
        raise HTTPException(status_code=400, detail="Le nom du secteur est obligatoire.")

    existant = db.exec(select(Secteur)).all()
    secteur_doublon = next(
        (s for s in existant if s.nom_secteur.strip().lower() == nom_propre.lower()),
        None
    )

    ids_cibles = list(secteur_in.etablissements_ids or [])
    if secteur_in.etablissement_id and secteur_in.etablissement_id not in ids_cibles:
        ids_cibles.append(secteur_in.etablissement_id)

    if secteur_doublon:
        liens_actuels = db.exec(
            select(EtablissementSecteur).where(EtablissementSecteur.id_secteur == secteur_doublon.id_secteur)
        ).all()
        ids_fusionnes = list({l.id_etablissement for l in liens_actuels} | set(ids_cibles))
        if secteur_doublon.etablissement_id:
            ids_fusionnes.append(secteur_doublon.etablissement_id)

        synchroniser_liaisons_secteur(secteur_doublon.id_secteur, ids_fusionnes, db)
        db.commit()
        return {
            "status": "success",
            "message": f"Le secteur '{secteur_doublon.nom_secteur}' existait déjà : les établissements sélectionnés y ont été rattachés sans doublon !",
            "data": secteur_doublon
        }

    nouveau_secteur = Secteur(
    nom_secteur=nom_propre.upper(),
    etablissement_id=int(ids_cibles[0]) if len(ids_cibles) > 0 else None,
    description_sec=secteur_in.description_sec
    )
    db.add(nouveau_secteur)
    db.commit()
    db.refresh(nouveau_secteur)

    synchroniser_liaisons_secteur(nouveau_secteur.id_secteur, ids_cibles, db)
    db.commit()

    return {
        "status": "success",
        "message": "Nouveau secteur enregistré avec succès !",
        "data": nouveau_secteur
    }


@router.put("/modifier/{id_secteur}", status_code=status.HTTP_200_OK)
def modifier_secteur_technologique(id_secteur: int, secteur_in: SecteurCreate, db: Session = Depends(get_db_session)):
    secteur_cible = db.get(Secteur, id_secteur)
    if not secteur_cible:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="⚠️ Erreur : Ce secteur technologique est introuvable."
        )

    ids_cibles = list(secteur_in.etablissements_ids or [])
    if secteur_in.etablissement_id and secteur_in.etablissement_id not in ids_cibles:
        ids_cibles.append(secteur_in.etablissement_id)

    secteur_cible.nom_secteur = (secteur_in.nom_secteur or secteur_cible.nom_secteur).strip().upper()
    secteur_cible.etablissement_id = ids_cibles[0] if len(ids_cibles) > 0 else None
    secteur_cible.description_sec = secteur_in.description_sec

    db.add(secteur_cible)
    synchroniser_liaisons_secteur(id_secteur, ids_cibles, db)
    db.commit()
    db.refresh(secteur_cible)

    return {
        "status": "success",
        "message": "Le secteur et ses établissements de rattachement ont été mis à jour !",
        "data": secteur_cible
    }


@router.delete("/supprimer/{id_secteur}", status_code=status.HTTP_200_OK)
def supprimer_secteur_technologique(id_secteur: int, db: Session = Depends(get_db_session)):
    secteur_cible = db.get(Secteur, id_secteur)
    if not secteur_cible:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="⚠️ Ce secteur technologique est introuvable."
        )

    liens = db.exec(
        select(EtablissementSecteur).where(EtablissementSecteur.id_secteur == id_secteur)
    ).all()
    for l in liens:
        db.delete(l)

    db.delete(secteur_cible)
    db.commit()

    return {
        "status": "success",
        "message": "Le secteur et ses rattachements ont été supprimés avec succès."
    }
