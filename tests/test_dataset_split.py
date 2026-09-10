"""Le split, le jeu visuel de référence, et l'aperçu de contrôle — LOT B.

Trois choses sont éprouvées ici, et chacune répond à une manière connue de se
tromper :

* un jeu de référence qui ne dit pas **pourquoi** une scène y figure dérive en
  collection de jolies photos, et personne ne sait plus ce qu'il couvre ;
* un rapport de couverture qui **comble** un trou au lieu de le publier
  laisserait croire le corpus complet ;
* un relevé humain qu'on ne peut pas **regarder** est un relevé qu'on approuve
  sans le voir.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from benchmarks.dataset import (
    GOLDEN_CASES_REQUIRED,
    Difficulty,
    GoldenCase,
    Manifest,
    Photo,
    SceneTrait,
    Split,
    golden_coverage,
    load_manifest,
)
from scripts.import_annotation import render_overlay

PROVENANCE = {
    "source": "test",
    "license": "aucune",
    "verifiedOn": "2026-09-10",
    "usage": "local_evaluation_only",
}


def _photo(identifiant: str, **kwargs: object) -> Photo:
    base: dict[str, object] = {
        "id": identifiant,
        "file": f"private-real/{identifiant}.png",
        "difficulty": "hard",
        "provenance": PROVENANCE,
    }
    base.update(kwargs)
    return Photo.model_validate(base)


# --- Le split ------------------------------------------------------------


def test_une_photo_est_de_developpement_par_defaut() -> None:
    """Le défaut ne doit pas être le jeu de référence : on n'y entre que par
    décision."""
    assert _photo("p1").split is Split.PILOT_DEVELOPMENT


def test_une_scene_de_reference_doit_dire_pour_quel_cas() -> None:
    with pytest.raises(ValidationError, match="goldenCase"):
        _photo("p1", split="golden_holdout")


def test_un_cas_de_reference_sur_une_photo_de_travail_est_refuse() -> None:
    """Sinon `goldenCase` devient un commentaire, et le split ne veut plus rien
    dire."""
    with pytest.raises(ValidationError, match="golden_holdout"):
        _photo("p1", golden_case="rug")


def test_une_photo_refusee_n_entre_pas_au_jeu_de_reference() -> None:
    """Une photo inexploitable n'a aucun rendu à juger : l'y mettre gonflerait
    la couverture sans rien couvrir."""
    with pytest.raises(ValidationError, match="refusée"):
        _photo("p1", difficulty="rejected", split="golden_holdout", golden_case="rug")


def test_une_scene_de_reference_bien_declaree_est_acceptee() -> None:
    photo = _photo("p1", split="golden_holdout", golden_case="thin_occluders")
    assert photo.golden_case is GoldenCase.THIN_OCCLUDERS


# --- La couverture, publiée et jamais comblée ----------------------------


def _manifeste(photos: list[Photo]) -> Manifest:
    return Manifest(photos=photos)


def test_la_couverture_publie_les_cas_manquants() -> None:
    manifest = _manifeste(
        [
            _photo("a", split="golden_holdout", golden_case="rug"),
            _photo("b", split="golden_holdout", golden_case="opening"),
        ]
    )
    rapport = golden_coverage(manifest)
    assert rapport["scenes"] == 2
    assert rapport["byCase"]["rug"] == ["a"]
    manquants = set(rapport["missingCases"])
    assert "rug" not in manquants and "opening" not in manquants
    assert "thin_occluders" in manquants
    assert len(manquants) == len(GOLDEN_CASES_REQUIRED) - 2


def test_un_jeu_de_reference_vide_ne_couvre_rien() -> None:
    rapport = golden_coverage(_manifeste([_photo("a")]))
    assert rapport["scenes"] == 0
    assert len(rapport["missingCases"]) == len(GOLDEN_CASES_REQUIRED)
    assert rapport["majorityIsHard"] is False


def test_un_jeu_de_reference_majoritairement_facile_est_signale() -> None:
    """Mesurer sur des scènes faciles donne de beaux chiffres et aucune
    information."""
    manifest = _manifeste(
        [
            _photo("a", difficulty="easy", split="golden_holdout", golden_case="rug"),
            _photo("b", difficulty="easy", split="golden_holdout", golden_case="opening"),
            _photo("c", difficulty="hard", split="golden_holdout", golden_case="wall_floor_hard"),
        ]
    )
    assert golden_coverage(manifest)["majorityIsHard"] is False


# --- Le corpus réel, tel qu'il est --------------------------------------


def test_le_corpus_reel_declare_son_split_et_sa_couverture() -> None:
    """Contrôle du corpus livré : il doit se lire sans surprise, y compris sur
    ce qu'il ne couvre pas."""
    racine = Path("datasets")
    if not (racine / "manifest.json").is_file():
        pytest.skip("corpus absent")
    manifest = load_manifest(racine)
    rapport = golden_coverage(manifest)

    assert rapport["scenes"] >= 5
    assert rapport["majorityIsHard"] is True, "le jeu de référence doit rester difficile"
    for identifiant in sum((ids for ids in rapport["byCase"].values()), []):
        photo = next(p for p in manifest.photos if p.id == identifiant)
        assert photo.difficulty is not Difficulty.REJECTED
    #: Les deux cas connus comme non couverts au LOT B. Ce test tombera le jour
    #: où les photos existeront — c'est le but, et le message le dira.
    assert set(rapport["missingCases"]) == {"rug", "massive_furniture"}, (
        "la couverture du jeu de référence a changé : mettez à jour "
        "docs/DATASET-STRATEGY-V2.md avant de toucher ce test"
    )


