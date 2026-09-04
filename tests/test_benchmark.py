"""Le banc d'essai, sur les fixtures qu'il sait générer lui-même."""

import csv
import json

import pytest

from benchmarks.dataset import DATASET_SCHEMA, Difficulty, load_manifest
from benchmarks.run_benchmark import CSV_COLUMNS, run
from scripts.make_fixtures import FIXTURES, generate


@pytest.fixture(scope="module")
def corpus(tmp_path_factory):
    """Un corpus synthétique complet, écrit dans un dossier temporaire."""
    directory = tmp_path_factory.mktemp("synthetic")
    generate(directory)
    return directory


def test_le_manifeste_genere_est_valide(corpus):
    manifest = load_manifest(corpus)
    assert manifest.dataset_schema == DATASET_SCHEMA
    assert len(manifest.photos) == len(FIXTURES)


def test_aucune_verite_terrain_n_est_inventee(corpus):
    """Ces images n'ont pas de sol : prétendre le contraire serait le pire défaut."""
    for photo in load_manifest(corpus).photos:
        assert photo.ground_truth.available is False
        assert photo.ground_truth.floor_mask is None
        assert photo.ground_truth.floor_boundary is None


def test_chaque_photo_declare_source_et_licence(corpus):
    """Une photo sans provenance ne peut pas servir de référence commune."""
    for photo in load_manifest(corpus).photos:
        assert photo.source
        assert photo.license


def test_les_quatre_difficultes_sont_un_vocabulaire_ferme(corpus):
    valid = {d.value for d in Difficulty}
    assert valid == {"easy", "medium", "hard", "rejected"}
    for photo in load_manifest(corpus).photos:
        assert photo.difficulty.value in valid


def test_un_manifeste_absent_est_une_erreur_claire(tmp_path):
    with pytest.raises(FileNotFoundError, match="Manifeste absent"):
        load_manifest(tmp_path)


# --- Exécution -----------------------------------------------------------


@pytest.fixture(scope="module")
def report(corpus, tmp_path_factory):
    return run(corpus, tmp_path_factory.mktemp("out")), corpus


def test_le_benchmark_analyse_tout_le_corpus(report):
    result, _ = report
    assert result["dataset"]["analysed"] == len(FIXTURES)


def test_le_benchmark_mesure_les_metriques_attendues(report):
    """Les colonnes du LOT 0 : dimensions, flou, exposition, objectif, durées."""
    result, _ = report
    row = next(r for r in result["rows"] if r["id"] == "synth-sharp-midtone")

    assert row["width"] > 0 and row["height"] > 0
    assert row["blur_laplacian_variance"] > 0
    assert 0.0 < row["luma_mean"] < 1.0
    assert row["contrast_std"] > 0
    assert row["lens_verdict"]
    assert row["load_image_ms"] is not None
    assert row["quality_analysis_ms"] is not None
    assert row["total_ms"] is not None


def test_aucun_defaut_annonce_n_est_manque(report):
    """Le chiffre qu'on lit en premier : ce que le corpus annonçait et qu'on n'a pas vu."""
    result, _ = report
    missed = {row["id"]: row["missed_issues"] for row in result["rows"] if row["missed_issues"]}
    assert missed == {}, f"défauts manqués : {missed}"


def test_les_droites_droites_ne_sont_pas_declarees_distordues(report):
    """Le faux positif qui compte : inventer une distorsion là où il n'y en a pas."""
    result, _ = report
    row = next(r for r in result["rows"] if r["id"] == "synth-straight-edges")
    assert row["lens_verdict"] == "no_distortion_detected"


def test_les_droites_courbees_sont_declarees_suspectes(report):
    result, _ = report
    row = next(r for r in result["rows"] if r["id"] == "synth-bowed-edges")
    assert row["lens_verdict"] == "distortion_suspected"


def test_une_photo_refusee_apparait_comme_refusee(report):
    """Le bac `rejected` vérifie que le service sait dire non."""
    result, _ = report
    row = next(r for r in result["rows"] if r["id"] == "synth-too-small")
    assert row["status"] == "rejected"
    assert "image_too_small" in row["warnings"]


def test_les_deux_rapports_sont_ecrits(corpus, tmp_path):
    run(corpus, tmp_path)
    report_json = json.loads((tmp_path / "benchmark.json").read_text(encoding="utf-8"))
    assert report_json["schema"] == "pose-parquet-ai/benchmark@1"

    with (tmp_path / "benchmark.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    # Colonnes fixes : deux rapports doivent rester comparables même si le
    # contenu des corpus diffère.
    assert tuple(rows[0]) == CSV_COLUMNS
    assert len(rows) == len(FIXTURES)


def test_un_corpus_vide_ne_plante_pas(tmp_path):
    """Le cas de départ du projet : la structure existe, les photos pas encore."""
    (tmp_path / "manifest.json").write_text(
        json.dumps({"schema": DATASET_SCHEMA, "photos": []}), encoding="utf-8"
    )
    result = run(tmp_path, tmp_path / "out")
    assert result["dataset"]["analysed"] == 0
