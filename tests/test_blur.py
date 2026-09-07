"""Netteté : le support d'abord, et les trois candidates.

Le test qui compte est `test_mur_lisse_net_n_est_pas_declare_flou`. Tous les
autres décrivent des propriétés utiles ; celui-là décrit la raison d'être du
module.
"""

import pytest

from app.core.config import BlurMethod, get_settings
from app.core.warnings import Warn
from app.services import blur_analysis
from app.services.image_loader import luma
from app.services.image_quality import analyse_quality, quality_warnings
from corpus import patterns, scenes
from corpus import transforms as tr

#: Résolution d'**étalonnage**, la même que celle du corpus. Les bornes de
#: netteté sont mesurées sur des images ramenées à `blur_working_side` ; les
#: éprouver à une autre résolution reviendrait à tester la mesure hors de son
#: domaine, et à confondre une borne mal placée avec une extrapolation.
SIZE = (1600, 1067)


def _read(image):
    return blur_analysis.measure(luma(image))


def _verdict(image):
    reading = _read(image)
    return blur_analysis.classify(reading)


def _use(monkeypatch, method: BlurMethod) -> None:
    monkeypatch.setenv("PPAI_BLUR_METHOD", method.value)
    get_settings.cache_clear()


# --- Les trois cas que le lot doit distinguer ----------------------------


def test_mur_lisse_net_n_est_pas_declare_flou():
    """LE test du lot. Une image sans détail n'est pas une image floue.

    Ce mur est un dégradé lisse : aucun pixel n'a été moyenné avec son voisin,
    rien n'est flou. Le verdict doit être « je ne sais pas », jamais « floue ».
    """
    sharp, low_texture = _verdict(scenes.smooth_wall(SIZE))

    assert sharp is None, "un mur lisse net ne doit pas recevoir de verdict de netteté"
    assert low_texture is True


def test_mur_lisse_net_et_floute_sont_indiscernables():
    """Et le service doit le dire, plutôt que de choisir au hasard.

    Les deux images sont réellement indistinguables pour toute mesure de
    netteté. Deux verdicts identiques et indéterminés sont donc le seul
    résultat vrai — pas un aveu de faiblesse.
    """
    net = _verdict(scenes.smooth_wall(SIZE))
    floute = _verdict(tr.gaussian_blur(scenes.smooth_wall(SIZE), 6.0))

    assert net == floute == (None, True)


def test_une_image_texturee_nette_est_declaree_nette():
    sharp, low_texture = _verdict(scenes.textured(SIZE))
    assert sharp is True
    assert low_texture is False


def test_la_meme_image_floutee_est_declaree_floue():
    sharp, _ = _verdict(tr.gaussian_blur(scenes.textured(SIZE), 3.0))
    assert sharp is False


def test_peu_de_texture_mais_assez_pour_conclure():
    """Un mur avec trois arêtes franches : pauvre, mais décidable.

    C'est la paire décisive avec le mur lisse : même pauvreté apparente, mais
    ici il y a de quoi mesurer, et la netteté est donc jugée — dans les deux
    sens.
    """
    net, _ = _verdict(scenes.sparse_detail(SIZE))
    floute, _ = _verdict(tr.gaussian_blur(scenes.sparse_detail(SIZE), 6.0))

    assert net is True
    assert floute is False


# --- La bande d'incertitude ---------------------------------------------


def test_une_image_reechantillonnee_reste_indeterminee():
    """Ce que la bande capture réellement sur ce corpus.

    Appliquer une distorsion radiale adoucit l'image : l'interpolation est un
    filtre. L'image n'est pas floue pour autant, et elle n'est plus tout à
    fait nette. La bande répond « je ne sais pas », ce qui est exact — et
    évite d'annoncer un flou à chaque photo distordue, ce que ferait un seuil
    unique posé au milieu de la marge.
    """
    sharp, low_texture = _verdict(tr.radial_distort(scenes.architectural(SIZE), 0.15))

    assert sharp is None
    assert low_texture is False, "il y a du support : l'incertitude vient de la bande, pas du vide"


