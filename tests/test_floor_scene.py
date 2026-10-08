"""La scène EXPÉRIMENTALE dérivée d'un masque — LOT PHOTO.1.

Ce que ces tests protègent : qu'un masque devienne une scène que le moteur
sait lire, que la géométrie soit celle qu'on croit (ordre des coins, horizon
au-dessus du mur du fond, mètres plausibles), que le raffineur ne mange pas un
pied de chaise, et que les trois statuts tombent là où ils doivent.

Ce qu'ils ne mesurent pas : la justesse de la perspective sur une vraie
photo. Il n'y a pas de vérité terrain pour cela, et un test qui prétendrait
en avoir une mentirait.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.schemas.scene_data import SceneData
from app.services.floor_scene import (
    STATUS_ADJUST,
    STATUS_AUTO,
    STATUS_NONE,
    build_experimental_scene,
    estimate_perspective,
    mask_zones,
    refine_mask,
    rug_occluders,
)

W, H = 640, 480


def _sol_trapeze(largeur: int = W, hauteur: int = H, y_fond: int = 230) -> np.ndarray:
    """Un sol de pièce rectangulaire vu de face : trapèze qui fuit vers (w/2, 0.35h)."""
    m = np.zeros((hauteur, largeur), dtype=bool)
    vx, vy = largeur / 2, 0.35 * hauteur
    for y in range(y_fond, hauteur):
        t = (y - vy) / (hauteur - vy)
        xl = int(vx + (-0.1 * largeur - vx) * t)
        xr = int(vx + (1.1 * largeur - vx) * t)
        m[y, max(0, xl) : min(largeur, xr)] = True
    return m


# --- Raffineur ------------------------------------------------------------


def test_le_raffineur_retire_les_miettes_et_garde_le_sol() -> None:
    m = _sol_trapeze()
    bruit = m.copy()
    bruit[20:24, 30:34] = True  # une miette loin du sol
    r = refine_mask(bruit)
    assert not r[20:24, 30:34].any(), "la miette a disparu"
    assert r[400, 320], "le sol est toujours là"


def test_le_raffineur_bouche_un_petit_trou_compact() -> None:
    m = _sol_trapeze()
    m[400:406, 300:306] = False  # 6×6 px : bruit de prédiction
    r = refine_mask(m)
    assert r[403, 303], "un trou minuscule et compact est rebouché"


def test_le_raffineur_ne_bouche_pas_un_pied_de_chaise() -> None:
    """Un trou allongé est un objet fin : il reste un trou."""
    m = _sol_trapeze()
    m[330:440, 300:306] = False  # 110×6 px : un pied
    r = refine_mask(m)
    assert not r[380, 302], "le pied de chaise est préservé"
    assert r[380, 320], "le sol autour est intact"


# --- Perspective ----------------------------------------------------------


def test_deux_rails_visibles_donnent_un_point_de_fuite() -> None:
    p = estimate_perspective(_sol_trapeze())
    assert p is not None
    assert p.method == "vanishing-point"
    assert p.vanishing is not None
    # Le trapèze fuit vers (0.5, 0.35) : on doit le retrouver, à peu près.
    assert abs(p.vanishing[0] - 0.5) < 0.05
    assert abs(p.horizon - 0.35) < 0.05
    assert p.confidence >= 0.5


def test_l_ordre_des_coins_est_celui_du_moteur() -> None:
    """fond-gauche, fond-droite, proche-droite, proche-gauche — sans quoi
    `squareToQuad` du front rend une perspective à l'envers."""
    p = estimate_perspective(_sol_trapeze())
    assert p is not None
    fg, fd, pd, pg = p.quad
    assert fg[1] == fd[1] < pd[1] == pg[1], "le fond est au-dessus du proche"
    assert fg[0] < fd[0] and pg[0] < pd[0], "gauche à gauche, droite à droite"
    assert fd[0] - fg[0] < pd[0] - pg[0], "le fond est plus étroit : ça fuit"
    assert p.horizon < fg[1], "l'horizon est au-dessus du mur du fond"


def test_sans_rails_l_horizon_est_suppose_et_la_confiance_le_dit() -> None:
    """Sol qui touche les deux bords du cadre : aucun rail à ajuster."""
    m = np.zeros((H, W), dtype=bool)
    m[260:, :] = True
    p = estimate_perspective(m)
    assert p is not None
    assert p.method == "far-edge-fallback"
    assert p.vanishing is None
    assert p.confidence < 0.5
    assert p.horizon < 260 / H


def test_les_metres_sont_plausibles_pour_une_piece() -> None:
    p = estimate_perspective(_sol_trapeze())
    assert p is not None
    w, d = p.meters
    assert 1.5 <= w <= 14.0
    assert 0.8 <= d <= 20.0


def test_trop_peu_de_sol_ne_donne_aucune_perspective() -> None:
    m = np.zeros((H, W), dtype=bool)
    m[470:, 300:340] = True
    assert estimate_perspective(m) is None


# --- Zones, tapis ---------------------------------------------------------


