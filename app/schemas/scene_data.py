"""SceneData — miroir Pydantic du schéma réellement consommé par le front.

Ce module ne décrit **rien de nouveau**. Il traduit `js/scene/schema.js` de
pose-parquet.com, champ par champ, pour que le jour où Python produira une
scène, `normalizeScene()` l'accepte sans rien renier. Voir
`docs/scene-data.md` pour la comparaison ligne à ligne, et la liste explicite
de ce que Python ne saura pas remplir avant le LOT 6.

Deux règles héritées du front, et elles ne sont pas négociables :

* **toutes les coordonnées sont normalisées** (0 → 1 sur l'image analysée),
  jamais en pixels. Le front retaille librement la photo sans invalider la
  scène ;
* **les valeurs légèrement hors [0, 1] sont permises et utiles** : un plan de
  sol se prolonge très souvent au-delà du cadre. Aucun champ de coordonnée
  n'est donc borné ici — les borner casserait des scènes valides.

La version du schéma est portée par le champ `schema` lui-même
(`pose-parquet/scene@1`), comme côté front. Le front refuse une **majeure**
inconnue plutôt que de peindre n'importe quoi ; `major_of()` sert à faire le
même contrôle côté Python avant d'émettre.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

#: Version du contrat de scène, telle qu'écrite par le front.
SCENE_SCHEMA = "pose-parquet/scene@1"


def major_of(schema: str) -> str:
    """Partie du schéma qui doit correspondre — tout avant le `@`."""
    return schema.split("@")[0]


class _Model(BaseModel):
    """Base commune : entrée/sortie en camelCase, champs inconnus ignorés.

    `extra="ignore"` est un choix : les scènes calibrées à la main du front
    portent des champs de travail (`note`, `status`, `visualReason`) qui ne
    concernent pas le rendu. Les refuser empêcherait de valider les scènes
    réelles, qui sont notre seule vérité terrain géométrique.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
    )


class Point(_Model):
    """Point normalisé sur l'image. Volontairement non borné (voir en-tête)."""

    x: float
    y: float


class VanishingPoint(Point):
    """Point de fuite, avec le poids de la mesure qui l'a produit."""

    weight: float = 1.0
    role: str | None = None


class Meters(_Model):
    """Échelle réelle du plan de sol. Sans elle, une lame de 14 cm n'a pas de taille."""

    width: float
    depth: float


class Origin(_Model):
    """Décalage de la trame, en mètres dans le repère du sol.

    C'est ce qui aligne les lames de part et d'autre d'une porte : deux
    projections différentes, une seule trame.
    """

    u: float = 0.0
    v: float = 0.0


class Plane(_Model):
    """Repère de perspective d'une zone : une homographie et une échelle.

    `quad` est un **repère**, pas un contour : il peut déborder largement de
    la zone visible. Le contour, c'est `Mask.polygon`.
    """

    quad: list[Point] = Field(min_length=4, max_length=4)
    meters: Meters
    origin: Origin = Field(default_factory=Origin)
    rotation_deg: float = 0.0


class Mask(_Model):
    """Surface réellement peinte, et ses trous (pied de meuble, tapis, trémie)."""

    polygon: list[Point] = Field(min_length=3)
    holes: list[list[Point]] = Field(default_factory=list)


class Surface(_Model):
    """Un sol. Deux zones qui partagent un `surfaceId` reçoivent le même matériau."""

    id: str
    label: str = "Sol"
    continuous: bool = True


class FloorZone(_Model):
    """Une zone de sol : un plan de perspective **et** un masque.

    La distinction est ce qui permet de traiter une pièce vue à travers une
    ouverture : le plan donne la fuite et l'échelle, le masque dit ce qui est
    peint.
    """

    id: str
    label: str
    surface_id: str = "sol"
    #: Renvoi vers `SceneData.planes`. Un plan peut être **partagé** : deux
    #: pièces en enfilade sur la même dalle sont un seul plan de sol vu à
    #: travers une ouverture. Le déclarer une fois et le référencer garantit
    #: une continuité exacte, là où deux plans calibrés séparément laissent
    #: un décalage au raccord. C'est la forme employée par presque toutes les
    #: scènes réelles du front.
    plane_ref: str | None = None
    order: int = 0
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    #: `None` seulement si `plane_ref` est renseigné : le validateur de
    #: `SceneData` résout alors la référence et remplit ce champ.
    plane: Plane | None = None
    mask: Mask
    #: Contour édité par l'utilisateur. Toujours `None` à la sortie du
    #: service : c'est un champ du front, jamais une prédiction.
    runtime_mask: None = None


