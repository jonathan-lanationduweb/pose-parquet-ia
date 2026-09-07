"""Métriques de segmentation, sur des cas dont on connaît la réponse à la main.

Le test qui porte le préambule est
`test_un_contour_decale_reste_bon_en_surface_et_s_effondre_en_contour` : c'est
la raison d'être de la métrique de contour, et le chiffre qu'un IoU seul aurait
caché.
"""

import numpy as np
import pytest

from benchmarks.segmentation import (
    MaskError,
    MetricConfig,
    boundary_metrics,
    evaluate,
    load_mask,
    mask_metrics,
    save_mask,
)

HEIGHT, WIDTH = 400, 600


def _floor() -> np.ndarray:
    """Un sol plausible : le tiers bas de l'image."""
    mask = np.zeros((HEIGHT, WIDTH), dtype=bool)
    mask[250:, :] = True
    return mask


# --- Surface -------------------------------------------------------------


def test_un_masque_parfait_donne_un_sur_toutes_les_metriques():
    truth = _floor()
    metrics = mask_metrics(truth.copy(), truth)

    assert metrics.iou == 1.0
    assert metrics.dice == 1.0
    assert metrics.precision == 1.0
    assert metrics.recall == 1.0
    assert metrics.false_positive == 0
    assert metrics.false_negative == 0


def test_un_masque_vide_ne_trouve_rien_et_n_invente_rien():
    """Rappel nul, et précision **indéfinie** : rien n'a été affirmé."""
    metrics = mask_metrics(np.zeros((HEIGHT, WIDTH), dtype=bool), _floor())

    assert metrics.iou == 0.0
    assert metrics.recall == 0.0
    assert metrics.precision is None, "aucune prédiction : la précision n'a pas de sens"


def test_un_masque_plein_a_un_rappel_parfait_et_une_precision_mediocre():
    """Pourquoi un rappel publié sans sa précision ne veut rien dire."""
    metrics = mask_metrics(np.ones((HEIGHT, WIDTH), dtype=bool), _floor())

    assert metrics.recall == 1.0
    assert metrics.precision == pytest.approx(150 / 400, abs=0.01)
    assert metrics.iou == pytest.approx(0.375, abs=0.01)


def test_un_faux_positif_massif_fait_chuter_la_precision():
    """Le mur pris pour du sol : le rappel reste parfait, la précision tombe."""
    prediction = _floor()
    prediction[100:250, :] = True
    metrics = mask_metrics(prediction, _floor())

    assert metrics.recall == 1.0
    assert metrics.precision == pytest.approx(0.5, abs=0.01)


def test_un_faux_negatif_massif_fait_chuter_le_rappel():
    prediction = _floor()
    prediction[250:330, :] = False
    metrics = mask_metrics(prediction, _floor())

    assert metrics.precision == 1.0
    assert metrics.recall < 0.5


def test_vide_contre_vide_n_est_pas_une_reussite():
    """Sur une scène sans sol visible, une prédiction vide n'est pas parfaite.

    Publier 1,0 ferait grimper la moyenne d'un corpus à chaque scène sans sol.
    `None` dit la vérité : il n'y a rien à mesurer.
    """
    empty = np.zeros((HEIGHT, WIDTH), dtype=bool)
    metrics = mask_metrics(empty, empty)

    assert metrics.iou is None
    assert metrics.dice is None


def test_dice_est_toujours_au_moins_egal_a_l_iou():
    """Propriété mathématique : elle attrape une inversion de formule."""
    for shift in (0, 5, 40, 120):
        metrics = mask_metrics(np.roll(_floor(), -shift, axis=0), _floor())
        assert metrics.iou is not None and metrics.dice is not None
        assert metrics.dice >= metrics.iou - 1e-9


# --- Zones incertaines ---------------------------------------------------


def test_les_pixels_incertains_sortent_du_comptage():
    truth = _floor()
    prediction = truth.copy()
    prediction[300:340, :] = False  # une erreur…

    ignore = np.zeros((HEIGHT, WIDTH), dtype=bool)
    ignore[300:340, :] = True  # …dans une zone déclarée indécidable

    metrics = mask_metrics(prediction, truth, ignore)
    assert metrics.iou == 1.0, "l'erreur est dans une zone exclue : elle ne compte pas"
    assert metrics.ignored_pixels == 40 * WIDTH


def test_la_part_ignoree_est_publiee():
    """Un IoU sur 60 % d'une image ne se lit pas comme un IoU sur 99 %."""
    ignore = np.zeros((HEIGHT, WIDTH), dtype=bool)
    ignore[:100, :] = True
    metrics = mask_metrics(_floor(), _floor(), ignore)

    assert metrics.ignored_fraction == pytest.approx(0.25, abs=0.01)


def test_sans_masque_d_incertitude_rien_n_est_exclu():
    metrics = mask_metrics(_floor(), _floor())
    assert metrics.ignored_pixels == 0
    assert metrics.ignored_fraction == 0.0


def test_un_masque_d_incertitude_de_mauvaises_dimensions_est_refuse():
    with pytest.raises(MaskError, match="incompatible"):
        mask_metrics(_floor(), _floor(), np.zeros((10, 10), dtype=bool))


# --- Contour -------------------------------------------------------------


def test_un_contour_decale_reste_bon_en_surface_et_s_effondre_en_contour():
    """LE test du préambule.

    Un masque décalé de 30 px garde un IoU de 0,67 — un chiffre qu'on lirait
    comme « à peu près juste ». Sa frontière, elle, est ailleurs : et c'est la
    frontière qui fixera le plan de perspective, donc toutes les lames posées.
    """
    truth = _floor()
    shifted = np.roll(truth, -30, axis=0)
    metrics = evaluate(shifted, truth)

    assert metrics.area.iou is not None and metrics.area.iou > 0.6
    assert metrics.boundary.f1 is not None and metrics.boundary.f1 < 0.05


