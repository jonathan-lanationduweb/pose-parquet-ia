"""Scène EXPÉRIMENTALE depuis un masque de sol — LOT PHOTO.1.

    EXPERIMENTAL PRODUCT PIPELINE · AUCUN MODÈLE RETENU · PAS UNE VÉRITÉ TERRAIN

Ce module fait ce que le LOT C.0 refusait de faire, et il le dit : il
transforme un masque de sol en une **scène** que le moteur de rendu sait
poser. Le refus d'alors tenait à une raison précise — ne pas laisser un masque
exploratoire se faire passer pour une détection — et cette raison n'a pas
disparu. Elle est portée autrement : la scène produite ici voyage dans le bloc
`experimental`, jamais dans `sceneData`, avec une confiance, un statut et une
provenance qui disent d'où elle vient et ce qu'elle vaut.

## La chaîne, et ce que chaque maillon sait vraiment

    masque brut ─► refine_mask ─► polygones (contour + trous)
                          │
                          └─► estimate_perspective ─► plan du sol (quad, mètres)
                                                            │
    classes sémantiques ─► rug_occluders ──────────────────┤
                                                            ▼
                                                    SceneData @1

* **Le raffineur** retire les miettes de prédiction et bouche les trous
  minuscules et compacts. Il ne bouche pas un trou allongé : un pied de chaise
  est un trou allongé, et le boucher repeindrait la chaise.
* **La perspective** est estimée depuis le masque seul. Le sol d'une pièce
  rectangulaire a deux bords qui fuient vers le même point : quand le masque
  les montre, leur intersection est le point de fuite et donne l'horizon sans
  rien supposer. Quand il ne les montre pas — mur de fond seul, cadrage serré,
  meubles qui mangent les bords — on **suppose** l'horizon un peu au-dessus du
  mur du fond, et la confiance le dit.
* **L'échelle** est une hypothèse de sténopé : focale ≈ 0,85 × largeur
  d'image (environ 61° de champ, un téléphone ordinaire), caméra à 1,50 m.
  Une photo seule ne porte pas sa propre échelle ; celle-ci est plausible,
  pas mesurée, et le rapport l'écrit en toutes lettres.

## Ce que ce module ne fait pas

Il ne choisit pas de modèle. Il ne détecte pas les meubles : les objets sont
protégés **seulement** là où le modèle de sol les a laissés hors du masque, et
le LOT D reste à faire. Il ne valide pas les tapis : la classe `rug` d'ADE20K
est utilisée comme signal, marqué non validé, parce que le corpus officiel n'en
contient aucun.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

from app.schemas.scene_data import (
    Camera,
    FloorZone,
    ImageRef,
    Light,
    Mask,
    Meters,
    Occluder,
    Plane,
    Point,
    SceneData,
    Surface,
    VanishingPoint,
)
from app.services.camera_geometry import (
    FOCAL_PRIOR_RATIO,
    CameraEstimate,
    estimate_camera,
    focal_from_exif_35mm,
)
from app.services.floor_segmentation import ADE20K_RUG, clean_mask

#: Focale **a priori**, en fraction de la largeur d'image, quand ni l'EXIF ni
#: les droites de la photo ne la mesurent. 0,70 ≈ 71° de champ horizontal :
#: la caméra principale d'un téléphone. LOT PHOTO.1 supposait 0,85 (≈ 61°,
#: un 35 mm) ; la revue a mesuré ce que cela coûte sur une photo grand-angle :
#: une chambre de cinq mètres rendue à quinze. Voir `camera_geometry`.
FOCAL_RATIO = FOCAL_PRIOR_RATIO
#: Hauteur de prise de vue supposée, en mètres. Debout, téléphone à hauteur
#: de poitrine. Même statut : une hypothèse écrite, pas une mesure — et la
#: seule grandeur de la chaîne qu'aucune photo ne permet de lire.
CAMERA_HEIGHT_M = 1.5
#: Largeur de lame de référence pour la vérification d'échelle : la plus
#: étroite du catalogue de démonstration, donc la plus vite illisible.
REFERENCE_PLANK_M = 0.092
#: Rapport profondeur / largeur du sol rendu au-delà duquel la géométrie
#: n'est plus celle d'une pièce vue depuis un mur : un couloir atteint 4, une
#: pièce ordinaire reste sous 2,5. Ce n'est pas une borne appliquée — c'est
#: le seuil à partir duquel on **dit** que l'échelle métrique est douteuse.
DEPTH_OVER_WIDTH_MAX = 5.0
#: Part de l'image sous laquelle on ne cherche pas de sol : il n'y en a pas.
MIN_COVERAGE = 0.03

#: Statuts de la scène expérimentale. Le front ne lit que ces trois mots.
STATUS_AUTO = "auto_render"
STATUS_ADJUST = "needs_manual_adjustment"
STATUS_NONE = "no_floor"


# ---------------------------------------------------------------------------
# 1. Raffinage du masque
# ---------------------------------------------------------------------------


def refine_mask(
    mask: np.ndarray,
    *,
    min_component_ratio: float = 0.002,
    max_hole_ratio: float = 0.0004,
) -> np.ndarray:
    """Masque brut → masque posable.

    Trois gestes, chacun borné par la taille de l'image et jamais par la
    photo :

    1. une ouverture morphologique **petite** (3 à 7 px selon la résolution)
       retire les filaments et les miettes collées au bord du sol ;
    2. les composantes sous `min_component_ratio` disparaissent — ce sont des
       éclats de prédiction, pas des sols ;
    3. les trous sont bouchés **seulement s'ils sont petits ET compacts**.
       Un trou allongé reste un trou : c'est la forme d'un pied de chaise, d'un
       pied de table, d'un barreau. Les boucher repeindrait le meuble.

    Aucune fermeture morphologique large : elle effacerait justement ces
    pieds fins, et c'est la mesure que le LOT C.0 avait relevée comme la
    plus fragile (4 objets fins sur 6 perdus par le modèle seul).
    """
    if mask.dtype != bool:
        mask = mask.astype(bool)
    hauteur, largeur = mask.shape[:2]
    if not mask.any():
        return mask.copy()

    k = max(3, int(round(min(largeur, hauteur) * 0.0035)))
    k += 1 - (k % 2)  # impair
    noyau = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    brut = mask.astype(np.uint8)
    ouvert = cv2.morphologyEx(brut, cv2.MORPH_OPEN, noyau)
    # Fermeture minimale : trois pixels, de quoi recoller une fissure d'un
    # pixel sans toucher à un pied de 10.
    ferme = cv2.morphologyEx(ouvert, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))

    propre = clean_mask(ferme.astype(bool), min_area_ratio=min_component_ratio)

    # Trous : petits ET compacts.
    inverse = (~propre).astype(np.uint8)
    nb, etiquettes, stats, _ = cv2.connectedComponentsWithStats(inverse, connectivity=4)
    seuil_aire = propre.size * max_hole_ratio
    cote_max = 0.03 * min(largeur, hauteur)
    for i in range(1, nb):
        x, y, w, h, aire = (int(v) for v in stats[i])
        touche_bord = x == 0 or y == 0 or x + w >= largeur or y + h >= hauteur
        if touche_bord or aire >= seuil_aire:
            continue
        compact = aire / max(1, w * h) > 0.45 and max(w, h) < cote_max
        if compact:
            propre[etiquettes == i] = True
    return propre


# ---------------------------------------------------------------------------
# 2. Perspective
# ---------------------------------------------------------------------------


@dataclass
class PerspectiveEstimate:
    """Ce qu'on sait du plan du sol, et comment on l'a su."""

    horizon: float  # y normalisé
    vanishing: tuple[float, float] | None  # normalisé
    method: str  # 'vanishing-point' | 'lines-vp' | 'far-edge-fallback'
    far_edge: float  # y normalisé du mur du fond (bord haut du sol)
    quad: list[tuple[float, float]]  # fond-gauche, fond-droite, proche-droite, proche-gauche
    meters: tuple[float, float]  # largeur, profondeur
    focal_px: float
    camera_height_m: float
    confidence: float
    notes: list[str] = field(default_factory=list)
    #: D'où vient la focale : 'exif' | 'vanishing-points' | 'prior'.
    focal_source: str = "prior"
    #: Ce que vaut l'échelle métrique : 'medium' quand la focale est mesurée
    #: (la hauteur de caméra reste supposée), 'low' quand elle est supposée
    #: aussi ou quand la géométrie obtenue n'est pas celle d'une pièce.
    metric_scale_confidence: str = "low"
    #: Vérification de plausibilité : rapport profondeur/largeur, largeur de
    #: lame projetée proche / milieu / fond, en pixels de l'image analysée.
    plausibility: dict[str, Any] = field(default_factory=dict)
    #: Les points de fuite lus dans les droites de l'image, pour le rapport.
    camera: dict[str, Any] = field(default_factory=dict)


def _fit_rail(ys: np.ndarray, xs: np.ndarray) -> tuple[float, float, float] | None:
    """Droite x = a·y + b par moindres carrés. Rend (a, b, rms) ou None."""
    if len(ys) < 8:
        return None
    a, b = np.polyfit(ys, xs, 1)
    residus = xs - (a * ys + b)
    return float(a), float(b), float(np.sqrt(np.mean(residus**2)))


@dataclass
class _Rails:
    """Point de fuite des deux rails du masque, quand ils existent."""

    vx: float
    vy: float
    confidence: float


def _rails_vanishing_point(
    mask: np.ndarray, far_edge_px: float, y_bas_px: int, notes: list[str]
) -> _Rails | None:
    """Les deux bords latéraux du sol, ajustés par deux droites.

    Si les deux existent et se croisent au-dessus du mur du fond, leur
    intersection est un point de fuite. Ce n'est qu'**une** mesure : un bord de
    masque qui longe un meuble plutôt qu'un mur donne une droite parfaitement
    ajustée et parfaitement fausse — la revue l'a vu sur un bureau.
    """
    hauteur, largeur = mask.shape[:2]
    y0 = int(max(0, far_edge_px))
    rangs = np.arange(y0, y_bas_px + 1)
    gauche: list[tuple[int, int]] = []
    droite: list[tuple[int, int]] = []
    for y in rangs:
        ligne = mask[y]
        if not ligne.any():
            continue
        nz = np.nonzero(ligne)[0]
        xl, xr = int(nz[0]), int(nz[-1])
        if xl > 1:
            gauche.append((int(y), xl))
        if xr < largeur - 2:
            droite.append((int(y), xr))

    min_support = max(8, int(0.12 * len(rangs)))
    ajust_g = ajust_d = None
    if len(gauche) >= min_support:
        ys, xs = np.array(gauche, dtype=float).T
        if ys.max() - ys.min() >= 0.15 * hauteur:
            ajust_g = _fit_rail(ys, xs)
    if len(droite) >= min_support:
        ys, xs = np.array(droite, dtype=float).T
        if ys.max() - ys.min() >= 0.15 * hauteur:
            ajust_d = _fit_rail(ys, xs)

    if not (ajust_g and ajust_d):
        notes.append("rails latéraux insuffisants")
        return None
    ag, bg, rg = ajust_g
    ad, bd, rd = ajust_d
    if abs(ag - ad) <= 1e-6:
        notes.append("rails parallèles")
        return None
    y_star = (bd - bg) / (ag - ad)
    x_star = ag * y_star + bg
    # Le point de fuite doit être au-dessus du mur du fond, et pas
    # absurdement loin au-dessus de l'image.
    if not (-0.5 * hauteur < y_star < far_edge_px - 0.02 * hauteur):
        notes.append("point de fuite des rails hors plage")
        return None
    rms = (rg + rd) / 2 / largeur
    # 0,01 de la largeur de résidu → pleine confiance ; 0,04 → basse.
    confiance = float(np.clip(0.85 - (rms - 0.01) * 10, 0.5, 0.85))
    return _Rails(float(x_star), float(y_star), confiance)


def _choose_horizon(
    rails: _Rails | None,
    cam: CameraEstimate | None,
    far_edge_px: float,
    largeur: int,
    hauteur: int,
    notes: list[str],
) -> tuple[float, float, str, float, bool]:
    """Horizon et point de fuite : droites de l'image, rails du masque, ou repli.

    Rend (horizon_px, vx_px, méthode, confiance, point de fuite mesuré ?).

    La règle de fusion tient en trois lignes, et chacune a été payée par un
    défaut vu :

    * quand les deux mesures existent et s'accordent (moins de 5 % de la
      hauteur), on les moyenne et la confiance monte — deux mesures
      indépendantes qui disent la même chose, c'est ce qu'on a de mieux ;
    * quand elles se contredisent, les droites gagnent **si leur support est
      réel** : elles résument des dizaines d'arêtes de la pièce, là où les
      rails ne sont que deux bords de masque ;
    * quand il n'y a ni l'une ni l'autre, l'horizon est supposé un peu
      au-dessus du mur du fond, et la confiance le dit.
    """
    lignes_px: float | None = None
    if cam is not None and cam.horizon is not None:
        candidat = cam.horizon * hauteur
        if candidat < far_edge_px - 0.02 * hauteur:
            lignes_px = candidat
        else:
            notes.append("horizon des droites sous le sol visible, ignoré")

    def vx_des_droites(horizon_px: float) -> float | None:
        if cam is None:
            return None
        proches = [
            p
            for p in cam.vanishing_points
            if abs(p.y - horizon_px) < 0.08 * hauteur and abs(p.x - largeur / 2) < 3 * largeur
        ]
        return proches[0].x if proches else None

    if rails is not None and lignes_px is not None:
        if abs(lignes_px - rails.vy) <= 0.05 * hauteur:
            horizon = 0.5 * (lignes_px + rails.vy)
            notes.append("horizon confirmé par les droites de l'image")
            conf = min(0.92, max(rails.confidence, cam.horizon_confidence) + 0.05)  # type: ignore[union-attr]
            return horizon, rails.vx, "vanishing-point", conf, True
        if cam is not None and cam.horizon_confidence >= 0.5:
            notes.append(
                f"rails du masque ({rails.vy / hauteur:.3f}) contredits par les droites "
                f"({lignes_px / hauteur:.3f}) : droites retenues"
            )
            vx = vx_des_droites(lignes_px)
            conf = cam.horizon_confidence * 0.9
            return lignes_px, vx if vx is not None else rails.vx, "lines-vp", conf, True
        notes.append("droites peu soutenues, rails du masque retenus")
        return rails.vy, rails.vx, "vanishing-point", rails.confidence - 0.1, True

    if lignes_px is not None and cam is not None:
        vx = vx_des_droites(lignes_px)
        conf = cam.horizon_confidence
        return lignes_px, vx if vx is not None else largeur / 2, "lines-vp", conf, True

    if rails is not None:
        return rails.vy, rails.vx, "vanishing-point", rails.confidence, True

    notes.append("aucun point de fuite mesuré, horizon supposé")
    return far_edge_px - 0.12 * hauteur, largeur / 2, "far-edge-fallback", 0.45, False


def _projected_plank_px(
    d_px: float, camera_height_m: float, plank_m: float = REFERENCE_PLANK_M
) -> float:
    """Largeur projetée d'une lame posée en travers, à `d_px` sous l'horizon.

    `p · f / z` avec `z = f · H / d` donne `p · d / H` : la largeur apparente ne
    dépend **pas** de la focale, seulement de la hauteur de caméra. C'est ce
    qui rend cette vérification lisible même quand la focale est supposée.
    """
    return plank_m * d_px / camera_height_m


def estimate_perspective(
    mask: np.ndarray,
    *,
    image_rgb: np.ndarray | None = None,
    exif_focal_px: float | None = None,
    focal_ratio: float = FOCAL_RATIO,
    camera_height_m: float = CAMERA_HEIGHT_M,
) -> PerspectiveEstimate | None:
    """Plan du sol : horizon, point de fuite, échelle — et ce que chacun vaut.

    Trois sources d'horizon, de la plus riche à la plus pauvre : les droites de
    la photo (`camera_geometry`), les deux rails du masque, le mur du fond. La
    focale vient de l'EXIF quand il la déclare, des points de fuite quand la
    photo en montre deux perpendiculaires, et d'un a priori sinon — avec
    `metric_scale_confidence` qui dit lequel des trois a servi.

    Le quadrilatère rendu est un rectangle du sol vu en perspective : ses deux
    côtés fuient vers le point de fuite, ses deux autres sont horizontaux à
    l'image. Un rectangle aligné sur l'axe de visée, donc — la rotation du
    motif se règle ensuite, librement, dans le moteur.

    Sans `image_rgb`, le comportement est celui du LOT PHOTO.1 (rails seuls),
    ce qui garde les tests de géométrie synthétique valides.
    """
    hauteur, largeur = mask.shape[:2]
    if mask.mean() < MIN_COVERAGE:
        return None
    notes: list[str] = []

    colonnes = mask.any(axis=0)
    if colonnes.sum() < largeur * 0.1:
        return None
    # Première rangée de sol par colonne : le bord haut, c'est-à-dire le mur
    # du fond (ou ce qui en tient lieu).
    y_top = np.where(colonnes, mask.argmax(axis=0), hauteur)
    y_top_valides = y_top[colonnes]
    far_edge_px = float(np.percentile(y_top_valides, 15))
    # Dernière rangée de sol de l'image.
    lignes = mask.any(axis=1)
    y_bas_px = int(np.max(np.nonzero(lignes)[0]))

    # --- Horizon : droites de l'image, rails du masque, ou repli ------------
    rails = _rails_vanishing_point(mask, far_edge_px, y_bas_px, notes)
    cam: CameraEstimate | None = None
    if image_rgb is not None:
        try:
            cam = estimate_camera(image_rgb, floor_mask=mask)
            notes.extend(cam.notes)
        except (cv2.error, ValueError, np.linalg.LinAlgError) as exc:
            # La lecture des droites est un bonus de mesure, jamais une
            # condition : si OpenCV refuse l'image, on retombe sur les rails.
            notes.append(f"droites illisibles ({type(exc).__name__}), rails seuls")
    horizon_px, vx_px, method, confiance, mesure = _choose_horizon(
        rails, cam, far_edge_px, largeur, hauteur, notes
    )
    vanishing: tuple[float, float] | None = (
        (vx_px / largeur, horizon_px / hauteur) if mesure else None
    )

    # Bornes de sanité. Un horizon hors de cette plage n'est pas une photo de
    # pièce prise debout.
    borne_bas, borne_haut = 0.12 * hauteur, 0.75 * hauteur
    if horizon_px < borne_bas or horizon_px > borne_haut:
        notes.append("horizon borné")
        horizon_px = float(np.clip(horizon_px, borne_bas, borne_haut))
        confiance -= 0.1

    # --- Quadrilatère : rectangle du sol dans l'axe de visée -----------------
    y_near = 1.08 * hauteur
    y_farq = max(far_edge_px - 0.004 * hauteur, horizon_px + 0.05 * hauteur)
    xnl, xnr = -0.08 * largeur, 1.08 * largeur

    def rail(xn: float, y: float) -> float:
        return float(vx_px + (xn - vx_px) * (y - horizon_px) / (y_near - horizon_px))

    quad_px = [
        (rail(xnl, y_farq), y_farq),
        (rail(xnr, y_farq), y_farq),
        (xnr, y_near),
        (xnl, y_near),
    ]
    quad = [(x / largeur, y / hauteur) for x, y in quad_px]

    # --- Focale : EXIF, points de fuite, ou a priori -------------------------
    if exif_focal_px is not None and exif_focal_px > 0:
        f, focal_source, metric = float(exif_focal_px), "exif", "medium"
    elif cam is not None and cam.focal_px is not None:
        f, focal_source, metric = float(cam.focal_px), "vanishing-points", "medium"
    else:
        f, focal_source, metric = focal_ratio * largeur, "prior", "low"
        notes.append("focale supposée, échelle métrique indicative")

    # --- Échelle : sténopé ---------------------------------------------------
    #
    # z = f·H / d pour un point du sol à d pixels sous l'horizon. La largeur
    # ne dépend que de H ; la profondeur, et donc le rapport profondeur /
    # largeur qui comprime ou étire le motif, dépend de f. C'est pour cela
    # que la focale est mesurée quand elle peut l'être.
    d_near = y_near - horizon_px
    d_far = y_farq - horizon_px
    z_near = f * camera_height_m / d_near
    z_far = f * camera_height_m / d_far
    depth = z_far - z_near
    width = (xnr - xnl) / f * z_near
    w_m = float(np.clip(width, 1.5, 14.0))
    d_m = float(np.clip(depth, 0.8, 20.0))
    if w_m != width or d_m != depth:
        notes.append("échelle bornée")
        confiance -= 0.05
        metric = "low"

    # --- Plausibilité : la géométrie obtenue est-elle celle d'une pièce ? ----
    rapport = d_m / w_m
    d_mid = 0.5 * (d_near + d_far)
    plausibility: dict[str, Any] = {
        "depthOverWidth": round(rapport, 2),
        "projectedPlankWidthPx": {
            "near": round(_projected_plank_px(hauteur - horizon_px, camera_height_m), 1),
            "mid": round(_projected_plank_px(d_mid, camera_height_m), 1),
            "far": round(_projected_plank_px(d_far, camera_height_m), 1),
        },
        "referencePlankM": REFERENCE_PLANK_M,
        "ok": True,
    }
    if rapport > DEPTH_OVER_WIDTH_MAX or rapport < 0.2:
        plausibility["ok"] = False
        notes.append(f"rapport profondeur/largeur {rapport:.1f} hors d'une pièce ordinaire")
        confiance -= 0.1
        metric = "low"
    if plausibility["projectedPlankWidthPx"]["far"] < 1.5:
        notes.append("lame de référence sous 1,5 px au fond : motif illisible là-bas")

    return PerspectiveEstimate(
        horizon=horizon_px / hauteur,
        vanishing=vanishing,
        method=method,
        far_edge=far_edge_px / hauteur,
        quad=quad,
        meters=(round(w_m, 2), round(d_m, 2)),
        focal_px=round(f, 1),
        camera_height_m=camera_height_m,
        confidence=float(np.clip(confiance, 0.0, 1.0)),
        notes=notes,
        focal_source=focal_source,
        metric_scale_confidence=metric,
        plausibility=plausibility,
        camera=(
            {
                "horizon": None if cam.horizon is None else round(cam.horizon, 4),
                "horizonSource": cam.horizon_source,
                "horizonConfidence": round(cam.horizon_confidence, 2),
                "focalPx": None if cam.focal_px is None else round(cam.focal_px, 1),
                "segments": cam.segments,
                "vanishingPoints": [p.as_dict(largeur, hauteur) for p in cam.vanishing_points],
            }
            if cam is not None
            else {}
        ),
    )


# ---------------------------------------------------------------------------
# 3. Contours, tapis, confiance
# ---------------------------------------------------------------------------


def _normaliser(contour: np.ndarray, largeur: int, hauteur: int) -> list[Point]:
    return [
        Point(x=float(p[0][0]) / (largeur - 1), y=float(p[0][1]) / (hauteur - 1)) for p in contour
    ]


def mask_zones(
    mask: np.ndarray, *, epsilon_ratio: float = 0.0015, max_zones: int = 3
) -> list[tuple[list[Point], list[list[Point]]]]:
    """Composantes extérieures du sol, chacune avec ses trous.

    Plusieurs zones quand le sol visible est coupé en morceaux — un canapé au
    milieu, une porte ouverte. Elles partagent toutes le même plan : c'est le
    même sol, vu en plusieurs fois.
    """
    hauteur, largeur = mask.shape[:2]
    contours, hierarchie = cv2.findContours(
        mask.astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE
    )
    if hierarchie is None:
        return []
    eps = epsilon_ratio * max(largeur, hauteur)
    hier = hierarchie[0]
    exterieurs = [
        (i, cv2.contourArea(c))
        for i, c in enumerate(contours)
        if hier[i][3] == -1 and cv2.contourArea(c) >= mask.size * 0.01
    ]
    exterieurs.sort(key=lambda t: -t[1])
    zones: list[tuple[list[Point], list[list[Point]]]] = []
    for i, _ in exterieurs[:max_zones]:
        ext = _normaliser(cv2.approxPolyDP(contours[i], eps, True), largeur, hauteur)
        if len(ext) < 3:
            continue
        trous: list[list[Point]] = []
        enfant = hier[i][2]
        while enfant != -1:
            c = contours[enfant]
            if cv2.contourArea(c) >= mask.size * 0.0005:
                trou = _normaliser(cv2.approxPolyDP(c, eps, True), largeur, hauteur)
                if len(trou) >= 3:
                    trous.append(trou)
            enfant = hier[enfant][0]
        zones.append((ext, trous))
    return zones


def rug_occluders(labels: np.ndarray | None, *, min_ratio: float = 0.002) -> list[Occluder]:
    """Tapis vus par la sémantique ADE20K — **signal non validé**.

    Le corpus officiel ne contient aucun tapis : rien ici n'a été mesuré
    contre une vérité. On s'en sert parce que la classe existe et que c'est
    mieux que de peindre par-dessus un tapis, pas parce qu'on sait qu'elle est
    juste.
    """
    if labels is None:
        return []
    tapis = labels == ADE20K_RUG
    if not tapis.any():
        return []
    hauteur, largeur = tapis.shape[:2]
    contours, _ = cv2.findContours(
        tapis.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    occ: list[Occluder] = []
    for n, c in enumerate(contours):
        if cv2.contourArea(c) < tapis.size * min_ratio:
            continue
        poly = _normaliser(
            cv2.approxPolyDP(c, 0.002 * max(largeur, hauteur), True), largeur, hauteur
        )
        if len(poly) < 3:
            continue
        occ.append(
            Occluder(
                id=f"rug-{n + 1}",
                label="Tapis (expérimental)",
                kind="rug",
                polygon=poly,
                depth=0.6,
                casts_shadow=False,
                feather=0.002,
            )
        )
    return occ


def scene_confidence(persp: PerspectiveEstimate, mask: np.ndarray) -> float:
    """Une confiance qui descend quand quelque chose cloche, jamais l'inverse."""
    c = persp.confidence
    couverture = float(mask.mean())
    if couverture < 0.08:
        c *= 0.6
    elif couverture > 0.65:
        c *= 0.7
    nb, _, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    grosses = sum(1 for i in range(1, nb) if stats[i, cv2.CC_STAT_AREA] >= mask.size * 0.005)
    if grosses > 4:
        c *= 0.85
    # Un sol dont le bord haut est dans le tiers inférieur de l'image : on ne
    # voit presque rien de la pièce. Quand l'horizon ne vient que du masque
    # (rails, ou mur du fond), la perspective est alors mal contrainte et la
    # confiance baisse franchement. Quand il vient des droites de l'image
    # (LOT PHOTO.2), la contrainte est ailleurs que dans le sol : un petit sol
    # visible reste un petit sol, mais sa fuite est mesurée — la baisse est
    # légère, et dit seulement qu'on voit peu de pièce.
    if persp.far_edge > 0.7:
        c *= 0.95 if persp.method == "lines-vp" else 0.8
    return float(np.clip(c, 0.0, 1.0))


