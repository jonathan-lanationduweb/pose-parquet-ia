"""AnalysisResult — le contrat de sortie du service.

Ce contrat est **le nôtre**, distinct de `SceneData` qui est celui du front.
La séparation est délibérée : une analyse peut avoir beaucoup à dire sans
produire de scène du tout, et c'est encore le cas au LOT 1.

La règle de conception du projet tient dans le champ `status` : le service
doit savoir dire « je ne suis pas assez sûr » plutôt que livrer une mauvaise
géométrie. Un `needs_manual_adjustment` accompagné de mesures est un bon
résultat ; un `success` obtenu en devinant l'horizon n'en est pas un.

Le LOT 1 étend cette exigence aux mesures elles-mêmes : `BlurMetrics.sharp` et
`LensMetrics.verdict` peuvent tous deux répondre « indéterminé », et ce n'est
pas un échec de mesure — c'est le seul résultat vrai quand l'image ne porte
pas de quoi conclure.
"""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.core.warnings import Warn
from app.schemas.scene_data import SceneData

#: Version du contrat d'analyse. Indépendante de celle de SceneData.
#:
#: Passée à @2 au LOT 1. Les ruptures, toutes dans les blocs de mesure :
#:   - `lens.verdict` : `no_distortion_detected` devient
#:     `no_distortion_evidence` (voir `LensVerdict`) ;
#:   - `quality.blur` : `sharp` devient nullable, et le bloc porte de
#:     nouvelles mesures ;
#:   - `lens` porte `method`, `support` et `k1`.
#:
#: Le bloc `image`, le `status`, `confidence`, `warnings` et `sceneData` sont
#: inchangés. Aucun consommateur n'existe à ce jour — le front n'est pas
#: branché (LOT 8) — mais la version bouge quand même : c'est le seul signal
#: qu'un client aurait pu lire.
ANALYSIS_SCHEMA = "pose-parquet/analysis@2"