def test_les_zones_portent_leurs_trous() -> None:
    m = _sol_trapeze()
    m[380:420, 280:360] = False  # un trou franc, un pied de table carré
    zones = mask_zones(m)
    assert len(zones) == 1
    ext, trous = zones[0]
    assert len(ext) >= 4
    assert len(trous) == 1


def test_le_tapis_devient_un_occulteur_marque_experimental() -> None:
    labels = np.zeros((H, W), dtype=np.int32)
    labels[300:400, 200:400] = 28  # rug;carpet
    occ = rug_occluders(labels)
    assert len(occ) == 1
    assert occ[0].kind == "rug"
    assert "expérimental" in occ[0].label.lower()
    assert rug_occluders(None) == []


# --- Assemblage -----------------------------------------------------------


def test_une_scene_valide_est_produite_et_se_relit() -> None:
    s = build_experimental_scene(_sol_trapeze(), W, H, candidate="test", min_confidence=0.5)
    assert s.status == STATUS_AUTO
    assert s.scene is not None
    #: Elle doit repasser par le modèle : c'est ce que le front fera.
    relue = SceneData.model_validate(s.scene.model_dump(by_alias=True))
    assert relue.floor_zones[0].plane is not None, "planeRef résolu"
    assert relue.source == "ai"
    assert "experimental_scene" in relue.warnings
    assert s.provenance["modelSelected"] is False
    assert s.rug["status"].startswith("EXPERIMENTAL")


def test_le_statut_descend_quand_la_confiance_est_basse() -> None:
    s = build_experimental_scene(_sol_trapeze(), W, H, min_confidence=0.99)
    assert s.status == STATUS_ADJUST
    assert s.scene is not None, "la scène existe quand même : elle se corrige"
    assert "low_confidence" in (s.scene.warnings or [])


def test_aucun_sol_donne_no_floor_sans_scene() -> None:
    s = build_experimental_scene(np.zeros((H, W), dtype=bool), W, H)
    assert s.status == STATUS_NONE
    assert s.scene is None
    assert s.confidence is None


def test_la_lumiere_de_la_scene_ia_floute_plus_large() -> None:
    """On ne sait rien de l'ancien sol : le fantôme de ses lames est le défaut
    le plus visible, et le flou est le réglage qui l'écarte."""
    s = build_experimental_scene(_sol_trapeze(), W, H)
    assert s.scene is not None
    assert s.scene.light.blur_radius > 0.035


@pytest.mark.parametrize("taille", [(480, 640), (1067, 1600), (720, 720)])
def test_la_geometrie_tient_a_toutes_les_resolutions(taille: tuple[int, int]) -> None:
    h, w = taille
    m = _sol_trapeze(w, h, y_fond=int(0.48 * h))
    s = build_experimental_scene(m, w, h)
    assert s.scene is not None
    for p in s.scene.planes["sol"].quad:
        assert -0.5 < p.x < 1.5 and -0.5 < p.y < 1.5


def test_l_exposition_des_scenes_photo_est_moderee() -> None:
    """LOT PHOTO.2 : un sol d'origine foncé l'est par sa matière, pas par la
    lumière. L'ancrage d'exposition des scènes photo reste donc sous celui des
    pièces calibrées (0,55 côté front)."""
    s = build_experimental_scene(_sol_trapeze(), W, H)
    assert s.scene is not None
    assert s.scene.light.exposure is not None
    assert s.scene.light.exposure < 0.55
    assert s.scene.light.contact_shadow > 0


# --- Décision combinée d'auto-rendu (MISSION STABILISATION) ---------------


def test_la_decision_est_expliquee_et_auto_quand_tout_passe() -> None:
    s = build_experimental_scene(_sol_trapeze(), W, H, min_confidence=0.5)
    d = s.provenance["decision"]
    assert s.status == STATUS_AUTO
    assert d["status"] == STATUS_AUTO and d["reasons"] == []
    assert not any(d["checks"].values())


def test_un_sol_qui_monte_jusqu_en_haut_n_est_pas_auto_rendu() -> None:
    """Un « sol » qui touche le haut de l'image est un mur pris pour du sol."""
    m = _sol_trapeze()
    m[0:40, 200:440] = True
    s = build_experimental_scene(m, W, H, min_confidence=0.0)
    assert s.status == STATUS_ADJUST
    assert "floor_touches_top" in s.provenance["decision"]["reasons"]
    assert s.scene is not None, "la scène reste proposée à la correction"


def test_un_sol_eclate_n_est_pas_auto_rendu() -> None:
    m = np.zeros((H, W), dtype=bool)
    for k in range(5):
        m[300:470, 20 + k * 125 : 120 + k * 125] = True
    s = build_experimental_scene(m, W, H, min_confidence=0.0)
    assert s.status != STATUS_AUTO
    if s.scene is not None:
        assert "fragmented_floor" in s.provenance["decision"]["reasons"]


def test_la_confiance_basse_reste_une_raison_nommee() -> None:
    s = build_experimental_scene(_sol_trapeze(), W, H, min_confidence=0.99)
    assert s.provenance["decision"]["reasons"][0] == "low_confidence"
