"""Horizon et focale lus dans les droites de la photo — LOT PHOTO.2.

    EXPERIMENTAL PRODUCT PIPELINE · AUCUN MODÈLE RETENU · PAS UNE VÉRITÉ TERRAIN

## Pourquoi ce module existe

Le LOT PHOTO.1 estimait la perspective depuis le **masque seul** : deux rails
latéraux ajustés sur le bord du sol, leur intersection pour point de fuite, et
une focale **supposée** (0,85 × largeur) pour passer aux mètres. La revue
visuelle a mesuré ce que cela donne sur de vraies photos :

* un rail contaminé par un meuble (le bord d'un bureau pris pour un mur) pose
  l'horizon au milieu de la pièce ; la largeur estimée double, les chevrons
  deviennent microscopiques ;
* une focale supposée trop longue pour une photo grand-angle donne une
  profondeur de 15 à 20 m à une chambre de 5 : le motif se comprime trois fois
  trop vite vers le fond.

La photo porte pourtant bien plus que deux rails : plinthes, encadrements de
portes et de fenêtres, corniches, bords de meubles. Dans une pièce, presque
toutes ces droites sont horizontales ou verticales, et **toutes les droites
horizontales fuient vers un point situé sur l'horizon**. Deux directions
horizontales d'une même pièce sont de plus perpendiculaires, et deux points de
fuite perpendiculaires donnent la focale :

    f² = −(v₁ − c) · (v₂ − c)        (c = centre de l'image)

C'est de la géométrie projective élémentaire, et c'est **général** : aucune
règle par photo, aucune valeur codée pour une pièce.

## Ce qui est mesuré, ce qui est supposé

| grandeur | source | statut |
| --- | --- | --- |
| horizon | points de fuite des segments de l'image | mesuré, si ≥ 1 point solide |
| focale | EXIF 35 mm > deux points de fuite > a priori 0,70 × largeur | mesuré > mesuré > supposé |
| hauteur de caméra | 1,50 m | toujours supposé |

La hauteur de caméra n'est pas lisible dans une photo seule : elle fixe
l'échelle absolue (combien de lames en travers), et son incertitude est
reportée telle quelle dans `metricScaleConfidence`. Ce que la focale fixe, en
revanche, est le **rapport** profondeur/largeur du sol — c'est lui qui
comprime ou étire le motif — et c'est lui qui est mesuré ici quand il peut
l'être.

## Ce que ce module ne fait pas

Il ne choisit pas de modèle, ne regarde pas le masque autrement que pour
rejeter un horizon absurde (un horizon sous le sol n'est pas un horizon), et
ne borne rien à une valeur « typique » : quand il ne sait pas, il le dit.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import cv2
import numpy as np

#: Côté long de l'image de travail pour la détection des segments. La position
#: d'une droite se mesure aussi bien à 900 px qu'à 4000 ; le coût, non.
WORK_SIDE = 900
#: Longueur minimale d'un segment, en fraction de la diagonale de travail.
#: Sous ce seuil, une « droite » est un bord de texture, pas une arête.
MIN_SEGMENT_RATIO = 0.03
#: Segments à moins de cet angle de la verticale : ils ne fuient pas vers
#: l'horizon, ils fuient vers le zénith.
VERTICAL_TOL_DEG = 12.0
#: Tolérance de cohérence segment / point de fuite.
INLIER_TOL_DEG = 1.6
#: Tirages RANSAC par point de fuite. Déterministes : la graine est fixe.
RANSAC_ITERS = 600
#: Focale a priori quand rien ne la mesure : 0,70 × largeur ≈ 71° de champ
#: horizontal, la caméra principale d'un téléphone récent. L'ancienne valeur
#: (0,85, ≈ 61°) est celle d'un 35 mm : presque personne ne photographie une
#: pièce avec.
FOCAL_PRIOR_RATIO = 0.70
#: Bornes de plausibilité d'une focale mesurée, en fraction de la largeur :
#: de l'ultra grand-angle (0,30 ≈ 118°) au téléobjectif court (1,60 ≈ 35°).
FOCAL_MIN_RATIO = 0.30
FOCAL_MAX_RATIO = 1.60
#: Support minimal d'un point de fuite pour compter : longueur cumulée des
#: segments cohérents, en fraction de la largeur d'image, et nombre.
MIN_VP_SUPPORT = 0.8
MIN_VP_COUNT = 4
#: Au-delà de cet angle, la droite joignant deux points de fuite n'est pas un
#: horizon de photo tenue droite : l'un des deux est faux.
MAX_HORIZON_ROLL_DEG = 6.0


@dataclass(frozen=True, slots=True)
class Segment:
    """Un segment de droite, en pixels de l'image d'origine."""

    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def length(self) -> float:
        return math.hypot(self.x1 - self.x0, self.y1 - self.y0)

    @property
    def midpoint(self) -> tuple[float, float]:
        return ((self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2)

    @property
    def direction(self) -> tuple[float, float]:
        n = self.length or 1.0
        return ((self.x1 - self.x0) / n, (self.y1 - self.y0) / n)

    @property
    def angle_from_vertical_deg(self) -> float:
        dx, dy = self.direction
        return math.degrees(math.atan2(abs(dx), abs(dy)))

    @property
    def line(self) -> np.ndarray:
        """Coordonnées homogènes (a, b, c) de la droite porteuse, normalisées."""
        p0 = np.array([self.x0, self.y0, 1.0])
        p1 = np.array([self.x1, self.y1, 1.0])
        ligne = np.cross(p0, p1)
        n = math.hypot(ligne[0], ligne[1]) or 1.0
        return ligne / n


@dataclass
class VanishingPointEstimate:
    """Un point de fuite et ce qui le soutient."""

    x: float
    y: float
    #: Longueur cumulée des segments cohérents, en fraction de la largeur.
    support: float
    count: int
    inliers: list[int] = field(default_factory=list)

    def as_dict(self, width: int, height: int) -> dict[str, float | int]:
        return {
            "x": round(self.x / width, 4),
            "y": round(self.y / height, 4),
            "support": round(self.support, 2),
            "count": self.count,
        }


@dataclass
class CameraEstimate:
    """Ce que les droites de la photo disent de la caméra."""

    horizon: float | None  # y normalisé, None si aucune mesure
    horizon_source: str | None  # 'lines-2vp' | 'lines-1vp'
    horizon_confidence: float
    focal_px: float | None  # None si aucune mesure
    focal_source: str | None  # 'vanishing-points'
    vanishing_points: list[VanishingPointEstimate]
    segments: int
    notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 1. Segments
# ---------------------------------------------------------------------------


def detect_segments(gray: np.ndarray, *, max_side: int = WORK_SIDE) -> list[Segment]:
    """Segments de droite de l'image, en pixels d'origine.

    LSD (Line Segment Detector) quand OpenCV le fournit ; sinon Canny suivi de
    Hough probabiliste. Les deux donnent des segments ; LSD en donne de plus
    propres. Le repli existe parce que LSD a disparu de certaines
    distributions d'OpenCV pendant quelques versions.
    """
    if gray.ndim != 2:
        raise ValueError("detect_segments attend une image en niveaux de gris")
    hauteur, largeur = gray.shape[:2]
    echelle = min(1.0, max_side / max(largeur, hauteur))
    if echelle < 1.0:
        petit = cv2.resize(
            gray,
            (int(round(largeur * echelle)), int(round(hauteur * echelle))),
            interpolation=cv2.INTER_AREA,
        )
    else:
        petit = gray
    diag = math.hypot(petit.shape[1], petit.shape[0])
    mini = MIN_SEGMENT_RATIO * diag

    brut: np.ndarray | None = None
    try:
        lsd = cv2.createLineSegmentDetector(cv2.LSD_REFINE_STD)
        lignes = lsd.detect(petit)[0]
        if lignes is not None:
            brut = lignes.reshape(-1, 4)
    except (cv2.error, AttributeError):
        brut = None
    if brut is None:
        bords = cv2.Canny(petit, 60, 160, L2gradient=True)
        hough = cv2.HoughLinesP(
            bords, 1, math.pi / 360, threshold=40, minLineLength=int(mini), maxLineGap=4
        )
        brut = hough.reshape(-1, 4) if hough is not None else np.zeros((0, 4))

    segments: list[Segment] = []
    for x0, y0, x1, y1 in brut.astype(float):
        if math.hypot(x1 - x0, y1 - y0) < mini:
            continue
        segments.append(Segment(x0 / echelle, y0 / echelle, x1 / echelle, y1 / echelle))
    return segments


# ---------------------------------------------------------------------------
# 2. Points de fuite
# ---------------------------------------------------------------------------


def _consistency_deg(seg: Segment, vx: float, vy: float) -> float:
    """Angle entre le segment et la direction de son milieu vers le point.

    Zéro quand la droite du segment passe exactement par le point de fuite.
    La mesure est angulaire, donc valable pour un point très éloigné — un
    point de fuite de mur presque frontal est à dix largeurs d'image.
    """
    mx, my = seg.midpoint
    dx, dy = seg.direction
    ux, uy = vx - mx, vy - my
    n = math.hypot(ux, uy)
    if n < 1e-9:
        return 0.0
    croix = abs(dx * uy - dy * ux) / n
    return math.degrees(math.asin(min(1.0, croix)))


def _score(segments: list[Segment], vx: float, vy: float, tol: float) -> tuple[float, list[int]]:
    total = 0.0
    inliers: list[int] = []
    for i, seg in enumerate(segments):
        ang = _consistency_deg(seg, vx, vy)
        if ang < tol:
            total += seg.length * (1.0 - ang / tol)
            inliers.append(i)
    return total, inliers


def _refine(segments: list[Segment], inliers: list[int]) -> tuple[float, float] | None:
    """Point le plus proche de toutes les droites retenues, au sens des
    moindres carrés pondérés par la longueur (plus petit vecteur singulier)."""
    if len(inliers) < 2:
        return None
    lignes = np.stack([segments[i].line * math.sqrt(segments[i].length) for i in inliers])
    _, _, vt = np.linalg.svd(lignes, full_matrices=False)
    p = vt[-1]
    if abs(p[2]) < 1e-9:
        return None
    return float(p[0] / p[2]), float(p[1] / p[2])


def find_vanishing_points(
    segments: list[Segment],
    width: int,
    height: int,
    *,
    max_points: int = 3,
    iters: int = RANSAC_ITERS,
    tol_deg: float = INLIER_TOL_DEG,
    seed: int = 7,
) -> list[VanishingPointEstimate]:
    """Points de fuite **horizontaux** dominants, par RANSAC séquentiel.

    Les segments quasi verticaux sont écartés d'emblée : ils fuient vers le
    zénith, pas vers l'horizon. Un candidat n'est retenu que si sa hauteur est
    celle d'un horizon possible — entre une demi-hauteur au-dessus du cadre et
    une demi-hauteur en dessous — et s'il n'est pas à plus de douze largeurs
    d'image, au-delà de quoi la mesure ne dit plus rien de sa position.

    Déterministe : même image, mêmes points. Une estimation qui changerait
    d'un appel à l'autre rendrait les rendus incomparables.
    """
    candidats = [s for s in segments if s.angle_from_vertical_deg > VERTICAL_TOL_DEG]
    if len(candidats) < MIN_VP_COUNT:
        return []
    rng = np.random.default_rng(seed)
    restants = list(range(len(candidats)))
    trouves: list[VanishingPointEstimate] = []
    cx = width / 2

    for _ in range(max_points):
        if len(restants) < MIN_VP_COUNT:
            break
        pool = [candidats[i] for i in restants]
        poids = np.array([s.length for s in pool])
        poids /= poids.sum()
        meilleur: tuple[float, float, float, list[int]] | None = None
        for _ in range(iters):
            a, b = rng.choice(len(pool), size=2, replace=False, p=poids)
            sa, sb = pool[a], pool[b]
            da, db = sa.direction, sb.direction
            if abs(da[0] * db[1] - da[1] * db[0]) < math.sin(math.radians(1.0)):
                continue  # presque parallèles : intersection instable
            p = np.cross(sa.line, sb.line)
            if abs(p[2]) < 1e-12:
                continue
            vx, vy = float(p[0] / p[2]), float(p[1] / p[2])
            if not (-0.5 * height < vy < 1.5 * height) or abs(vx - cx) > 12 * width:
                continue
            total, inl = _score(pool, vx, vy, tol_deg)
            if meilleur is None or total > meilleur[0]:
                meilleur = (total, vx, vy, inl)
        if meilleur is None:
            break
        total, vx, vy, inl = meilleur
        affine = _refine(pool, inl)
        if affine is not None and -0.5 * height < affine[1] < 1.5 * height:
            t2, inl2 = _score(pool, affine[0], affine[1], tol_deg)
            if t2 >= total * 0.9:
                total, (vx, vy), inl = t2, affine, inl2
        support = total / width
        if support < MIN_VP_SUPPORT or len(inl) < MIN_VP_COUNT:
            break
        trouves.append(
            VanishingPointEstimate(
                x=vx,
                y=vy,
                support=support,
                count=len(inl),
                inliers=[restants[i] for i in inl],
            )
        )
        # Les segments expliqués — et ceux qui le sont presque — quittent le
        # jeu : sans quoi le second tirage retrouverait le premier point.
        retires = {
            restants[i] for i, s in enumerate(pool) if _consistency_deg(s, vx, vy) < 2 * tol_deg
        }
        restants = [i for i in restants if i not in retires]
    return trouves


# ---------------------------------------------------------------------------
# 3. Horizon et focale
# ---------------------------------------------------------------------------


def focal_from_vanishing_points(
    v1: tuple[float, float], v2: tuple[float, float], width: int, height: int
) -> float | None:
    """Focale depuis deux points de fuite de directions **perpendiculaires**.

    Pour une caméra sténopé dont le point principal est le centre de l'image,
    deux directions orthogonales de la scène ont des points de fuite tels que
    `(v₁ − c) · (v₂ − c) = −f²`. On rend `None` si le produit n'est pas
    négatif (les deux points sont du même côté : pas perpendiculaires), si
    l'un des points est trop près du centre (mal conditionné) ou si la focale
    sort des bornes d'un objectif réel.
    """
    cx, cy = width / 2, height / 2
    ax, ay = v1[0] - cx, v1[1] - cy
    bx, by = v2[0] - cx, v2[1] - cy
    if min(abs(ax), abs(bx)) < 0.04 * width or max(abs(ax), abs(bx)) > 15 * width:
        return None
    produit = -(ax * bx + ay * by)
    if produit <= 0:
        return None
    f = math.sqrt(produit)
    if not (FOCAL_MIN_RATIO * width <= f <= FOCAL_MAX_RATIO * width):
        return None
    return f


def estimate_camera(
    image_rgb: np.ndarray,
    *,
    floor_mask: np.ndarray | None = None,
) -> CameraEstimate:
    """Horizon et focale depuis les droites de la photo.

    Le masque de sol, s'il est donné, ne sert qu'à **rejeter** : un horizon
    situé dans le sol visible ou en dessous n'est pas un horizon, quel que
    soit le nombre de segments qui le soutiennent — c'est le point de fuite
    d'autre chose (un meuble oblique, un motif de carrelage).
    """
    hauteur, largeur = image_rgb.shape[:2]
    gris = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY)
    segments = detect_segments(gris)
    notes: list[str] = []
    points = find_vanishing_points(segments, largeur, hauteur)

    plafond: float | None = None
    if floor_mask is not None and floor_mask.any():
        colonnes = floor_mask.any(axis=0)
        y_top = np.where(colonnes, floor_mask.argmax(axis=0), hauteur)
        plafond = float(np.percentile(y_top[colonnes], 15)) - 0.02 * hauteur

    # Un horizon est au-dessus du sol visible et dans la plage d'une photo
    # tenue debout. Les points qui ne respectent pas cela gardent leur rôle
    # pour la focale (un point de fuite perpendiculaire peut être n'importe
    # où sur la ligne), mais ne posent pas l'horizon.
    def horizon_possible(p: VanishingPointEstimate) -> bool:
        if not (0.05 * hauteur <= p.y <= 0.85 * hauteur):
            return False
        return plafond is None or p.y <= plafond

    forts = [p for p in points if p.support >= MIN_VP_SUPPORT and p.count >= MIN_VP_COUNT]
    horizon: float | None = None
    source: str | None = None
    confiance = 0.0

    if len(forts) >= 2:
        a, b = forts[0], forts[1]
        if abs(b.x - a.x) > 0.3 * largeur:
            roll = math.degrees(math.atan2(b.y - a.y, b.x - a.x))
            if abs(roll) <= MAX_HORIZON_ROLL_DEG or abs(abs(roll) - 180) <= MAX_HORIZON_ROLL_DEG:
                y_centre = a.y + (b.y - a.y) * ((largeur / 2 - a.x) / (b.x - a.x))
                dans_la_plage = 0.05 * hauteur <= y_centre <= 0.85 * hauteur
                if dans_la_plage and (plafond is None or y_centre <= plafond):
                    horizon, source = y_centre, "lines-2vp"
                    confiance = min(0.9, 0.55 + 0.1 * min(a.support, b.support))
            else:
                notes.append("deux points de fuite non alignés : horizon sur le plus fort")
    if horizon is None:
        for p in forts:
            if horizon_possible(p):
                horizon, source = p.y, "lines-1vp"
                confiance = min(0.8, 0.45 + 0.1 * p.support)
                break
    if horizon is None and forts:
        notes.append("points de fuite trouvés mais aucun à hauteur d'horizon")

    focal: float | None = None
    focal_source: str | None = None
    meilleur_support = 0.0
    for i in range(len(forts)):
        for j in range(i + 1, len(forts)):
            f = focal_from_vanishing_points(
                (forts[i].x, forts[i].y), (forts[j].x, forts[j].y), largeur, hauteur
            )
            if f is None:
                continue
            s = min(forts[i].support, forts[j].support)
            if s > meilleur_support:
                focal, focal_source, meilleur_support = f, "vanishing-points", s
    if focal is None and len(forts) >= 2:
        notes.append("deux points de fuite sans focale plausible")

    return CameraEstimate(
        horizon=None if horizon is None else horizon / hauteur,
        horizon_source=source,
        horizon_confidence=confiance,
        focal_px=focal,
        focal_source=focal_source,
        vanishing_points=points,
        segments=len(segments),
        notes=notes,
    )


def focal_from_exif_35mm(focal_35mm: float | None, width: int, height: int) -> float | None:
    """Focale en pixels depuis l'équivalent 35 mm déclaré par l'appareil.

    Le format 24 × 36 est la référence de cet équivalent : 36 mm sur le grand
    côté. Une photo en portrait a son grand côté vertical ; le rapport reste
    celui du grand côté.
    """
    if focal_35mm is None or not (3.0 <= focal_35mm <= 400.0):
        return None
    return focal_35mm / 36.0 * max(width, height)
