"""Annotation humaine du sol : le format de la vérité terrain du LOT 2.

Ce n'est pas une vérité terrain estimée. C'est un relevé fait par une personne
qui regarde la photo, et tout ce fichier existe pour que ce relevé soit
**dénombrable, relisable et contestable** — pas pour qu'il ait l'air précis.

## Les trois notions qu'il ne faut jamais confondre

**1. Le sol visible** (`floor_visible`). Les pixels où l'on voit réellement le
sol. Un tapis n'est pas du sol visible : il le cache. Un pied de chaise non
plus. C'est le seul masque contre lequel une segmentation sera mesurée, parce
que c'est le seul dont un humain peut décider en regardant l'image.

**2. L'étendue géométrique du sol.** La surface que le sol occupe *vraiment*,
y compris derrière le canapé et sous le tapis. Elle ne se voit pas, elle se
déduit de la perspective — et c'est ce dont le Visualiseur a besoin pour poser
des lames continues. Elle **n'est pas annotée ici** : le champ existe
(`floor_extent`) pour que la place soit réservée et que personne ne soit tenté
de la ranger dans `floor_visible`, mais il reste vide jusqu'au lot qui saura
en décider.

Confondre les deux serait l'erreur la plus coûteuse du projet : on
entraînerait, puis on mesurerait, un segmenteur contre une cible que l'image
ne contient pas.

**3. L'incertain** (`uncertain`). Les pixels dont une personne honnête dit
qu'elle ne sait pas. Un coin caché, une ombre dure, un meuble collé au mur, un
sol coupé par le bord du cadre. Ces pixels sont **exclus des métriques
officielles** : les forcer à 0 ou à 1 ferait payer à un modèle une frontière
que personne ne sait tracer.

## Conventions, écrites une fois

* les masques sont des **PNG 8 bits en niveaux de gris**, sans perte. Jamais de
  JPEG : un artefact de compression sur une frontière de masque est une
  frontière fausse ;
* **0 = non, 255 = oui.** Toute valeur intermédiaire est un défaut et le
  validateur la refuse — un masque à 127 veut dire que quelqu'un a
  redimensionné avec interpolation ;
* les dimensions du masque sont **exactement** celles de l'image telle que le
  pipeline la charge, c'est-à-dire **après redressement EXIF**
  (`image_loader.load_image`). C'est le seul cadre dont les coordonnées
  veuillent dire quelque chose, et le validateur le vérifie ;
* la géométrie complémentaire (contours) est stockée en coordonnées
  **normalisées** 0 → 1, comme dans `SceneData`. Elle survit donc à un
  changement de résolution, là où un masque raster ne survit pas ;
* **aucun redimensionnement de masque n'est fait automatiquement.** Si les
  dimensions ne correspondent plus, c'est une erreur à corriger, pas une
  interpolation à appliquer.

## Plusieurs relevés de la même photo

Une photo peut être annotée deux fois, pour mesurer ce que le protocole a de
reproductible. `pass_label` distingue les passes, `independent_pass` dit si
elles ont été faites sans se regarder.

Le nom de la mesure qui en sort dépend de qui a tenu la souris, et la
distinction n'est pas cosmétique :

* deux **personnes différentes** → accord inter-annotateurs. Il mesure ce que
  le protocole transmet ;
* la **même personne**, deux fois → répétabilité intra-annotateur. Elle mesure
  la stabilité d'une main, ce qui est une borne optimiste : personne ne
  reproduit ses propres hésitations aussi mal que celles d'un autre.

Appeler la seconde « accord inter-annotateurs » gonflerait le chiffre qui
servira de plafond aux exigences posées aux modèles.
`benchmarks/agreement.py` déduit le nom des `annotator` et refuse de le
choisir à notre place.
"""

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

#: Version du format d'annotation. Indépendante de celle du manifeste : on
#: peut ajouter des images sans changer la façon de les annoter, et l'inverse.
ANNOTATION_SCHEMA = "pose-parquet-ai/floor-annotation@1"

#: Valeurs autorisées dans un masque. Rien entre les deux.
MASK_FALSE = 0
MASK_TRUE = 255


class AnnotationStatus(StrEnum):
    """Où en est ce relevé.

    La règle qui donne son sens à ce champ : **seules les annotations
    `approved` entrent dans le banc d'essai officiel.** Sans elle, un brouillon
    oublié deviendrait de la vérité terrain, et personne ne s'en apercevrait —
    un chiffre d'IoU ne dit pas contre quoi il a été calculé.

    `reviewed` et `approved` sont distincts exprès : relire, c'est constater
    l'état ; approuver, c'est engager la mesure. La même personne peut faire
    les deux, mais pas sans le dire.
    """

    DRAFT = "draft"
    REVIEWED = "reviewed"
    APPROVED = "approved"