# ---------------------------------------------------------------------------
# 4. Décision d'auto-rendu — MISSION STABILISATION
# ---------------------------------------------------------------------------

#: Problèmes qui interdisent l'auto-rendu, quelle que soit la confiance. Chacun
#: décrit une scène que le moteur rendrait FAUSSE — ou ne rendrait pas du tout.
BLOCKING_CHECKS = (
    "non_finite",
    "degenerate_plane",
    "horizon_below_floor",
    "horizon_out_of_frame",
    "non_positive_meters",
    "degenerate_zone",
    "zone_outside_image",
    "geometry_implausible",
    "plank_microscopic",
    "floor_touches_top",
    "fragmented_floor",
    "refiner_rewrote_mask",
)

#: Largeur projetée minimale d'une lame de 92 mm AU PREMIER PLAN, en pixels de
#: l'image analysée. Sous ce seuil, le motif est illisible là même où il devrait
#: être le plus grand : la projection est incohérente, pas seulement l'échelle.
MIN_NEAR_PLANK_PX = 6.0


def _finite(*valeurs: float) -> bool:
    return all(math.isfinite(v) for v in valeurs)


def validate_scene(
    scene: SceneData,
    persp: PerspectiveEstimate,
    raw_mask: np.ndarray,
    refined_mask: np.ndarray,
) -> dict[str, bool]:
    """Contrôles d'une scène AVANT tout rendu automatique.

    Rend `{code: échoué}` pour chaque contrôle. Tous sont généraux : ils lisent
    la scène, le masque et la perspective — jamais le nom d'une photo.
    """
    checks: dict[str, bool] = {}
    plan = scene.planes["sol"]
    coords = [v for p in plan.quad for v in (p.x, p.y)]
    zone_pts = [(p.x, p.y) for z in scene.floor_zones for p in z.mask.polygon]
    trous = [(p.x, p.y) for z in scene.floor_zones for t in z.mask.holes for p in t]
    checks["non_finite"] = not _finite(
        *coords,
        persp.horizon,
        plan.meters.width,
        plan.meters.depth,
        *[v for xy in zone_pts + trous for v in xy],
    )
    if checks["non_finite"]:
        return checks

    # Homographie : quadrilatère convexe, d'aire non nulle, coins dans l'ordre
    # fond-gauche, fond-droite, proche-droite, proche-gauche.
    quad = np.array([[p.x, p.y] for p in plan.quad], dtype=np.float32)
    aire = float(cv2.contourArea(quad))
    carre = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], dtype=np.float32)
    det = float(np.linalg.det(cv2.getPerspectiveTransform(carre, quad)))
    checks["degenerate_plane"] = (
        aire < 1e-3
        or not bool(cv2.isContourConvex(quad.reshape(-1, 1, 2)))
        or abs(det) < 1e-9
        or not (quad[0, 1] < quad[3, 1] and quad[1, 1] < quad[2, 1])
    )
    checks["horizon_below_floor"] = not persp.horizon < float(min(quad[0, 1], quad[1, 1]))
    checks["horizon_out_of_frame"] = not (0.05 <= persp.horizon <= 0.85)
    checks["non_positive_meters"] = plan.meters.width <= 0 or plan.meters.depth <= 0

    degenerees = 0
    for z in scene.floor_zones:
        poly = np.array([[p.x, p.y] for p in z.mask.polygon], dtype=np.float32)
        if len(poly) < 3 or float(cv2.contourArea(poly)) < 0.005:
            degenerees += 1
    checks["degenerate_zone"] = degenerees == len(scene.floor_zones)
    checks["zone_outside_image"] = any(
        not (-0.01 <= x <= 1.01 and -0.01 <= y <= 1.01) for x, y in zone_pts
    )

    pl = persp.plausibility or {}
    checks["geometry_implausible"] = pl.get("ok") is False
    pw = pl.get("projectedPlankWidthPx") or {}
    checks["plank_microscopic"] = float(pw.get("near", MIN_NEAR_PLANK_PX)) < MIN_NEAR_PLANK_PX

    # Frontière : un « sol » qui atteint le haut de l'image est un mur ou un
    # plafond pris pour du sol ; un sol en plus de trois grands morceaux est un
    # masque éclaté ; un raffinage qui change plus d'un quart de la surface a
    # réécrit la prédiction au lieu de la nettoyer.
    hauteur = refined_mask.shape[0]
    checks["floor_touches_top"] = bool(refined_mask[: max(1, int(0.04 * hauteur))].any())
    nb, _, stats, _ = cv2.connectedComponentsWithStats(
        refined_mask.astype(np.uint8), connectivity=8
    )
    grandes = sum(1 for i in range(1, nb) if stats[i, cv2.CC_STAT_AREA] >= refined_mask.size * 0.01)
    checks["fragmented_floor"] = grandes > 3
    brut = max(1, int(raw_mask.sum()))
    change = int(np.logical_xor(raw_mask.astype(bool), refined_mask).sum())
    checks["refiner_rewrote_mask"] = change / brut > 0.25
    return checks


