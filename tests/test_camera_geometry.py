"""Horizon et focale lus dans les droites — LOT PHOTO.2.

Ce que ces tests protègent : qu'une pièce synthétique dont on connaît la
caméra rende l'horizon et la focale qu'on y a mis, que le masque de sol
serve bien à REJETER un horizon posé dans le sol, et que la fusion avec les
rails du masque tranche dans le sens voulu quand les deux se contredisent.

Ce qu'ils ne mesurent pas : la justesse sur de vraies photos. Elle se lit
dans `review/photo-mode-v2/geometry-bench.md`, hors Git, et à l'œil.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from app.services.camera_geometry import (
    FOCAL_PRIOR_RATIO,
    Segment,
    detect_segments,
    estimate_camera,
    find_vanishing_points,
    focal_from_exif_35mm,
    focal_from_vanishing_points,
)
from app.services.floor_scene import estimate_perspective

W, H = 1200, 800


def _projette(f: float, horizon_y: float, pan_deg: float):
    """Une caméra sténopé sans roulis : X à droite, Y vers le bas, Z devant.

    L'horizon à `horizon_y` donne l'inclinaison ; `pan_deg` tourne la pièce
    autour de la verticale pour que ses deux directions horizontales fuient
    toutes les deux vers des points finis.
    """
    cx, cy = W / 2, H / 2
    tilt = np.arctan((cy - horizon_y) / f)  # positif : caméra penchée vers le bas
    pan = np.radians(pan_deg)

    def point(x: float, y: float, z: float) -> tuple[float, float] | None:
        # Monde → caméra : rotation pan (autour de Y), puis tilt (autour de X).
        xr = x * np.cos(pan) + z * np.sin(pan)
        zr = -x * np.sin(pan) + z * np.cos(pan)
        yc = y * np.cos(tilt) - zr * np.sin(tilt)
        zc = y * np.sin(tilt) + zr * np.cos(tilt)
        if zc <= 0.05:
            return None
        return (cx + f * xr / zc, cy + f * yc / zc)

    return point


def _piece_synthetique(f: float = 760.0, horizon_y: float = 330.0, pan_deg: float = 28.0):
    """Une boîte filaire : arêtes sol/mur, plinthes, cadres, le tout bien droit."""
    image = np.full((H, W), 235, dtype=np.uint8)
    proj = _projette(f, horizon_y, pan_deg)
    segments: list[tuple[tuple[float, float, float], tuple[float, float, float]]] = []
    # Sol : y = +1,5 (caméra à 1,5 m au-dessus). Lignes parallèles à X et à Z.
    for z in (2.0, 3.0, 4.0, 5.5, 7.0):
        segments.append(((-4.0, 1.5, z), (4.0, 1.5, z)))
        segments.append(((-4.0, 0.4, z), (4.0, 0.4, z)))  # un rail à mi-hauteur
    for x in (-3.0, -1.5, 0.0, 1.5, 3.0):
        segments.append(((x, 1.5, 1.5), (x, 1.5, 8.0)))
        segments.append(((x, -0.8, 1.5), (x, -0.8, 8.0)))  # corniche
    # Quelques verticales : elles doivent être ignorées pour l'horizon.
    for x in (-2.0, 1.0):
        segments.append(((x, 1.5, 3.0), (x, -1.0, 3.0)))
    for a, b in segments:
        pa, pb = proj(*a), proj(*b)
        if pa is None or pb is None:
            continue
        cv2.line(image, (int(pa[0]), int(pa[1])), (int(pb[0]), int(pb[1])), 40, 2, cv2.LINE_AA)
    return cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)


# --- Briques --------------------------------------------------------------


def test_les_segments_d_une_scene_filaire_sont_detectes() -> None:
    gris = cv2.cvtColor(_piece_synthetique(), cv2.COLOR_RGB2GRAY)
    segs = detect_segments(gris)
    assert len(segs) >= 12
    assert all(s.length > 0 for s in segs)


def test_la_focale_vient_de_deux_points_perpendiculaires() -> None:
    """f² = −(v₁ − c)·(v₂ − c) : vérifié sur deux points construits exprès."""
    f = 700.0
    cx, cy = W / 2, H / 2
    v1 = (cx + 500.0, cy)
    v2 = (cx - f * f / 500.0, cy)
    estime = focal_from_vanishing_points(v1, v2, W, H)
    assert estime is not None
    assert abs(estime - f) < 1e-6


def test_deux_points_du_meme_cote_ne_donnent_aucune_focale() -> None:
    cx, cy = W / 2, H / 2
    assert focal_from_vanishing_points((cx + 500, cy), (cx + 3000, cy), W, H) is None


def test_la_focale_exif_suit_le_grand_cote() -> None:
    assert focal_from_exif_35mm(26.0, 1600, 1067) == pytest.approx(26 / 36 * 1600)
    assert focal_from_exif_35mm(26.0, 1067, 1600) == pytest.approx(26 / 36 * 1600)
    assert focal_from_exif_35mm(None, 1600, 1067) is None
    assert focal_from_exif_35mm(0.0, 1600, 1067) is None


def test_les_verticales_ne_posent_pas_de_point_de_fuite() -> None:
    verticales = [Segment(100 + 50 * i, 100, 100 + 50 * i + 2, 700) for i in range(10)]
    assert find_vanishing_points(verticales, W, H) == []


# --- La scène entière -----------------------------------------------------


def test_l_horizon_et_la_focale_d_une_piece_connue_sont_retrouves() -> None:
    f, horizon_y = 760.0, 330.0
    cam = estimate_camera(_piece_synthetique(f, horizon_y))
    assert cam.horizon is not None
    assert abs(cam.horizon * H - horizon_y) < 0.02 * H, f"horizon {cam.horizon * H:.0f}"
    assert cam.focal_px is not None
    assert abs(cam.focal_px - f) / f < 0.12, f"focale {cam.focal_px:.0f} vs {f}"
    assert cam.focal_source == "vanishing-points"


def test_l_estimation_est_deterministe() -> None:
    image = _piece_synthetique()
    a = estimate_camera(image)
    b = estimate_camera(image)
    assert a.horizon == b.horizon and a.focal_px == b.focal_px


def test_un_horizon_dans_le_sol_est_refuse() -> None:
    """Le masque ne sert qu'à rejeter : un sol dont le bord haut est au-dessus
    de l'horizon mesuré rend cet horizon impossible."""
    image = _piece_synthetique(horizon_y=330.0)
    masque = np.zeros((H, W), dtype=bool)
    masque[200:, :] = True  # du « sol » bien au-dessus de l'horizon à 330
    cam = estimate_camera(image, floor_mask=masque)
    assert cam.horizon is None or cam.horizon * H <= 200 - 0.02 * H


