"""Suivi d'arêtes presque droites, et mesure de leur courbure signée.

Extrait de `lens_analysis.py` au LOT 1 pour deux raisons mesurables : les
arêtes **horizontales** comptent autant que les verticales, et le **signe** de
la courbure est l'information qui manquait pour distinguer une distorsion
d'objectif d'un accident de texture.

## Pourquoi les deux orientations

Une distorsion radiale courbe les droites d'autant plus qu'elles passent loin
du centre optique. Pour une verticale, cet éloignement se lit horizontalement ;
pour une horizontale, verticalement. N'observer que les verticales revient donc
à n'échantillonner qu'un axe : on divise par deux le support disponible, et on
devient aveugle aux photos dont les seules longues droites sont les plinthes et
les corniches — c'est-à-dire beaucoup de photos d'intérieur.

Le suivi est écrit une fois et appliqué à l'image **transposée** pour les
horizontales. Transposer est exact et sans coût : aucune interpolation, aucun
rééchantillonnage, et donc aucune courbure introduite par le traitement.

## Pourquoi le signe

Le LOT 0 mesurait `|a| · L² / 4`, une flèche **non signée**. C'est ce qui l'a
laissé déclarer une distorsion sur un damier : des dizaines d'arêtes y bombent
un peu, dans tous les sens, et une mesure d'amplitude ne voit que « ça bombe ».

Une distorsion radiale, elle, est **cohérente** : toutes les droites s'écartent
du centre (barillet) ou s'en rapprochent (coussinet), sans exception. En
gardant le signe de la courbure *relativement au centre de l'image*, la
cohérence devient mesurable — et c'est elle, pas l'amplitude, qui sépare un
objectif fautif d'un carrelage.

`radial_bulge_px` porte cette convention : **positif = l'arête bombe en
s'écartant du centre = barillet**. Négatif = coussinet.
"""

from dataclasses import dataclass
from typing import Literal

import cv2
import numpy as np

from app.core.config import get_settings

Orientation = Literal["vertical", "horizontal"]

#: Demi-largeur de la fenêtre de recherche, en pixels, à chaque ligne. Assez
#: large pour suivre une arête inclinée, assez étroite pour ne pas sauter sur
#: l'arête voisine.
_SEARCH_HALF_WINDOW = 6

#: Bande centrale exclue, en fraction de la demi-largeur : une arête plus
#: proche du centre que cela ne prouve rien sur la distorsion, puisque la
#: distorsion radiale ne déplace rien sur l'axe optique.
MIN_CENTER_OFFSET = 0.25

#: Marge ignorée aux deux extrémités du balayage, en fraction. Les bords
#: d'image portent souvent du vignettage et des artefacts de compression.
_SCAN_MARGIN = 0.08

#: Écart minimal entre deux amorces, en fraction de la largeur balayée.
_MIN_SEED_GAP = 0.04

#: Nombre d'amorces examinées au plus, par orientation.
_MAX_SEEDS = 12

#: Contraste minimal d'un tracé : médiane de |gradient| le long de l'arête, en
#: unités de luma par pixel.
#:
#: Sans ce garde-fou, le traqueur suit les **marches de quantification** d'un
#: dégradé lisse : sur un mur uni parfaitement vide, il rapportait onze arêtes
#: « utilisables ». Le verdict restait juste — ces fausses arêtes ne bombent
#: pas — mais le support était faux, et le support est précisément ce sur quoi
#: reposera la confiance. Une mesure qui dit « onze arêtes » là où il n'y a
#: rien à voir est pire qu'inutile.
#:
#: Mesuré : une marche de quantification 8 bits répond vers 0,016 ; une arête
#: franche vers 1,4 ; la même arête floutée à sigma 6 tient encore 0,09.
_MIN_TRACK_CONTRAST = 0.05


@dataclass(frozen=True, slots=True)
class Track:
    """Une arête suivie, et tout ce qui permet de juger si elle prouve quelque chose."""

    orientation: Orientation
    #: Points du tracé en coordonnées image, tableau (N, 2) de (x, y).
    points: np.ndarray
    #: Flèche non signée, en pixels. Conservée telle que le LOT 0 la définissait,
    #: pour que la candidate A reste rejouable à l'identique.
    sagitta_px: float
    #: Flèche **signée** relativement au centre. Positif = barillet.
    radial_bulge_px: float
    #: Écart-type d'ajustement de la parabole. Sans lui, la flèche ne veut rien
    #: dire : c'est l'indicateur qui dit si la parabole *décrit* le tracé.
    fit_rms_px: float
    #: Part de l'axe balayé que le tracé couvre. La flèche croît comme le carré
    #: de la longueur : un tracé court ne prouve rien.
    span_ratio: float
    #: Éloignement du centre optique sur l'axe transverse (0 = sur l'axe).
    center_offset: float
    #: Médiane de |gradient| le long du tracé. Dit si l'arête existe vraiment,
    #: par opposition à une marche de quantification dans un dégradé.
    contrast: float
    #: Retenu comme preuve : contrasté, bien ajusté, assez long, assez loin du
    #: centre.
    usable: bool

    @property
    def length_px(self) -> float:
        """Longueur du tracé le long de l'axe balayé."""
        return float(self.points.shape[0])


