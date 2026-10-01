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
from app.services.floor_segmentation import ADE20K_RUG, clean_mask

#: Focale supposée, en fraction de la largeur d'image. 0,85 ≈ 61° de champ
#: horizontal : le milieu de ce que font les téléphones. Supposée, pas lue.
FOCAL_RATIO = 0.85
#: Hauteur de prise de vue supposée, en mètres. Debout, téléphone à hauteur
#: de poitrine. Même statut : une hypothèse écrite, pas une mesure.
CAMERA_HEIGHT_M = 1.5
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
    method: str  # 'vanishing-point' | 'far-edge-fallback'
    far_edge: float  # y normalisé du mur du fond (bord haut du sol)
    quad: list[tuple[float, float]]  # fond-gauche, fond-droite, proche-droite, proche-gauche
    meters: tuple[float, float]  # largeur, profondeur
    focal_px: float
    camera_height_m: float
    confidence: float
    notes: list[str] = field(default_factory=list)


def _fit_rail(ys: np.ndarray, xs: np.ndarray) -> tuple[float, float, float] | None:
    """Droite x = a·y + b par moindres carrés. Rend (a, b, rms) ou None."""
    if len(ys) < 8:
        return None
    a, b = np.polyfit(ys, xs, 1)
    residus = xs - (a * ys + b)
    return float(a), float(b), float(np.sqrt(np.mean(residus**2)))


def estimate_perspective(
    mask: np.ndarray,
    *,
    focal_ratio: float = FOCAL_RATIO,
    camera_height_m: float = CAMERA_HEIGHT_M,
) -> PerspectiveEstimate | None:
    """Plan du sol depuis le masque seul.

    Les deux bords latéraux du sol — là où ils ne sont pas coupés par le cadre
    — sont ajustés par deux droites. Si les deux existent et se croisent
    au-dessus du mur du fond, leur intersection est le point de fuite, et sa
    hauteur **est** l'horizon. C'est la mesure. Sinon, l'horizon est posé un
    peu au-dessus du mur du fond, et c'est une hypothèse.

    Le quadrilatère rendu est un rectangle du sol vu en perspective : ses deux
    côtés fuient vers le point de fuite, ses deux autres sont horizontaux à
    l'image. Un rectangle aligné sur l'axe de visée, donc — la rotation du
    motif se règle ensuite, librement, dans le moteur.
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

    # Rails gauche et droit : première et dernière colonne de sol par rangée,
    # en ne gardant que les rangées où le bord n'est PAS le cadre.
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

    horizon_px: float
    vx_px: float
    vanishing: tuple[float, float] | None = None
    method = "far-edge-fallback"
    confiance = 0.45

    if ajust_g and ajust_d:
        ag, bg, rg = ajust_g
        ad, bd, rd = ajust_d
        if abs(ag - ad) > 1e-6:
            y_star = (bd - bg) / (ag - ad)
            x_star = ag * y_star + bg
            # Le point de fuite doit être au-dessus du mur du fond, et pas
            # absurdement loin au-dessus de l'image.
            if -0.5 * hauteur < y_star < far_edge_px - 0.02 * hauteur:
                horizon_px, vx_px = float(y_star), float(x_star)
                vanishing = (vx_px / largeur, horizon_px / hauteur)
                method = "vanishing-point"
                rms = (rg + rd) / 2 / largeur
                # 0,01 de la largeur de résidu → pleine confiance ; 0,04 → basse.
                confiance = float(np.clip(0.85 - (rms - 0.01) * 10, 0.5, 0.85))
            else:
                notes.append("point de fuite hors plage, repli sur le mur du fond")
        else:
            notes.append("rails parallèles, repli sur le mur du fond")
    else:
        notes.append("rails latéraux insuffisants, horizon supposé")

    if method == "far-edge-fallback":
        horizon_px = far_edge_px - 0.12 * hauteur
        vx_px = largeur / 2

    # Bornes de sanité. Un horizon hors de cette plage n'est pas une photo de
    # pièce prise debout.
    borne_bas, borne_haut = 0.12 * hauteur, 0.75 * hauteur
    if horizon_px < borne_bas or horizon_px > borne_haut:
        notes.append("horizon borné")
        horizon_px = float(np.clip(horizon_px, borne_bas, borne_haut))
        confiance -= 0.1

    # Quadrilatère : rectangle du sol dans l'axe de visée.
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

    # Échelle : sténopé, focale et hauteur supposées.
    f = focal_ratio * largeur
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
    # voit presque rien de la pièce, la perspective est mal contrainte.
    if persp.far_edge > 0.7:
        c *= 0.8
    return float(np.clip(c, 0.0, 1.0))


# ---------------------------------------------------------------------------
# 4. Assemblage
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
) -> ExperimentalScene:
    """Masque → scène expérimentale, statut et confiance.

    Trois issues, et les trois sont honnêtes :

    * `no_floor` : trop peu de sol ou aucune géométrie possible — pas de scène,
      le front dit qu'il faut ajuster ;
    * `needs_manual_adjustment` : une scène existe mais la confiance est sous
      le seuil — le front la montre comme proposition, pas comme résultat ;
    * `auto_render` : scène et confiance suffisante — le parquet se pose, et
      reste corrigible.
    """
    provenance: dict[str, Any] = {
        "pipeline": "EXPERIMENTAL PRODUCT PIPELINE — LOT PHOTO.1",
        "candidate": candidate,
        "modelSelected": False,
        "refiner": "ouverture morphologique petite + filtre de composantes + trous compacts",
        "perspective": None,
        "focalAssumption": f"f = {FOCAL_RATIO} × largeur d'image",
        "cameraHeightAssumption": f"{CAMERA_HEIGHT_M} m",
        "disclaimer": (
            "EXPERIMENTAL — scène dérivée d'une segmentation exploratoire ; "
            "échelle supposée, pas mesurée ; aucun modèle retenu"
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

    persp = estimate_perspective(raffine)
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
        light=Light(
            kind="photo-luma", strength=1.0, blur_radius=0.045, ambient=0.22, tint=0.5, contact=0.4
        ),
        warnings=warnings,
    )
    provenance["perspective"] = persp.method
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
        "notes": persp.notes,
    }
    status = STATUS_AUTO if confiance >= min_confidence else STATUS_ADJUST
    return ExperimentalScene(scene, status, round(confiance, 3), perspective, rug, provenance)