class BoundaryKind(StrEnum):
    """Nature d'un segment de contour relevé.

    Distinguer les natures sert une chose précise : pouvoir mesurer plus tard
    la qualité **là où elle compte**. Une erreur de dix pixels sur la jonction
    mur/sol décale tout le plan de perspective ; la même erreur sur un bord de
    cadre ne coûte rien, puisque le sol y est simplement coupé.
    """

    #: La jonction mur/sol, le relevé le plus précieux du lot.
    WALL_FLOOR = "wall_floor"
    #: Le bas de plinthe, quand il se distingue du mur.
    BASEBOARD = "baseboard"
    #: Un seuil de porte : changement de sol, pas fin de sol.
    DOOR_THRESHOLD = "door_threshold"
    #: Le sol est coupé par le bord de l'image. Ce n'est pas une frontière de
    #: la scène, et une métrique de contour n'a pas à la récompenser.
    FRAME_CUT = "frame_cut"
    #: Contact d'un objet posé au sol — pied de meuble, bord de tapis.
    OBJECT_CONTACT = "object_contact"
    OTHER = "other"


class UncertainReason(StrEnum):
    """Pourquoi une personne n'a pas su trancher.

    Enregistré par zone, et pas seulement globalement : on veut pouvoir dire
    *où* l'humain a renoncé, pour savoir si un modèle échoue sur les cas
    difficiles ou sur les cas faciles.
    """

    HIDDEN_CORNER = "hidden_corner"
    STRONG_SHADOW = "strong_shadow"
    FURNITURE_AGAINST_WALL = "furniture_against_wall"
    LOW_CONTRAST = "low_contrast"
    CUT_BY_FRAME = "cut_by_frame"
    REFLECTION = "reflection"
    MOTION_BLUR = "motion_blur"
    OTHER = "other"