def _scan_span(length: int) -> tuple[int, int]:
    """Bandes exclues aux deux extrémités du balayage."""
    return int(length * _SCAN_MARGIN), int(length * (1.0 - _SCAN_MARGIN))


def gradient_across(image: np.ndarray) -> np.ndarray:
    """Gradient **signé** perpendiculaire au balayage, légèrement lissé.

    Le lissage préalable est indispensable : sur une photo compressée, le bruit
    de bloc produit des maxima de gradient d'un pixel de large qui attirent le
    traqueur hors de l'arête. Le signe, lui, est ce qui permet de ne pas sauter
    sur l'arête opposée d'un même jambage (voir `_polarity`).
    """
    smoothed = cv2.GaussianBlur(image, (3, 3), 0)
    return cv2.Sobel(smoothed, cv2.CV_32F, 1, 0, ksize=3)


def _seed_positions(grad: np.ndarray) -> list[int]:
    """Positions transverses les plus susceptibles de porter une longue arête.

    L'énergie de gradient d'une colonne entière favorise naturellement les
    arêtes qui traversent l'image — jambages, angles de murs — sur les
    accidents locaux. Elle est ensuite pondérée par l'éloignement du centre.
    """
    rows, columns = grad.shape
    start, stop = _scan_span(rows)
    # Magnitude ici : pour choisir une colonne, seule compte la quantité de
    # contraste qu'elle porte, pas le sens des transitions.
    energy = np.abs(grad[start:stop, :]).sum(axis=0)

    center = (columns - 1) / 2.0
    offset = np.abs(np.arange(columns) - center) / max(center, 1.0)
    scored = energy * offset

    gap = max(1, int(columns * _MIN_SEED_GAP))
    seeds: list[int] = []
    for column in np.argsort(scored)[::-1]:
        position = int(column)
        if offset[position] < MIN_CENTER_OFFSET:
            continue
        if any(abs(position - kept) < gap for kept in seeds):
            continue
        seeds.append(position)
        if len(seeds) >= _MAX_SEEDS:
            break
    return seeds


def _subpixel_offset(left: float, peak: float, right: float) -> float:
    """Sommet de la parabole passant par trois échantillons voisins.

    Sans cette interpolation la position de l'arête est quantifiée au pixel, et
    le bruit de quantification (± 0,5 px) noie une flèche de 1 px.
    """
    denominator = left - 2.0 * peak + right
    if denominator == 0.0:
        return 0.0
    return float(np.clip((left - right) / (2.0 * denominator), -1.0, 1.0))


def _polarity(grad: np.ndarray, seed: int) -> float:
    """Sens de la transition portée par la position d'amorce : +1 ou −1.

    Un jambage a deux arêtes, à quelques pixels l'une de l'autre, et elles sont
    de sens opposés : clair → sombre d'un côté, sombre → clair de l'autre. Un
    traqueur qui ne regarde que la magnitude passe de l'une à l'autre dès que
    le contraste varie, et mesure alors la largeur du jambage, pas sa courbure.

    Le sens est lu **là où la transition est la plus franche**, pas en moyenne :
    une arête qui dérive fait entrer les deux côtés du jambage dans la même
    colonne, et leur somme s'annule au lieu de trancher.
    """
    start, stop = _scan_span(grad.shape[0])
    column = grad[start:stop, seed]
    strongest = int(np.argmax(np.abs(column)))
    return -1.0 if float(column[strongest]) < 0.0 else 1.0


def _step_once(grad: np.ndarray, index: int, current: float, polarity: float) -> float | None:
    """Position transverse de l'arête à la ligne suivante, ou `None` si perdue.

    Perdue veut dire : le maximum de gradient de même sens a atteint le bord de
    la fenêtre de recherche. Continuer alors reviendrait à mesurer sa propre
    dérive — l'erreur exacte qui avait fait rejeter une scène côté front.
    """
    columns = grad.shape[1]
    low = max(0, int(round(current)) - _SEARCH_HALF_WINDOW)
    high = min(columns, int(round(current)) + _SEARCH_HALF_WINDOW + 1)
    window = grad[index, low:high] * polarity
    if window.size < 3:
        return None
    local = int(np.argmax(window))
    if local == 0 or local == window.size - 1:
        return None
    return (
        low
        + local
        + _subpixel_offset(float(window[local - 1]), float(window[local]), float(window[local + 1]))
    )


