"""Analyse d'objectif : la mesure de flèche, et sa prudence."""

import pytest

from app.core.warnings import Warn
from app.schemas.analysis import LensVerdict
from app.services.image_loader import luma
from app.services.lens_analysis import analyse_lens, lens_warnings
from tests import factories


def test_des_droites_droites_donnent_une_fleche_quasi_nulle():
    """Vérité terrain : des barres parfaitement verticales ne bombent pas.

    Le seuil de comparaison (1 px) est volontairement lâche : ce qui est
    vérifié ici, c'est qu'aucune courbure n'est *fabriquée* par le traqueur —
    l'erreur exacte qui avait fait rejeter une scène côté front.
    """
    lens = analyse_lens(luma(factories.straight_bars(size=(1600, 1000))))

    assert lens.usable_edges >= 2
    assert lens.max_sagitta_px is not None
    assert lens.max_sagitta_px < 1.0
    assert lens.verdict is LensVerdict.NO_DISTORTION_DETECTED


def test_des_droites_courbees_sont_reperees():
    lens = analyse_lens(luma(factories.bowed_bars(size=(1600, 1000), amplitude=18.0)))

    assert lens.usable_edges >= 2
    assert lens.max_sagitta_px is not None
    assert lens.max_sagitta_px > lens.suspect_threshold_px
    assert lens.verdict is LensVerdict.DISTORTION_SUSPECTED


def test_aucune_correction_n_est_jamais_appliquee():
    """Le champ est un `Literal[False]` : il ne peut pas devenir vrai par erreur."""
    lens = analyse_lens(luma(factories.straight_bars()))
    assert lens.correction_applied is False


def test_sans_arete_exploitable_le_verdict_reste_indetermine():
    """Une image uniforme n'a aucune arête. Le seul verdict honnête est « je ne sais pas »."""
    lens = analyse_lens(luma(factories.flat(180)))

    assert lens.usable_edges == 0
    assert lens.max_sagitta_px is None
    assert lens.verdict is LensVerdict.UNDETERMINED
    assert lens_warnings(lens) == [Warn.LENS_ANALYSIS_UNDETERMINED]


def test_une_seule_arete_ne_suffit_pas(monkeypatch):
    """Deux arêtes au minimum : une seule ne prouve rien."""
    monkeypatch.setenv("PPAI_LENS_MIN_USABLE_EDGES", "99")
    from app.core.config import get_settings

    get_settings.cache_clear()
    lens = analyse_lens(luma(factories.straight_bars(size=(1600, 1000))))
    assert lens.verdict is LensVerdict.UNDETERMINED


def test_la_fleche_et_l_ecart_type_voyagent_ensemble():
    """`sagitta_px` seule ne veut rien dire — c'est la leçon du front."""
    lens = analyse_lens(luma(factories.straight_bars(size=(1600, 1000))))
    for track in lens.tracks:
        assert track.fit_rms_px >= 0.0
        assert track.points > 0
        # Un tracé retenu comme preuve est nécessairement bien ajusté.
        if track.usable:
            assert track.fit_rms_px <= 2.0


def test_le_seuil_est_mis_a_l_echelle_de_l_image():
    """La flèche est en pixels : le seuil doit suivre la résolution.

    Sans mise à l'échelle, une même photo tirée en 800 px et en 1600 px
    donnerait deux verdicts différents.
    """
    small = analyse_lens(luma(factories.straight_bars(size=(800, 500))))
    large = analyse_lens(luma(factories.straight_bars(size=(1600, 1000))))

    assert large.suspect_threshold_px == pytest.approx(small.suspect_threshold_px * 2, rel=0.01)


def test_la_fleche_normalisee_est_comparable_entre_resolutions():
    """Le même motif, deux résolutions : la valeur normalisée doit converger."""
    small = analyse_lens(luma(factories.bowed_bars(size=(800, 500), amplitude=9.0)))
    large = analyse_lens(luma(factories.bowed_bars(size=(1600, 1000), amplitude=18.0)))

    assert small.max_sagitta_px_normalized is not None
    assert large.max_sagitta_px_normalized is not None
    assert small.max_sagitta_px_normalized == pytest.approx(
        large.max_sagitta_px_normalized, rel=0.4
    )


def test_les_aretes_centrales_ne_sont_pas_retenues():
    """La distorsion radiale ne déplace rien sur l'axe optique.

    Des barres uniquement au centre du cadre ne peuvent donc rien prouver, et
    le verdict doit rester indéterminé plutôt que rassurant.
    """
    lens = analyse_lens(luma(factories.straight_bars(size=(1600, 1000), columns=(0.48, 0.5, 0.52))))
    assert all(not track.usable for track in lens.tracks)
    assert lens.verdict is LensVerdict.UNDETERMINED
