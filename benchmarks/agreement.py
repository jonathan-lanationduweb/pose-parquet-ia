"""Accord entre deux relevés humains de la même photo.

Ce module répond à une question qui précède tout modèle : **de combien deux
personnes compétentes diffèrent-elles sur la même image ?**

La réponse fixe le plafond de ce qu'on peut exiger. Si deux annotateurs
s'accordent à 0,90 d'IoU sur les scènes difficiles, viser 0,95 pour un modèle
n'est pas de l'ambition, c'est une erreur de lecture — on demanderait à une
machine d'être plus d'accord avec un humain que deux humains entre eux.

## Le nom de la mesure dépend de qui a annoté

* deux **personnes différentes** → `inter_annotator_agreement`. Mesure ce que
  le protocole transmet d'une tête à une autre ;
* la **même personne**, deux passes → `intra_annotator_repeatability`. Mesure
  la stabilité d'une main, et c'est une **borne optimiste** : personne ne
  reproduit ses propres hésitations aussi mal que celles d'un autre.

Le module déduit le nom des champs `annotator` et refuse de le choisir à notre
place. Appeler la seconde « accord inter-annotateurs » gonflerait précisément
le chiffre qui servira de plafond.

`independent_pass` est une **déclaration** de l'annotateur, invérifiable par
l'outil. Quand elle est absente sur l'une des passes, le résultat est marqué
comme tel : un accord élevé entre deux passes non indépendantes peut ne
mesurer que la mémoire de celui qui a dessiné.

## Les zones incertaines des deux relevés

L'exclusion porte sur l'**union** des deux masques d'incertitude. Si A déclare
un coin indécidable et B non, ce coin sort de la comparaison : on ne peut pas
reprocher à B de l'avoir tranché puisqu'il n'y avait pas de bonne réponse, ni à
A de s'être abstenu.

`ignored_fraction_delta` mesure le désaccord sur l'incertitude elle-même, qui
est une information à part entière : deux personnes qui ne renoncent pas aux
mêmes endroits ne lisent pas la même image.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.schemas.annotation import BoundaryKind, FloorAnnotation
from benchmarks.segmentation import (
    MaskError,
    MaskMetrics,
    MetricConfig,
    boundary_metrics,
    mask_metrics,
)

#: Version du format de résultat d'accord.
AGREEMENT_SCHEMA = "pose-parquet-ai/annotation-agreement@1"

#: Tolérances de contour comparées par défaut : 0,25 %, 0,5 % et 1 % de la
#: diagonale.
#:
#: Trois valeurs, pas dix. Le but n'est pas de trouver la bonne — aucune donnée
#: ne la justifierait encore — mais de voir **de combien le score bouge** quand
#: on la change. Si l'accord humain passe de 0,4 à 0,9 entre 0,25 % et 1 %, le
#: choix de tolérance compte plus que le choix de modèle, et il faudra le dire.
DEFAULT_TOLERANCES: tuple[float, ...] = (0.0025, 0.005, 0.01)

#: Multiple de la tolérance en deçà duquel un pixel de désaccord est imputé à
#: la frontière plutôt qu'à une région. Deux fois la tolérance : au-delà, le
#: désaccord n'est plus un tremblement de trait mais une surface entière que
#: l'un a incluse et l'autre pas.
_JUNCTION_REACH = 2

#: Nombre de foyers de désaccord détaillés dans le rapport. Assez pour aller
#: regarder, pas assez pour noyer.
_MAX_HOTSPOTS = 5


class AgreementKind:
    """Les deux noms possibles, et jamais un troisième."""

    INTER = "inter_annotator_agreement"
    INTRA = "intra_annotator_repeatability"


@dataclass(frozen=True, slots=True)
class Hotspot:
    """Un foyer de désaccord, localisé pour qu'on puisse aller le voir."""

    pixels: int
    fraction_of_image: float
    #: Boîte englobante en coordonnées normalisées, pour retrouver la zone.
    box: tuple[float, float, float, float]
    category: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "pixels": self.pixels,
            "fractionOfImage": self.fraction_of_image,
            "box": list(self.box),
            "category": self.category,
        }


