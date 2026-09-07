"""Dégradations contrôlées, appliquées à une image de départ nette.

Toute la valeur de ce module tient dans un mot : **connue**. On part d'une
image saine, on lui applique une transformation dont on connaît le paramètre
exact, et ce paramètre devient la vérité terrain. C'est la seule vérité
terrain que ce projet s'autorise à produire lui-même — parce qu'elle n'est pas
estimée, elle est *imposée*.

Le corollaire, écrit ici parce que c'est ici qu'on serait tenté de l'oublier :
rien de ce que produit ce module ne remplace une photo réelle. Une distorsion
polynomiale parfaite, sans vignettage, sans aberration chromatique et sans
bruit de capteur, est un cas d'école. Elle sert à savoir si un détecteur est
capable de voir ce qui est indiscutablement là — pas à prouver qu'il marchera
sur un téléphone.

Déterminisme
------------
Toutes les fonctions sont pures et déterministes. Le bruit prend une graine
explicite, sans valeur par défaut aléatoire : deux exécutions du corpus, à
n'importe quelle date, donnent les mêmes octets.
"""

from dataclasses import dataclass
from typing import cast

import cv2
import numpy as np

#: Modèle de distorsion radiale employé, dans le sens de l'**échantillonnage** :
#: pour un pixel de destination à la distance normalisée `r` du centre, on va
#: chercher la source à `r · (1 + k1·r² + k2·r⁴)`.
#:
#: Conséquence des signes, vérifiée par un test et non par raisonnement :
#:   k1 > 0  →  barillet   (les droites bombent en s'écartant du centre)
#:   k1 < 0  →  coussinet  (les droites se creusent vers le centre)
#:
#: `r` est normalisé par la **demi-diagonale**, donc r = 1 au coin. Un k1 de
#: 0,05 est une distorsion faible, 0,3 une distorsion franche d'ultra
#: grand-angle. Sans cette normalisation, la même valeur de k1 n'aurait pas le
#: même effet sur deux images de formats différents.
DISTORTION_MODEL = (
    "échantillonnage : r_src = r_dst · (1 + k1·r_dst² + k2·r_dst⁴), "
    "r normalisé par la demi-diagonale"
)


@dataclass(frozen=True, slots=True)
class LensGroundTruth:
    """Ce qu'on a réellement imposé à l'image.

    `sign` est redondant avec `k1` et c'est voulu : un rapport de benchmark se
    lit, et « barrel » se lit mieux que « k1 = 0.18 ».
    """

    k1: float
    k2: float = 0.0

    @property
    def sign(self) -> str:
        if self.k1 > 0.0:
            return "barrel"
        if self.k1 < 0.0:
            return "pincushion"
        return "none"

    @property
    def distorted(self) -> bool:
        return self.k1 != 0.0 or self.k2 != 0.0


def _radial_maps(shape: tuple[int, int], k1: float, k2: float) -> tuple[np.ndarray, np.ndarray]:
    """Cartes de rééchantillonnage pour une distorsion radiale."""
    height, width = shape
    center_x = (width - 1) / 2.0
    center_y = (height - 1) / 2.0
    half_diagonal = float(np.hypot(center_x, center_y))

    ys, xs = np.mgrid[0:height, 0:width].astype(np.float32)
    dx = (xs - center_x) / half_diagonal
    dy = (ys - center_y) / half_diagonal
    r2 = dx * dx + dy * dy
    factor = 1.0 + k1 * r2 + k2 * r2 * r2

    map_x = (center_x + dx * factor * half_diagonal).astype(np.float32)
    map_y = (center_y + dy * factor * half_diagonal).astype(np.float32)
    return map_x, map_y


def radial_distort(image: np.ndarray, k1: float, k2: float = 0.0) -> np.ndarray:
    """Applique une distorsion radiale de coefficients connus.

    Les bords sont prolongés par réplication plutôt que remplis d'une couleur.
    Un remplissage constant créerait aux coins une frontière franche, droite,
    et absente de l'original : le détecteur y verrait des arêtes que la scène
    ne contient pas, et l'on mesurerait l'artefact du générateur.
    """
    map_x, map_y = _radial_maps(image.shape[:2], k1, k2)
    return cast(
        np.ndarray,
        cv2.remap(
            image, map_x, map_y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE
        ),
    )


def gaussian_blur(image: np.ndarray, sigma: float) -> np.ndarray:
    """Flou gaussien isotrope d'écart-type connu, en pixels."""
    if sigma <= 0.0:
        return image.copy()
    # Noyau déduit de sigma par OpenCV (ksize=0) : la relation reste la même
    # d'une version à l'autre, et sigma est le paramètre qu'on veut retrouver.
    return cast(np.ndarray, cv2.GaussianBlur(image, (0, 0), sigmaX=sigma, sigmaY=sigma))


