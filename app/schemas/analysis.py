"""AnalysisResult — le contrat de sortie du service, stable dès le LOT 0.

Ce contrat est **le nôtre**, distinct de `SceneData` qui est celui du front.
La séparation est délibérée : une analyse peut avoir beaucoup à dire sans
produire de scène du tout, et c'est précisément le cas au LOT 0.

La règle de conception du projet tient dans le champ `status` : le service
doit savoir dire « je ne suis pas assez sûr » plutôt que livrer une mauvaise
géométrie. Un `needs_manual_adjustment` accompagné de mesures est un bon
résultat ; un `success` obtenu en devinant l'horizon n'en est pas un.
"""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.core.warnings import Warn
from app.schemas.scene_data import SceneData

#: Version du contrat d'analyse. Indépendante de celle de SceneData.
ANALYSIS_SCHEMA = "pose-parquet/analysis@1"


class AnalysisStatus(StrEnum):
    """Verdict d'ensemble.

    Les quatre premières valeurs sont le vocabulaire cible, stable. La
    cinquième est celle du LOT 0 et disparaîtra quand les étages de géométrie
    existeront : elle dit « les contrôles techniques ont tourné, l'analyse de
    la pièce n'existe pas encore ». Elle n'est pas un échec, et surtout pas un
    succès partiel — la confondre avec `partial` ferait croire qu'un sol a été
    cherché.
    """

    SUCCESS = "success"
    PARTIAL = "partial"
    NEEDS_MANUAL_ADJUSTMENT = "needs_manual_adjustment"
    REJECTED = "rejected"
    ANALYSIS_INCOMPLETE = "analysis_incomplete"


class _Model(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class ImageInfo(_Model):
    """Dimensions de l'image **après** redressement EXIF.

    C'est le seul cadre auquel les coordonnées d'une future scène pourront se
    rapporter. Renvoyer les dimensions d'avant rotation serait une erreur
    silencieuse d'un facteur ratio.
    """

    width: int = Field(ge=1)
    height: int = Field(ge=1)
    #: largeur / hauteur, arrondi. > 1 : paysage, < 1 : portrait.
    aspect_ratio: float
    megapixels: float
    #: Format tel que décodé, pas tel qu'annoncé par le client.
    format: Literal["JPEG", "PNG", "WEBP"]
    #: Vrai si une balise d'orientation EXIF a été appliquée.
    exif_orientation_applied: bool


class BlurMetrics(_Model):
    """Mesure de flou : variance du Laplacien.

    Volontairement **une mesure brute et son contexte**, pas un verdict
    « bonne / mauvaise photo ». La variance du Laplacien dépend de la
    résolution, du contenu (un mur nu est net et plat) et du bruit. Aucun
    seuil universel n'existe ; `sharp` n'est qu'une classification
    configurable, et `laplacian_variance` reste la valeur qui compte.
    """

    laplacian_variance: float
    #: Côté long auquel la mesure a été faite. Sans lui le chiffre ne se
    #: compare pas d'une photo à l'autre.
    working_side: int
    #: Classification selon `PPAI_BLUR_SHARP_MIN`, révisable.
    sharp: bool


class ExposureMetrics(_Model):
    """Luminance et contraste globaux, en luma Rec. 709 ramené à 0 → 1."""

    luma_mean: float
    luma_median: float
    #: Écart-type de la luma : le contraste global.
    contrast_std: float
    #: Étendue entre les percentiles 5 et 95 — moins sensible aux extrêmes.
    contrast_p5_p95: float
    #: Proportion de pixels sous `PPAI_DARK_LUMA_MAX`.
    dark_pixel_ratio: float
    #: Proportion de pixels au-dessus de `PPAI_BRIGHT_LUMA_MIN`.
    bright_pixel_ratio: float


class QualityMetrics(_Model):
    """Contrôle qualité photo, sans aucun modèle."""

    blur: BlurMetrics
    exposure: ExposureMetrics


class EdgeTrack(_Model):
    """Une arête suivie dans l'image, et ce qu'elle vaut comme preuve.

    `sagitta_px` seul ne veut rien dire : c'est `fit_rms_px` qui dit si la
    parabole **décrit** le tracé. Le front a perdu une scène à cette
    confusion (voir docs/lens-distortion.md) — les deux voyagent ensemble.
    """

    #: Flèche d'arc : écart de la parabole à sa corde, au milieu, en pixels.
    sagitta_px: float
    #: Écart-type d'ajustement de la parabole, en pixels.
    fit_rms_px: float
    points: int
    #: Part de la hauteur d'image couverte par le tracé. Un tracé court ne
    #: prouve rien : la flèche y est dominée par le bruit.
    span_ratio: float
    #: Distance normalisée du centre optique (0 = sur l'axe, 1 = au bord).
    #: La distorsion radiale ne déplace rien sur l'axe : une arête centrale
    #: ne prouve jamais rien.
    center_offset: float
    #: Retenu comme preuve : assez de points, ajustement assez serré.
    usable: bool


class LensVerdict(StrEnum):
    """Ce que la mesure autorise à dire, et rien de plus."""

    NO_DISTORTION_DETECTED = "no_distortion_detected"
    DISTORTION_SUSPECTED = "distortion_suspected"
    #: Pas assez d'arêtes exploitables. Le cas le plus fréquent sur une photo
    #: d'intérieur ordinaire, et le seul honnête quand c'est vrai.
    UNDETERMINED = "undetermined"


class LensMetrics(_Model):
    """Analyse d'objectif. **Aucune correction n'est appliquée.**

    Le service mesure et rapporte. Corriger une distorsion demande un
    étalonnage que nous n'avons pas, et une correction fausse est pire qu'une
    absence de correction : elle entre dans tous les relevés suivants sans
    plus rien qui la distingue du reste.
    """

    verdict: LensVerdict
    #: Flèche maximale parmi les arêtes retenues, en pixels de l'image.
    max_sagitta_px: float | None = None
    #: Le même chiffre ramené à `PPAI_LENS_REFERENCE_WIDTH`, comparable
    #: entre photos de résolutions différentes.
    max_sagitta_px_normalized: float | None = None
    usable_edges: int
    tracks: list[EdgeTrack] = Field(default_factory=list)
    #: Seuil effectivement appliqué, en pixels de l'image analysée.
    suspect_threshold_px: float
    correction_applied: Literal[False] = False


class AnalysisResult(_Model):
    """Réponse de `POST /v1/analyze-room`."""

    analysis_schema: str = Field(default=ANALYSIS_SCHEMA, alias="schema")
    status: AnalysisStatus
    #: `None` tant qu'aucun étage de géométrie n'existe. Un nombre inventé
    #: ici serait le pire mensonge que ce service puisse dire : c'est sur lui
    #: que le front décide d'ouvrir ou non l'écran de correction.
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    warnings: list[Warn] = Field(default_factory=list)

    image: ImageInfo
    quality: QualityMetrics | None = None
    lens: LensMetrics | None = None
    #: `None` jusqu'au LOT 6. Le front retombe alors sur la sélection
    #: manuelle, qui reste le socle du Visualiseur.
    scene_data: SceneData | None = None
    #: Durée par étage, en ms. `None` = étage non exécuté, `0.0` =
    #: instantané. Voir app/core/timing.py.
    timings: dict[str, float | None] = Field(default_factory=dict)
