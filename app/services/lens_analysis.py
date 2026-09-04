"""Analyse d'objectif : mesurer la courbure des droites, et rien de plus.

**Aucune correction de distorsion n'est appliquée, ici ou ailleurs.** Corriger
demande un étalonnage que nous n'avons pas, et une correction fausse est pire
qu'aucune correction : une fois les points de fuite calculés sur une image mal
redressée, l'erreur est entrée dans toutes les valeurs et plus rien ne la
sépare du reste. Ce module mesure et rapporte ; la décision viendra au LOT 1,
armée d'un corpus.

## La mesure

La perspective **conserve les droites** : une arête droite du monde reste
droite dans l'image, où qu'elle soit dans le cadre. La distorsion optique, au
contraire, **courbe les droites**, d'autant plus qu'elles passent loin du
centre optique. C'est cette signature qu'on cherche.

On suit donc une arête presque verticale, ligne par ligne, on lui ajuste une
parabole, et on mesure sa **flèche** : l'écart de la parabole à sa corde, au
milieu, en pixels. Pour une parabole ajustée sur une base L, la flèche vaut
|a| · L² / 4 — le bombement croît comme le carré de la longueur, ce qui est
exactement pourquoi une arête courte ne prouve rien.

## Trois pièges, tous rencontrés par le front

1. **Suivre la mauvaise grandeur.** Un traqueur doit suivre *ce qui définit
   l'arête*. Le front a d'abord suivi le **minimum de luminance** : sur un
   jambage clair contre un mur clair, il n'y a pas de minimum, le traqueur a
   glissé sur le bois sombre de la porte et a mesuré **sa propre dérive** —
   un arc de +3,1 / −4,0 / +4,0 px, d'allure parfaitement crédible. Le même
   jambage suivi par le **maximum de gradient** donne 0,13 px de flèche. Ici
   on suit le gradient, jamais la luminance.

2. **Lire la flèche sans l'écart-type.** `sagitta_px` seule ne veut rien
   dire : c'est `fit_rms_px` qui dit si la parabole *décrit* le tracé. Les
   deux voyagent ensemble dans `EdgeTrack`, et un tracé mal ajusté est écarté
   avant tout verdict.

3. **Mesurer au centre du cadre.** La distorsion radiale ne déplace rien sur
   l'axe optique : une verticale au milieu de l'image reste droite quelle que
   soit la force de la distorsion. Les colonnes candidates sont donc pondérées
   par leur éloignement du centre, et une bande centrale est exclue.

4. **Retenir des tracés courts.** Un motif répétitif — carrelage, rayures,
   étagères — fournit des dizaines de petits segments verticaux. Leur flèche
   n'est que du bruit d'ajustement, mais elle est non nulle, et en nombre elle
   finit par franchir n'importe quel seuil. Le corpus synthétique a produit
   exactement ce faux positif sur un damier. Un tracé doit donc couvrir une
   fraction minimale de la hauteur d'image pour compter.

Enfin : la résolution compte. La flèche est en pixels, donc proportionnelle à
la taille de l'image. Le seuil configuré vaut pour une largeur de référence et
est mis à l'échelle de l'image réellement analysée.

Voir `docs/lens-distortion.md` et, côté front,
`pose-parquet.com/docs/photo-lens-distortion.md`.
"""

from dataclasses import dataclass

import cv2
import numpy as np

from app.core.config import get_settings
from app.core.warnings import Warn
from app.schemas.analysis import EdgeTrack, LensMetrics, LensVerdict

#: Demi-largeur de la fenêtre de recherche, en pixels, à chaque ligne. Assez
#: large pour suivre une arête inclinée, assez étroite pour ne pas sauter sur
#: l'arête voisine.
_SEARCH_HALF_WINDOW = 6

#: Bande centrale exclue, en fraction de la demi-largeur : une arête plus
#: proche du centre que cela ne prouve rien sur la distorsion.
_MIN_CENTER_OFFSET = 0.25

#: Marge haute et basse ignorée, en fraction de la hauteur. Les bords d'image
#: portent souvent du vignettage et des artefacts de compression.
_VERTICAL_MARGIN = 0.08

#: Écart minimal entre deux colonnes candidates, en fraction de la largeur.
_MIN_SEED_GAP = 0.04

#: Nombre de colonnes candidates examinées au plus.
_MAX_SEEDS = 12


@dataclass(frozen=True, slots=True)
class _Arc:
    """Un suivi d'arête ajusté, avant traduction en schéma."""

    sagitta_px: float
    fit_rms_px: float
    points: int
    span_ratio: float
    center_offset: float