class AnalysisStatus(StrEnum):
    """Verdict d'ensemble.

    Les quatre premières valeurs sont le vocabulaire cible, stable. La
    cinquième est celle des LOT 0 et 1 et disparaîtra quand les étages de
    géométrie existeront : elle dit « les contrôles techniques ont tourné,
    l'analyse de la pièce n'existe pas encore ». Elle n'est pas un échec, et
    surtout pas un succès partiel — la confondre avec `partial` ferait croire
    qu'un sol a été cherché.
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
    """Netteté : le support d'abord, les trois candidates ensuite.

    Aucune de ces valeurs n'est un verdict « bonne / mauvaise photo ». Les
    trois mesures sont renvoyées ensemble pour qu'un rapport de benchmark
    permette de rejouer un choix de méthode sans réanalyser le corpus.

    Voir `app/services/blur_analysis.py` pour ce que chacune vaut et pourquoi
    `reblur_ratio` a été retenue.
    """

    #: **Le support.** Part des pixels portant une transition franche. C'est
    #: lui qui décide si une conclusion est possible, avant toute netteté :
    #: un mur lisse net et un mur lisse flou sont indiscernables, et le seul
    #: résultat vrai est alors `sharp: null`.
    strong_gradient_ratio: float
    #: Candidate A (LOT 0). Non normalisée : son échelle dépend du contenu
    #: autant que de la netteté. Conservée pour pouvoir rejouer le LOT 0.
    laplacian_variance: float
    #: Candidate B, **retenue**. 0 = net, 1 = flou. `null` si l'image n'a
    #: aucune variation à comparer.
    reblur_ratio: float | None = None
    #: Candidate C, écartée : elle rate le bougé aligné sur un axe. Largeur
    #: médiane des transitions fortes, en pixels à la résolution de travail.
    #: `null` si aucune n'est mesurable.
    edge_width_px: float | None = None
    #: La même, ramenée à la taille de travail de référence. C'est elle qui
    #: décide : une largeur en pixels natifs n'est pas comparable d'une
    #: résolution à l'autre, et la même scène en 960 px et en 1600 px
    #: recevait deux verdicts.
    edge_width_normalized: float | None = None
    #: Nombre de transitions fortes mesurées, pour lire `edge_width_px`.
    edge_count: int
    #: Côté long auquel les mesures ont été faites. Sans lui, aucun de ces
    #: chiffres ne se compare d'une photo à l'autre.
    working_side: int
    #: Méthode qui a conclu.
    method: str
    #: `null` = support insuffisant pour conclure. **Ce n'est pas « floue ».**
    sharp: bool | None = None
    #: L'image contient trop peu de transitions franches pour qu'on juge sa
    #: netteté. Peut être vrai sur une image parfaitement nette.
    low_texture: bool


class ExposureMetrics(_Model):
    """Luminance, contraste et écrêtage, en luma Rec. 709 ramené à 0 → 1.

    Volontairement **continues**. Une scène naturellement sombre et une photo
    sous-exposée ont la même luminance moyenne ; les distinguer demanderait de
    savoir ce que la scène *devrait* valoir, ce qu'aucune mesure d'image ne
    sait. On mesure donc, et on avertit large.
    """

    luma_mean: float
    luma_median: float
    #: Écart-type de la luma : le contraste global, en valeur absolue.
    #: **Mesure, pas critère** : il est proportionnel à la luminance, donc une
    #: photo sombre l'a mécaniquement bas. S'y fier confondait
    #: « sous-exposée » et « plate ».
    contrast_std: float
    #: Contraste **relatif** : écart-type / luminance moyenne. Sans dimension,
    #: donc indépendant de l'exposition — c'est lui qui décide. La même scène
    #: texturée donne 0,34 en pleine lumière et 0,35 après un gain de 0,20 ;
    #: une scène réellement plate donne 0,071.
    contrast_ratio: float
    #: Étendue entre les percentiles 5 et 95 — moins sensible aux extrêmes.
    contrast_p5_p95: float
    #: Proportion de pixels sous le seuil « très sombre ».
    dark_pixel_ratio: float
    #: Proportion de pixels au-dessus du seuil « très clair ».
    bright_pixel_ratio: float
    #: Pixels **écrêtés** : information détruite, pas seulement extrême. Un
    #: gain de 1,8 ne se contente pas d'éclaircir, il efface les hautes
    #: lumières — et cela ne se répare pas. La distinction avec
    #: `bright_pixel_ratio` est ce qui sépare une photo claire d'une photo
    #: dont les hautes lumières sont perdues.
    clipped_high_ratio: float
    clipped_low_ratio: float


class QualityMetrics(_Model):
    """Contrôle qualité photo, sans aucun modèle."""

    blur: BlurMetrics
    exposure: ExposureMetrics


class EdgeTrack(_Model):
    """Une arête suivie, et ce qu'elle vaut comme preuve.

    `sagitta_px` seul ne veut rien dire : c'est `fit_rms_px` qui dit si la
    parabole **décrit** le tracé. Le front a perdu une scène à cette confusion
    (voir docs/lens-distortion.md) — les deux voyagent ensemble.
    """

    orientation: Literal["vertical", "horizontal"]
    #: Flèche d'arc non signée, en pixels. Ce que mesurait le LOT 0.
    sagitta_px: float
    #: Flèche **signée** relativement au centre de l'image.
    #: Positif = l'arête bombe en s'écartant du centre = barillet.
    #: C'est le champ qui manquait au LOT 0 pour distinguer une distorsion
    #: d'objectif d'un motif répétitif.
    radial_bulge_px: float
    #: Écart-type d'ajustement de la parabole, en pixels.
    fit_rms_px: float
    points: int
    #: Part de l'axe balayé couverte par le tracé. Un tracé court ne prouve
    #: rien : la flèche croît comme le carré de la longueur.
    span_ratio: float
    #: Distance normalisée du centre optique (0 = sur l'axe, 1 = au bord).
    #: La distorsion radiale ne déplace rien sur l'axe : une arête centrale
    #: ne prouve jamais rien.
    center_offset: float
    #: Retenu comme preuve : assez long, bien ajusté, assez loin du centre.
    usable: bool


class LensSupport(_Model):
    """De quoi le verdict d'objectif dispose pour se prononcer.

    Ce bloc existe pour qu'un verdict ne soit jamais un score opaque. À terme
    (LOT 7) c'est lui qui alimentera la confiance ; ici il sert déjà à lire un
    rapport de benchmark et à comprendre *pourquoi* une réponse est
    indéterminée plutôt que de constater qu'elle l'est.
    """

    usable_edges: int
    vertical_edges: int
    horizontal_edges: int
    #: Somme des longueurs des tracés retenus, en pixels. Le vrai volume de
    #: preuve : quatre arêtes de 800 px ne valent pas quarante de 40 px.
    total_track_px: float
    #: Part des quadrants de l'image (relativement au centre) contenant au
    #: moins un tracé retenu. Une distorsion radiale se constate sur tout le
    #: cadre ; des arêtes groupées dans un coin ne la prouvent pas.
    spatial_coverage: float
    #: Part des tracés retenus qui bombent dans le **même sens radial**.
    #: 1,0 = parfaitement cohérent, 0,5 = aléatoire. C'est le discriminant
    #: entre une distorsion d'objectif et un accident de texture.
    sign_agreement: float
    #: Médiane des flèches signées, en pixels. Son signe dit le sens supposé.
    median_radial_bulge_px: float


class K1Estimate(_Model):
    """Coefficient radial estimé en redressant les tracés observés.

    Le modèle est celui du corpus synthétique, dans le sens de
    l'échantillonnage : `r_source = r_image · (1 + k1·r²)`, `r` normalisé par
    la demi-diagonale. Positif = barillet.

    `residual_gain` compte autant que `k1` : la recherche renvoie *toujours* un
    k1 optimal, y compris sur une image sans distorsion. Ce qui distingue une
    vraie détection, c'est la part de non-rectitude que ce k1 fait
    effectivement disparaître.
    """

    k1: float
    #: Non-rectitude résiduelle sans correction, sans dimension : rapport de
    #: l'écart perpendiculaire à l'étendue du tracé. Sans dimension exprès —
    #: une mesure en pixels croîtrait avec l'échelle de la correction et
    #: biaiserait la recherche vers les k1 négatifs, qui contractent l'image.
    straightness_at_zero: float
    #: La même, au meilleur k1.
    straightness_at_best: float
    #: `1 - best/zero`. Proche de 0 : le k1 trouvé n'explique rien.
    residual_gain: float
    #: Bornes de la recherche, pour qu'un résultat au bord se repère.
    search_min: float
    search_max: float


class LensVerdict(StrEnum):
    """Ce que la mesure autorise à dire, et rien de plus.

    `NO_DISTORTION_EVIDENCE` remplace le `no_distortion_detected` du LOT 0.
    Le changement n'est pas cosmétique : « rien détecté » se lit facilement
    comme « l'objectif est sain », alors que la mesure ne dit que « les arêtes
    que j'ai su mesurer sont droites ». Une photo peut n'offrir que des arêtes
    proches du centre optique — là où la distorsion radiale ne déplace rien —
    et être franchement distordue aux bords. L'absence de preuve n'est pas une
    preuve d'absence, et le nom du verdict doit le dire.
    """

    NO_DISTORTION_EVIDENCE = "no_distortion_evidence"
    DISTORTION_SUSPECTED = "distortion_suspected"
    #: Support insuffisant. Le cas le plus fréquent sur une photo d'intérieur
    #: ordinaire, et le seul honnête quand c'est vrai.
    UNDETERMINED = "undetermined"


class LensMetrics(_Model):
    """Analyse d'objectif. **Aucune correction n'est appliquée.**

    Le service mesure et rapporte. Corriger une distorsion demande un
    étalonnage que nous n'avons pas, et une correction fausse est pire qu'une
    absence de correction : elle entre dans tous les relevés suivants sans plus
    rien qui la distingue du reste.
    """

    verdict: LensVerdict
    #: Détecteur qui a conclu.
    method: str
    #: Sens supposé, quand il y en a un.
    suspected_sign: Literal["barrel", "pincushion"] | None = None
    support: LensSupport
    #: `null` si l'estimation n'a pas pu tourner, faute de tracés.
    k1: K1Estimate | None = None
    #: Flèche maximale parmi les arêtes retenues, en pixels de l'image.
    max_sagitta_px: float | None = None
    #: Le même chiffre ramené à la largeur de référence, comparable entre
    #: photos de résolutions différentes.
    max_sagitta_px_normalized: float | None = None
    #: Seuil effectivement appliqué par la candidate A, en pixels de l'image.
    suspect_threshold_px: float
    tracks: list[EdgeTrack] = Field(default_factory=list)
    correction_applied: Literal[False] = False


class AnalysisResult(_Model):
    """Réponse de `POST /v1/analyze-room`."""

    analysis_schema: str = Field(default=ANALYSIS_SCHEMA, alias="schema")
    status: AnalysisStatus
    #: `None` tant qu'aucun étage de géométrie n'existe. Un nombre inventé ici
    #: serait le pire mensonge que ce service puisse dire : c'est sur lui que
    #: le front décide d'ouvrir ou non l'écran de correction.
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
