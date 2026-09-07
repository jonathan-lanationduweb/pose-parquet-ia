"""Le corpus : reproductible, et sans vérité terrain inventée.

Deux tests portent le lot : `test_le_corpus_est_reproductible_au_bit_pres` —
sans quoi aucun rapport de benchmark n'est comparable à un autre — et
`test_aucune_verite_terrain_n_est_inventee`, qui interdit au corpus de
contenir autre chose que ce qu'on lui a imposé.
"""

import numpy as np
import pytest

from app.core.warnings import SCORED, Warn
from corpus import patterns, scenes
from corpus import transforms as tr
from corpus.catalogue import CATALOGUE, SEED, by_id, graded_entries

#: Paramètres qu'une transformation a réellement **imposés**. Toute autre clé
#: dans `Entry.truth` serait une estimation déguisée en vérité.
IMPOSED_KEYS = frozenset(
    {
        "k1",
        "k2",
        "sign",
        "blur_sigma",
        "motion_length",
        "motion_angle_deg",
        "noise_sigma",
        "exposure_gain",
        "contrast_factor",
        "shadow_gain",
        "shadow_extent",
        "optical_center_shifted",
    }
)


# --- Reproductibilité ----------------------------------------------------


def test_le_corpus_est_reproductible_au_bit_pres():
    """Deux constructions de la même entrée doivent donner les mêmes octets.

    Sans cela, deux rapports de benchmark ne mesurent pas la même chose et
    aucune comparaison de méthodes ne veut rien dire.
    """
    for entry in CATALOGUE:
        first = entry.build()
        second = entry.build()
        assert np.array_equal(first, second), f"{entry.id} n'est pas déterministe"


def test_les_transformations_bruitees_prennent_une_graine_explicite():
    """Aucune graine par défaut aléatoire, sinon le corpus dérive en silence."""
    base = scenes.textured((320, 240))
    assert np.array_equal(tr.add_noise(base, 8.0, 42), tr.add_noise(base, 8.0, 42))
    assert not np.array_equal(tr.add_noise(base, 8.0, 42), tr.add_noise(base, 8.0, 43))


def test_le_corpus_a_une_graine_unique_declaree():
    assert isinstance(SEED, int)


# --- Vérité terrain ------------------------------------------------------


def test_aucune_verite_terrain_n_est_inventee():
    """`truth` ne contient que des paramètres imposés par une transformation."""
    for entry in CATALOGUE:
        unknown = set(entry.truth) - IMPOSED_KEYS
        assert not unknown, f"{entry.id} déclare des vérités non imposées : {unknown}"


def test_une_entree_sans_transformation_ne_declare_aucune_intensite():
    """Une scène saine n'a pas de flou ni de gain à déclarer."""
    entry = by_id("sharp-textured")
    assert "blur_sigma" not in entry.truth
    assert "exposure_gain" not in entry.truth


def test_le_signe_declare_correspond_au_k1_declare():
    for entry in CATALOGUE:
        if "k1" not in entry.truth or "sign" not in entry.truth:
            continue
        k1 = float(entry.truth["k1"])
        expected = "barrel" if k1 > 0 else "pincushion" if k1 < 0 else "none"
        assert entry.truth["sign"] == expected, entry.id


# --- Cohérence du catalogue ---------------------------------------------


def test_les_identifiants_sont_uniques():
    ids = [entry.id for entry in CATALOGUE]
    assert len(ids) == len(set(ids))


def test_les_difficultes_sont_un_vocabulaire_ferme():
    valid = {"easy", "medium", "hard", "rejected"}
    for entry in CATALOGUE:
        assert entry.difficulty in valid, entry.id


def test_tous_les_defauts_attendus_sont_comptables():
    """Un code attendu hors du jeu d'étiquettes serait invisible au comptage."""
    for entry in CATALOGUE:
        for code in entry.expected:
            assert code in SCORED, f"{entry.id} attend {code}, hors du jeu compté"


def test_les_entrees_non_gradees_portent_une_note():
    """Une zone grise sans explication est indistinguable d'un oubli."""
    for entry in CATALOGUE:
        if not entry.graded:
            assert entry.note, f"{entry.id} n'est pas gradée et n'explique pas pourquoi"