def decide(
    confidence: float, min_confidence: float, checks: dict[str, bool]
) -> tuple[str, list[str]]:
    """`auto_render` seulement si la confiance ET tous les contrôles passent.

    Rend le statut et les raisons, lisibles dans `sceneProvenance.decision` :
    une scène proposée à la correction doit pouvoir dire pourquoi.
    """
    raisons = [code for code in BLOCKING_CHECKS if checks.get(code)]
    if confidence < min_confidence:
        raisons.insert(0, "low_confidence")
    return (STATUS_AUTO if not raisons else STATUS_ADJUST), raisons


# ---------------------------------------------------------------------------
# 5. Assemblage
# ---------------------------------------------------------------------------


@dataclass
class ExperimentalScene:
    """Ce que le pipeline renvoie dans `experimental.floor`."""

    scene: SceneData | None
    status: str
    confidence: float | None
    perspective: dict[str, Any]
    rug: dict[str, Any]
    provenance: dict[str, Any]


def build_experimental_scene(
    mask: np.ndarray,
    width: int,
    height: int,
    *,
    labels: np.ndarray | None = None,
    candidate: str = "inconnu",
    min_confidence: float = 0.55,
    image_rgb: np.ndarray | None = None,
    exif_focal_35mm: float | None = None,
) -> ExperimentalScene:
    """Masque → scène expérimentale, statut et confiance.

    Trois issues, et les trois sont honnêtes :

    * `no_floor` : trop peu de sol ou aucune géométrie possible — pas de scène,
      le front dit qu'il faut ajuster ;
    * `needs_manual_adjustment` : une scène existe mais la confiance est sous
      le seuil — le front la montre comme proposition, pas comme résultat ;
    * `auto_render` : scène et confiance suffisante — le parquet se pose, et
      reste corrigible.

    `image_rgb` permet de lire l'horizon et la focale dans les droites de la
    photo (LOT PHOTO.2) ; sans lui, la géométrie vient du masque seul.
    `exif_focal_35mm` est l'équivalent 35 mm déclaré par l'appareil, quand la
    photo le porte : c'est la seule focale réellement mesurée dont on dispose.
    """
    provenance: dict[str, Any] = {
        "pipeline": "EXPERIMENTAL PRODUCT PIPELINE — LOT PHOTO.2",
        "candidate": candidate,
        "modelSelected": False,
        "refiner": "ouverture morphologique petite + filtre de composantes + trous compacts",
        "perspective": None,
        "horizonSources": "droites de l'image (points de fuite) > rails du masque > mur du fond",
        "focalSources": f"EXIF 35 mm > deux points de fuite > a priori {FOCAL_RATIO} × largeur",
        "cameraHeightAssumption": f"{CAMERA_HEIGHT_M} m (toujours supposée)",
        "disclaimer": (
            "EXPERIMENTAL — scène dérivée d'une segmentation exploratoire ; "
            "échelle métrique indicative, voir metricScaleConfidence ; aucun modèle retenu"
        ),
    }
    rug: dict[str, Any] = {
        "status": "EXPERIMENTAL / UNVALIDATED",
        "present": False,
        "areaRatio": 0.0,
    }

    raffine = refine_mask(mask)
    if raffine.mean() < MIN_COVERAGE:
        return ExperimentalScene(None, STATUS_NONE, None, {"method": None}, rug, provenance)

    persp = estimate_perspective(
        raffine,
        image_rgb=image_rgb,
        exif_focal_px=focal_from_exif_35mm(exif_focal_35mm, width, height),
    )
    if persp is None:
        return ExperimentalScene(None, STATUS_NONE, None, {"method": None}, rug, provenance)

    zones = mask_zones(raffine)
    if not zones:
        return ExperimentalScene(None, STATUS_NONE, None, {"method": persp.method}, rug, provenance)

    confiance = scene_confidence(persp, raffine)
    occluders = rug_occluders(labels)
    if labels is not None:
        part = float((labels == ADE20K_RUG).mean())
        rug.update({"present": bool(occluders), "areaRatio": round(part, 4)})

    plan = Plane(
        quad=[Point(x=x, y=y) for x, y in persp.quad],
        meters=Meters(width=persp.meters[0], depth=persp.meters[1]),
    )
    floor_zones = [
        FloorZone(
            id=f"sol-{n + 1}",
            label="Sol détecté" if n == 0 else f"Sol détecté ({n + 1})",
            surface_id="sol",
            plane_ref="sol",
            order=n,
            confidence=confiance,
            mask=Mask(polygon=ext, holes=trous),
        )
        for n, (ext, trous) in enumerate(zones)
    ]
    camera = Camera(
        horizon=round(persp.horizon, 4),
        vanishing_points=(
            [
                VanishingPoint(
                    x=persp.vanishing[0], y=persp.vanishing[1], weight=1.0, role="rails-sol"
                )
            ]
            if persp.vanishing
            else []
        ),
        fov_deg=round(math.degrees(2 * math.atan(width / (2 * persp.focal_px))), 1),
        height_m=persp.camera_height_m,
    )
    warnings = ["experimental_scene", f"perspective_{persp.method}"] + [
        "scale_assumed",
    ]
    if confiance < min_confidence:
        warnings.append("low_confidence")

    scene = SceneData(
        id="photo",
        label="Ma pièce",
        source="ai",
        confidence=round(confiance, 3),
        image=ImageRef(width=width, height=height, alt="Photo importée"),
        camera=camera,
        surfaces=[Surface(id="sol", label="Sol", continuous=True)],
        planes={"sol": plan},
        floor_zones=floor_zones,
        occluders=occluders,
        # Flou un peu plus large que le défaut des scènes calibrées : on ne
        # sait rien de l'ancien revêtement, et un joint ou une veine de
        # l'ancien sol qui réapparaîtrait sous le nouveau est le défaut le
        # plus visible. 0,045 contre 0,035 : mesuré sur le séjour, cela coûte
        # un peu de modelé et retire le fantôme des anciennes lames.
        # `exposure` 0,25 au lieu du 0,55 des pièces calibrées — LOT PHOTO.2.
        # L'ancrage rapproche la clarté du parquet de celle de l'ancien sol.
        # Sur une pièce calibrée, on sait ce qu'était ce sol ; ici non, et un
        # sol foncé l'est par sa MATIÈRE, pas par la lumière. Mesuré sur la
        # petite pièce : un chêne miel tombait à 62 % de sa clarté et se lisait
        # kaki à côté d'une photo orangée, alors que sa teinte était juste
        # (rendu 125/97/53, matière 191/146/92, même rapport R/G).
        light=Light(
            kind="photo-luma",
            strength=1.0,
            blur_radius=0.045,
            ambient=0.22,
            tint=0.5,
            contact=0.4,
            exposure=0.25,
        ),
        warnings=warnings,
    )
    provenance["perspective"] = persp.method
    provenance["focalSource"] = persp.focal_source
    perspective = {
        "method": persp.method,
        "horizon": round(persp.horizon, 4),
        "vanishingPoint": (
            {"x": round(persp.vanishing[0], 4), "y": round(persp.vanishing[1], 4)}
            if persp.vanishing
            else None
        ),
        "farEdge": round(persp.far_edge, 4),
        "metersWidth": persp.meters[0],
        "metersDepth": persp.meters[1],
        "focalPx": persp.focal_px,
        "focalSource": persp.focal_source,
        "metricScaleConfidence": persp.metric_scale_confidence,
        "plausibility": persp.plausibility,
        "camera": persp.camera,
        "notes": persp.notes,
    }
    checks = validate_scene(scene, persp, mask.astype(bool), raffine)
    status, raisons = decide(confiance, min_confidence, checks)
    provenance["decision"] = {
        "status": status,
        "reasons": raisons,
        "confidence": round(confiance, 3),
        "minConfidence": min_confidence,
        "checks": checks,
    }
    if checks.get("non_finite"):
        # Une scène qui porte un NaN ne doit même pas voyager : le front la
        # refuserait, et la proposer à la correction serait mentir.
        return ExperimentalScene(None, STATUS_NONE, None, perspective, rug, provenance)
    if status == STATUS_ADJUST and "low_confidence" not in (scene.warnings or []):
        scene.warnings = [*(scene.warnings or []), "needs_manual_adjustment"]
    return ExperimentalScene(scene, status, round(confiance, 3), perspective, rug, provenance)
