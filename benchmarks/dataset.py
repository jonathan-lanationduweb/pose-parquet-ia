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

import hashlib
import json
from datetime import date
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.core.warnings import Warn

#: Version du format de manifeste.
#:
#: Passée à @2 pour le préambule du LOT 2 : `source` / `license` / `credit`
#: plats deviennent un bloc `provenance` qui porte en plus le hash, la date de
#: vérification, la redistribuabilité et l'usage autorisé. Un champ `traits`
#: apparaît. Le manifeste réel étant vide, aucune donnée n'a été migrée.
DATASET_SCHEMA = "pose-parquet-ai/dataset@2"


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


class SceneTrait(StrEnum):
    """Ce que la scène **contient**, par opposition à ce qu'elle vaut.

    La difficulté est un jugement d'ensemble ; les traits sont des faits
    observables. Les séparer permet de répondre à la question qui décidera du
    modèle : « échoue-t-il sur les tapis, ou sur les sols sombres ? » — un
    corpus rangé seulement par difficulté ne peut pas y répondre.

    Le vocabulaire est **fermé** : un trait libre en texte ne se compte pas, et
    une liste qu'on ne peut pas compter ne sert qu'à se rassurer.
    """

    # Contenu de la pièce
    EMPTY_ROOM = "empty_room"
    FURNISHED = "furnished"
    RUG = "rug"
    THIN_FURNITURE_LEGS = "thin_furniture_legs"
    RADIATOR = "radiator"
    DOORS = "doors"

    # Nature du sol
    EXISTING_PARQUET = "existing_parquet"
    TILES = "tiles"
    UNIFORM_FLOOR = "uniform_floor"
    DARK_FLOOR = "dark_floor"
    REFLECTIVE_FLOOR = "reflective_floor"

    # Ce qui rend le relevé difficile
    LOW_WALL_FLOOR_CONTRAST = "low_wall_floor_contrast"
    HIDDEN_CORNERS = "hidden_corners"
    CROPPED = "cropped"
    WIDE_ANGLE = "wide_angle"
    EASY_PERSPECTIVE = "easy_perspective"
    HARD_PERSPECTIVE = "hard_perspective"
    BLURRY = "blurry"

    # Géométrie de la pièce
    CORRIDOR = "corridor"
    SMALL_ROOM = "small_room"
    LARGE_ROOM = "large_room"

    #: Ce n'est pas une pièce, ou la photo est inexploitable. À accorder avec
    #: `difficulty = rejected`.
    NOT_A_ROOM = "not_a_room"


class Usage(StrEnum):
    """Ce que l'on s'autorise à faire de l'image.

    `LOCAL_EVALUATION_ONLY` est le régime par défaut d'une photo dont la
    licence n'autorise pas la redistribution : elle sert à mesurer chez nous et
    ne quitte jamais la machine. Le manifeste la référence par chemin et par
    hash ; ses octets restent hors de Git.
    """

    LOCAL_EVALUATION_ONLY = "local_evaluation_only"
    REDISTRIBUTABLE = "redistributable"


class _Model(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class Provenance(_Model):
    """D'où vient l'image, et à quelles conditions on peut s'en servir.

    Aucun champ n'a de défaut permissif. `license` est obligatoire et n'accepte
    pas de valeur vide : **une licence absente ne doit jamais devenir une
    licence supposée.** S'il faut écrire « inconnue », il faut l'écrire, et
    `redistributable` reste alors faux.

    `verified_on` est la date à laquelle une personne a *regardé* les
    conditions, pas celle du téléchargement. Sans elle, une licence recopiée il
    y a deux ans se lit comme une licence vérifiée aujourd'hui.
    """

    source: str = Field(min_length=1)
    source_url: str | None = None
    author: str | None = None
    #: Nom exact de la licence. « inconnue » est une réponse acceptable ;
    #: l'inventer ne l'est pas.
    license: str = Field(min_length=1)
    verified_on: date
    #: Faux par défaut. On ne redistribue que ce qu'on a vérifié pouvoir
    #: redistribuer, et l'inverse d'un défaut permissif est un défaut sûr.
    redistributable: bool = False
    usage: Usage = Usage.LOCAL_EVALUATION_ONLY
    #: SHA-256 du fichier local. C'est ce qui permet à un rapport d'affirmer
    #: sur quels octets il a été calculé, même pour une image hors de Git.
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    note: str | None = None


class GroundTruth(_Model):
    """Relevés humains **autres que le sol**. Tout est facultatif, rien n'est deviné.

    Le sol a quitté ce bloc au préambule du LOT 2 : il a désormais son propre
    format, dans `app/schemas/annotation.py`, et ses fichiers dans
    `datasets/annotations/`. Les champs `floorMask`, `floorBoundary` et
    `occlusionMask` du LOT 0 sont donc retirés plutôt que laissés vides.

    La raison n'est pas le rangement. Un `floorMask` ici et un `floor_visible`
    là auraient été deux vérités terrain pour la même chose, sans que rien ne
    dise laquelle fait foi — et la première n'aurait su distinguer ni le sol
    visible de l'étendue géométrique, ni le décidable de l'indécidable. Deux
    formats concurrents pour une même mesure sont pires qu'un format
    incomplet.

    Ce qui reste ici concerne la caméra et l'objectif, et servira aux LOT 3
    et 4.
    """

    available: bool = False
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
    #: Chemin relatif au dossier du manifeste. `public/…` pour une image
    #: redistribuable et versionnée, `private-real/…` pour une image qui reste
    #: hors de Git.
    file: str
    difficulty: Difficulty
    #: D'où vient la photo, et ce qu'on s'autorise à en faire. Obligatoire :
    #: une photo sans provenance vérifiée ne peut servir de référence commune.
    provenance: Provenance
    #: Ce que la scène contient. Vocabulaire fermé, voir `SceneTrait`.
    traits: list[SceneTrait] = Field(default_factory=list)
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


def sha256_of(path: Path) -> str:
    """SHA-256 d'un fichier, en flux.

    Lu par morceaux et non d'un bloc : une photo de 20 Mo n'a pas besoin d'être
    tenue entière en mémoire pour être empreintée, et le corpus grandira.
    """
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(directory: Path) -> Manifest:
    """Charge `<directory>/manifest.json`.

    :raises FileNotFoundError: si le manifeste n'existe pas. Un corpus sans
        manifeste n'est pas un corpus, c'est un dossier d'images.
    """
    path = directory / "manifest.json"
    if not path.is_file():
        raise FileNotFoundError(f"Manifeste absent : {path}")
    return Manifest.model_validate(json.loads(path.read_text(encoding="utf-8")))