@dataclass(frozen=True, slots=True)
class DisagreementProfile:
    """Où se concentre le désaccord, par nature.

    Les catégories sont **géométriques** et donc toujours calculables, même
    sans contours annotés. C'est délibéré : demander des contours pour pouvoir
    localiser un désaccord rendrait la mesure indisponible là où elle est la
    plus utile — sur les scènes que l'annotateur a trouvées trop pénibles pour
    tracer les contours.
    """

    total_pixels: int
    #: Le long de la jonction sol/reste : un trait qui tremble.
    along_junction: int
    #: Contre le bord de l'image : désaccord sur ce que le cadre coupe.
    at_frame: int
    #: Une surface entière, loin de toute frontière : un tapis, une ombre, un
    #: reflet que l'un a compté comme sol et l'autre pas. Le désaccord le plus
    #: instructif, parce qu'il porte sur la **définition** et non sur la main.
    interior_region: int
    #: Répartition par nature de contour annotée, quand elle existe.
    by_boundary_kind: dict[str, int] = field(default_factory=dict)
    hotspots: tuple[Hotspot, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "totalPixels": self.total_pixels,
            "alongJunction": self.along_junction,
            "atFrame": self.at_frame,
            "interiorRegion": self.interior_region,
            "byBoundaryKind": dict(self.by_boundary_kind),
            "hotspots": [spot.as_dict() for spot in self.hotspots],
        }


def _dilate(mask: np.ndarray, radius: int) -> np.ndarray:
    if radius <= 0 or not mask.any():
        return mask.copy()
    size = 2 * radius + 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))
    return np.asarray(cv2.dilate(mask.astype(np.uint8), kernel)).astype(bool)


def _inner_boundary(mask: np.ndarray) -> np.ndarray:
    if not mask.any():
        return np.zeros_like(mask)
    eroded = np.asarray(cv2.erode(mask.astype(np.uint8), np.ones((3, 3), np.uint8), borderValue=0))
    boundary: np.ndarray = mask & ~eroded.astype(bool)
    return boundary


def _frame_band(shape: tuple[int, int], margin: int) -> np.ndarray:
    band = np.ones(shape, dtype=bool)
    if margin * 2 < min(shape):
        band[margin : shape[0] - margin, margin : shape[1] - margin] = False
    return band


def _segments_mask(segments: list[Any], kind: BoundaryKind, shape: tuple[int, int]) -> np.ndarray:
    """Rastérise les polylignes d'une nature donnée, pour imputer le désaccord."""
    height, width = shape
    canvas = np.zeros(shape, dtype=np.uint8)
    for segment in segments:
        if segment.kind is not kind:
            continue
        points = np.array(
            [
                [
                    int(round(min(max(point.x, 0.0), 1.0) * (width - 1))),
                    int(round(min(max(point.y, 0.0), 1.0) * (height - 1))),
                ]
                for point in segment.points
            ],
            dtype=np.int32,
        )
        cv2.polylines(canvas, [points], isClosed=False, color=1, thickness=1)
    return canvas.astype(bool)


