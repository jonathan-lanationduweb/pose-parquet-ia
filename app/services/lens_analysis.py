"""Distorsion d'objectif : trois détecteurs candidats, aucune correction.

**Aucune correction de distorsion n'est appliquée, ici ou ailleurs.**
`LensMetrics.correction_applied` est un `Literal[False]` : il ne peut pas
devenir vrai par accident. Corriger demande un étalonnage que nous n'avons
pas, et une correction fausse est pire qu'aucune : une fois les points de fuite
calculés sur une image mal redressée, l'erreur est entrée dans toutes les
valeurs et plus rien ne la sépare du reste.

Le suivi d'arêtes vit dans `edge_tracking.py`. Ici on ne fait que décider ce
que des tracés autorisent à dire.

## Les trois candidates

**A — `sagitta_magnitude`** (celle du LOT 0). La flèche d'arc maximale dépasse
un seuil ⇒ distorsion. Simple, et **structurellement incapable** de distinguer
une distorsion d'un accident de texture : elle ne mesure qu'une amplitude, et
une amplitude ne dit pas d'où la courbure vient. C'est elle qui avait déclaré
une distorsion sur un damier. Conservée pour que la comparaison ait une base.

**B — `radial_consistency`.** Même mesure, mais **signée** relativement au
centre de l'image, et on exige que les arêtes s'accordent. Une distorsion
radiale courbe *toutes* les droites dans le même sens radial ; un carrelage ou
un objet réellement courbe donnent des signes désordonnés. Le discriminant
devient la cohérence, pas l'amplitude — ce qui est le bon critère, puisque
c'est la propriété qui définit une distorsion radiale.

**C — `k1_fit`, retenue.** On cherche le coefficient radial `k1` qui rend les
tracés observés **le plus droits possible**, et on regarde ce qu'il fait
gagner. Trois choses en découlent, qu'aucune mesure de flèche ne donne :

* une **estimation quantitative** de l'intensité, comparable à la vérité
  terrain synthétique ;
* le **sens** (barillet / coussinet) sans avoir à le déduire d'un signe ;
* un **test de cohérence intégré**. Le k1 est ajusté sur tous les tracés à la
  fois : s'ils ne se courbent pas de façon compatible avec une distorsion
  radiale, aucun k1 unique ne les redresse, et `residual_gain` reste bas.

Ce dernier point est ce qui rend C préférable à B plutôt que simplement
différente : B teste la cohérence des *signes*, C teste en plus celle des
*amplitudes* — une arête proche du centre doit bomber moins qu'une arête au
bord, dans un rapport que le modèle impose.

## Le piège qui a coûté une scène au front

Un traqueur doit suivre *ce qui définit l'arête*. Le front a d'abord suivi le
minimum de luminance : sur un jambage clair contre un mur clair, il n'y a pas
de minimum, le traqueur a glissé sur le bois sombre de la porte et a mesuré
**sa propre dérive** — un arc parfaitement crédible de +3,1 / −4,0 / +4,0 px.
Se tromper de grandeur ne donne pas un résultat bruité, il donne un résultat
faux et d'allure convaincante. Voir `docs/lens-distortion.md`.
"""

import numpy as np

from app.core.config import LensMethod, get_settings
from app.core.warnings import Warn
from app.schemas.analysis import (
    EdgeTrack,
    K1Estimate,
    LensMetrics,
    LensSupport,
    LensVerdict,
)
from app.services.edge_tracking import Track, find_tracks

#: Nombre minimal de points pour qu'un tracé entre dans l'ajustement de k1.
#: Deux points définissent une droite : la non-rectitude d'un tracé si court
#: est nulle par construction, et l'inclure fabriquerait du gain.
_MIN_FIT_POINTS = 8


def _straightness(points: np.ndarray) -> float:
    """Non-rectitude d'un nuage de points, sans dimension.

    Rapport de l'écart perpendiculaire à l'étendue le long de la droite,
    obtenu des deux valeurs propres de la covariance. **Sans dimension
    exprès** : une mesure en pixels croîtrait avec l'échelle appliquée par la
    correction, et la recherche de k1 dériverait vers les valeurs négatives —
    elles contractent l'image, donc réduisent tous les résidus absolus sans
    rien redresser.
    """
    centered = points - points.mean(axis=0)
    sxx = float((centered[:, 0] ** 2).mean())
    syy = float((centered[:, 1] ** 2).mean())
    sxy = float((centered[:, 0] * centered[:, 1]).mean())

    trace = sxx + syy
    determinant = sxx * syy - sxy * sxy
    spread = max(trace * trace / 4.0 - determinant, 0.0) ** 0.5
    minor = max(trace / 2.0 - spread, 0.0)
    major = max(trace / 2.0 + spread, 1e-12)
    return float((minor / major) ** 0.5)