class _Model(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class Point(_Model):
    """Point normalisé sur l'image. Même convention que `SceneData`."""

    x: float
    y: float


class BoundarySegment(_Model):
    """Une portion de contour relevée à la main, en coordonnées normalisées.

    C'est une **polyligne**, pas un polygone fermé : un contour mur/sol est un
    trait, pas une surface. Deux points suffisent.
    """

    kind: BoundaryKind
    points: list[Point] = Field(min_length=2)
    note: str | None = None


class UncertainZone(_Model):
    """Une zone que l'annotateur déclare indécidable, et pourquoi.

    Le polygone est redondant avec le masque `uncertain`, et c'est voulu : le
    masque sert aux métriques, la liste sert à **lire** le corpus. On veut
    pouvoir compter les scènes dont un coin est caché sans ouvrir une image.
    """

    reason: UncertainReason
    polygon: list[Point] = Field(min_length=3)
    note: str | None = None


class MaskFiles(_Model):
    """Chemins des masques, relatifs au dossier du fichier d'annotation."""

    #: **Obligatoire.** Le sol réellement visible. Voir l'en-tête du module.
    floor_visible: str
    #: Zones indécidables, exclues des métriques. Absent = aucune.
    uncertain: str | None = None
    #: **Réservé, jamais rempli à ce stade.** L'étendue géométrique du sol,
    #: meubles compris. Le champ existe pour que personne ne soit tenté de
    #: ranger cette notion dans `floor_visible` — les deux ne se mesurent pas
    #: l'une contre l'autre.
    floor_extent: None = None


class AnnotationTiming(_Model):
    """Combien de temps ce relevé a coûté. Une métrique du LOT 2A.

    Le temps d'annotation décide si un corpus de trente scènes est réaliste ou
    non, et c'est une donnée qu'aucune mesure d'image ne remplace. Il est donc
    mesuré comme le reste.

    Les trois durées sont séparées parce qu'elles ne se réduisent pas l'une à
    l'autre : une première passe rapide suivie de longues corrections dit
    autre chose qu'une passe lente et propre — la première signale un protocole
    ambigu, la seconde une image difficile.

    Chronométrage volontairement grossier. Un dispositif de télémétrie fin
    coûterait plus à écrire qu'il ne rapporterait sur une douzaine d'images, et
    la seconde près n'apprendrait rien.
    """

    #: Premier tracé, du chargement de l'image au premier enregistrement.
    first_pass_seconds: float = Field(ge=0.0)
    #: Reprises ultérieures par l'annotateur lui-même, cumulées.
    corrections_seconds: float = Field(default=0.0, ge=0.0)
    #: Relecture par une autre personne, ou par la même à distance.
    review_seconds: float = Field(default=0.0, ge=0.0)
    #: Nombre de reprises, s'il se compte sans effort. `None` sinon — un
    #: chiffre approximatif inventé après coup ne vaut rien.
    correction_count: int | None = Field(default=None, ge=0)

    @property
    def total_seconds(self) -> float:
        return self.first_pass_seconds + self.corrections_seconds + self.review_seconds


class Review(_Model):
    """Qui a relu, quand, et ce qu'il en a pensé.

    Séparé de l'annotation elle-même : c'est un acte distinct, par une
    personne éventuellement distincte, et le confondre avec la signature de
    l'annotateur rendrait `approved` invérifiable.
    """

    reviewer: str
    reviewed_on: date
    #: Vrai si le relecteur a modifié le masque, pas seulement donné un avis.
    corrected: bool = False
    note: str | None = None


class FloorAnnotation(_Model):
    """Le relevé humain du sol d'une scène.

    La provenance de l'image, sa difficulté et ses traits ne sont **pas**
    dupliqués ici : ils vivent dans l'entrée de manifeste que `photo_id`
    désigne, qui est leur seule source de vérité. `benchmarks/annotations.py`
    joint les deux et refuse une annotation dont la photo n'est pas décrite —
    c'est ce refus, et non un champ recopié, qui garantit qu'aucune annotation
    n'entre au banc d'essai sans provenance.
    """

    annotation_schema: str = Field(default=ANNOTATION_SCHEMA, alias="schema")
    #: Identifiant de la photo dans `datasets/manifest.json`.
    photo_id: str
    #: Dimensions de l'image **après redressement EXIF**, en pixels. Les
    #: masques doivent les respecter exactement.
    width: int = Field(ge=1)
    height: int = Field(ge=1)

    masks: MaskFiles
    boundary: list[BoundarySegment] = Field(default_factory=list)
    uncertain_zones: list[UncertainZone] = Field(default_factory=list)

    #: Qui a dessiné. Un nom, un pseudo, un identifiant — mais quelque chose :
    #: une vérité terrain anonyme n'est pas contestable.
    annotator: str
    annotated_on: date
    #: Numéro de révision du relevé lui-même. Incrémenté quand le masque
    #: change, pour qu'un résultat de banc d'essai reste rattachable.
    revision: int = Field(default=1, ge=1)

    status: AnnotationStatus = AnnotationStatus.DRAFT
    review: Review | None = None

    #: Étiquette de passe, quand une même photo est annotée plusieurs fois :
    #: « A », « B »… Absente pour une annotation unique.
    pass_label: str | None = None

    #: L'annotateur déclare avoir fait cette passe **sans regarder** les
    #: autres.
    #:
    #: C'est une déclaration, et rien dans l'outil ne peut la vérifier — le
    #: champ le dit plutôt que de laisser croire à une garantie. Sa valeur est
    #: pourtant décisive : sans elle, on ne saurait pas si un accord élevé
    #: mesure la reproductibilité du protocole ou la mémoire de l'annotateur.
    #:
    #: Faux par défaut, comme toute affirmation non vérifiée dans ce projet.
    independent_pass: bool = False

    #: Coût du relevé. Voir `AnnotationTiming`.
    timing: AnnotationTiming | None = None

    #: SHA-256 des fichiers de masque, pour qu'un rapport puisse affirmer
    #: contre quels octets il a été calculé.
    mask_sha256: dict[str, str] = Field(default_factory=dict)

    notes: str | None = None

    @model_validator(mode="after")
    def _review_matches_status(self) -> "FloorAnnotation":
        """Un statut relu ou approuvé exige une relecture nommée.

        C'est le garde-fou qui donne du poids à `approved`. Sans lui, le champ
        de statut ne serait qu'une déclaration d'intention : on pourrait
        approuver sans que personne n'ait jamais regardé, et le banc d'essai
        mesurerait contre un brouillon en croyant mesurer contre une référence.
        """
        if self.status is not AnnotationStatus.DRAFT and self.review is None:
            raise ValueError(
                f"statut « {self.status.value} » sans bloc review : "
                "une annotation relue ou approuvée doit dire par qui et quand"
            )
        if self.status is AnnotationStatus.DRAFT and self.review is not None:
            raise ValueError(
                "une annotation avec relecture ne peut pas rester « draft » : "
                "passez-la en reviewed ou approved"
            )
        return self

    @property
    def usable_as_ground_truth(self) -> bool:
        """Vrai seulement pour `approved`. Le banc d'essai officiel s'y limite."""
        return self.status is AnnotationStatus.APPROVED