def _gradient_x(luma01: np.ndarray) -> np.ndarray:
    """Gradient horizontal **signé**, légèrement lissé.

    Le lissage préalable est indispensable : sur une photo compressée, le
    bruit de bloc produit des maxima de gradient d'un pixel de large qui
    attirent le traqueur hors de l'arête.

    Le signe est conservé, et c'est essentiel : voir `_follow_edge`.
    """
    smoothed = cv2.GaussianBlur(luma01, (3, 3), 0)
    return cv2.Sobel(smoothed, cv2.CV_32F, 1, 0, ksize=3)


def _vertical_span(height: int) -> tuple[int, int]:
    """Bandes haute et basse exclues du suivi."""
    return int(height * _VERTICAL_MARGIN), int(height * (1.0 - _VERTICAL_MARGIN))


def _seed_columns(grad: np.ndarray) -> list[int]:
    """Colonnes les plus susceptibles de porter une arête verticale longue.

    L'énergie de gradient d'une colonne entière favorise naturellement les
    arêtes qui traversent l'image — jambages, angles de murs — sur les
    accidents locaux. Elle est ensuite pondérée par l'éloignement du centre,
    pour la raison dite en en-tête.
    """
    height, width = grad.shape
    top, bottom = _vertical_span(height)
    # Magnitude ici : pour choisir une colonne, seule compte la quantité de
    # contraste vertical qu'elle porte, pas le sens des transitions.
    energy = np.abs(grad[top:bottom, :]).sum(axis=0)

    center = (width - 1) / 2.0
    offset = np.abs(np.arange(width) - center) / max(center, 1.0)
    scored = energy * offset

    gap = max(1, int(width * _MIN_SEED_GAP))
    seeds: list[int] = []
    for column in np.argsort(scored)[::-1]:
        x = int(column)
        if offset[x] < _MIN_CENTER_OFFSET:
            continue
        if any(abs(x - kept) < gap for kept in seeds):
            continue
        seeds.append(x)
        if len(seeds) >= _MAX_SEEDS:
            break
    return seeds


def _subpixel_offset(left: float, peak: float, right: float) -> float:
    """Sommet de la parabole passant par trois échantillons voisins.

    Sans cette interpolation la position de l'arête est quantifiée au pixel,
    et le bruit de quantification (± 0,5 px) noie une flèche de 1 px.
    """
    denominator = left - 2.0 * peak + right
    if denominator == 0.0:
        return 0.0
    return float(np.clip((left - right) / (2.0 * denominator), -1.0, 1.0))


def _polarity(grad: np.ndarray, seed_x: int) -> float:
    """Sens de la transition portée par la colonne : +1 ou −1.

    Un jambage de porte a deux arêtes, à quelques pixels l'une de l'autre, et
    elles sont de **sens opposés** : clair → sombre d'un côté, sombre → clair
    de l'autre. Un traqueur qui ne regarde que la magnitude saute de l'une à
    l'autre dès que le contraste varie un peu, et il mesure alors la largeur
    du jambage plutôt que sa courbure.
    """
    top, bottom = _vertical_span(grad.shape[0])
    column = grad[top:bottom, seed_x]
    # Le sens est lu **là où la transition est la plus franche**, pas en
    # moyenne sur la colonne : une arête qui dérive de quelques pixels fait
    # entrer les deux côtés du jambage dans la même colonne, et leur somme
    # s'annule au lieu de trancher.
    strongest = int(np.argmax(np.abs(column)))
    return -1.0 if float(column[strongest]) < 0.0 else 1.0


def _follow_edge(grad: np.ndarray, seed_x: int) -> tuple[np.ndarray, np.ndarray] | None:
    """Suit une arête ligne par ligne, par maximum de gradient **de même sens**.

    Le suivi s'arrête dès que le maximum atteint le bord de la fenêtre de
    recherche : l'arête s'échappe, et continuer voudrait dire mesurer sa
    propre dérive — l'erreur exacte qui avait fait rejeter une scène côté
    front.

    :returns: les lignes et les abscisses sous-pixel du tracé, ou `None` si
        l'arête n'est pas assez longue pour valoir quelque chose.
    """
    height, width = grad.shape
    top, bottom = _vertical_span(height)
    polarity = _polarity(grad, seed_x)

    rows: list[int] = []
    positions: list[float] = []
    current = float(seed_x)

    for y in range(top, bottom):
        lo = max(0, int(round(current)) - _SEARCH_HALF_WINDOW)
        hi = min(width, int(round(current)) + _SEARCH_HALF_WINDOW + 1)
        # L'arête de sens contraire répond négativement : elle ne peut donc
        # jamais remporter l'argmax.
        window = grad[y, lo:hi] * polarity
        if window.size < 3:
            break
        local = int(np.argmax(window))
        if local == 0 or local == window.size - 1:
            break
        current = (
            lo
            + local
            + _subpixel_offset(
                float(window[local - 1]), float(window[local]), float(window[local + 1])
            )
        )
        rows.append(y)
        positions.append(current)

    if len(rows) < get_settings().lens_min_track_points:
        return None
    return np.asarray(rows, dtype=np.float64), np.asarray(positions, dtype=np.float64)