def _undistort(
    points: np.ndarray, k1: float, center: np.ndarray, half_diagonal: float
) -> np.ndarray:
    """Applique le modèle radial aux points observés, pour un k1 candidat.

    C'est exactement le modèle du générateur de corpus, dans le même sens :
    `p_ideal = c + (p_image − c) · (1 + k1·r²)`. Appliqué avec le vrai k1 à des
    points qui étaient alignés dans la scène, il les réaligne.
    """
    delta = points - center
    r2 = (delta**2).sum(axis=1) / (half_diagonal**2)
    corrected: np.ndarray = center + delta * (1.0 + k1 * r2)[:, None]
    return corrected


def _pooled_straightness(
    tracks: list[Track], k1: float, center: np.ndarray, half_diagonal: float
) -> float:
    """Non-rectitude de tous les tracés à la fois, pondérée par leur longueur.

    Pondérer par le nombre de points empêche une poignée de tracés courts de
    peser autant qu'une longue arête traversant l'image.
    """
    total = 0.0
    total_weight = 0.0
    for track in tracks:
        weight = float(track.points.shape[0])
        total += _straightness(_undistort(track.points, k1, center, half_diagonal)) * weight
        total_weight += weight
    return total / total_weight if total_weight > 0.0 else 0.0


def _image_center(shape: tuple[int, int]) -> tuple[np.ndarray, float]:
    """Centre optique **supposé** au centre du cadre, et demi-diagonale.

    C'est une hypothèse, pas une mesure, et elle tombe sur une photo recadrée :
    le centre optique n'est alors plus le centre de l'image. Estimer le centre
    en même temps que k1 demanderait un support bien supérieur à ce qu'offre
    une photo d'intérieur ordinaire — c'est une limite assumée du lot, notée
    dans `docs/quality-methodology.md`.
    """
    height, width = shape
    center = np.array([(width - 1) / 2.0, (height - 1) / 2.0])
    return center, float(np.hypot(center[0], center[1]))


def estimate_k1(tracks: list[Track], shape: tuple[int, int]) -> K1Estimate | None:
    """Cherche le coefficient radial qui redresse le mieux les tracés retenus.

    Balayage régulier plutôt qu'optimisation : le critère n'est pas garanti
    convexe sur des tracés réels, une descente pourrait s'arrêter dans un
    minimum local, et 181 évaluations sur quelques milliers de points restent
    très en dessous du budget de l'étage.

    :returns: `None` si aucun tracé n'est assez long pour porter un ajustement.
    """
    settings = get_settings()
    usable = [t for t in tracks if t.usable and t.points.shape[0] >= _MIN_FIT_POINTS]
    if not usable:
        return None

    center, half_diagonal = _image_center(shape)
    grid = np.linspace(
        settings.lens_k1_search_min, settings.lens_k1_search_max, settings.lens_k1_search_steps
    )
    scores = [_pooled_straightness(usable, float(k1), center, half_diagonal) for k1 in grid]
    best = int(np.argmin(scores))

    at_zero = _pooled_straightness(usable, 0.0, center, half_diagonal)
    at_best = float(scores[best])
    gain = 0.0 if at_zero <= 1e-9 else max(0.0, 1.0 - at_best / at_zero)

    return K1Estimate(
        k1=round(float(grid[best]), 5),
        straightness_at_zero=round(at_zero, 8),
        straightness_at_best=round(at_best, 8),
        residual_gain=round(gain, 5),
        search_min=settings.lens_k1_search_min,
        search_max=settings.lens_k1_search_max,
    )


def _support(tracks: list[Track], shape: tuple[int, int]) -> LensSupport:
    """Quantité et répartition de la preuve géométrique disponible."""
    height, width = shape
    usable = [t for t in tracks if t.usable]
    bulges = [t.radial_bulge_px for t in usable]

    if bulges:
        positives = sum(1 for bulge in bulges if bulge > 0.0)
        agreement = max(positives, len(bulges) - positives) / len(bulges)
        median_bulge = float(np.median(bulges))
    else:
        # Sans tracé il n'y a pas d'accord à mesurer. 0 et non 1 : « aucune
        # donnée » ne doit jamais se lire comme « parfaitement cohérent ».
        agreement = 0.0
        median_bulge = 0.0

    quadrants = {
        (
            float(track.points[:, 0].mean()) >= (width - 1) / 2.0,
            float(track.points[:, 1].mean()) >= (height - 1) / 2.0,
        )
        for track in usable
    }

    return LensSupport(
        usable_edges=len(usable),
        vertical_edges=sum(1 for t in usable if t.orientation == "vertical"),
        horizontal_edges=sum(1 for t in usable if t.orientation == "horizontal"),
        total_track_px=round(sum(t.length_px for t in usable), 1),
        spatial_coverage=round(len(quadrants) / 4.0, 3),
        sign_agreement=round(agreement, 4),
        median_radial_bulge_px=round(median_bulge, 4),
    )