def test_une_image_sans_droites_ne_mesure_rien() -> None:
    rng = np.random.default_rng(3)
    bruit = rng.integers(0, 255, size=(H, W, 3), dtype=np.uint8)
    cam = estimate_camera(bruit)
    assert cam.horizon is None
    assert cam.focal_px is None


# --- Fusion avec les rails du masque -------------------------------------


def _sol_trapeze(y_fond: int, vy: float, vx: float = W / 2) -> np.ndarray:
    m = np.zeros((H, W), dtype=bool)
    for y in range(y_fond, H):
        t = (y - vy) / (H - vy)
        xl = int(vx + (-0.1 * W - vx) * t)
        xr = int(vx + (1.1 * W - vx) * t)
        m[y, max(0, xl) : min(W, xr)] = True
    return m


def test_les_droites_de_l_image_corrigent_des_rails_trompeurs() -> None:
    """Le cas de la revue : un rail de masque qui suit un meuble pose
    l'horizon au milieu de la pièce. Les droites de la photo le contredisent,
    et ce sont elles qu'on garde."""
    image = _piece_synthetique(f=760.0, horizon_y=330.0)
    # Un masque dont les rails fuient vers 0,62 h : faux, mais parfaitement ajusté.
    masque = _sol_trapeze(y_fond=560, vy=0.62 * H)
    sans = estimate_perspective(masque)
    avec = estimate_perspective(masque, image_rgb=image)
    assert sans is not None and avec is not None
    assert abs(sans.horizon * H - 0.62 * H) < 0.03 * H, "les rails seuls croient le meuble"
    assert abs(avec.horizon * H - 330.0) < 0.04 * H, "les droites rétablissent l'horizon"
    assert avec.method == "lines-vp"
    assert any("contredits" in n for n in avec.notes)


def test_la_focale_mesuree_remplace_l_a_priori_et_le_dit() -> None:
    image = _piece_synthetique(f=760.0, horizon_y=330.0)
    masque = _sol_trapeze(y_fond=420, vy=330.0)
    p = estimate_perspective(masque, image_rgb=image)
    assert p is not None
    assert p.focal_source == "vanishing-points"
    assert p.metric_scale_confidence == "medium"
    assert abs(p.focal_px - 760.0) / 760.0 < 0.12


def test_sans_image_la_focale_est_l_a_priori_et_l_echelle_est_basse() -> None:
    p = estimate_perspective(_sol_trapeze(y_fond=420, vy=330.0))
    assert p is not None
    assert p.focal_source == "prior"
    assert p.focal_px == pytest.approx(FOCAL_PRIOR_RATIO * W, rel=1e-3)
    assert p.metric_scale_confidence == "low"


def test_l_exif_prime_sur_tout() -> None:
    image = _piece_synthetique()
    masque = _sol_trapeze(y_fond=420, vy=330.0)
    p = estimate_perspective(masque, image_rgb=image, exif_focal_px=900.0)
    assert p is not None
    assert p.focal_source == "exif"
    assert p.focal_px == 900.0


def test_la_plausibilite_est_rapportee() -> None:
    p = estimate_perspective(_sol_trapeze(y_fond=420, vy=330.0))
    assert p is not None
    pw = p.plausibility["projectedPlankWidthPx"]
    assert pw["near"] > pw["mid"] > pw["far"] > 0, "la lame rétrécit vers le fond"
    assert p.plausibility["depthOverWidth"] == pytest.approx(p.meters[1] / p.meters[0], rel=0.02)
