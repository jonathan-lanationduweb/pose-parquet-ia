"""Le corpus synthétique du LOT 1, déclaré une fois.

Chaque entrée dit trois choses : comment fabriquer l'image, ce qu'on lui a
**imposé** (la vérité terrain), et ce qu'on **attend** que l'analyse en dise.

## D'où viennent les attentes

Elles viennent de la transformation, jamais de la sortie du système. Un gain
d'exposition de 0,20 retire plus de deux diaphragmes : la photo est
sous-exposée, que le détecteur le voie ou non. Écrire l'attente d'après ce que
le code répond aujourd'hui transformerait le banc d'essai en miroir — il
confirmerait toujours, et ne mesurerait jamais rien.

Conséquence à assumer : quand le système contredit une attente, c'est un
**faux négatif à rapporter**, pas une étiquette à corriger.

## Les cas non gradés

`graded=False` marque les cas dont la bonne réponse est **discutable**, et ils
sont aussi utiles que les autres. Un flou de sigma 0,8 est-il « flou » ? Une
pièce à moitié dans l'ombre est-elle « sous-exposée » ? Personne ne peut le
dire d'une image seule. Les grader reviendrait à inventer une vérité pour
gonfler un score ; les exclure du corpus reviendrait à ne jamais regarder la
zone grise. Ils sont donc mesurés et rapportés, hors comptage.

## Ce que ce corpus ne prouve pas

Aucune de ces images n'est une photographie. Pas de vignettage, pas
d'aberration chromatique, pas de bruit de capteur corrélé, pas de compression
JPEG agressive, pas de vraie pièce. Une distorsion polynomiale parfaite est un
cas d'école : elle dit si un détecteur voit ce qui est indiscutablement là.
Elle ne dit pas s'il marchera sur un téléphone. Voir `datasets/README.md` pour
l'état du corpus réel.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

from app.core.warnings import Warn
from corpus import patterns, scenes
from corpus import transforms as tr

#: Format de travail du corpus, aligné sur les scènes calibrées du front.
SIZE = scenes.CORPUS_SIZE

#: Graine unique de tout le corpus. Une seule, déclarée ici, pour qu'aucune
#: entrée ne puisse dériver silencieusement d'une exécution à l'autre.
SEED = 20260907


@dataclass(frozen=True, slots=True)
class Entry:
    """Une image du corpus, sa fabrication, sa vérité terrain, son attente."""

    id: str
    difficulty: str
    build: Callable[[], np.ndarray]
    #: Ce que la transformation a imposé. Vide quand on n'a rien imposé.
    #: N'est **jamais** une estimation — seulement un paramètre d'entrée.
    truth: dict[str, float | str] = field(default_factory=dict)
    expected: tuple[Warn, ...] = ()
    #: Faux : la bonne réponse est discutable, l'entrée est mesurée mais pas
    #: comptée. Voir l'en-tête du module.
    graded: bool = True
    image_format: str = "PNG"
    note: str = ""


def _textured() -> np.ndarray:
    return scenes.textured(SIZE, seed=SEED % 1000)


def _archi() -> np.ndarray:
    return scenes.architectural(SIZE, seed=SEED % 97)


def _distorted(k1: float) -> Callable[[], np.ndarray]:
    return lambda: tr.radial_distort(_archi(), k1)


# --- Netteté --------------------------------------------------------------
# Les trois cas que le lot doit impérativement distinguer sont ici :
# `sharp-textured` (net et riche), `blur-sigma-3` (le même, réellement flouté)
# et `smooth-wall-sharp` (net mais sans texture). Confondre les deux derniers
# était le défaut de la variance du Laplacien.

_SHARPNESS: tuple[Entry, ...] = (
    Entry("sharp-textured", "easy", _textured, note="Référence : nette et riche en détail."),
    Entry(
        "blur-sigma-0.8",
        "medium",
        lambda: tr.gaussian_blur(_textured(), 0.8),
        truth={"blur_sigma": 0.8},
        graded=False,
        note="Flou léger, à la limite du perceptible. La bonne réponse est discutable.",
    ),
    Entry(
        "blur-sigma-1.5",
        "medium",
        lambda: tr.gaussian_blur(_textured(), 1.5),
        truth={"blur_sigma": 1.5},
        expected=(Warn.IMAGE_BLURRY,),
    ),
    Entry(
        "blur-sigma-3",
        "medium",
        lambda: tr.gaussian_blur(_textured(), 3.0),
        truth={"blur_sigma": 3.0},
        expected=(Warn.IMAGE_BLURRY,),
    ),
    Entry(
        "blur-sigma-6",
        "hard",
        lambda: tr.gaussian_blur(_textured(), 6.0),
        truth={"blur_sigma": 6.0},
        expected=(Warn.IMAGE_BLURRY,),
    ),
    Entry(
        "motion-blur-15",
        "medium",
        lambda: tr.motion_blur(_textured(), 15, 30.0),
        truth={"motion_length": 15.0, "motion_angle_deg": 30.0},
        expected=(Warn.IMAGE_BLURRY,),
        note="Flou anisotrope : les arêtes parallèles au mouvement restent nettes.",
    ),
    Entry(
        "motion-blur-31",
        "hard",
        lambda: tr.motion_blur(_textured(), 31, 70.0),
        truth={"motion_length": 31.0, "motion_angle_deg": 70.0},
        expected=(Warn.IMAGE_BLURRY,),
    ),
    # Bougé aligné sur un axe. Détecté par la candidate retenue (B), et
    # **manqué par la candidate C** — c'est ce couple de cas qui a fait
    # basculer le choix, en rendant la marge de C négative. Ils restent gradés
    # pour que le jour où l'on repasserait à C, le rapport le dise.
    # Voir docs/quality-methodology.md.
    Entry(
        "motion-blur-21-horizontal",
        "hard",
        lambda: tr.motion_blur(_textured(), 21, 0.0),
        truth={"motion_length": 21.0, "motion_angle_deg": 0.0},
        expected=(Warn.IMAGE_BLURRY,),
        note=(
            "Bougé aligné sur l'axe x. NON DÉTECTÉ : sur une texture dense, un "
            "noyau en créneau de 21 px transforme les arêtes voisines en "
            "ondulations rapprochées, et la marche vers les minima locaux y "
            "trouve des bosses étroites — largeur médiane 8 px, comme une image "
            "nette. Le gradient de crête, lui, chute de 1,55 à 0,37 : le signal "
            "existe, la mesure retenue ne le lit pas."
        ),
    ),
    Entry(
        "motion-blur-21-vertical",
        "hard",
        lambda: tr.motion_blur(_textured(), 21, 90.0),
        truth={"motion_length": 21.0, "motion_angle_deg": 90.0},
        expected=(Warn.IMAGE_BLURRY,),
        note="Le symétrique du précédent, sur l'axe y. Non détecté pour la même raison.",
    ),
    Entry(
        "sharp-noise-6",
        "medium",
        lambda: tr.add_noise(_textured(), 6.0, SEED),
        truth={"noise_sigma": 6.0},
        note="Nette malgré le bruit. Le bruit fait MONTER la variance du Laplacien.",
    ),
    Entry(
        "blur3-noise-6",
        "hard",
        lambda: tr.add_noise(tr.gaussian_blur(_textured(), 3.0), 6.0, SEED),
        truth={"blur_sigma": 3.0, "noise_sigma": 6.0},
        expected=(Warn.IMAGE_BLURRY,),
        note="Floue ET bruitée : le bruit fournit de la variation que le reflou détruit.",
    ),
    Entry(
        "blur3-noise-12",
        "hard",
        lambda: tr.add_noise(tr.gaussian_blur(_textured(), 3.0), 12.0, SEED),
        truth={"blur_sigma": 3.0, "noise_sigma": 12.0},
        expected=(Warn.IMAGE_BLURRY,),
        note="Bruit fort : le cas où la mesure de netteté est le plus en danger.",
    ),
    Entry(
        "smooth-wall-sharp",
        "hard",
        lambda: scenes.smooth_wall(SIZE),
        expected=(Warn.IMAGE_LOW_TEXTURE,),
        note=(
            "PARFAITEMENT NETTE et sans détail. Ne doit PAS être déclarée floue : "
            "c'est le contre-exemple qui interdit de traduire « peu de haute "
            "fréquence » par « floue »."
        ),
    ),
    Entry(
        "smooth-wall-blurred",
        "hard",
        lambda: tr.gaussian_blur(scenes.smooth_wall(SIZE), 6.0),
        truth={"blur_sigma": 6.0},
        expected=(Warn.IMAGE_LOW_TEXTURE,),
        note=(
            "Réellement floutée, et indiscernable de la précédente. Le seul "
            "résultat vrai est « je ne sais pas » — d'où l'attente de "
            "low_texture et non de blurry."
        ),
    ),
    Entry(
        "sparse-detail-sharp",
        "medium",
        lambda: scenes.sparse_detail(SIZE),
        note="Mur presque vide, trois arêtes franches. Assez de support pour conclure : nette.",
    ),
    Entry(
        "sparse-detail-blurred",
        "hard",
        lambda: tr.gaussian_blur(scenes.sparse_detail(SIZE), 6.0),
        truth={"blur_sigma": 6.0},
        expected=(Warn.IMAGE_BLURRY,),
        note="Peu de texture MAIS assez pour conclure. Paire décisive avec la précédente.",
    ),
)


# --- Exposition et contraste ---------------------------------------------

_EXPOSURE: tuple[Entry, ...] = (
    Entry(
        "underexposed-0.20",
        "hard",
        lambda: tr.exposure_gain(_textured(), 0.20),
        truth={"exposure_gain": 0.20},
        expected=(Warn.IMAGE_TOO_DARK,),
        note="Plus de deux diaphragmes perdus : sous-exposée, quoi qu'en dise le détecteur.",
    ),
    Entry(
        "underexposed-0.45",
        "medium",
        lambda: tr.exposure_gain(_textured(), 0.45),
        truth={"exposure_gain": 0.45},
        graded=False,
        note=(
            "Sombre mais exploitable. La frontière avec « sous-exposée » est un choix, pas un fait."
        ),
    ),
    Entry(
        "overexposed-1.60",
        "hard",
        lambda: tr.exposure_gain(_textured(), 1.60),
        truth={"exposure_gain": 1.60},
        expected=(Warn.IMAGE_OVEREXPOSED, Warn.IMAGE_CLIPPED),
        note="Hautes lumières écrêtées : l'information est détruite, pas seulement claire.",
    ),
    Entry(
        "overexposed-1.20",
        "medium",
        lambda: tr.exposure_gain(_textured(), 1.20),
        truth={"exposure_gain": 1.20},
        graded=False,
        note="Claire, un peu d'écrêtage. Zone grise assumée.",
    ),
    Entry(
        "low-contrast-0.20",
        "hard",
        lambda: tr.contrast_scale(_textured(), 0.20),
        truth={"contrast_factor": 0.20},
        expected=(Warn.IMAGE_LOW_CONTRAST,),
        note="Plate mais CORRECTEMENT EXPOSÉE : sépare « faible contraste » de « sombre ».",
    ),
    Entry(
        "low-contrast-0.55",
        "medium",
        lambda: tr.contrast_scale(_textured(), 0.55),
        truth={"contrast_factor": 0.55},
        graded=False,
        note="Contraste réduit de moitié : encore lisible. La frontière est un choix.",
    ),
    Entry(
        "half-shadow-0.25",
        "hard",
        lambda: tr.half_shadow(_textured(), 0.25),
        truth={"shadow_gain": 0.25, "shadow_extent": 0.5},
        graded=False,
        note=(
            "Moitié de l'image dans l'ombre franche, moitié correcte — une pièce "
            "à une seule fenêtre. Photo exploitable dont la luminance moyenne est "
            "basse. Cas d'observation : aucune mesure d'image seule ne peut "
            "trancher, et le grader serait inventer la réponse."
        ),
    ),
    Entry(
        "flat-black",
        "hard",
        lambda: patterns.flat(2, SIZE),
        expected=(Warn.IMAGE_TOO_DARK, Warn.IMAGE_LOW_CONTRAST, Warn.IMAGE_LOW_TEXTURE),
    ),
    Entry(
        "flat-white",
        "hard",
        lambda: patterns.flat(254, SIZE),
        expected=(
            Warn.IMAGE_OVEREXPOSED,
            Warn.IMAGE_LOW_CONTRAST,
            Warn.IMAGE_LOW_TEXTURE,
            Warn.IMAGE_CLIPPED,
        ),
    ),
)


# --- Distorsion ----------------------------------------------------------
# La vérité terrain est ici exacte : k1 est le coefficient réellement appliqué
# par `transforms.radial_distort`. Elle permet de mesurer non seulement la
# détection, mais le SENS et l'INTENSITÉ estimés.

_DISTORTION: tuple[Entry, ...] = (
    Entry(
        "archi-k1-0",
        "easy",
        _archi,
        truth={"k1": 0.0, "k2": 0.0, "sign": "none"},
        note="Référence rectilinéaire : peu d'arêtes, très longues.",
    ),
    *(
        Entry(
            f"archi-{'barrel' if k1 > 0 else 'pincushion'}-{abs(k1):.2f}".replace(".", ""),
            "medium" if abs(k1) <= 0.15 else "hard",
            _distorted(k1),
            truth={"k1": k1, "k2": 0.0, "sign": "barrel" if k1 > 0 else "pincushion"},
            expected=(Warn.LENS_DISTORTION_SUSPECTED,),
        )
        for k1 in (0.05, 0.15, 0.30, -0.05, -0.15, -0.30)
    ),
    Entry(
        "archi-barrel-002-subthreshold",
        "hard",
        _distorted(0.02),
        truth={"k1": 0.02, "k2": 0.0, "sign": "barrel"},
        graded=False,
        note="Distorsion sous le seuil de détection déclaré. Non gradé : la limite est un choix.",
    ),
    # Les trois entrées suivantes attendent `image_low_contrast`, et ce n'est
    # pas une concession au détecteur : un champ de lignes est un fond
    # uniforme sur 97 % de sa surface. Son contraste relatif mesuré vaut 0,054
    # à 0,060, contre 0,34 pour une scène texturée. L'attente d'origine — rien
    # à signaler — était fausse sur l'image, pas trop sévère pour le code.
    Entry(
        "lines-long",
        "easy",
        lambda: scenes.line_field(SIZE),
        truth={"k1": 0.0, "sign": "none"},
        expected=(Warn.IMAGE_LOW_CONTRAST,),
        note=(
            "Quatre droites traversant tout le cadre : le meilleur support "
            "possible pour la distorsion. Globalement peu contrastée, puisque "
            "presque tout est fond uni — c'est un motif de test, pas une photo."
        ),
    ),
    Entry(
        "lines-long-barrel-020",
        "medium",
        lambda: tr.radial_distort(scenes.line_field(SIZE), 0.20),
        truth={"k1": 0.20, "k2": 0.0, "sign": "barrel"},
        expected=(
            Warn.LENS_DISTORTION_SUSPECTED,
            Warn.IMAGE_LOW_CONTRAST,
            Warn.IMAGE_BLURRY,
        ),
        note=(
            "ARTEFACT DU GÉNÉRATEUR, assumé et étiqueté. Rééchantillonner des "
            "traits de 4 px les adoucit réellement : le rapport de reflou "
            "monte de 0,000 à 0,687, soit autant qu'un flou gaussien de "
            "sigma 3 (0,699). Ce n'est pas une erreur du détecteur mais une "
            "propriété de l'image, donc l'attente la déclare. Testé avec les "
            "trois interpolations d'OpenCV : bilinéaire 0,687, bicubique "
            "0,737, Lanczos 0,727 — aucune ne préserve des traits si fins. "
            "Une pièce réelle n'a pas de traits de 4 px isolés sur fond uni ; "
            "c'est le motif de test qui est extrême, pas la mesure qui est "
            "fautive."
        ),
    ),
    Entry(
        "lines-short",
        "hard",
        lambda: scenes.line_field(SIZE, span=0.15),
        truth={"k1": 0.0, "sign": "none"},
        expected=(Warn.IMAGE_LOW_CONTRAST, Warn.IMAGE_LOW_TEXTURE),
        note=(
            "Lignes courtes : la flèche croît comme le carré de la longueur, "
            "donc rien à conclure sur l'objectif. Support de texture mesuré à "
            "0,0044, sous le plancher de 0,005 — l'image est réellement trop "
            "pauvre pour qu'on juge sa netteté."
        ),
    ),
    Entry(
        "lines-interrupted",
        "hard",
        lambda: scenes.line_field(SIZE, gaps=3),
        truth={"k1": 0.0, "sign": "none"},
        expected=(Warn.IMAGE_LOW_CONTRAST,),
        note=(
            "Chambranles coupés par du mobilier. Le traqueur doit s'arrêter au "
            "trou, pas le franchir en inventant la suite."
        ),
    ),
    Entry(
        "repetitive-checkerboard",
        "hard",
        lambda: patterns.checkerboard(SIZE, square=40, low=70, high=190),
        truth={"k1": 0.0, "sign": "none"},
        note=(
            "NON-RÉGRESSION DU LOT 0. C'est sur cette image que le détecteur "
            "d'origine avait déclaré une distorsion : des dizaines d'arêtes "
            "courtes bombant dans tous les sens, et une mesure d'amplitude qui "
            "ne voit que « ça bombe ». Ne doit JAMAIS produire "
            "lens_distortion_suspected."
        ),
    ),
    Entry(
        "curved-objects",
        "hard",
        lambda: scenes.curved_objects(SIZE),
        truth={"k1": 0.0, "sign": "none"},
        note=(
            "Des courbes que la scène contient VRAIMENT. Un détecteur qui mesure "
            "de la courbure sans vérifier sa cohérence radiale les impute à "
            "l'objectif — faux positif qui ne se corrige pas en durcissant un seuil."
        ),
    ),
    Entry(
        "textured-only",
        "hard",
        _textured,
        truth={"k1": 0.0, "sign": "none"},
        note="Aucune droite. Faux positif de la candidate A (accord de signe 0,57).",
    ),
    Entry(
        "cropped-off-center",
        "hard",
        lambda: tr.crop_offset(tr.radial_distort(_archi(), 0.20), keep=0.6, shift=0.18),
        truth={"k1": 0.20, "k2": 0.0, "sign": "barrel", "optical_center_shifted": 1.0},
        expected=(Warn.LENS_DISTORTION_SUSPECTED,),
        note=(
            "Recadrage décentré : le centre optique n'est plus le centre du "
            "cadre, hypothèse que notre estimation fait. La DÉTECTION reste "
            "attendue — l'image porte bel et bien un k1 de 0,20 — et elle est "
            "donc gradée. C'est l'INTENSITÉ qui se dégrade : mesurée à 0,115 "
            "au lieu de 0,20, soit 43 % d'erreur, avec le bon sens. Le chiffre "
            "apparaît dans le bilan d'objectif sans peser sur la matrice, ce "
            "qui est exactement le bon endroit pour une limite connue."
        ),
    ),
)


# --- Cadre et format -----------------------------------------------------

_FRAMING: tuple[Entry, ...] = (
    Entry(
        "too-small",
        "rejected",
        lambda: scenes.textured((320, 240), seed=SEED % 1000),
        expected=(Warn.IMAGE_TOO_SMALL,),
        note=(
            "Seul avertissement bloquant : la seule entrée réellement refusée. "
            "Sa netteté n'est pas jugée — 320 px est sous la taille de travail "
            "de la mesure, hors de son domaine étalonné."
        ),
        image_format="JPEG",
    ),
    Entry(
        "panorama",
        "hard",
        lambda: scenes.textured((2000, 400), seed=SEED % 1000),
        expected=(Warn.IMAGE_EXTREME_ASPECT_RATIO,),
        image_format="JPEG",
    ),
    Entry(
        "exif-portrait",
        "medium",
        lambda: patterns.checkerboard((960, 720), square=30, low=70, high=190),
        note="Orientation EXIF 6 appliquée à l'encodage : vérifie le redressement.",
        image_format="JPEG-EXIF6",
    ),
)


#: Le corpus complet, dans un ordre stable.
CATALOGUE: tuple[Entry, ...] = (*_SHARPNESS, *_EXPOSURE, *_DISTORTION, *_FRAMING)


def by_id(entry_id: str) -> Entry:
    """Une entrée par son identifiant. Lève si elle n'existe pas."""
    for entry in CATALOGUE:
        if entry.id == entry_id:
            return entry
    raise KeyError(f"Entrée de corpus inconnue : {entry_id}")


def graded_entries() -> tuple[Entry, ...]:
    """Les entrées comptées dans la matrice de confusion."""
    return tuple(entry for entry in CATALOGUE if entry.graded)