def disagreement_profile(
    first: np.ndarray,
    second: np.ndarray,
    ignore: np.ndarray | None,
    tolerance_px: int,
    segments: list[Any] | None = None,
) -> DisagreementProfile:
    """Localise le désaccord entre deux masques, par nature."""
    valid = np.ones(first.shape, dtype=bool) if ignore is None else ~ignore
    disagreement = (first ^ second) & valid
    total = int(np.count_nonzero(disagreement))

    if total == 0:
        return DisagreementProfile(0, 0, 0, 0)

    frame = _frame_band(first.shape, tolerance_px) & disagreement
    junction_zone = _dilate(
        _inner_boundary(first) | _inner_boundary(second), tolerance_px * _JUNCTION_REACH
    )
    junction = disagreement & junction_zone & ~frame
    interior = disagreement & ~junction_zone & ~frame

    by_kind: dict[str, int] = {}
    if segments:
        for kind in BoundaryKind:
            reach = _dilate(
                _segments_mask(segments, kind, first.shape), tolerance_px * _JUNCTION_REACH
            )
            count = int(np.count_nonzero(disagreement & reach))
            if count:
                by_kind[kind.value] = count

    return DisagreementProfile(
        total_pixels=total,
        along_junction=int(np.count_nonzero(junction)),
        at_frame=int(np.count_nonzero(frame)),
        interior_region=int(np.count_nonzero(interior)),
        by_boundary_kind=by_kind,
        hotspots=_hotspots(disagreement, junction, frame),
    )


def _hotspots(
    disagreement: np.ndarray, junction: np.ndarray, frame: np.ndarray
) -> tuple[Hotspot, ...]:
    """Les plus gros foyers connexes, avec leur boîte et leur nature dominante."""
    height, width = disagreement.shape
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        disagreement.astype(np.uint8), connectivity=8
    )
    spots: list[Hotspot] = []
    # L'étiquette 0 est le fond.
    order = sorted(range(1, count), key=lambda index: -int(stats[index, cv2.CC_STAT_AREA]))
    for index in order[:_MAX_HOTSPOTS]:
        area = int(stats[index, cv2.CC_STAT_AREA])
        region = labels == index
        if np.count_nonzero(region & frame) > area / 2:
            category = "at_frame"
        elif np.count_nonzero(region & junction) > area / 2:
            category = "along_junction"
        else:
            category = "interior_region"
        left = int(stats[index, cv2.CC_STAT_LEFT])
        top = int(stats[index, cv2.CC_STAT_TOP])
        spots.append(
            Hotspot(
                pixels=area,
                fraction_of_image=round(area / disagreement.size, 6),
                box=(
                    round(left / (width - 1), 4),
                    round(top / (height - 1), 4),
                    round((left + int(stats[index, cv2.CC_STAT_WIDTH])) / (width - 1), 4),
                    round((top + int(stats[index, cv2.CC_STAT_HEIGHT])) / (height - 1), 4),
                ),
                category=category,
            )
        )
    return tuple(spots)


@dataclass(frozen=True, slots=True)
class PairAgreement:
    """Tout ce qu'on sait dire de deux relevés de la même photo."""

    photo_id: str
    kind: str
    first_label: str
    second_label: str
    #: Faux dès qu'une des deux passes ne se déclare pas indépendante.
    both_independent: bool
    area: MaskMetrics
    #: F-mesure de contour par tolérance, en fraction de diagonale.
    boundary_by_tolerance: dict[str, dict[str, float | int | None]]
    ignored_fraction_first: float
    ignored_fraction_second: float
    ignored_fraction_delta: float
    disagreement: DisagreementProfile

    def as_dict(self) -> dict[str, Any]:
        return {
            "photoId": self.photo_id,
            "kind": self.kind,
            "firstLabel": self.first_label,
            "secondLabel": self.second_label,
            "bothIndependent": self.both_independent,
            "area": self.area.as_dict(),
            "boundaryByTolerance": self.boundary_by_tolerance,
            "ignoredFractionFirst": self.ignored_fraction_first,
            "ignoredFractionSecond": self.ignored_fraction_second,
            "ignoredFractionDelta": self.ignored_fraction_delta,
            "disagreement": self.disagreement.as_dict(),
        }


def _label(annotation: FloorAnnotation) -> str:
    return annotation.pass_label or annotation.annotator


