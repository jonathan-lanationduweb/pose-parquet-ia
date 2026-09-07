"""Distorsion : détection, sens, intensité, et refus de conclure.

Les deux tests de non-régression du lot sont
`test_un_damier_n_est_jamais_declare_distordu` et
`test_des_courbes_reelles_ne_sont_pas_imputees_a_l_objectif`. Le premier fige
le faux positif du LOT 0 ; le second son cousin, qu'aucun durcissement de seuil
ne réglerait.
"""

import pytest

from app.core.config import LensMethod, get_settings
from app.core.warnings import Warn
from app.schemas.analysis import LensVerdict
from app.services.edge_tracking import find_tracks
from app.services.image_loader import luma
from app.services.lens_analysis import analyse_lens, lens_warnings
from corpus import patterns, scenes
from corpus import transforms as tr

#: Assez grand pour que les arêtes soient longues, assez petit pour que la
#: suite de tests reste rapide.
SIZE = (1600, 1067)


def _lens(image):
    return analyse_lens(luma(image))


def _archi(k1: float = 0.0):
    base = scenes.architectural(SIZE)
    return tr.radial_distort(base, k1) if k1 else base


def _use(monkeypatch, method: LensMethod) -> None:
    monkeypatch.setenv("PPAI_LENS_METHOD", method.value)
    get_settings.cache_clear()


# --- Non-régression : les faux positifs à ne jamais reproduire -----------


def test_un_damier_n_est_jamais_declare_distordu():
    """NON-RÉGRESSION DU LOT 0.

    Le détecteur d'origine voyait une distorsion ici : des dizaines d'arêtes
    courtes bombant dans tous les sens, et une mesure d'amplitude qui ne voit
    que « ça bombe ». Un motif répétitif ne doit jamais suffire.
    """
    lens = _lens(patterns.checkerboard(SIZE, square=40, low=70, high=190))
    assert lens.verdict is not LensVerdict.DISTORTION_SUSPECTED


def test_des_courbes_reelles_ne_sont_pas_imputees_a_l_objectif():
    """Des arches et des cercles que la scène contient vraiment.

    Le faux positif le plus intéressant du corpus : il ne se corrige pas en
    durcissant un seuil d'amplitude, seulement en vérifiant que la courbure
    est cohérente avec une distorsion radiale.
    """
    lens = _lens(scenes.curved_objects(SIZE))
    assert lens.verdict is not LensVerdict.DISTORTION_SUSPECTED


def test_une_texture_sans_droite_ne_suffit_pas():
    lens = _lens(scenes.textured(SIZE))
    assert lens.verdict is not LensVerdict.DISTORTION_SUSPECTED


# --- Détection sur vérité terrain connue --------------------------------


def test_une_scene_rectilineaire_ne_montre_aucune_preuve():
    lens = _lens(_archi())
    assert lens.verdict is LensVerdict.NO_DISTORTION_EVIDENCE
    assert lens.support.usable_edges >= 2


@pytest.mark.parametrize("k1", [0.05, 0.15, 0.30])
def test_un_barillet_connu_est_detecte(k1):
    lens = _lens(_archi(k1))
    assert lens.verdict is LensVerdict.DISTORTION_SUSPECTED
    assert lens.suspected_sign == "barrel"


@pytest.mark.parametrize("k1", [-0.05, -0.15, -0.30])
def test_un_coussinet_connu_est_detecte(k1):
    lens = _lens(_archi(k1))
    assert lens.verdict is LensVerdict.DISTORTION_SUSPECTED
    assert lens.suspected_sign == "pincushion"


@pytest.mark.parametrize("k1", [0.05, 0.15, 0.30, -0.05, -0.15, -0.30])
def test_l_intensite_estimee_approche_la_verite_terrain(k1):
    """Le k1 estimé doit retrouver le k1 imposé.

    La tolérance est le pas de la recherche plus une marge : ce test vérifie
    que l'estimateur trouve le bon coefficient, pas qu'il est exact au
    millième.
    """
    lens = _lens(_archi(k1))
    assert lens.k1 is not None
    assert lens.k1.k1 == pytest.approx(k1, abs=0.03)