def test_les_bornes_sont_ordonnees():
    settings = get_settings()
    assert settings.blur_edge_width_sharp_max < settings.blur_edge_width_blurry_min
    assert settings.blur_reblur_sharp_max < settings.blur_reblur_blurry_min


# --- Robustesse au bruit -------------------------------------------------


def test_le_bruit_ne_fait_pas_passer_une_image_nette_pour_floue():
    sharp, _ = _verdict(tr.add_noise(scenes.textured(SIZE), 6.0, 1))
    assert sharp is True


def test_le_bruit_ne_fait_pas_passer_une_image_floue_pour_nette():
    """Le piège du bruit : il fabrique du gradient et simule du détail."""
    for sigma in (6.0, 12.0):
        blurred = tr.gaussian_blur(scenes.textured(SIZE), 3.0)
        sharp, _ = _verdict(tr.add_noise(blurred, sigma, 1))
        assert sharp is False, f"bruit {sigma} : image floue déclarée nette"


def test_le_flou_de_bouge_oblique_est_detecte():
    """Anisotrope : les arêtes parallèles au mouvement restent nettes.

    Mesuré à la résolution d'étalonnage, où la mesure est valide.
    """
    calibrated = (1600, 1067)
    sharp, _ = _verdict(tr.motion_blur(scenes.textured(calibrated), 15, 30.0))
    assert sharp is False


def test_le_bouge_aligne_sur_un_axe_est_detecte():
    """Le cas qui a décidé du choix de méthode.

    Un bougé purement horizontal ou vertical est courant à main levée, et
    c'est celui que la candidate C rate. La candidate retenue le voit.
    """
    calibrated = (1600, 1067)
    for angle in (0.0, 90.0):
        sharp, _ = _verdict(tr.motion_blur(scenes.textured(calibrated), 21, angle))
        assert sharp is False, f"bougé à {angle}° non détecté"


def test_la_candidate_ecartee_rate_le_bouge_aligne_sur_un_axe(monkeypatch):
    """ÉCHEC de la candidate C, épinglé pour qu'il ne se perde pas.

    Sur une texture dense, un noyau en créneau de 21 px transforme les arêtes
    voisines en ondulations rapprochées : la marche vers les minima locaux y
    trouve des bosses étroites, et la largeur médiane reste celle d'une image
    nette. Le gradient de crête chute pourtant de 1,55 à 0,37 — le signal est
    là, c'est cette mesure-là qui ne le lit pas.

    C'est ce couple de cas qui a rendu la marge de C négative et fait retenir
    B. Le test fige la raison, pour que personne ne repasse à C sans savoir ce
    qu'il perd.
    """
    _use(monkeypatch, BlurMethod.EDGE_WIDTH)
    calibrated = (1600, 1067)

    horizontal, _ = _verdict(tr.motion_blur(scenes.textured(calibrated), 21, 0.0))
    assert horizontal is True, "défaut connu de C : le bougé aligné passe pour net"


# --- Monotonie de la mesure ---------------------------------------------


def test_la_largeur_d_arete_croit_avec_le_flou():
    """La mesure retenue doit être monotone, pas seulement du bon côté d'un seuil."""
    widths = [
        _read(tr.gaussian_blur(scenes.textured(SIZE), sigma)).edge_width_px
        for sigma in (0.0, 1.5, 3.0, 6.0)
    ]
    assert all(w is not None for w in widths)
    assert widths == sorted(widths)
    assert widths[0] < widths[-1]


# --- Le support ---------------------------------------------------------


def test_le_support_distingue_le_vide_de_la_pauvrete():
    """Trois ordres de grandeur séparent un aplat d'un mur à trois arêtes."""
    vide = _read(scenes.smooth_wall(SIZE)).strong_gradient_ratio
    pauvre = _read(scenes.sparse_detail(SIZE)).strong_gradient_ratio
    riche = _read(scenes.textured(SIZE)).strong_gradient_ratio

    assert vide < 0.001
    assert pauvre > 0.01
    assert riche > 0.2


def test_un_aplat_parfait_n_a_aucune_mesure_de_nettete():
    reading = _read(patterns.flat(140, SIZE))
    assert reading.edge_width_px is None
    assert reading.strong_gradient_ratio == 0.0


# --- Les trois candidates sont toujours mesurées ------------------------