def _follow(grad: np.ndarray, seed: int) -> tuple[np.ndarray, np.ndarray] | None:
    """Suit une arête par maximum de gradient de même sens, **dans les deux sens**.

    Le point de départ est la ligne où l'amorce porte la transition la plus
    franche, et non le haut du cadre. La distinction est décisive : une amorce
    est choisie sur l'énergie de gradient de toute sa colonne, ce qui, pour une
    arête **courbée**, désigne l'endroit où elle traverse cette colonne — donc
    son milieu. Partir du haut du cadre revenait à partir à côté de l'arête, à
    ne trouver que du bruit dans la fenêtre, et à abandonner dès la première
    ligne. C'est ce qui rendait le détecteur aveugle aux distorsions fortes,
    lesquelles écartent l'arête de plusieurs dizaines de pixels : il ne
    répondait pas « distordu », il répondait « rien à mesurer ».

    Partir du plus franc et s'étendre des deux côtés sert aussi les **arêtes
    interrompues** : un chambranle coupé par un meuble donne un tracé qui
    s'arrête au meuble, pas un tracé qui aurait inventé le morceau manquant.

    :returns: les index de balayage et les positions transverses sous-pixel, ou
        `None` si le tracé est trop court pour valoir quelque chose.
    """
    rows = grad.shape[0]
    start, stop = _scan_span(rows)
    polarity = _polarity(grad, seed)

    column = grad[start:stop, seed] * polarity
    origin = start + int(np.argmax(column))

    # Vers le bas depuis l'origine, puis vers le haut. Les deux moitiés
    # partagent exactement la même mécanique de pas.
    forward: list[tuple[int, float]] = []
    current = float(seed)
    for index in range(origin + 1, stop):
        nxt = _step_once(grad, index, current, polarity)
        if nxt is None:
            break
        current = nxt
        forward.append((index, current))

    backward: list[tuple[int, float]] = []
    current = float(seed)
    for index in range(origin - 1, start - 1, -1):
        nxt = _step_once(grad, index, current, polarity)
        if nxt is None:
            break
        current = nxt
        backward.append((index, current))

    walked = [*reversed(backward), (origin, float(seed)), *forward]
    if len(walked) < get_settings().lens_min_track_points:
        return None

    scan = np.asarray([index for index, _ in walked], dtype=np.float64)
    across = np.asarray([position for _, position in walked], dtype=np.float64)
    return scan, across


def _build_track(
    scan: np.ndarray,
    across: np.ndarray,
    contrast: float,
    orientation: Orientation,
    shape: tuple[int, int],
) -> Track:
    """Ajuste une parabole au tracé et en tire flèche, signe et support.

    La flèche d'une parabole sur une base `L` vaut `|a| · L² / 4` : c'est
    l'écart de la courbe à sa corde, en son milieu. Le signe de cet écart est
    `-a`, et c'est lui qui, rapporté au centre de l'image, dit barillet ou
    coussinet.
    """
    height, width = shape
    scan_length, across_length = (height, width) if orientation == "vertical" else (width, height)
    across_center = (across_length - 1) / 2.0

    coefficients = np.polyfit(scan, across, 2)
    residuals = across - np.polyval(coefficients, scan)
    base = float(scan[-1] - scan[0])

    # Écart signé de la courbe à sa corde, au milieu.
    bulge = -float(coefficients[0]) * base * base / 4.0
    # Rapporté au centre : bomber vers +x à droite du centre et vers −x à
    # gauche est le même phénomène — un barillet.
    radial_side = 1.0 if float(across.mean()) >= across_center else -1.0

    settings = get_settings()
    fit_rms = float(np.sqrt(np.mean(residuals**2)))
    span_ratio = base / max(scan_length - 1, 1)
    center_offset = abs(float(across.mean()) - across_center) / max(across_center, 1.0)

    if orientation == "vertical":
        points = np.column_stack((across, scan))
    else:
        points = np.column_stack((scan, across))

    return Track(
        orientation=orientation,
        points=points,
        sagitta_px=round(abs(bulge), 4),
        radial_bulge_px=round(bulge * radial_side, 4),
        fit_rms_px=round(fit_rms, 4),
        span_ratio=round(span_ratio, 4),
        center_offset=round(center_offset, 4),
        contrast=round(contrast, 5),
        usable=(
            contrast >= _MIN_TRACK_CONTRAST
            and fit_rms <= settings.lens_max_fit_rms_px
            and int(scan.size) >= settings.lens_min_track_points
            and span_ratio >= settings.lens_min_track_height_ratio
            and center_offset >= MIN_CENTER_OFFSET
        ),
    )


def _track_contrast(grad: np.ndarray, scan: np.ndarray, across: np.ndarray) -> float:
    """Médiane de |gradient| le long du tracé."""
    rows = np.clip(scan.astype(np.int64), 0, grad.shape[0] - 1)
    columns = np.clip(np.rint(across).astype(np.int64), 0, grad.shape[1] - 1)
    return float(np.median(np.abs(grad[rows, columns])))


def find_tracks(luma01: np.ndarray) -> list[Track]:
    """Tous les tracés d'arêtes de l'image, verticaux puis horizontaux."""
    shape = (int(luma01.shape[0]), int(luma01.shape[1]))
    tracks: list[Track] = []

    for orientation, image in (("vertical", luma01), ("horizontal", luma01.T)):
        grad = gradient_across(np.ascontiguousarray(image))
        for seed in _seed_positions(grad):
            followed = _follow(grad, seed)
            if followed is None:
                continue
            scan, across = followed
            tracks.append(
                _build_track(
                    scan,
                    across,
                    _track_contrast(grad, scan, across),
                    orientation,  # type: ignore[arg-type]
                    shape,
                )
            )

    return tracks
