"""Configuration du service, en un seul endroit.

Tout seuil numérique du projet est déclaré ici. La raison n'est pas
l'élégance : c'est qu'aucun de ces seuils n'est universel. Une variance de
Laplacien de 120 ne veut pas dire « photo nette » dans l'absolu — elle le veut
dire pour des photos d'intérieur ramenées à 1024 px de côté, et il faudra la
réviser quand le corpus sera assez grand pour la mesurer. Un seuil éparpillé
dans le code est un seuil qu'on ne révise jamais.
"""

from enum import StrEnum
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICE_NAME = "pose-parquet-ai"

#: Formats acceptés, tels que Pillow les nomme après décodage.
#: On se fie au contenu décodé, jamais au `Content-Type` déclaré par le client.
ALLOWED_FORMATS: frozenset[str] = frozenset({"JPEG", "PNG", "WEBP"})

#: Types MIME annoncés dans la documentation de l'API, à titre indicatif.
ALLOWED_MIME_TYPES: tuple[str, ...] = ("image/jpeg", "image/png", "image/webp")


class BlurMethod(StrEnum):
    """Mesure de netteté active. Les trois sont toujours calculées et
    renvoyées ; ce réglage ne décide que de celle qui **conclut**.

    Voir `app/services/blur_analysis.py` pour ce que chacune vaut, et
    `docs/quality-methodology.md` pour la comparaison mesurée qui a fixé le
    défaut.
    """

    LAPLACIAN_VARIANCE = "laplacian_variance"
    REBLUR_RATIO = "reblur_ratio"
    EDGE_WIDTH = "edge_width"


class LensMethod(StrEnum):
    """Détecteur de distorsion actif.

    `SAGITTA_MAGNITUDE` est le détecteur du LOT 0, conservé comme candidate A
    et comme base de comparaison — pas comme solution retenue.
    """

    SAGITTA_MAGNITUDE = "sagitta_magnitude"
    RADIAL_CONSISTENCY = "radial_consistency"
    K1_FIT = "k1_fit"


