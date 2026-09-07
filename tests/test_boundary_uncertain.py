"""La règle du contour dans l'incertain, prouvée cas par cas.

**La règle.** Une portion de frontière située dans une zone `uncertain` ne doit
contribuer ni positivement ni négativement à la précision ou au rappel du
contour. Ni récompense, ni pénalité : silence.

L'implémentation du préambule la respecte déjà. Ce fichier ne la corrige pas,
il la **prouve** — et une règle non testée est une intention, pas une garantie.

## Ce que ces tests ont appris sur le protocole

Le premier jet de `test_une_erreur_couverte_par_l_incertain_ne_coute_rien`
mesurait une précision de 0,929 au lieu de 1,000, et le défaut n'était pas dans
le code : la zone incertaine s'arrêtait pile là où l'erreur commençait.

Un décrochement de masque produit une frontière **épaisse de quelques pixels**
— l'érosion travaille sur un voisinage 3 × 3, donc le contour d'une marche
occupe cinq colonnes et non une. Une zone incertaine tracée au ras de
l'incertitude laisse ces colonnes évaluées, et l'annotateur se voit reprocher
exactement ce qu'il avait déclaré indécidable.

D'où la consigne, désormais dans `docs/annotation-protocol.md` : **une zone
incertaine doit couvrir le désaccord qu'elle excuse, avec une petite marge.**
C'est une règle d'annotation, pas un correctif de code.
"""

import numpy as np
import pytest

from benchmarks.segmentation import MetricConfig, boundary_metrics

HEIGHT, WIDTH = 400, 600

#: Tolérance confortable (~7 px sur 600 × 400) pour que les cas se lisent sans
#: être au pixel près.
CONFIG = MetricConfig(boundary_tolerance_fraction=0.01)


def _floor() -> np.ndarray:
    """Sol plausible : le tiers bas, jonction franche à y = 250."""
    mask = np.zeros((HEIGHT, WIDTH), dtype=bool)
    mask[250:, :] = True
    return mask


def _zone(top: int, bottom: int, right: int = WIDTH) -> np.ndarray:
    mask = np.zeros((HEIGHT, WIDTH), dtype=bool)
    mask[top:bottom, :right] = True
    return mask


# --- Cas 1 : frontière correcte hors zone incertaine ---------------------


def test_une_zone_incertaine_ailleurs_ne_change_rien():
    """Le cas de contrôle : si l'incertain ne touche pas la frontière, il est nul.

    Sans ce test, un défaut de masquage pourrait faire chuter tous les scores
    dès qu'une zone incertaine existe quelque part dans l'image, et on
    l'attribuerait au détecteur.
    """
    reference = boundary_metrics(_floor(), _floor(), None, CONFIG)
    with_zone = boundary_metrics(_floor(), _floor(), _zone(0, 80), CONFIG)

    assert reference.f1 == 1.0
    assert with_zone.f1 == reference.f1
    assert with_zone.precision == reference.precision
    assert with_zone.recall == reference.recall
    assert with_zone.predicted_boundary_pixels == reference.predicted_boundary_pixels


@pytest.mark.parametrize("band", [20, 60, 120, 200])
def test_agrandir_une_zone_incertaine_loin_du_sol_ne_penalise_jamais(band):
    """Aucune pénalisation artificielle, quelle que soit la taille de la zone."""
    metrics = boundary_metrics(_floor(), _floor(), _zone(0, band), CONFIG)
    assert metrics.f1 == 1.0


# --- Cas 2 : frontière différente uniquement dans l'incertain ------------


def test_une_erreur_couverte_par_l_incertain_ne_coute_rien():
    """LE test de la règle.

    La prédiction se trompe franchement sur la moitié gauche — 30 px de
    décalage — mais l'annotateur avait déclaré cette zone indécidable. Le score
    doit être parfait.

    La zone couvre le décrochement **avec une marge** : sans elle, les cinq
    colonnes de frontière que produit la marche restent évaluées et la
    précision tombe à 0,929. Voir l'en-tête du module.
    """
    prediction = _floor()
    prediction[250:280, :300] = False

    excused = boundary_metrics(prediction, _floor(), _zone(240, 290, right=320), CONFIG)
    assert excused.precision == 1.0
    assert excused.recall == 1.0
    assert excused.f1 == 1.0


def test_la_meme_erreur_non_couverte_est_lourdement_penalisee():
    """Le pendant du précédent : sans excuse déclarée, l'erreur compte.

    Les deux tests n'ont de sens qu'ensemble. Le premier seul prouverait
    seulement qu'on sait annuler un score ; celui-ci montre que la mesure voit
    bien l'erreur quand personne ne l'a déclarée indécidable.
    """
    prediction = _floor()
    prediction[250:280, :300] = False

    judged = boundary_metrics(prediction, _floor(), None, CONFIG)
    assert judged.f1 is not None and judged.f1 < 0.6