def test_le_gain_de_rectitude_distingue_une_vraie_detection():
    """La recherche renvoie TOUJOURS un k1 optimal. C'est le gain qui tranche.

    Sans ce second critère, une image parfaitement rectilinéaire recevrait le
    k1 « le moins mauvais » et serait déclarée distordue.
    """
    propre = _lens(_archi())
    distordue = _lens(_archi(0.15))

    assert propre.k1 is not None and distordue.k1 is not None
    assert propre.k1.residual_gain < 0.25
    assert distordue.k1.residual_gain > 0.5


# --- Refus de conclure ---------------------------------------------------


def test_un_mur_lisse_ne_permet_aucune_conclusion():
    """Aucune arête contrastée : le seul verdict honnête est l'indétermination."""
    lens = _lens(scenes.smooth_wall(SIZE))

    assert lens.verdict is LensVerdict.UNDETERMINED
    assert lens.support.usable_edges == 0
    assert lens_warnings(lens) == [Warn.LENS_ANALYSIS_UNDETERMINED]


def test_des_lignes_courtes_ne_prouvent_rien():
    """La flèche croît comme le carré de la longueur : un segment court est du bruit."""
    lens = _lens(scenes.line_field(SIZE, span=0.15))
    assert lens.verdict is LensVerdict.UNDETERMINED


def test_une_arete_interrompue_ne_devient_pas_une_longue_arete():
    """Le traqueur doit s'arrêter au trou, pas inventer la suite."""
    coupees = _lens(scenes.line_field(SIZE, gaps=3))
    entieres = _lens(scenes.line_field(SIZE))

    longest_cut = max((t.span_ratio for t in coupees.tracks), default=0.0)
    longest_whole = max((t.span_ratio for t in entieres.tracks), default=0.0)
    assert longest_cut < longest_whole


def test_un_aplat_parfait_reste_indetermine():
    lens = _lens(patterns.flat(150, SIZE))
    assert lens.verdict is LensVerdict.UNDETERMINED
    assert lens.support.usable_edges == 0


def test_sans_support_l_accord_de_signe_vaut_zero_et_non_un():
    """« Aucune donnée » ne doit jamais se lire comme « parfaitement cohérent »."""
    lens = _lens(patterns.flat(150, SIZE))
    assert lens.support.sign_agreement == 0.0


# --- Le vocabulaire ------------------------------------------------------


def test_le_verdict_negatif_ne_pretend_pas_a_une_preuve_d_absence():
    """`no_distortion_evidence`, et non `no_distortion_detected`.

    « Rien détecté » se lit comme « l'objectif est sain ». La mesure ne dit
    que « les arêtes que j'ai su mesurer sont droites ».
    """
    assert LensVerdict.NO_DISTORTION_EVIDENCE.value == "no_distortion_evidence"
    assert "no_distortion_detected" not in {verdict.value for verdict in LensVerdict}


def test_aucune_correction_n_est_jamais_appliquee():
    """Le champ est un `Literal[False]` : il ne peut pas devenir vrai par erreur."""
    assert _lens(_archi(0.20)).correction_applied is False


# --- Support géométrique -------------------------------------------------


def test_le_support_est_rapporte_en_detail():
    """Un verdict ne doit jamais être un score opaque."""
    support = _lens(_archi(0.15)).support

    assert support.usable_edges >= 2
    assert support.total_track_px > 0
    assert 0.0 <= support.spatial_coverage <= 1.0
    assert 0.0 <= support.sign_agreement <= 1.0


def test_une_distorsion_radiale_fait_bomber_toutes_les_aretes_du_meme_cote():
    """C'est la propriété qui définit une distorsion radiale, et le discriminant."""
    support = _lens(_archi(0.15)).support
    assert support.sign_agreement == pytest.approx(1.0)


