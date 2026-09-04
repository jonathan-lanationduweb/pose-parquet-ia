"""Configuration du service, en un seul endroit.

Tout seuil numérique du projet est déclaré ici. La raison n'est pas
l'élégance : c'est qu'aucun de ces seuils n'est universel. Une variance de
Laplacien de 120 ne veut pas dire « photo nette » dans l'absolu — elle le veut
dire pour des photos d'intérieur ramenées à 1024 px de côté, et il faudra la
réviser quand le corpus sera assez grand pour la mesurer. Un seuil éparpillé
dans le code est un seuil qu'on ne révise jamais.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICE_NAME = "pose-parquet-ai"

#: Formats acceptés, tels que Pillow les nomme après décodage.
#: On se fie au contenu décodé, jamais au `Content-Type` déclaré par le client.
ALLOWED_FORMATS: frozenset[str] = frozenset({"JPEG", "PNG", "WEBP"})

#: Types MIME annoncés dans la documentation de l'API, à titre indicatif.
ALLOWED_MIME_TYPES: tuple[str, ...] = ("image/jpeg", "image/png", "image/webp")


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
    #: Variance du Laplacien au-dessus de laquelle on classe « net ».
    #: Indicatif et révisable — la mesure brute est toujours renvoyée.
    blur_sharp_min: float = 120.0
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
    contrast_min: float = 0.05

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

    @property
    def cors_origin_list(self) -> list[str]:
        """Origines CORS, découpées. Vide par défaut : rien n'est ouvert."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Réglages du processus. Mis en cache : lus une fois, pas à chaque requête."""
    return Settings()