def _to_schema(track: Track) -> EdgeTrack:
    return EdgeTrack(
        orientation=track.orientation,
        sagitta_px=track.sagitta_px,
        radial_bulge_px=track.radial_bulge_px,
        fit_rms_px=track.fit_rms_px,
        points=int(track.points.shape[0]),
        span_ratio=track.span_ratio,
        center_offset=track.center_offset,
        usable=track.usable,
    )


def _sign_of(value: float) -> str | None:
    if value > 0.0:
        return "barrel"
    if value < 0.0:
        return "pincushion"
    return None


def _decide(
    support: LensSupport, k1: K1Estimate | None, max_sagitta: float | None, threshold: float
) -> tuple[LensVerdict, str | None]:
    """Applique le détecteur configuré, et renvoie le verdict et le sens supposé.

    Une règle est commune aux trois : **sans support suffisant, on ne conclut
    pas**. Aucun détecteur n'a le droit de répondre « pas de distorsion » sur
    une image où il n'a rien pu mesurer — ce serait rassurer sans avoir
    regardé, et c'est exactement ce que le nom `no_distortion_evidence` refuse
    de laisser croire.
    """
    settings = get_settings()

    if support.usable_edges < settings.lens_min_usable_edges:
        return LensVerdict.UNDETERMINED, None

    if settings.lens_method is LensMethod.SAGITTA_MAGNITUDE:
        # Candidate A : l'amplitude, et rien d'autre. Reproduite telle quelle,
        # y compris son incapacité à voir d'où vient la courbure — sans quoi la
        # comparaison serait flatteuse pour la méthode retenue.
        if max_sagitta is not None and max_sagitta >= threshold:
            return LensVerdict.DISTORTION_SUSPECTED, _sign_of(support.median_radial_bulge_px)
        return LensVerdict.NO_DISTORTION_EVIDENCE, None

    if settings.lens_method is LensMethod.RADIAL_CONSISTENCY:
        coherent = support.sign_agreement >= settings.lens_min_sign_agreement
        strong = max_sagitta is not None and max_sagitta >= threshold
        if coherent and strong:
            return LensVerdict.DISTORTION_SUSPECTED, _sign_of(support.median_radial_bulge_px)
        return LensVerdict.NO_DISTORTION_EVIDENCE, None

    # Candidate C : intensité estimée **et** part de courbure expliquée. Les
    # deux conditions sont nécessaires. Sans la seconde, la recherche
    # renverrait un k1 « optimal » sur n'importe quelle image, y compris
    # parfaitement rectilinéaire.
    if k1 is None:
        return LensVerdict.UNDETERMINED, None
    if (
        abs(k1.k1) >= settings.lens_k1_suspect_min
        and k1.residual_gain >= settings.lens_k1_min_residual_gain
    ):
        return LensVerdict.DISTORTION_SUSPECTED, _sign_of(k1.k1)
    return LensVerdict.NO_DISTORTION_EVIDENCE, None


def analyse_lens(luma01: np.ndarray) -> LensMetrics:
    """Mesure la courbure des arêtes de l'image et en tire un verdict prudent.

    Toutes les mesures sont calculées quel que soit le détecteur configuré : un
    rapport de benchmark porte donc de quoi rejouer les trois candidates sans
    réanalyser le corpus.
    """
    settings = get_settings()
    shape = (int(luma01.shape[0]), int(luma01.shape[1]))
    threshold = settings.lens_sagitta_suspect_px * (shape[1] / settings.lens_reference_width)

    tracks = find_tracks(luma01)
    support = _support(tracks, shape)
    k1 = estimate_k1(tracks, shape)

    usable = [t for t in tracks if t.usable]
    max_sagitta = max((t.sagitta_px for t in usable), default=None)
    verdict, sign = _decide(support, k1, max_sagitta, threshold)

    return LensMetrics(
        verdict=verdict,
        method=settings.lens_method.value,
        suspected_sign=sign,  # type: ignore[arg-type]
        support=support,
        k1=k1,
        max_sagitta_px=max_sagitta,
        max_sagitta_px_normalized=(
            None
            if max_sagitta is None
            else round(max_sagitta * settings.lens_reference_width / shape[1], 4)
        ),
        suspect_threshold_px=round(threshold, 4),
        tracks=[_to_schema(track) for track in tracks],
    )


def lens_warnings(lens: LensMetrics) -> list[Warn]:
    """Traduit le verdict d'objectif en codes machine."""
    if lens.verdict is LensVerdict.DISTORTION_SUSPECTED:
        return [Warn.LENS_DISTORTION_SUSPECTED]
    if lens.verdict is LensVerdict.UNDETERMINED:
        return [Warn.LENS_ANALYSIS_UNDETERMINED]
    return []