def test_le_corpus_reel_ne_contient_aucun_tapis() -> None:
    """Le manque le plus coûteux du corpus, verrouillé pour qu'il ne se perde
    pas de vue."""
    racine = Path("datasets")
    if not (racine / "manifest.json").is_file():
        pytest.skip("corpus absent")
    manifest = load_manifest(racine)
    avec_tapis = [p.id for p in manifest.photos if SceneTrait.RUG in p.traits]
    assert avec_tapis == [], f"un tapis est apparu ({avec_tapis}) : mettez à jour la stratégie"


def test_le_manifeste_reel_se_relit_apres_ecriture() -> None:
    """Le manifeste est écrit par des scripts et relu par pydantic : la
    sérialisation doit faire l'aller-retour."""
    racine = Path("datasets")
    if not (racine / "manifest.json").is_file():
        pytest.skip("corpus absent")
    manifest = load_manifest(racine)
    copie = Manifest.model_validate(json.loads(manifest.model_dump_json(by_alias=True)))
    assert [p.id for p in copie.photos] == [p.id for p in manifest.photos]
    assert [p.split for p in copie.photos] == [p.split for p in manifest.photos]


# --- L'aperçu de contrôle ------------------------------------------------


def test_l_apercu_marque_le_sol_et_laisse_le_reste(tmp_path: Path) -> None:
    image = np.full((40, 60, 3), 128, dtype=np.uint8)
    floor = np.zeros((40, 60), dtype=np.uint8)
    floor[20:, :] = 255

    sortie = tmp_path / "apercu.png"
    render_overlay(image, floor, None, sortie)
    assert sortie.is_file()

    import cv2

    relu = cv2.cvtColor(cv2.imread(str(sortie)), cv2.COLOR_BGR2RGB)
    #: Le sol relevé verdit ; le haut de l'image, non.
    assert relu[30, 30, 1] > relu[30, 30, 0] + 20
    assert abs(int(relu[5, 30, 1]) - 128) <= 2


def test_l_apercu_distingue_l_incertain_du_sol(tmp_path: Path) -> None:
    """Deux teintes, parce que « je ne sais pas » et « c'est du sol » ne se
    relisent pas de la même façon."""
    image = np.full((40, 60, 3), 128, dtype=np.uint8)
    floor = np.zeros((40, 60), dtype=np.uint8)
    floor[20:, :] = 255
    uncertain = np.zeros((40, 60), dtype=np.uint8)
    uncertain[20:24, :] = 255

    sortie = tmp_path / "apercu.png"
    render_overlay(image, floor, uncertain, sortie)

    import cv2

    relu = cv2.cvtColor(cv2.imread(str(sortie)), cv2.COLOR_BGR2RGB)
    zone_sol = relu[35, 30]
    zone_incertaine = relu[22, 30]
    assert not np.array_equal(zone_sol, zone_incertaine)
    #: L'ambre de l'incertain est plus rouge que le vert du sol.
    assert int(zone_incertaine[0]) > int(zone_sol[0])


def test_l_apercu_ne_touche_pas_la_photo(tmp_path: Path) -> None:
    image = np.full((30, 30, 3), 100, dtype=np.uint8)
    original = image.copy()
    floor = np.ones((30, 30), dtype=np.uint8) * 255
    render_overlay(image, floor, None, tmp_path / "a.png")
    assert np.array_equal(image, original)