def test_les_aretes_horizontales_sont_suivies_aussi():
    """N'observer que les verticales diviserait le support par deux."""
    tracks = [t for t in find_tracks(luma(_archi(0.15))) if t.usable]
    orientations = {t.orientation for t in tracks}
    assert "horizontal" in orientations
    assert "vertical" in orientations


def test_les_aretes_centrales_ne_sont_pas_retenues():
    """La distorsion radiale ne déplace rien sur l'axe optique."""
    lens = _lens(scenes.line_field(SIZE, columns=(0.48, 0.5, 0.52)))
    assert all(not track.usable for track in lens.tracks)


def test_une_marche_de_quantification_n_est_pas_une_arete():
    """Sur un dégradé lisse, le traqueur suivait les marches de quantification.

    Le verdict restait juste, mais le support annonçait onze arêtes là où il
    n'y a rien à voir — et le support est ce sur quoi reposera la confiance.
    """
    tracks = find_tracks(luma(scenes.smooth_wall(SIZE)))
    assert all(not track.usable for track in tracks)


# --- Les trois candidates ------------------------------------------------


def test_la_candidate_du_lot_0_produit_un_faux_positif(monkeypatch):
    """Épingle la faiblesse mesurée de la mesure d'amplitude seule.

    Ce test ne demande pas à la candidate A d'être bonne : il fige la raison
    de son écartement. Une amplitude ne dit pas d'où vient la courbure.
    """
    _use(monkeypatch, LensMethod.SAGITTA_MAGNITUDE)
    lens = _lens(scenes.textured(SIZE))

    assert lens.verdict is LensVerdict.DISTORTION_SUSPECTED
    assert lens.support.sign_agreement < get_settings().lens_min_sign_agreement


@pytest.mark.parametrize("method", list(LensMethod))
def test_toutes_les_candidates_detectent_une_distorsion_franche(monkeypatch, method):
    _use(monkeypatch, method)
    lens = _lens(_archi(0.20))
    assert lens.verdict is LensVerdict.DISTORTION_SUSPECTED
    assert lens.method == method.value


@pytest.mark.parametrize("method", list(LensMethod))
def test_aucune_candidate_ne_conclut_sans_support(monkeypatch, method):
    """Répondre « pas de distorsion » sans avoir rien mesuré serait rassurer à tort."""
    _use(monkeypatch, method)
    assert _lens(patterns.flat(150, SIZE)).verdict is LensVerdict.UNDETERMINED


def test_les_mesures_des_trois_candidates_sont_toujours_presentes(monkeypatch):
    """Un rapport doit permettre de rejouer un choix sans réanalyser le corpus."""
    _use(monkeypatch, LensMethod.SAGITTA_MAGNITUDE)
    lens = _lens(_archi(0.15))

    assert lens.max_sagitta_px is not None
    assert lens.support.sign_agreement > 0
    assert lens.k1 is not None


# --- Mise à l'échelle ----------------------------------------------------


def test_le_seuil_d_amplitude_suit_la_resolution():
    """La flèche est en pixels : sans mise à l'échelle, deux tirages divergent."""
    petit = _lens(scenes.architectural((800, 534)))
    grand = _lens(scenes.architectural((1600, 1068)))
    assert grand.suspect_threshold_px == pytest.approx(petit.suspect_threshold_px * 2, rel=0.02)


def test_l_intensite_estimee_ne_depend_pas_de_la_resolution():
    """k1 est normalisé par la demi-diagonale : il doit être invariant d'échelle."""
    petit = _lens(tr.radial_distort(scenes.architectural((800, 534)), 0.15))
    grand = _lens(tr.radial_distort(scenes.architectural((1600, 1068)), 0.15))

    assert petit.k1 is not None and grand.k1 is not None
    assert petit.k1.k1 == pytest.approx(grand.k1.k1, abs=0.03)
