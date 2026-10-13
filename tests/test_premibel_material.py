"""Extraction des matières Premibel exactes, sur des images synthétiques.

Aucune photo produit ici : elles ne sont pas versionnées. On fabrique des
sols dont on connaît la vérité (aspect, position des joints) et on vérifie
que l'extraction la retrouve — et qu'elle refuse ce qu'elle doit refuser.
"""

import math

import cv2
import numpy as np

from scripts import import_premibel_material as imp


def _projeter(points_m: np.ndarray, f: float, largeur: int, hauteur: int) -> np.ndarray:
    """Caméra à 1,5 m au-dessus d'un sol, inclinée de 35°, vers +y."""
    tilt = math.radians(35)
    out = []
    for x, y in points_m:
        # repère caméra : x à droite, y vers le bas de l'image, z devant
        pz = y * math.cos(tilt) + 1.5 * math.sin(tilt)
        py = -y * math.sin(tilt) + 1.5 * math.cos(tilt)
        out.append([largeur / 2 + f * x / pz, hauteur / 2 + f * py / pz])
    return np.array(out)


def test_aspect_d_un_rectangle_vu_en_perspective():
    largeur, hauteur = 1200, 900
    f = largeur / (2 * math.tan(math.radians(imp.CHAMP_SUPPOSE_DEG) / 2))
    # rectangle 0,5 m de large (en x), 1,5 m de long (en y) : aspect 3
    debut, fin = 1.0, 2.5
    quad_m = np.array([[-0.25, debut], [0.25, debut], [0.25, fin], [-0.25, fin]])
    quad = _projeter(quad_m, f, largeur, hauteur)
    aspect, origine = imp.rapport_aspect(quad, largeur, hauteur)
    assert abs(aspect - 3.0) / 3.0 < 0.05, (aspect, origine)


def _parquet(n_lames: int, haut_lame: int = 40, long: int = 400) -> np.ndarray:
    rng = np.random.default_rng(3)
    img = np.full((n_lames * haut_lame, long), 170, np.float32)
    img += rng.normal(0, 6, img.shape)  # veinage
    for k in range(1, n_lames):
        img[k * haut_lame - 1 : k * haut_lame + 1, :] = 70  # joints longs
    return np.clip(img, 0, 255).astype(np.uint8)


def test_les_joints_longs_sont_retrouves():
    gris = _parquet(3)
    joints = imp.joints_longs(gris, 3)
    assert all(abs(j - v) <= 2 for j, v in zip(joints, [40, 80], strict=True)), joints


def test_la_largeur_de_lame_est_estimee_sans_compte_donne():
    assert abs(imp.periode_lames(_parquet(6)) - 40) <= 3


def test_un_joint_interieur_ecarte_le_morceau_mais_pas_une_fissure():
    lame = _parquet(1, haut_lame=40, long=400)
    avec_joint = lame.copy()
    avec_joint[19:21, :] = 70  # joint sur toute la longueur
    fissure = lame.copy()
    fissure[19:21, 40:140] = 60  # fissure sur un quart de la longueur
    assert imp.joint_interieur(avec_joint)
    assert not imp.joint_interieur(fissure)
    assert not imp.joint_interieur(lame)


def test_un_joint_de_bout_coupe_la_lame():
    lame = _parquet(1, haut_lame=40, long=400)
    lame[:, 199:201] = 60
    assert any(abs(c - 200) <= 2 for c in imp.joints_de_bout(lame))


def _rapport(n: int, longueur_mm: float, ppm: float, lame_m: float = 1.0) -> imp.Rapport:
    r = imp.Rapport("TEST", longueur_lame_m=lame_m)
    for i in range(n):
        r.morceaux.append(imp.Morceau(np.zeros((10, 10, 3), np.uint8), ppm, longueur_mm, i))
    return r


def test_la_validation_refuse_ce_qui_ne_suffit_pas():
    assert imp.valider(_rapport(5, 400, 0.5)) == []
    assert any("px/mm" in x for x in imp.valider(_rapport(5, 400, 0.2)))
    assert any("morceau" in x for x in imp.valider(_rapport(3, 800, 0.5)))
    assert any("m de bois" in x for x in imp.valider(_rapport(4, 300, 0.5)))
    # assez de morceaux mais moins de bois qu'une longueur de lame
    assert any("longueur de lame" in x for x in imp.valider(_rapport(4, 400, 0.5, lame_m=1.9)))


def test_l_egalisation_garde_la_teinte_et_retire_le_gradient():
    h, w = 40, 400
    degrade = np.linspace(0.6, 1.4, w, dtype=np.float32)[None, :, None]
    bois = np.full((h, w, 3), (60, 110, 160), np.float32) * degrade
    sortie = imp.egaliser(np.clip(bois, 0, 255).astype(np.uint8)).astype(np.float32)
    gauche, droite = sortie[:, :40].mean(), sortie[:, -40:].mean()
    assert abs(gauche - droite) / max(gauche, droite) < 0.12
    b, g, r = sortie.reshape(-1, 3).mean(axis=0)
    assert b < g < r  # la teinte (chaude) est gardée
    assert cv2.cvtColor(sortie.astype(np.uint8), cv2.COLOR_BGR2GRAY).std() < 25