class Settings(BaseSettings):
    """Réglages lus depuis l'environnement, préfixe `PPAI_`.

    Voir `.env.example` pour la liste commentée.
    """

    model_config = SettingsConfigDict(
        env_prefix="PPAI_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Service ---------------------------------------------------------
    log_level: str = "INFO"
    log_format: str = Field(default="text", pattern="^(text|json)$")
    cors_origins: str = ""

    # --- Développement -----------------------------------------------------
    #: Servir AUSSI les fichiers du visualiseur, en développement seulement.
    #:
    #: Deux serveurs pour regarder une photo dans une pièce, c'est deux
    #: serveurs à démarrer, deux ports à retenir, et une politique CORS à
    #: tenir. Avec ce drapeau, FastAPI sert `tools/`, `web/` et `datasets/`
    #: en plus de son API : le visualiseur et l'analyse partagent alors la
    #: MÊME ORIGINE, et il n'y a plus de CORS du tout.
    #:
    #: **Faux par défaut, et ce défaut compte.** En production ce service est
    #: un analyseur, pas un serveur de fichiers : c'est un rôle de plus,
    #: une surface d'attaque de plus, et des fichiers privés
    #: (`datasets/private-real/`) à un chemin devinable. Le mettre à vrai est
    #: une décision de poste de travail, jamais un défaut d'image.
    dev_serve_static: bool = False

    # --- Limites d'upload ------------------------------------------------
    #: 20 Mo, aligné sur le contrat du front (docs/future-ai-api-contract.md).
    max_upload_bytes: int = 20 * 1024 * 1024
    #: Garde-fou anti bombe de décompression : un PNG de 40 ko peut décoder
    #: en plusieurs gigaoctets. Pillow refuse au-delà de cette limite.
    max_image_pixels: int = 50_000_000
    #: En dessous, la photo est trop petite pour qu'un relevé de géométrie
    #: ait un sens. Seule limite bloquante du LOT 0.
    min_long_side: int = 640
    #: Au-delà, l'image est un panorama ou une bande : ce n'est pas une pièce
    #: photographiée, et la perspective n'y est pas exploitable.
    max_aspect_ratio: float = 3.0

    # --- Qualité d'image -------------------------------------------------
    #: Côté long auquel l'image est ramenée avant la mesure de flou. La
    #: variance du Laplacien dépend fortement de la résolution : sans taille
    #: de travail fixe, deux tirages de la même photo donnent deux scores.
    blur_working_side: int = 1024
    #: Méthode qui conclut sur la netteté. Les trois mesures sont calculées
    #: dans tous les cas : changer ce réglage ne change pas ce qui est
    #: mesuré, seulement ce qui est déduit.
    blur_method: BlurMethod = BlurMethod.REBLUR_RATIO
    #: Candidate A — variance du Laplacien au-dessus de laquelle on classe
    #: « net ». Conservé pour pouvoir rejouer le comportement du LOT 0.
    blur_sharp_min: float = 120.0
    # Chaque candidate a DEUX bornes, pas un seuil. Entre les deux, la
    # netteté est déclarée **indéterminée** plutôt que tranchée au hasard.
    # Les bornes sont posées sur les bords des groupes réellement mesurés
    # (`python -m benchmarks.compare_candidates`), pas au milieu : un seuil
    # unique placé au centre d'une marge étroite tranche des cas que la mesure
    # ne sépare pas.
    #
    #: Candidate B (**retenue**) — rapport de reflou. Bords mesurés sur le
    #: corpus : nets <= 0,358, flous >= 0,478. Marge 0,120, séparation 0,142.
    #: Les images rééchantillonnées par une distorsion tombent dans la bande,
    #: donc en « indéterminé » plutôt qu'en « floue » — c'est exactement ce
    #: que la bande sert à éviter.
    blur_reblur_sharp_max: float = 0.3583
    blur_reblur_blurry_min: float = 0.4778
    #: Candidate C — largeur médiane de transition, ramenée à
    #: `blur_working_side`. **Écartée par la mesure** : sur le corpus complet
    #: sa marge est NÉGATIVE (−1,0 px), les deux cas de bougé aligné sur un
    #: axe tombant à 8,0 px, dans l'intervalle des images nettes. Aucune borne
    #: ne peut donc les séparer. Les valeurs ci-dessous sont celles du corpus
    #: avant ces deux cas, conservées pour rejouer la comparaison.
    blur_edge_width_sharp_max: float = 9.0
    blur_edge_width_blurry_min: float = 12.0
    #: Support minimal : part des pixels portant une transition franche en
    #: dessous de laquelle la netteté est déclarée **indéterminée**, et non
    #: « floue ». Mesuré : un mur lisse donne 0,00000, un mur avec trois
    #: arêtes 0,025, une scène architecturale 0,068. Trois ordres de grandeur
    #: séparent l'absence de support de sa présence la plus maigre.
    blur_min_strong_gradient_ratio: float = 0.005
    #: Luminance (0 → 1) sous laquelle un pixel est compté « très sombre ».
    dark_luma_max: float = 0.06
    #: Luminance au-dessus de laquelle un pixel est compté « brûlé ».
    bright_luma_min: float = 0.98
    #: Proportions au-delà desquelles on avertit.
    dark_ratio_max: float = 0.35
    bright_ratio_max: float = 0.12
    #: Bornes de la luminance moyenne acceptable.
    luma_mean_min: float = 0.12
    luma_mean_max: float = 0.85
    #: Écart-type de luminance sous lequel l'image est jugée plate.
    #: **Conservé comme mesure, plus utilisé comme critère** : l'écart-type
    #: est proportionnel à la luminance, donc une photo sombre l'a
    #: mécaniquement bas. Il confondait « sous-exposée » et « plate ».
    contrast_min: float = 0.05
    #: Contraste **relatif** (écart-type / luminance moyenne), sans dimension
    #: et donc indépendant de l'exposition. C'est lui qui décide.
    #: Mesuré : une scène texturée donne 0,34 quelle que soit son exposition
    #: (0,34 en pleine lumière, 0,35 après un gain de 0,20), une scène
    #: réellement plate 0,071. Deux groupes séparés par un facteur cinq.
    contrast_ratio_min: float = 0.10
    #: Part de pixels écrêtés au-delà de laquelle on avertit. Séparé des
    #: seuils « sombre / clair » : une photo claire se rattrape, une photo
    #: dont les hautes lumières sont écrêtées a perdu l'information.
    clipped_high_ratio_max: float = 0.02
    clipped_low_ratio_max: float = 0.05

    # --- Analyse d'objectif ----------------------------------------------
    #: Flèche d'arc, en pixels, au-delà de laquelle une distorsion est
    #: soupçonnée. Exprimée pour `lens_reference_width` ; mise à l'échelle
    #: de l'image réelle à l'usage. Ordre de grandeur relevé par le front :
    #: une arête franche donne 0,1 à 2 px sur 1600 px de large.
    lens_sagitta_suspect_px: float = 3.0
    lens_reference_width: int = 1600
    #: Écart-type d'ajustement maximal pour qu'un suivi d'arête compte.
    #: Au-delà, la parabole ne décrit pas le tracé et la flèche ne veut rien
    #: dire (voir docs/lens-distortion.md).
    lens_max_fit_rms_px: float = 2.0
    #: Nombre minimal de points d'un suivi retenu.
    lens_min_track_points: int = 40
    #: Fraction de la hauteur d'image qu'un suivi doit couvrir pour compter.
    #: « Le bombement croît comme le carré de la longueur ; sur un segment
    #: court il se noie dans le bruit. » Sans ce garde-fou, un motif répétitif
    #: — carrelage, bibliothèque, rayures — fournit des dizaines de tracés
    #: courts dont la flèche n'est que du bruit, et le verdict devient un
    #: tirage au sort. Mesuré sur le corpus synthétique : c'est ce seuil qui
    #: distingue une arête d'un accident de texture.
    lens_min_track_height_ratio: float = 0.25
    #: Nombre d'arêtes utilisables en dessous duquel le verdict reste
    #: indéterminé. Une seule arête ne prouve rien.
    lens_min_usable_edges: int = 2

    # --- Analyse d'objectif : candidates du LOT 1 ------------------------
    #: Détecteur qui conclut. Toutes les mesures sont calculées dans tous les
    #: cas — comme pour la netteté, ce réglage ne change que la déduction.
    lens_method: LensMethod = LensMethod.K1_FIT
    #: Part des arêtes retenues qui doivent bomber dans le **même sens
    #: radial** pour que la courbure soit imputable à l'objectif. Une
    #: distorsion radiale courbe toutes les droites de façon cohérente ; un
    #: carrelage ou un objet courbe donnent des signes désordonnés. C'est ce
    #: critère, et non un seuil d'amplitude, qui sépare les deux.
    lens_min_sign_agreement: float = 0.8
    #: Bornes et pas de la recherche de k1 (candidate C). L'intervalle couvre
    #: du coussinet franc au barillet d'ultra grand-angle.
    lens_k1_search_min: float = -0.45
    lens_k1_search_max: float = 0.45
    lens_k1_search_steps: int = 181
    #: |k1| estimé en dessous duquel on ne conclut pas à une distorsion. En
    #: dessous, l'effet est plus petit que le bruit de suivi d'arêtes.
    lens_k1_suspect_min: float = 0.03
    #: Part du résidu de rectitude que le meilleur k1 doit faire disparaître.
    #: Sans ce critère, la recherche renvoie toujours un k1 « optimal », y
    #: compris sur une image sans aucune distorsion.
    lens_k1_min_residual_gain: float = 0.25

    #: Réglages qui changent le **résultat** d'une analyse, par opposition à
    #: ceux qui changent son environnement (journalisation, CORS, limites de
    #: transfert). Un rapport de benchmark en embarque une copie : sans elle,
    #: deux rapports ne sont pas comparables et on ne sait pas lequel croire.
    #:
    #: La liste est explicite plutôt que déduite du modèle. C'est un peu de
    #: redondance contre un vrai risque : un réglage ajouté et oublié ici
    #: influencerait les mesures sans laisser de trace dans les rapports.
    ALGORITHM_FIELDS: tuple[str, ...] = (
        "min_long_side",
        "max_aspect_ratio",
        "blur_working_side",
        "blur_method",
        "blur_sharp_min",
        "blur_reblur_sharp_max",
        "blur_edge_width_sharp_max",
        "blur_min_strong_gradient_ratio",
        "dark_luma_max",
        "bright_luma_min",
        "dark_ratio_max",
        "bright_ratio_max",
        "luma_mean_min",
        "luma_mean_max",
        "contrast_min",
        "contrast_ratio_min",
        "blur_reblur_blurry_min",
        "blur_edge_width_blurry_min",
        "clipped_high_ratio_max",
        "clipped_low_ratio_max",
        "lens_method",
        "lens_sagitta_suspect_px",
        "lens_reference_width",
        "lens_max_fit_rms_px",
        "lens_min_track_points",
        "lens_min_track_height_ratio",
        "lens_min_usable_edges",
        "lens_min_sign_agreement",
        "lens_k1_search_min",
        "lens_k1_search_max",
        "lens_k1_search_steps",
        "lens_k1_suspect_min",
        "lens_k1_min_residual_gain",
    )

    def algorithm_config(self) -> dict[str, float | int | str]:
        """Instantané des réglages qui décident d'un résultat.

        Destiné à être écrit tel quel dans un rapport de benchmark, pour qu'une
        exécution soit rejouable des mois plus tard sans deviner quels seuils
        étaient en vigueur.
        """
        snapshot: dict[str, float | int | str] = {}
        for name in self.ALGORITHM_FIELDS:
            value = getattr(self, name)
            snapshot[name] = value.value if isinstance(value, StrEnum) else value
        return snapshot

    @property
    def cors_origin_list(self) -> list[str]:
        """Origines CORS, découpées. Vide par défaut : rien n'est ouvert."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Réglages du processus. Mis en cache : lus une fois, pas à chaque requête."""
    return Settings()
