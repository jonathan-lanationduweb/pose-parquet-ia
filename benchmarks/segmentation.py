"""Métriques de segmentation du sol. Aucun modèle, seulement la mesure.

Ce module sait comparer deux masques. Il ne sait pas en produire, et c'est
volontaire : le préambule du LOT 2 met en place la balance avant d'y poser
quoi que ce soit.

## Ce qui est mesuré, et pourquoi deux familles

**Les métriques de surface** — IoU, Dice, précision, rappel — répondent à
« quelle part du sol est trouvée ». Elles sont dominées par les grandes zones
plates : sur une photo dont le sol occupe le tiers bas de l'image, se tromper
de dix pixels au pied du mur coûte quelques millièmes d'IoU.

**La métrique de contour** répond à « la frontière est-elle au bon endroit ».
C'est celle qui compte pour ce projet. Un masque de sol dont la jonction
mur/sol est décalée de dix pixels décale tout le plan de perspective qu'on en
déduira, et donc toutes les lames posées. Un IoU de 0,95 peut cacher ce
décalage ; une F-mesure de contour, non.

Les deux sont publiées, jamais résumées en un seul chiffre : elles ne mesurent
pas la même faute.

## Les pixels qu'on refuse de juger

Un masque `uncertain` marque ce qu'une personne n'a pas su trancher — coin
caché, ombre dure, meuble collé au mur. Ces pixels sont **exclus** de toutes
les métriques. Les forcer à 0 ou à 1 ferait payer à un modèle une frontière
que personne ne sait tracer, et le classement obtenu mesurerait alors la
chance plutôt que la justesse.

`ignored_fraction` est publiée avec chaque résultat. Un IoU calculé sur 60 %
d'une image ne se lit pas comme un IoU calculé sur 99 % de la même image, et
le rapport doit permettre de le voir.

## Le bord du cadre n'est pas une frontière

Quand le sol est coupé par le bas de l'image, le masque y a un bord — mais la
scène, non. Ce bord est trivialement partagé par toute prédiction raisonnable,
et le compter **gonfle** la F-mesure de contour sans rien mesurer. Une bande de
la largeur de la tolérance est donc écartée le long du cadre.

Conséquence à connaître : un masque couvrant toute l'image n'a plus aucun
contour évaluable, et sa précision de contour devient indéfinie plutôt que
parfaite. C'est le bon comportement — un tel masque ne propose aucune
frontière.
"""

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image

from app.schemas.annotation import MASK_FALSE, MASK_TRUE

#: Version du format de résultat métrique.
METRICS_SCHEMA = "pose-parquet-ai/segmentation-metrics@1"


class MaskError(Exception):
    """Un masque n'est pas exploitable. Le dire, jamais le rattraper."""


@dataclass(frozen=True, slots=True)
class MetricConfig:
    """Réglages des métriques, embarqués dans chaque rapport.

    Volontairement **hors de `app/core/config.py`** : ces valeurs ne changent
    rien à ce que le service répond. Les ranger dans les réglages du pipeline
    mêlerait la configuration de la balance à celle de ce qu'on pèse, et un
    `Settings` qui grossit de tout ce qui ressemble à un seuil finit par ne
    plus documenter rien.
    """

    #: Tolérance de contour, en fraction de la **diagonale** de l'image.
    #: Exprimée relativement pour qu'une même erreur visuelle donne le même
    #: score sur une photo de 1600 px et sur la même en 3200 px. La diagonale
    #: plutôt que la largeur : elle ne change pas de sens en portrait.
    #:
    #: 0,005 vaut environ 10 px sur 1600 × 1067. C'est un ordre de grandeur
    #: **provisoire** : aucune donnée réelle ne l'a encore justifié, et le
    #: fixer comme seuil produit serait exactement l'erreur que le LOT 1 a
    #: appris à éviter.
    boundary_tolerance_fraction: float = 0.005

    #: Écarter du calcul de contour une bande le long du cadre, large de la
    #: tolérance. Voir l'en-tête du module.
    exclude_frame_border: bool = True

    def tolerance_px(self, width: int, height: int) -> int:
        """Tolérance en pixels pour une image donnée. Au moins 1."""
        diagonal = float(np.hypot(width, height))
        return max(1, int(round(self.boundary_tolerance_fraction * diagonal)))

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


# --- Lecture des masques -------------------------------------------------


