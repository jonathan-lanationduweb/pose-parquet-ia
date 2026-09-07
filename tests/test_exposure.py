"""Exposition, contraste et écrêtage, sur des transformations contrôlées.

Le test central est `test_le_contraste_relatif_ne_depend_pas_de_l_exposition` :
il fige la correction d'un défaut réel du LOT 0, où toute photo sombre
recevait `image_low_contrast` en plus de `image_too_dark` — deux
avertissements pour un seul défaut, dont un faux.
"""

import pytest

from app.core.config import get_settings
from app.core.warnings import Warn
from app.services.image_loader import luma
from app.services.image_quality import analyse_quality, measure_exposure, quality_warnings
from corpus import patterns, scenes
from corpus import transforms as tr

SIZE = (1280, 854)


def _exposure(image):
    return measure_exposure(luma(image))


def _warnings(image):
    return quality_warnings(analyse_quality(luma(image)), *image.shape[1::-1])


# --- Contraste : absolu contre relatif -----------------------------------


def test_le_contraste_relatif_ne_depend_pas_de_l_exposition():
    """La même scène, deux expositions : le contraste relatif ne bouge pas.

    L'écart-type absolu, lui, est divisé par cinq — il est proportionnel à la
    luminance. C'est pourquoi il ne sert plus de critère.
    """
    claire = _exposure(scenes.textured(SIZE))
    sombre = _exposure(tr.exposure_gain(scenes.textured(SIZE), 0.20))

    assert sombre.contrast_std < claire.contrast_std / 3
    assert sombre.contrast_ratio == pytest.approx(claire.contrast_ratio, rel=0.15)


def test_une_photo_sous_exposee_n_est_pas_declaree_plate():
    """Le défaut du LOT 0 : un seul défaut, un seul avertissement."""
    found = _warnings(tr.exposure_gain(scenes.textured(SIZE), 0.20))

    assert Warn.IMAGE_TOO_DARK in found
    assert Warn.IMAGE_LOW_CONTRAST not in found


def test_une_photo_plate_mais_bien_exposee_est_declaree_plate():
    """Le symétrique : plate sans être sombre."""
    found = _warnings(tr.contrast_scale(scenes.textured(SIZE), 0.20))

    assert Warn.IMAGE_LOW_CONTRAST in found
    assert Warn.IMAGE_TOO_DARK not in found


def test_les_deux_mesures_de_contraste_ne_disent_pas_la_meme_chose():
    """Un aplat avec un spot brûlé : écart-type flatté, étendue honnête."""
    array = patterns.flat(128, SIZE)
    array[:40, :40] = 255
    metrics = _exposure(array)

    assert metrics.contrast_std > 0.0
    assert metrics.contrast_p5_p95 == pytest.approx(0.0, abs=1e-3)


# --- Écrêtage ------------------------------------------------------------


def test_l_ecretage_est_distingue_de_la_simple_clarte():
    """Une photo claire se rattrape ; une photo écrêtée a perdu l'information."""
    claire = _exposure(tr.exposure_gain(scenes.textured(SIZE), 1.25))
    brulee = _exposure(tr.exposure_gain(scenes.textured(SIZE), 1.90))

    assert brulee.clipped_high_ratio > claire.clipped_high_ratio
    assert brulee.clipped_high_ratio > 0.05


def test_une_surexposition_franche_signale_ecretage_et_surexposition():
    found = _warnings(tr.exposure_gain(scenes.textured(SIZE), 1.60))
    assert Warn.IMAGE_OVEREXPOSED in found
    assert Warn.IMAGE_CLIPPED in found


def test_une_image_blanche_est_entierement_ecretee():
    metrics = _exposure(patterns.flat(255, SIZE))
    assert metrics.clipped_high_ratio == pytest.approx(1.0)
    assert metrics.clipped_low_ratio == pytest.approx(0.0)


def test_une_image_noire_est_entierement_ecretee_en_bas():
    metrics = _exposure(patterns.flat(0, SIZE))
    assert metrics.clipped_low_ratio == pytest.approx(1.0)
    assert metrics.clipped_high_ratio == pytest.approx(0.0)


def test_une_scene_correcte_n_ecrete_rien():
    metrics = _exposure(scenes.textured(SIZE))
    assert metrics.clipped_high_ratio == 0.0
    assert metrics.clipped_low_ratio == 0.0


# --- Luminance -----------------------------------------------------------


def test_la_luminance_suit_le_gain_applique():
    """Monotonie : la mesure doit refléter la transformation imposée."""
    means = [
        _exposure(tr.exposure_gain(scenes.textured(SIZE), g)).luma_mean
        for g in (0.2, 0.5, 1.0, 1.4)
    ]
    assert means == sorted(means)


def test_une_image_noire_et_une_blanche_sont_signalees():
    assert Warn.IMAGE_TOO_DARK in _warnings(patterns.flat(2, SIZE))
    assert Warn.IMAGE_OVEREXPOSED in _warnings(patterns.flat(254, SIZE))


def test_une_zone_sombre_importante_ne_condamne_pas_la_photo():
    """Une pièce à une seule fenêtre : moitié dans l'ombre, moitié correcte.

    Le test ne fixe pas de verdict — c'est le cas non gradé du corpus, et
    personne ne peut trancher d'une image seule. Il vérifie seulement que la
    moitié éclairée reste mesurable, donc que la photo n'est pas perdue.
    """
    metrics = _exposure(tr.half_shadow(scenes.textured(SIZE), 0.25))

    assert metrics.clipped_low_ratio < 0.02, "l'ombre ne doit pas être écrêtée"
    assert metrics.luma_median > 0.05


# --- Cadre ---------------------------------------------------------------


def test_un_panorama_est_signale():
    """Une bande de 5:1 n'est pas une pièce photographiée."""
    assert Warn.IMAGE_EXTREME_ASPECT_RATIO in _warnings(scenes.textured((2000, 400)))


def test_une_image_trop_petite_est_signalee():
    array = scenes.textured((320, 240))
    assert Warn.IMAGE_TOO_SMALL in quality_warnings(analyse_quality(luma(array)), 320, 240)


def test_les_seuils_d_exposition_sont_configurables(monkeypatch):
    array = tr.exposure_gain(scenes.textured(SIZE), 0.20)
    assert Warn.IMAGE_TOO_DARK in _warnings(array)

    monkeypatch.setenv("PPAI_LUMA_MEAN_MIN", "0.01")
    monkeypatch.setenv("PPAI_DARK_RATIO_MAX", "0.99")
    get_settings.cache_clear()
    assert Warn.IMAGE_TOO_DARK not in _warnings(array)
