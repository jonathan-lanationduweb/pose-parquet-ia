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
    #: Hautes lumières ou ombres **écrêtées** : l'information est détruite, pas
    #: seulement extrême. Distinct de `IMAGE_OVEREXPOSED`, qui dit seulement
    #: que la photo est claire — une photo claire se rattrape, une photo
    #: écrêtée non.
    IMAGE_CLIPPED = "image_clipped"
    #: Trop peu de transitions franches pour juger la netteté. **N'est pas un
    #: défaut de la photo** : un mur lisse parfaitement net le déclenche. Ce
    #: code dit « je n'ai pas de quoi conclure », là où `IMAGE_BLURRY` dit
    #: « j'ai regardé, et c'est flou ». Les confondre était le défaut du
    #: LOT 0.
    IMAGE_LOW_TEXTURE = "image_low_texture"

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

#: Codes que le pipeline sait émettre aujourd'hui, et qui constituent une
#: **affirmation sur la photo**. C'est l'ensemble d'étiquettes sur lequel le
#: banc d'essai construit sa matrice de confusion : hors de cette liste, un
#: code n'est ni un vrai positif ni un faux positif, parce qu'il n'y avait
#: aucune chance qu'il soit émis ou qu'il ne prétend rien.
#:
#: La liste grandira étage par étage. La tenir à jour est ce qui garde le
#: dénominateur du comptage honnête : ajouter un code émis sans l'ajouter ici
#: le rendrait invisible aux faux positifs.
SCORED: frozenset[Warn] = frozenset(
    {
        Warn.IMAGE_TOO_SMALL,
        Warn.IMAGE_BLURRY,
        Warn.IMAGE_TOO_DARK,
        Warn.IMAGE_OVEREXPOSED,
        Warn.IMAGE_LOW_CONTRAST,
        Warn.IMAGE_EXTREME_ASPECT_RATIO,
        Warn.IMAGE_CLIPPED,
        Warn.IMAGE_LOW_TEXTURE,
        Warn.LENS_DISTORTION_SUSPECTED,
    }
)

#: Codes qui ne prétendent rien sur la photo, et qu'il serait donc faux de
#: compter comme des détections.
#:
#: `LENS_ANALYSIS_UNDETERMINED` mérite un mot : c'est un aveu d'ignorance. Le
#: compter en faux positif punirait l'honnêteté, et le compter en vrai positif
#: récompenserait un détecteur qui répondrait toujours « je ne sais pas ». Il
#: est donc **compté à part** — voir `benchmarks/scoring.py`, qui rapporte le
#: nombre de cas indéterminés à côté de la matrice, jamais dedans.
INFORMATIONAL: frozenset[Warn] = frozenset(
    {Warn.STAGE_NOT_IMPLEMENTED, Warn.LENS_ANALYSIS_UNDETERMINED}
)
