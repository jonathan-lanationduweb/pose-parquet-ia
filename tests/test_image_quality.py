"""Mesures de qualité : flou, exposition, contraste, et les codes qui en sortent."""

import pytest

from app.core.warnings import Warn
from app.services.image_loader import luma
from app.services.image_quality import (
    analyse_quality,
    measure_blur,
    measure_exposure,
    quality_warnings,
)
from tests import factories

# --- Flou ----------------------------------------------------------------


def test_le_flou_fait_chuter_la_variance_du_laplacien():
    """La seule comparaison qui vaille : même contenu, netteté différente."""
    sharp = measure_blur(luma(factories.checkerboard(blur=0)))
    blurred = measure_blur(luma(factories.checkerboard(blur=8)))

    assert sharp.laplacian_variance > blurred.laplacian_variance * 10
    assert sharp.sharp is True
    assert blurred.sharp is False


def test_la_mesure_est_faite_a_resolution_de_travail_fixe(monkeypatch):
    """Sans taille de travail fixe, deux tirages de la même photo divergent.

    Le damier est généré avec des carreaux proportionnels à la taille, donc
    visuellement identique aux deux résolutions. Les variances doivent rester
    du même ordre — ce qui n'est vrai que parce que les deux sont ramenées à
    la même taille avant mesure.
    """
    monkeypatch.setenv("PPAI_BLUR_WORKING_SIDE", "512")
    from app.core.config import get_settings

    get_settings.cache_clear()

    small = measure_blur(luma(factories.checkerboard(size=(640, 480), square=16)))
    large = measure_blur(luma(factories.checkerboard(size=(1280, 960), square=32)))

    assert small.working_side == large.working_side == 512
    assert large.laplacian_variance == pytest.approx(small.laplacian_variance, rel=0.35)


def test_une_petite_image_n_est_jamais_agrandie():
    """Agrandir fabriquerait du flou d'interpolation."""
    metrics = measure_blur(luma(factories.checkerboard(size=(320, 240), square=8)))
    assert metrics.working_side == 320


def test_une_image_uniforme_n_est_pas_nette():
    """Un mur nu ne contient aucun détail : la mesure le dit sans se tromper.

    C'est aussi la limite de la méthode, et la raison pour laquelle le seuil
    n'est pas un verdict : cette image n'est pas floue, elle est vide.
    """
    metrics = measure_blur(luma(factories.flat(128)))
    assert metrics.laplacian_variance == pytest.approx(0.0, abs=1e-6)
    assert metrics.sharp is False


# --- Exposition et contraste ---------------------------------------------


def test_luminance_moyenne_dune_image_noire_et_dune_blanche():
    black = measure_exposure(luma(factories.flat(0)))
    white = measure_exposure(luma(factories.flat(255)))

    assert black.luma_mean == pytest.approx(0.0, abs=1e-4)
    assert black.dark_pixel_ratio == pytest.approx(1.0)
    assert white.luma_mean == pytest.approx(1.0, abs=1e-4)
    assert white.bright_pixel_ratio == pytest.approx(1.0)


def test_le_contraste_dune_image_plate_est_nul():
    metrics = measure_exposure(luma(factories.flat(128)))
    assert metrics.contrast_std == pytest.approx(0.0, abs=1e-5)
    assert metrics.contrast_p5_p95 == pytest.approx(0.0, abs=1e-5)


def test_le_damier_est_le_contraste_maximal():
    """Moitié noir, moitié blanc : écart-type proche de 0,5, étendue de 1."""
    metrics = measure_exposure(luma(factories.checkerboard()))
    assert metrics.contrast_std == pytest.approx(0.5, abs=0.05)
    assert metrics.contrast_p5_p95 == pytest.approx(1.0, abs=0.05)


def test_les_deux_mesures_de_contraste_ne_disent_pas_la_meme_chose():
    """Une image plate avec un spot brûlé : écart-type flatté, étendue honnête.

    C'est précisément pour ce cas que les deux sont renvoyées.
    """
    array = factories.flat(128)
    array[:40, :40] = 255
    metrics = measure_exposure(luma(array))

    assert metrics.contrast_std > 0.0
    assert metrics.contrast_p5_p95 == pytest.approx(0.0, abs=1e-3)


# --- Codes machine -------------------------------------------------------


def test_une_image_trop_petite_est_signalee():
    array = factories.checkerboard(size=(320, 240))
    found = quality_warnings(analyse_quality(luma(array)), 320, 240)
    assert Warn.IMAGE_TOO_SMALL in found


def test_une_image_noire_est_signalee_sombre():
    array = factories.flat(2)
    found = quality_warnings(analyse_quality(luma(array)), *array.shape[1::-1])
    assert Warn.IMAGE_TOO_DARK in found
    assert Warn.IMAGE_LOW_CONTRAST in found


def test_une_image_blanche_est_signalee_surexposee():
    array = factories.flat(254)
    found = quality_warnings(analyse_quality(luma(array)), *array.shape[1::-1])
    assert Warn.IMAGE_OVEREXPOSED in found


def test_une_image_floue_est_signalee():
    array = factories.checkerboard(blur=8)
    found = quality_warnings(analyse_quality(luma(array)), *array.shape[1::-1])
    assert Warn.IMAGE_BLURRY in found


def test_un_panorama_est_signale():
    """Une bande de 4:1 n'est pas une pièce photographiée."""
    array = factories.checkerboard(size=(2000, 400))
    found = quality_warnings(analyse_quality(luma(array)), 2000, 400)
    assert Warn.IMAGE_EXTREME_ASPECT_RATIO in found


def test_un_damier_noir_et_blanc_est_a_moitie_brule():
    """Le damier par défaut n'est pas une photo correcte, et les mesures le disent.

    Moitié noire, moitié saturée : `image_too_dark` **et**
    `image_overexposed` sont tous deux justifiés. C'est une bonne fixture de
    netteté et une mauvaise fixture d'exposition.
    """
    array = factories.checkerboard()
    found = quality_warnings(analyse_quality(luma(array)), *array.shape[1::-1])
    assert Warn.IMAGE_TOO_DARK in found
    assert Warn.IMAGE_OVEREXPOSED in found


def test_une_photo_sans_reproche_ne_declenche_rien():
    array = factories.mid_tone_checkerboard()
    found = quality_warnings(analyse_quality(luma(array)), *array.shape[1::-1])
    assert found == []


def test_les_seuils_sont_configurables(monkeypatch):
    """Aucun seuil n'est universel : il doit pouvoir bouger sans toucher au code."""
    array = factories.checkerboard(blur=8)
    quality = analyse_quality(luma(array))
    assert Warn.IMAGE_BLURRY in quality_warnings(quality, *array.shape[1::-1])

    monkeypatch.setenv("PPAI_BLUR_SHARP_MIN", "0.0")
    from app.core.config import get_settings

    get_settings.cache_clear()
    relaxed = analyse_quality(luma(array))
    assert Warn.IMAGE_BLURRY not in quality_warnings(relaxed, *array.shape[1::-1])