def _fit_arc(rows: np.ndarray, positions: np.ndarray, shape: tuple[int, int]) -> _Arc:
    """Ajuste une parabole au tracé et en tire la flèche.

    La flèche d'une parabole sur une base L vaut |a| · L² / 4 : c'est l'écart
    de la courbe à sa corde, au milieu. Inutile de reconstruire la corde point
    par point.
    """
    height, width = shape
    center_x = (width - 1) / 2.0
    coefficients = np.polyfit(rows, positions, 2)
    residuals = positions - np.polyval(coefficients, rows)
    base = float(rows[-1] - rows[0])
    return _Arc(
        sagitta_px=round(abs(float(coefficients[0])) * base * base / 4.0, 4),
        fit_rms_px=round(float(np.sqrt(np.mean(residuals**2))), 4),
        points=int(rows.size),
        span_ratio=round(base / max(height - 1, 1), 4),
        center_offset=round(abs(float(positions.mean()) - center_x) / max(center_x, 1.0), 4),
    )


def analyse_lens(luma01: np.ndarray) -> LensMetrics:
    """Mesure la courbure des arêtes verticales de l'image.

    Le verdict reste `undetermined` tant que le nombre d'arêtes exploitables
    n'atteint pas le minimum configuré. C'est le cas le plus fréquent sur une
    photo d'intérieur ordinaire, et le seul honnête quand c'est vrai : une
    arête unique ne prouve rien, et prétendre le contraire ferait entrer une
    erreur dans tout ce qui suit.
    """
    settings = get_settings()
    shape = (int(luma01.shape[0]), int(luma01.shape[1]))
    width = shape[1]
    threshold = settings.lens_sagitta_suspect_px * (width / settings.lens_reference_width)

    grad = _gradient_x(luma01)
    tracks: list[EdgeTrack] = []
    for seed_x in _seed_columns(grad):
        followed = _follow_edge(grad, seed_x)
        if followed is None:
            continue
        arc = _fit_arc(followed[0], followed[1], shape)
        tracks.append(
            EdgeTrack(
                sagitta_px=arc.sagitta_px,
                fit_rms_px=arc.fit_rms_px,
                points=arc.points,
                span_ratio=arc.span_ratio,
                center_offset=arc.center_offset,
                usable=(
                    arc.fit_rms_px <= settings.lens_max_fit_rms_px
                    and arc.points >= settings.lens_min_track_points
                    and arc.span_ratio >= settings.lens_min_track_height_ratio
                    and arc.center_offset >= _MIN_CENTER_OFFSET
                ),
            )
        )

    usable = [t for t in tracks if t.usable]
    max_sagitta = max((t.sagitta_px for t in usable), default=None)

    if len(usable) < settings.lens_min_usable_edges:
        verdict = LensVerdict.UNDETERMINED
    elif max_sagitta is not None and max_sagitta >= threshold:
        verdict = LensVerdict.DISTORTION_SUSPECTED
    else:
        verdict = LensVerdict.NO_DISTORTION_DETECTED

    return LensMetrics(
        verdict=verdict,
        max_sagitta_px=max_sagitta,
        max_sagitta_px_normalized=(
            None
            if max_sagitta is None
            else round(max_sagitta * settings.lens_reference_width / width, 4)
        ),
        usable_edges=len(usable),
        tracks=tracks,
        suspect_threshold_px=round(threshold, 4),
    )


def lens_warnings(lens: LensMetrics) -> list[Warn]:
    """Traduit le verdict d'objectif en codes machine."""
    if lens.verdict is LensVerdict.DISTORTION_SUSPECTED:
        return [Warn.LENS_DISTORTION_SUSPECTED]
    if lens.verdict is LensVerdict.UNDETERMINED:
        return [Warn.LENS_ANALYSIS_UNDETERMINED]
    return []