def motion_blur(image: np.ndarray, length: int, angle_deg: float) -> np.ndarray:
    """Flou de bougé : moyenne le long d'un segment de longueur et d'angle connus.

    Il ne se confond pas avec un flou gaussien : il est **anisotrope**. Une
    arête parallèle au mouvement reste nette, une arête perpendiculaire
    disparaît. C'est le cas qui met en défaut toute mesure de netteté qui
    résume l'image en un seul nombre isotrope.
    """
    if length <= 1:
        return image.copy()
    line = np.zeros((length, length), dtype=np.float32)
    line[length // 2, :] = 1.0
    rotation = cv2.getRotationMatrix2D(((length - 1) / 2.0, (length - 1) / 2.0), angle_deg, 1.0)
    kernel = np.asarray(cv2.warpAffine(line, rotation, (length, length)), dtype=np.float32)
    total = float(kernel.sum())
    if total <= 0.0:
        return image.copy()
    return cast(np.ndarray, cv2.filter2D(image, -1, kernel / total))


def exposure_gain(image: np.ndarray, gain: float) -> np.ndarray:
    """Multiplie la luminance par un gain connu, avec écrêtage.

    L'écrêtage est le point : un gain de 1,8 ne se contente pas d'éclaircir,
    il **détruit** l'information des hautes lumières. Une surexposition
    réversible et une surexposition écrêtée n'appellent pas la même réponse, et
    c'est ce que `clipped_high_ratio` doit savoir distinguer.
    """
    gained: np.ndarray = np.clip(image.astype(np.float32) * gain, 0.0, 255.0).astype(np.uint8)
    return gained


def contrast_scale(image: np.ndarray, factor: float, pivot: float = 128.0) -> np.ndarray:
    """Comprime ou étire le contraste autour d'un **pivot** fixe.

    Un facteur de 0,25 donne une image plate mais **correctement exposée** :
    c'est le cas qui sépare « faible contraste » de « sous-exposée », deux
    défauts que la seule luminance moyenne confond.

    C'est le pivot qui est conservé, pas la moyenne : sur une image dont la
    moyenne n'est pas déjà le pivot, comprimer le contraste la rapproche du
    pivot. L'écrire ici parce que « sans déplacer la moyenne » serait faux, et
    qu'un corpus qui se trompe sur ce qu'il impose n'impose plus rien.
    """
    scaled = (image.astype(np.float32) - pivot) * factor + pivot
    clipped: np.ndarray = np.clip(scaled, 0.0, 255.0).astype(np.uint8)
    return clipped


def half_shadow(image: np.ndarray, gain: float) -> np.ndarray:
    """Assombrit la moitié gauche de l'image, en laissant l'autre intacte.

    Le cas d'une pièce éclairée par une seule fenêtre : une zone franchement
    sombre, et une image malgré tout exploitable. Il n'est pas gradé, et c'est
    l'essentiel de son intérêt — la luminance moyenne y est basse sans que la
    photo soit sous-exposée, et rien dans l'image seule ne permet de trancher.
    Le corpus l'enregistre pour qu'on **observe** ce que les métriques en
    disent, pas pour leur donner raison.
    """
    darkened = image.copy()
    half = image.shape[1] // 2
    darkened[:, :half] = exposure_gain(image[:, :half], gain)
    return darkened


def crop_offset(image: np.ndarray, keep: float, shift: float) -> np.ndarray:
    """Recadre hors du centre, en gardant `keep` de chaque côté.

    Décale le centre de l'image par rapport au **centre optique**, qui est
    resté là où l'objectif l'a mis. Toute estimation de distorsion qui suppose
    le centre optique au milieu du cadre — la nôtre le suppose — devient
    biaisée. C'est une limite assumée du lot, et le corpus doit la contenir
    pour qu'elle soit mesurée plutôt que découverte plus tard.
    """
    height, width = image.shape[:2]
    new_w, new_h = int(width * keep), int(height * keep)
    left = int(np.clip((width - new_w) / 2.0 + shift * width, 0, width - new_w))
    top = int(np.clip((height - new_h) / 2.0 + shift * height, 0, height - new_h))
    return image[top : top + new_h, left : left + new_w].copy()


def add_noise(image: np.ndarray, sigma: float, seed: int) -> np.ndarray:
    """Bruit gaussien de graine explicite.

    Le bruit est l'ennemi déclaré de toute mesure de netteté fondée sur la
    dérivée : il fabrique du gradient partout et fait *monter* la variance du
    Laplacien. Une image floue et bruitée peut donc paraître plus nette qu'une
    image nette et propre.
    """
    rng = np.random.default_rng(seed)
    noisy = image.astype(np.float32) + rng.normal(0.0, sigma, image.shape).astype(np.float32)
    return np.clip(noisy, 0.0, 255.0).astype(np.uint8)
