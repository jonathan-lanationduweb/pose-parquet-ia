"""Codes d'avertissement, déclarés une fois.

Un avertissement est un **code machine**, pas une phrase. Le front décide de
la formulation affichée ; le service se contente de dire ce qu'il a constaté.
Cette séparation évite deux ennuis : traduire côté Python, et voir un libellé
changer sans que rien ne signale que le sens a changé aussi.

Aucune de ces chaînes ne doit être écrite en dur ailleurs dans le projet.
"""

from enum import StrEnum


class Warn(StrEnum):
    """Tous les codes que le service sait émettre, à ce jour et à venir.

    Les codes marqués « LOT n » ne sont pas encore émis : ils sont déclarés
    ici pour que le vocabulaire soit fixé avant d'être produit, et pour que le
    front puisse être écrit contre la liste complète.
    """

    # --- Image : émis dès le LOT 0 ---------------------------------------
    IMAGE_TOO_SMALL = "image_too_small"
    IMAGE_BLURRY = "image_blurry"
    IMAGE_TOO_DARK = "image_too_dark"
    IMAGE_OVEREXPOSED = "image_overexposed"
    IMAGE_LOW_CONTRAST = "image_low_contrast"
    IMAGE_EXTREME_ASPECT_RATIO = "image_extreme_aspect_ratio"

    # --- Objectif : LOT 1 (mesure disponible, verdict prudent) -----------
    LENS_DISTORTION_SUSPECTED = "lens_distortion_suspected"
    LENS_ANALYSIS_UNDETERMINED = "lens_analysis_undetermined"

    # --- Géométrie et sol : LOT 2 à LOT 5 --------------------------------
    FLOOR_NOT_FOUND = "floor_not_found"
    FLOOR_BOUNDARY_UNCERTAIN = "floor_boundary_uncertain"
    FLOOR_PARTIALLY_COVERED = "floor_partially_covered"
    WALL_FLOOR_CONTRAST_LOW = "wall_floor_contrast_low"
    WALL_INTERSECTION_OCCLUDED = "wall_intersection_occluded"
    PERSPECTIVE_UNCERTAIN = "perspective_uncertain"
    SCALE_UNKNOWN = "scale_unknown"
    OCCLUSION_COMPLEX = "occlusion_complex"

    # --- Étage non implémenté --------------------------------------------
    # Émis tant qu'un étage du pipeline n'existe pas. C'est la façon honnête
    # de dire « je n'ai pas regardé » sans la confondre avec « rien à
    # signaler ». Retiré étage par étage, du LOT 2 au LOT 6.
    STAGE_NOT_IMPLEMENTED = "stage_not_implemented"


#: Codes qui, à eux seuls, rendent la photo inexploitable.
#: Le service répond alors `rejected` sans aller plus loin.
BLOCKING: frozenset[Warn] = frozenset({Warn.IMAGE_TOO_SMALL})