def compare(
    first: FloorAnnotation,
    first_floor: np.ndarray,
    first_uncertain: np.ndarray | None,
    second: FloorAnnotation,
    second_floor: np.ndarray,
    second_uncertain: np.ndarray | None,
    tolerances: tuple[float, ...] = DEFAULT_TOLERANCES,
) -> PairAgreement:
    """Compare deux relevés, à plusieurs tolérances de contour.

    :raises MaskError: si les deux relevés ne portent pas sur le même cadre —
        comparer des masques de tailles différentes ne veut rien dire, et
        redimensionner l'un des deux fabriquerait l'accord qu'on mesure.
    """
    if first.photo_id != second.photo_id:
        raise MaskError(f"relevés de photos différentes : {first.photo_id} et {second.photo_id}")
    if first_floor.shape != second_floor.shape:
        raise MaskError(f"cadres différents : {first_floor.shape} et {second_floor.shape}")

    # Union des incertitudes : ce qu'un seul des deux déclare indécidable sort
    # de la comparaison. Voir l'en-tête du module.
    ignore = None
    if first_uncertain is not None or second_uncertain is not None:
        ignore = (
            first_uncertain
            if second_uncertain is None
            else second_uncertain
            if first_uncertain is None
            else first_uncertain | second_uncertain
        )

    total = float(first_floor.size)
    fraction_first = (
        0.0 if first_uncertain is None else int(np.count_nonzero(first_uncertain)) / total
    )
    fraction_second = (
        0.0 if second_uncertain is None else int(np.count_nonzero(second_uncertain)) / total
    )

    by_tolerance: dict[str, dict[str, float | int | None]] = {}
    for fraction in tolerances:
        config = MetricConfig(boundary_tolerance_fraction=fraction)
        metrics = boundary_metrics(second_floor, first_floor, ignore, config)
        by_tolerance[f"{fraction:.4f}"] = {
            "tolerancePx": metrics.tolerance_px,
            "precision": metrics.precision,
            "recall": metrics.recall,
            "f1": metrics.f1,
        }

    middle = MetricConfig(boundary_tolerance_fraction=tolerances[len(tolerances) // 2])
    height, width = first_floor.shape

    return PairAgreement(
        photo_id=first.photo_id,
        kind=(AgreementKind.INTRA if first.annotator == second.annotator else AgreementKind.INTER),
        first_label=_label(first),
        second_label=_label(second),
        both_independent=first.independent_pass and second.independent_pass,
        # L'ordre importe pour précision/rappel : le premier relevé sert de
        # référence, le second de « prédiction ». Sur deux humains, aucun des
        # deux n'est la vérité — c'est pourquoi IoU et Dice, symétriques,
        # sont les chiffres à lire en premier.
        area=mask_metrics(second_floor, first_floor, ignore),
        boundary_by_tolerance=by_tolerance,
        ignored_fraction_first=round(fraction_first, 6),
        ignored_fraction_second=round(fraction_second, 6),
        ignored_fraction_delta=round(abs(fraction_first - fraction_second), 6),
        disagreement=disagreement_profile(
            first_floor,
            second_floor,
            ignore,
            middle.tolerance_px(width, height),
            [*first.boundary, *second.boundary],
        ),
    )


# --- Revue visuelle ------------------------------------------------------

#: Couleurs de la superposition, en BGR (convention OpenCV).
_COLOURS = {
    "agree": (120, 200, 120),
    "first_only": (230, 150, 80),
    "second_only": (80, 80, 230),
    "uncertain": (60, 210, 230),
}


def render_comparison(
    photo: np.ndarray,
    first_floor: np.ndarray,
    second_floor: np.ndarray,
    uncertain: np.ndarray | None,
    path: Path,
) -> None:
    """Écrit un PNG où les deux relevés se superposent à la photo.

    Le but est de **comprendre** un désaccord, pas de le présenter : quatre
    teintes sur la photo assombrie, et rien d'autre. Une légende gravée dans
    l'image gênerait la lecture de la zone qu'elle recouvrirait.

    * vert — les deux annotateurs sont d'accord : c'est du sol ;
    * bleu — seul le premier l'a compté ;
    * rouge — seul le second l'a compté ;
    * jaune — déclaré indécidable par au moins l'un des deux, donc exclu.
    """
    dimmed: np.ndarray = (photo.astype(np.float32) * 0.45).astype(np.uint8)
    canvas = dimmed if dimmed.ndim == 3 else np.asarray(cv2.cvtColor(dimmed, cv2.COLOR_GRAY2BGR))

    layers = [
        (first_floor & second_floor, _COLOURS["agree"]),
        (first_floor & ~second_floor, _COLOURS["first_only"]),
        (second_floor & ~first_floor, _COLOURS["second_only"]),
    ]
    if uncertain is not None:
        layers.append((uncertain, _COLOURS["uncertain"]))

    for mask, colour in layers:
        if not mask.any():
            continue
        tint = np.zeros_like(canvas)
        tint[:] = colour
        canvas = np.where(mask[:, :, None], (canvas * 0.4 + tint * 0.6).astype(np.uint8), canvas)

    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), canvas)