def test_les_trois_candidates_sont_renvoyees_ensemble(monkeypatch):
    """Un rapport doit permettre de rejouer un choix de méthode sans réanalyser."""
    _use(monkeypatch, BlurMethod.LAPLACIAN_VARIANCE)
    reading = _read(scenes.textured(SIZE))

    assert reading.laplacian_variance > 0
    assert reading.reblur_ratio is not None
    assert reading.edge_width_px is not None


def test_la_candidate_du_lot_0_confond_pauvrete_et_flou(monkeypatch):
    """Épingle la faiblesse mesurée de la variance du Laplacien.

    Ce test ne demande pas à la candidate A d'être bonne : il fige la raison
    pour laquelle elle a été écartée. Si un jour elle réussit ce cas, c'est la
    comparaison qu'il faudra refaire — pas ce test qu'il faudra supprimer.
    """
    _use(monkeypatch, BlurMethod.LAPLACIAN_VARIANCE)

    net_mais_pauvre, _ = _verdict(scenes.sparse_detail(SIZE))
    assert net_mais_pauvre is False, "A devrait échouer ici : c'est son défaut connu"


def test_la_methode_est_reportee_dans_les_mesures(monkeypatch):
    _use(monkeypatch, BlurMethod.REBLUR_RATIO)
    quality = analyse_quality(luma(scenes.textured(SIZE)))
    assert quality.blur.method == "reblur_ratio"


# --- Codes machine ------------------------------------------------------


def test_un_mur_lisse_signale_low_texture_et_pas_blurry():
    array = scenes.smooth_wall(SIZE)
    found = quality_warnings(analyse_quality(luma(array)), *array.shape[1::-1])

    assert Warn.IMAGE_LOW_TEXTURE in found
    assert Warn.IMAGE_BLURRY not in found


def test_une_image_floue_signale_blurry():
    array = tr.gaussian_blur(scenes.textured(SIZE), 3.0)
    found = quality_warnings(analyse_quality(luma(array)), *array.shape[1::-1])

    assert Warn.IMAGE_BLURRY in found
    assert Warn.IMAGE_LOW_TEXTURE not in found


def test_une_image_nette_et_texturee_ne_declenche_rien():
    array = scenes.textured(SIZE)
    assert quality_warnings(analyse_quality(luma(array)), *array.shape[1::-1]) == []


def test_les_bornes_sont_configurables(monkeypatch):
    """Aucune borne n'est universelle : elle doit bouger sans toucher au code."""
    array = tr.gaussian_blur(scenes.textured(SIZE), 3.0)
    assert Warn.IMAGE_BLURRY in quality_warnings(analyse_quality(luma(array)), *array.shape[1::-1])

    monkeypatch.setenv("PPAI_BLUR_REBLUR_SHARP_MAX", "0.99")
    monkeypatch.setenv("PPAI_BLUR_REBLUR_BLURRY_MIN", "0.999")
    get_settings.cache_clear()
    assert Warn.IMAGE_BLURRY not in quality_warnings(
        analyse_quality(luma(array)), *array.shape[1::-1]
    )


def test_une_petite_image_n_est_jamais_agrandie():
    """Agrandir fabriquerait du flou d'interpolation."""
    assert _read(scenes.textured((320, 240))).working_side == 320


def test_la_mesure_ne_depend_pas_de_la_resolution_de_depart():
    """Deux tirages de la même scène doivent donner le même verdict.

    C'est ce que garantit la taille de travail fixe. Sans elle, la même photo
    exportée en 1600 px et en 2400 px recevrait deux réponses.
    """
    petit, _ = _verdict(scenes.textured((1200, 800)))
    grand, _ = _verdict(scenes.textured((2400, 1600)))
    assert petit is grand is True


@pytest.mark.parametrize("method", list(BlurMethod))
def test_toutes_les_methodes_repondent_sans_lever(monkeypatch, method):
    _use(monkeypatch, method)
    for image in (scenes.textured(SIZE), scenes.smooth_wall(SIZE), patterns.flat(200, SIZE)):
        sharp, low_texture = _verdict(image)
        assert sharp is None or isinstance(sharp, bool)
        assert isinstance(low_texture, bool)