def load_mask(path: Path, width: int, height: int) -> np.ndarray:
    """Charge un masque PNG binaire et vérifie qu'il est exploitable.

    Trois refus, et aucun rattrapage :

    * **dimensions différentes de l'image** — on ne redimensionne pas. Un
      masque interpolé a des frontières fausses, et une frontière fausse est
      précisément ce que ce module doit mesurer ;
    * **valeurs intermédiaires** — un pixel à 127 est la signature d'un
      redimensionnement ou d'un enregistrement en JPEG. Le corpus n'accepte
      que 0 et 255 ;
    * **fichier absent**.

    :returns: tableau booléen `(height, width)`.
    :raises MaskError: dans les trois cas ci-dessus.
    """
    if not path.is_file():
        raise MaskError(f"masque absent : {path.name}")

    with Image.open(path) as image:
        if image.format != "PNG":
            raise MaskError(f"{path.name} : format {image.format}, or un masque doit être en PNG")
        array = np.asarray(image.convert("L"))

    if array.shape != (height, width):
        raise MaskError(
            f"{path.name} : dimensions {array.shape[1]}×{array.shape[0]}, "
            f"attendu {width}×{height} — aucun redimensionnement n'est appliqué"
        )

    unexpected = np.setdiff1d(np.unique(array), np.array([MASK_FALSE, MASK_TRUE]))
    if unexpected.size:
        raise MaskError(
            f"{path.name} : valeurs interdites {unexpected[:5].tolist()} — "
            f"un masque ne contient que {MASK_FALSE} et {MASK_TRUE}"
        )
    binary: np.ndarray = array == MASK_TRUE
    return binary


def save_mask(mask: np.ndarray, path: Path) -> None:
    """Écrit un masque booléen en PNG binaire, sans perte."""
    path.parent.mkdir(parents=True, exist_ok=True)
    as_bytes = np.where(mask, MASK_TRUE, MASK_FALSE).astype(np.uint8)
    Image.fromarray(as_bytes, mode="L").save(path, format="PNG", optimize=True)


# --- Métriques de surface ------------------------------------------------


@dataclass(frozen=True, slots=True)
class MaskMetrics:
    """Recouvrement entre un masque prédit et le masque humain.

    `None` plutôt que `1.0` quand il n'y a rien à mesurer : sur une scène dont
    le sol visible est vide, une prédiction vide n'est pas une segmentation
    parfaite, c'est une mesure impossible. Publier 1,0 ferait grimper la
    moyenne d'un corpus à chaque scène sans sol.
    """

    true_positive: int
    false_positive: int
    false_negative: int
    true_negative: int
    evaluated_pixels: int
    ignored_pixels: int
    ignored_fraction: float
    iou: float | None
    dice: float | None
    precision: float | None
    recall: float | None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _valid_region(shape: tuple[int, int], ignore: np.ndarray | None) -> np.ndarray:
    if ignore is None:
        return np.ones(shape, dtype=bool)
    if ignore.shape != shape:
        raise MaskError(f"masque d'incertitude {ignore.shape} incompatible avec l'image {shape}")
    return ~ignore


def mask_metrics(
    prediction: np.ndarray, truth: np.ndarray, ignore: np.ndarray | None = None
) -> MaskMetrics:
    """IoU, Dice, précision et rappel, hors zones incertaines."""
    if prediction.shape != truth.shape:
        raise MaskError(f"prédiction {prediction.shape} et vérité {truth.shape} incompatibles")

    valid = _valid_region(truth.shape, ignore)
    predicted = prediction & valid
    actual = truth & valid

    true_positive = int(np.count_nonzero(predicted & actual))
    false_positive = int(np.count_nonzero(predicted & ~actual & valid))
    false_negative = int(np.count_nonzero(~predicted & actual))
    true_negative = int(np.count_nonzero(~predicted & ~actual & valid))

    evaluated = int(np.count_nonzero(valid))
    ignored = int(truth.size - evaluated)
    union = true_positive + false_positive + false_negative

    return MaskMetrics(
        true_positive=true_positive,
        false_positive=false_positive,
        false_negative=false_negative,
        true_negative=true_negative,
        evaluated_pixels=evaluated,
        ignored_pixels=ignored,
        ignored_fraction=round(ignored / truth.size, 6),
        iou=None if union == 0 else round(true_positive / union, 6),
        dice=None if union == 0 else round(2 * true_positive / (union + true_positive), 6),
        precision=(
            None
            if true_positive + false_positive == 0
            else round(true_positive / (true_positive + false_positive), 6)
        ),
        recall=(
            None
            if true_positive + false_negative == 0
            else round(true_positive / (true_positive + false_negative), 6)
        ),
    )


# --- Métrique de contour -------------------------------------------------