def test_le_corpus_couvre_les_cas_obligatoires_du_lot():
    """Les cas dont l'absence rendrait le lot inévaluable."""
    ids = {entry.id for entry in CATALOGUE}
    for required in (
        "sharp-textured",
        "smooth-wall-sharp",
        "sparse-detail-sharp",
        "sparse-detail-blurred",
        "repetitive-checkerboard",
        "curved-objects",
        "lines-short",
        "lines-interrupted",
        "archi-k1-0",
        "archi-barrel-015",
        "archi-pincushion-015",
    ):
        assert required in ids, f"cas obligatoire absent : {required}"


def test_le_corpus_contient_les_deux_sens_de_distorsion():
    signs = {entry.truth.get("sign") for entry in CATALOGUE if "k1" in entry.truth}
    assert {"barrel", "pincushion", "none"} <= signs


def test_plusieurs_intensites_de_distorsion_sont_couvertes():
    magnitudes = {abs(float(entry.truth["k1"])) for entry in CATALOGUE if "k1" in entry.truth}
    assert len(magnitudes) >= 4


def test_plusieurs_niveaux_de_flou_sont_couverts():
    sigmas = {float(e.truth["blur_sigma"]) for e in CATALOGUE if "blur_sigma" in e.truth}
    assert len(sigmas) >= 3


def test_il_reste_des_entrees_gradees():
    assert len(graded_entries()) > len(CATALOGUE) // 2


# --- La convention de signe de la distorsion ----------------------------


def test_k1_positif_donne_un_barillet():
    """Vérifié sur les pixels, pas par raisonnement.

    Une droite verticale à droite du centre doit, sous k1 > 0, bomber vers
    l'extérieur : son milieu s'éloigne du centre plus que ses extrémités.
    """
    width, height = 800, 600
    image = np.full((height, width, 3), 200, dtype=np.uint8)
    x0 = int(width * 0.80)
    image[:, x0 - 2 : x0 + 3] = 30

    def line_x(array, row):
        dark = np.where(array[row, :, 0] < 115)[0]
        return float(dark.mean())

    barrel = tr.radial_distort(image, 0.20)
    pincushion = tr.radial_distort(image, -0.20)

    middle, top = height // 2, int(height * 0.06)
    assert line_x(barrel, middle) > line_x(barrel, top), "k1 > 0 doit bomber vers l'extérieur"
    assert line_x(pincushion, middle) < line_x(pincushion, top)


def test_k1_nul_ne_deforme_rien():
    base = scenes.architectural((400, 300))
    assert np.array_equal(tr.radial_distort(base, 0.0), base)


def test_la_verite_terrain_d_objectif_expose_son_sens():
    assert tr.LensGroundTruth(0.2).sign == "barrel"
    assert tr.LensGroundTruth(-0.2).sign == "pincushion"
    assert tr.LensGroundTruth(0.0).sign == "none"
    assert tr.LensGroundTruth(0.0).distorted is False
    assert tr.LensGroundTruth(0.05).distorted is True


# --- Les transformations font ce qu'elles annoncent ---------------------


def test_le_flou_gaussien_nul_ne_change_rien():
    base = scenes.textured((320, 240))
    assert np.array_equal(tr.gaussian_blur(base, 0.0), base)


def test_le_gain_d_exposition_ecrete_plutot_que_de_deborder():
    saturated = tr.exposure_gain(patterns.flat(200, (64, 64)), 4.0)
    assert saturated.max() == 255


def test_le_contraste_comprime_l_ecart_type_sans_toucher_au_pivot():
    """C'est le pivot qui est conservé, pas la moyenne.

    Sur une image dont la moyenne n'est pas le pivot, comprimer le contraste
    la rapproche du pivot. Le corpus doit dire juste ce qu'il impose.
    """
    base = patterns.flat(128, (64, 64))
    base[:32] = 200
    scaled = tr.contrast_scale(base, 0.3, pivot=128.0)

    assert float(scaled.std()) == pytest.approx(float(base.std()) * 0.3, rel=0.05)
    assert float(scaled.min()) == pytest.approx(128.0, abs=1.0)


def test_le_recadrage_reduit_bien_le_cadre():
    cropped = tr.crop_offset(scenes.textured((800, 600)), keep=0.6, shift=0.1)
    assert cropped.shape[0] < 600
    assert cropped.shape[1] < 800


def test_les_cas_obligatoires_declarent_ce_qu_ils_eprouvent():
    """Le damier et les courbes ne doivent jamais attendre une distorsion."""
    for entry_id in ("repetitive-checkerboard", "curved-objects", "textured-only"):
        assert Warn.LENS_DISTORTION_SUSPECTED not in by_id(entry_id).expected