def test_une_zone_au_ras_du_desaccord_laisse_la_marche_evaluee():
    """Fige la leçon de protocole, pour qu'elle ne se reperde pas.

    Ce n'est pas un défaut à corriger : c'est le comportement correct d'une
    frontière épaisse de plusieurs pixels. Le test existe pour que la consigne
    d'annotation — couvrir avec une marge — reste rattachée à sa raison.
    """
    prediction = _floor()
    prediction[250:280, :300] = False

    flush = boundary_metrics(prediction, _floor(), _zone(240, 290, right=300), CONFIG)
    assert flush.precision is not None and flush.precision < 1.0

    generous = boundary_metrics(prediction, _floor(), _zone(240, 290, right=320), CONFIG)
    assert generous.precision == 1.0


# --- Cas 3 : frontière juste au bord d'une zone incertaine ---------------


def test_une_zone_qui_jouxte_la_jonction_sans_la_toucher_ne_change_rien():
    """La zone s'arrête pile sur la ligne de jonction, sans l'inclure."""
    metrics = boundary_metrics(_floor(), _floor(), _zone(200, 250), CONFIG)
    assert metrics.f1 == 1.0
    assert metrics.truth_boundary_pixels > 0


def test_une_zone_qui_commence_juste_apres_la_jonction_ne_change_rien():
    metrics = boundary_metrics(_floor(), _floor(), _zone(252, 300), CONFIG)
    assert metrics.f1 == 1.0


# --- Cas 4 : tolérance chevauchant une zone incertaine ------------------


def test_une_bande_incertaine_sur_la_jonction_retire_le_contour_a_juger():
    """Rien n'est jugé, plutôt que jugé à tort.

    Une bande fine posée sur toute la jonction retire l'intégralité du contour
    évaluable des deux côtés : le résultat est **indéfini**, et c'est exact.
    Renvoyer 1,0 récompenserait un annotateur d'avoir tout déclaré indécidable ;
    renvoyer 0,0 le punirait de son honnêteté.
    """
    metrics = boundary_metrics(_floor(), _floor(), _zone(246, 254), CONFIG)

    assert metrics.predicted_boundary_pixels == 0
    assert metrics.truth_boundary_pixels == 0
    assert metrics.precision is None
    assert metrics.recall is None
    assert metrics.f1 is None


def test_une_zone_partielle_laisse_juger_le_reste():
    """L'exclusion est locale : la moitié non couverte reste mesurée."""
    metrics = boundary_metrics(_floor(), _floor(), _zone(240, 260, right=300), CONFIG)

    assert metrics.truth_boundary_pixels > 0
    assert metrics.truth_boundary_pixels < WIDTH
    assert metrics.f1 == 1.0


def test_la_cible_traverse_l_incertain_pour_ne_pas_punir_le_voisinage():
    """Point de méthode : on n'évalue pas dans l'incertain, mais on y cherche.

    La frontière humaine reste une **cible** valide même là où elle est
    déclarée indécidable. La retirer de la cible ferait compter fausse la
    prédiction qui la longe correctement juste à côté de la zone — l'inverse
    exact de ce qu'on veut.
    """
    metrics = boundary_metrics(_floor(), _floor(), _zone(248, 252, right=300), CONFIG)
    assert metrics.precision == 1.0, "la moitié droite doit trouver sa cible"


# --- Cas 5 : symétrie et absence d'effet de bord ------------------------


def test_l_exclusion_agit_pareillement_sur_la_precision_et_le_rappel():
    """Excuser un excès et excuser un manque doivent coûter autant : rien."""
    excess = _floor()
    excess[220:250, :] = True  # la prédiction monte sur le mur
    shortfall = _floor()
    shortfall[250:280, :] = False  # la prédiction s'arrête trop bas

    zone = _zone(210, 290)
    assert boundary_metrics(excess, _floor(), zone, CONFIG).f1 is None
    assert boundary_metrics(shortfall, _floor(), zone, CONFIG).f1 is None


def test_une_zone_incertaine_vide_equivaut_a_son_absence():
    empty = np.zeros((HEIGHT, WIDTH), dtype=bool)
    assert (
        boundary_metrics(_floor(), _floor(), empty, CONFIG).f1
        == boundary_metrics(_floor(), _floor(), None, CONFIG).f1
    )


def test_la_regle_tient_a_toutes_les_tolerances():
    """Le comportement ne doit pas dépendre du réglage de tolérance."""
    prediction = _floor()
    prediction[250:280, :300] = False
    zone = _zone(240, 290, right=330)

    for fraction in (0.0025, 0.005, 0.01):
        config = MetricConfig(boundary_tolerance_fraction=fraction)
        metrics = boundary_metrics(prediction, _floor(), zone, config)
        assert metrics.precision == 1.0, f"tolérance {fraction}"