def summarise(pairs: list[PairAgreement]) -> dict[str, Any]:
    """Agrégats sur un ensemble de paires.

    Aucun écart-type, aucun intervalle de confiance : sur une poignée
    d'images, ils donneraient une précision statistique que l'échantillon ne
    porte pas. Moyenne, médiane et minimum suffisent, et le minimum est le plus
    parlant des trois — c'est la scène sur laquelle deux humains se sont le
    moins entendus.
    """
    if not pairs:
        return {"pairs": 0}

    kinds = {pair.kind for pair in pairs}
    ious = [pair.area.iou for pair in pairs if pair.area.iou is not None]

    def aggregate(values: list[float]) -> dict[str, float | int | None]:
        if not values:
            return {"counted": 0, "mean": None, "median": None, "min": None}
        return {
            "counted": len(values),
            "mean": round(float(np.mean(values)), 4),
            "median": round(float(np.median(values)), 4),
            "min": round(float(min(values)), 4),
        }

    tolerance_keys = sorted(pairs[0].boundary_by_tolerance)
    worst = min(pairs, key=lambda pair: pair.area.iou if pair.area.iou is not None else 2.0)
    best = max(pairs, key=lambda pair: pair.area.iou if pair.area.iou is not None else -1.0)

    return {
        "pairs": len(pairs),
        # Si les deux natures se mélangent, on ne publie pas un nom unique :
        # une moyenne d'accord inter et intra ne veut rien dire.
        "kind": kinds.pop() if len(kinds) == 1 else "mixed",
        "allIndependent": all(pair.both_independent for pair in pairs),
        "iou": aggregate(ious),
        "dice": aggregate([p.area.dice for p in pairs if p.area.dice is not None]),
        "precision": aggregate([p.area.precision for p in pairs if p.area.precision is not None]),
        "recall": aggregate([p.area.recall for p in pairs if p.area.recall is not None]),
        "boundaryF1ByTolerance": {
            key: aggregate(
                [
                    value
                    for pair in pairs
                    if (value := pair.boundary_by_tolerance[key]["f1"]) is not None
                ]
            )
            for key in tolerance_keys
        },
        "ignoredFractionDelta": aggregate([pair.ignored_fraction_delta for pair in pairs]),
        "disagreementShare": {
            category: round(
                sum(getattr(pair.disagreement, attribute) for pair in pairs)
                / max(sum(pair.disagreement.total_pixels for pair in pairs), 1),
                4,
            )
            for category, attribute in (
                ("alongJunction", "along_junction"),
                ("atFrame", "at_frame"),
                ("interiorRegion", "interior_region"),
            )
        },
        "leastStableScene": {"photoId": worst.photo_id, "iou": worst.area.iou},
        "mostStableScene": {"photoId": best.photo_id, "iou": best.area.iou},
    }