@dataclass(frozen=True, slots=True)
class BoundaryMetrics:
    """Qualité de la frontière, à une tolérance donnée.

    F-mesure de contour au sens de Perazzi et al. (DAVIS, 2016) : un pixel de
    frontière compte comme juste s'il existe un pixel de frontière de l'autre
    masque à moins de `tolerance_px`.
    """

    tolerance_px: int
    tolerance_fraction: float
    predicted_boundary_pixels: int
    truth_boundary_pixels: int
    precision: float | None
    recall: float | None
    f1: float | None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _inner_boundary(mask: np.ndarray) -> np.ndarray:
    """Pixels du masque qui touchent son extérieur.

    Frontière **intérieure** et non centrée : elle appartient au masque, donc
    la comparer à celle de l'autre masque ne demande aucune convention
    supplémentaire sur qui possède le pixel de bord.
    """
    if not mask.any():
        return np.zeros_like(mask)
    kernel = np.ones((3, 3), dtype=np.uint8)
    eroded = np.asarray(cv2.erode(mask.astype(np.uint8), kernel, borderValue=0))
    boundary: np.ndarray = mask & ~eroded.astype(bool)
    return boundary


def _dilate(mask: np.ndarray, radius: int) -> np.ndarray:
    """Épaissit un masque d'un disque de rayon `radius`."""
    if not mask.any():
        return np.zeros_like(mask)
    size = 2 * radius + 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))
    dilated = np.asarray(cv2.dilate(mask.astype(np.uint8), kernel))
    return dilated.astype(bool)


def _interior(shape: tuple[int, int], margin: int) -> np.ndarray:
    """Vrai partout sauf dans une bande de `margin` pixels le long du cadre."""
    interior = np.zeros(shape, dtype=bool)
    if margin * 2 >= min(shape):
        return interior
    interior[margin : shape[0] - margin, margin : shape[1] - margin] = True
    return interior


def boundary_metrics(
    prediction: np.ndarray,
    truth: np.ndarray,
    ignore: np.ndarray | None = None,
    config: MetricConfig | None = None,
) -> BoundaryMetrics:
    """F-mesure de contour, hors zones incertaines et hors bord de cadre.

    Un point de méthode sur les zones incertaines. Les frontières **évaluées**
    en sont exclues — on ne juge pas un pixel que personne n'a su trancher.
    Mais les frontières **cibles**, celles qu'on épaissit pour chercher une
    correspondance, sont conservées entières. Sans cela, une frontière humaine
    passant dans une zone incertaine disparaîtrait de la cible, et la
    prédiction qui la longe correctement juste à côté serait comptée fausse.
    """
    if prediction.shape != truth.shape:
        raise MaskError(f"prédiction {prediction.shape} et vérité {truth.shape} incompatibles")

    settings = config or MetricConfig()
    height, width = truth.shape
    tolerance = settings.tolerance_px(width, height)

    predicted_boundary = _inner_boundary(prediction)
    truth_boundary = _inner_boundary(truth)

    region = _valid_region(truth.shape, ignore)
    if settings.exclude_frame_border:
        region = region & _interior(truth.shape, tolerance)

    predicted_eval = predicted_boundary & region
    truth_eval = truth_boundary & region

    predicted_count = int(np.count_nonzero(predicted_eval))
    truth_count = int(np.count_nonzero(truth_eval))

    precision = (
        None
        if predicted_count == 0
        else round(
            int(np.count_nonzero(predicted_eval & _dilate(truth_boundary, tolerance)))
            / predicted_count,
            6,
        )
    )
    recall = (
        None
        if truth_count == 0
        else round(
            int(np.count_nonzero(truth_eval & _dilate(predicted_boundary, tolerance)))
            / truth_count,
            6,
        )
    )

    if precision is None or recall is None or precision + recall == 0.0:
        f1 = None if precision is None or recall is None else 0.0
    else:
        f1 = round(2 * precision * recall / (precision + recall), 6)

    return BoundaryMetrics(
        tolerance_px=tolerance,
        tolerance_fraction=settings.boundary_tolerance_fraction,
        predicted_boundary_pixels=predicted_count,
        truth_boundary_pixels=truth_count,
        precision=precision,
        recall=recall,
        f1=f1,
    )


# --- Assemblage ----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SegmentationMetrics:
    """Tout ce qu'on sait dire de la comparaison d'un masque à sa référence."""

    area: MaskMetrics
    boundary: BoundaryMetrics
    config: MetricConfig = field(default_factory=MetricConfig)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": METRICS_SCHEMA,
            "area": self.area.as_dict(),
            "boundary": self.boundary.as_dict(),
            "config": self.config.as_dict(),
        }


def evaluate(
    prediction: np.ndarray,
    truth: np.ndarray,
    ignore: np.ndarray | None = None,
    config: MetricConfig | None = None,
) -> SegmentationMetrics:
    """Compare un masque prédit à un masque humain, surface et contour."""
    settings = config or MetricConfig()
    return SegmentationMetrics(
        area=mask_metrics(prediction, truth, ignore),
        boundary=boundary_metrics(prediction, truth, ignore, settings),
        config=settings,
    )
