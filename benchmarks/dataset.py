"""Lecture du manifeste d'un corpus.

Le manifeste est **la** description du corpus : les photos elles-mêmes ne sont
pas versionnées (voir `datasets/README.md`), lui l'est. Il porte pour chaque
photo sa difficulté, sa provenance, sa licence, les défauts qu'on sait y
trouver, et l'emplacement d'une éventuelle vérité terrain.

Un point de vigilance, écrit ici parce que c'est ici qu'on serait tenté :
`GroundTruth` n'a **que** des champs facultatifs, et aucun n'a de valeur par
défaut plausible. Une vérité terrain inventée est pire qu'absente — elle
transforme un banc d'essai en machine à valider ses propres erreurs.
"""

import json
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.core.warnings import Warn

#: Version du format de manifeste.
DATASET_SCHEMA = "pose-parquet-ai/dataset@1"


class Difficulty(StrEnum):
    """Les quatre bacs du corpus.

    Le classement décrit **ce que la photo demande à l'analyse**, pas sa
    qualité esthétique :

    * `easy` — sol dégagé, jonction mur/sol franche, perspective lisible ;
    * `medium` — quelques meubles, une ouverture, un contraste moyen ;
    * `hard` — les cas que le front a réellement rencontrés : faible contraste
      mur/sol, coins occultés, grand-angle, recadrage, meubles devant les
      plinthes ;
    * `rejected` — photo dont on attend qu'elle soit **refusée**. Ce n'est pas
      un rebut : c'est la seule catégorie qui vérifie que le service sait dire
      non, et elle a autant de valeur que les trois autres.
    """

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    REJECTED = "rejected"


class _Model(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class GroundTruth(_Model):
    """Relevé humain, quand il existe. Tout est facultatif, rien n'est deviné."""

    available: bool = False
    #: PNG binaire, même cadrage que la photo : le sol tel qu'un humain le voit.
    floor_mask: str | None = None
    #: Polygone normalisé de la jonction mur/sol, relevé à la main.
    floor_boundary: list[dict[str, float]] | None = None
    #: PNG binaire de ce qui doit rester devant le parquet.
    occlusion_mask: str | None = None
    #: Points de fuite relevés, normalisés.
    vanishing_points: list[dict[str, float]] | None = None
    #: Paramètres caméra connus : `fovDeg`, `tiltDeg`, `heightM`, `focalPx`.
    camera: dict[str, float] | None = None
    #: Objectif : coefficients radiaux, centre optique, et **la provenance** de
    #: ces valeurs — mesurée, lue dans les métadonnées, ou supposée. La
    #: distinction court dans tout le projet.
    lens: dict[str, float | str] | None = None
    notes: str | None = None


class Photo(_Model):
    """Une entrée du corpus."""

    id: str
    #: Chemin relatif au dossier du manifeste.
    file: str
    difficulty: Difficulty
    #: D'où vient la photo. Obligatoire : une photo sans provenance ne peut
    #: pas être partagée, donc pas servir de référence commune.
    source: str
    license: str
    credit: str | None = None
    #: Défauts qu'on **sait** présents. Sert à mesurer si le service les
    #: repère, et à repérer ceux qu'il invente.
    expected_issues: list[Warn] = Field(default_factory=list)
    #: Faux : la bonne réponse est discutable, la photo est mesurée mais pas
    #: comptée dans la matrice de confusion. Même sens que dans
    #: `corpus/catalogue.py` — une zone grise se documente, elle ne se grade
    #: pas.
    graded: bool = True
    ground_truth: GroundTruth = Field(default_factory=GroundTruth)
    notes: str | None = None


class Manifest(_Model):
    """Le corpus entier."""

    dataset_schema: str = Field(default=DATASET_SCHEMA, alias="schema")
    note: str = ""
    photos: list[Photo] = Field(default_factory=list)


def load_manifest(directory: Path) -> Manifest:
    """Charge `<directory>/manifest.json`.

    :raises FileNotFoundError: si le manifeste n'existe pas. Un corpus sans
        manifeste n'est pas un corpus, c'est un dossier d'images.
    """
    path = directory / "manifest.json"
    if not path.is_file():
        raise FileNotFoundError(f"Manifeste absent : {path}")
    return Manifest.model_validate(json.loads(path.read_text(encoding="utf-8")))