def test_un_decalage_sous_la_tolerance_est_pardonne():
    """La tolérance existe pour ne pas exiger l'exactitude au pixel."""
    truth = _floor()
    config = MetricConfig(boundary_tolerance_fraction=0.01)
    metrics = boundary_metrics(np.roll(truth, -3, axis=0), truth, config=config)

    assert metrics.f1 == 1.0
    assert metrics.tolerance_px >= 3


def test_la_tolerance_suit_la_taille_de_l_image():
    """Exprimée en fraction de diagonale : une même erreur visuelle, un même score."""
    config = MetricConfig(boundary_tolerance_fraction=0.005)
    small = config.tolerance_px(600, 400)
    large = config.tolerance_px(1200, 800)

    assert large == pytest.approx(small * 2, abs=1)


def test_la_tolerance_ne_descend_jamais_sous_un_pixel():
    assert MetricConfig(boundary_tolerance_fraction=1e-9).tolerance_px(100, 100) == 1


def test_un_masque_plein_ne_propose_aucun_contour():
    """Son seul bord est celui du cadre, et le cadre n'est pas une frontière.

    Précision indéfinie plutôt que parfaite : un tel masque ne propose aucune
    frontière de scène, il ne peut donc pas en proposer une bonne.
    """
    metrics = boundary_metrics(np.ones((HEIGHT, WIDTH), dtype=bool), _floor())

    assert metrics.predicted_boundary_pixels == 0
    assert metrics.precision is None


def test_le_bord_du_cadre_peut_etre_reintegre():
    """Le comportement est un réglage, pas une fatalité — et il est traçable."""
    included = boundary_metrics(
        np.ones((HEIGHT, WIDTH), dtype=bool),
        _floor(),
        config=MetricConfig(exclude_frame_border=False),
    )
    assert included.predicted_boundary_pixels > 0


def test_un_contour_parfait_donne_un():
    metrics = boundary_metrics(_floor().copy(), _floor())
    assert metrics.precision == 1.0
    assert metrics.recall == 1.0
    assert metrics.f1 == 1.0


def test_un_contour_entierement_incertain_ne_se_juge_pas():
    """Si la jonction est déclarée indécidable, il n'y a pas de contour à noter."""
    ignore = np.zeros((HEIGHT, WIDTH), dtype=bool)
    ignore[240:270, :] = True
    metrics = boundary_metrics(np.roll(_floor(), -3, axis=0), _floor(), ignore)

    assert metrics.f1 is None


def test_le_contour_cible_traverse_les_zones_incertaines():
    """Point de méthode : on n'évalue pas dans l'incertain, mais on y cherche.

    Une frontière humaine passant dans une zone incertaine reste une cible
    valide pour la prédiction qui la longe juste à côté. La retirer de la cible
    ferait compter fausse une prédiction correcte.
    """
    truth = _floor()
    ignore = np.zeros((HEIGHT, WIDTH), dtype=bool)
    ignore[248:252, :300] = True  # couvre la jonction sur la moitié gauche

    metrics = boundary_metrics(truth.copy(), truth, ignore)
    assert metrics.precision == 1.0, "la moitié droite doit encore trouver sa cible"


# --- Lecture et écriture des masques ------------------------------------


def test_un_masque_se_relit_a_l_identique(tmp_path):
    mask = _floor()
    path = tmp_path / "m.png"
    save_mask(mask, path)

    assert np.array_equal(load_mask(path, WIDTH, HEIGHT), mask)


def test_un_masque_de_mauvaises_dimensions_est_refuse(tmp_path):
    """Rien n'est redimensionné : un masque interpolé a des frontières fausses."""
    path = tmp_path / "m.png"
    save_mask(_floor(), path)

    with pytest.raises(MaskError, match="dimensions"):
        load_mask(path, WIDTH + 1, HEIGHT)


def test_un_masque_a_valeurs_intermediaires_est_refuse(tmp_path):
    """127 est la signature d'une interpolation ou d'un JPEG."""
    from PIL import Image

    path = tmp_path / "gris.png"
    array = np.full((HEIGHT, WIDTH), 127, dtype=np.uint8)
    Image.fromarray(array, mode="L").save(path, format="PNG")

    with pytest.raises(MaskError, match="valeurs interdites"):
        load_mask(path, WIDTH, HEIGHT)


def test_un_masque_en_jpeg_est_refuse(tmp_path):
    from PIL import Image

    path = tmp_path / "m.png"  # extension mensongère, contenu JPEG
    Image.fromarray(np.zeros((HEIGHT, WIDTH), dtype=np.uint8), mode="L").save(path, format="JPEG")

    with pytest.raises(MaskError, match="PNG"):
        load_mask(path, WIDTH, HEIGHT)


def test_un_masque_absent_est_refuse(tmp_path):
    with pytest.raises(MaskError, match="absent"):
        load_mask(tmp_path / "rien.png", WIDTH, HEIGHT)


# --- Assemblage ----------------------------------------------------------


def test_le_resultat_embarque_sa_configuration():
    """Deux rapports ne se comparent pas sans savoir à quelle tolérance."""
    config = MetricConfig(boundary_tolerance_fraction=0.02)
    dumped = evaluate(_floor(), _floor(), None, config).as_dict()

    assert dumped["config"]["boundary_tolerance_fraction"] == 0.02
    assert dumped["boundary"]["tolerance_px"] > 1
    assert "iou" in dumped["area"]


def test_des_masques_de_tailles_differentes_sont_refuses():
    with pytest.raises(MaskError, match="incompatibles"):
        evaluate(np.zeros((10, 10), dtype=bool), _floor())