class Occluder(_Model):
    """Ce qui doit rester **devant** le parquet.

    Ce n'est pas un trou de masque : un occulteur vaut pour toutes les zones
    et survit à une correction du contour. Le rendu y restaure les pixels
    d'origine — un canapé n'est donc jamais repeint.
    """

    id: str
    label: str = "Objet"
    kind: str = "furniture"
    polygon: list[Point] = Field(min_length=3)
    #: Ligne de contact avec le sol, utile pour poser une ombre de contact.
    contact: list[Point] | None = None
    #: 0 = collé à la caméra, 1 = au fond. Sert au tri quand les objets se
    #: recouvrent.
    depth: float = 0.5
    casts_shadow: bool = True
    feather: float = 0.0015


class Camera(_Model):
    """Caméra sténopé. Aucun coefficient de distorsion — voir docs/lens-distortion.md."""

    #: Le seul champ dont le front a réellement besoin aujourd'hui : il borne
    #: le plan du sol et interdit toute texture au-dessus.
    horizon: float | None = None
    vanishing_points: list[VanishingPoint] = Field(default_factory=list)
    fov_deg: float | None = None
    tilt_deg: float | None = None
    height_m: float | None = None


class ImageRef(_Model):
    """L'image **telle qu'analysée**. Toutes les coordonnées s'y rapportent."""

    file: str | None = None
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    alt: str = ""
    credit: str | None = None


class DepthInfo(_Model):
    """Profondeur. `plane` = calculée depuis le plan du sol, exacte pour ses pixels."""

    kind: Literal["plane", "image"] = "plane"
    file: str | None = None
    near: float | None = None
    far: float | None = None


class Light(_Model):
    """Éclairement relu dans la photo. Les défauts sont ceux du front."""

    kind: Literal["photo-luma", "estimated"] = "photo-luma"
    strength: float = 1.0
    #: En fraction de la largeur d'image. Sépare l'éclairement du détail :
    #: c'est ce qui empêche les lames de l'ancien sol de réapparaître en
    #: fantôme sous le nouveau parquet.
    blur_radius: float = 0.035
    ambient: float = 0.22
    tint: float = 0.5
    contact: float = 0.35
    #: Dose des ombres de contact relues dans la photo (LOT PHOTO.2).
    contact_shadow: float = 0.6
    #: Dose de la lumière haute fréquence relue dans la photo — soleil,
    #: reflets de fenêtre (LOT PHOTO.3).
    highlight: float = 1.2
    #: Ancrage de l'exposition sur la clarté de l'ancien sol. `None` : le
    #: défaut du front (0,55), réglé sur les pièces calibrées.
    exposure: float | None = None


class SceneData(_Model):
    """Une scène complète, prête pour `normalizeScene()` côté front."""

    scene_schema: str = Field(default=SCENE_SCHEMA, alias="schema")
    id: str
    label: str = "Ma pièce"
    #: `ai` dès que la scène vient de ce service. Le front ne prononce les
    #: mots « analyse » et « détection » que dans ce cas.
    source: Literal["manual", "precalibrated", "ai"] = "ai"
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    image: ImageRef
    camera: Camera = Field(default_factory=Camera)
    surfaces: list[Surface] = Field(default_factory=list)
    #: Plans nommés, référençables par `FloorZone.planeRef`.
    planes: dict[str, Plane] = Field(default_factory=dict)
    #: Au moins une zone : le front lève sur une scène qui n'en a aucune.
    floor_zones: list[FloorZone] = Field(min_length=1)
    occluders: list[Occluder] = Field(default_factory=list)
    depth: DepthInfo = Field(default_factory=DepthInfo)
    light: Light = Field(default_factory=Light)
    #: Codes machine. Le front décide de la formulation affichée.
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _resolve_plane_refs(self) -> "SceneData":
        """Résout `planeRef` vers `planes`, et lève sur une référence morte.

        Le front lève déjà dans ce cas, et il a raison : mieux vaut un
        message qu'un rendu faux. Le faire ici aussi évite d'envoyer une
        scène dont on sait qu'elle sera refusée à l'arrivée.

        Après validation, chaque zone porte son `plane` résolu : le reste du
        code Python n'a jamais à se demander laquelle des deux formes il lit.
        """
        for zone in self.floor_zones:
            if zone.plane is not None:
                continue
            if zone.plane_ref is None:
                raise ValueError(f"Zone « {zone.id} » : ni plane ni planeRef")
            resolved = self.planes.get(zone.plane_ref)
            if resolved is None:
                raise ValueError(f"Zone « {zone.id} » : plan « {zone.plane_ref} » introuvable")
            zone.plane = resolved
        return self
