"""Le banc d'essai : comptage, faux positifs, reproductibilité.

Le test le plus important du fichier est
`test_un_detecteur_qui_sur_detecte_est_pris_en_faute`. Le banc d'essai du
LOT 0 rapportait « aucun défaut manqué » et c'était vrai — mais un détecteur
qui déclare tout sur tout n'en manque aucun non plus. Un compteur qui ne sait
pas prendre la sur-détection en faute ne mesure rien.
"""

import csv
import json

import pytest

from app.core.warnings import INFORMATIONAL, SCORED, Warn
from benchmarks import scoring
from benchmarks.dataset import DATASET_SCHEMA, Difficulty, load_manifest
from benchmarks.run_benchmark import BENCHMARK_SCHEMA, CSV_COLUMNS, run, synthetic_cases

# --- Le comptage --------------------------------------------------------


def test_un_detecteur_qui_sur_detecte_est_pris_en_faute():
    """LE test du lot sur la méthodologie.

    Un détecteur qui annonce tous les défauts possibles ne manque rien — son
    rappel est parfait. Il est pourtant inutilisable : un utilisateur à qui
    l'on signale cinq problèmes sur une photo correcte cesse de lire les
    avertissements. Le comptage doit donc le condamner.
    """
    tout = scoring.score_image(expected={Warn.IMAGE_BLURRY}, emitted=set(SCORED))

    assert not tout.false_negatives, "il ne manque rien, par construction"
    assert len(tout.false_positives) == len(SCORED) - 1
    assert not tout.perfect


def test_un_detecteur_muet_est_pris_en_faute_aussi():
    """Le symétrique : ne rien dire n'est pas mieux."""
    rien = scoring.score_image(expected={Warn.IMAGE_BLURRY, Warn.IMAGE_TOO_DARK}, emitted=set())

    assert len(rien.false_negatives) == 2
    assert not rien.false_positives
    assert not rien.perfect


def test_une_detection_exacte_est_parfaite():
    exact = scoring.score_image(
        expected={Warn.IMAGE_BLURRY}, emitted={Warn.IMAGE_BLURRY, Warn.STAGE_NOT_IMPLEMENTED}
    )
    assert exact.perfect
    assert exact.detected == {Warn.IMAGE_BLURRY}
    assert exact.informational == {Warn.STAGE_NOT_IMPLEMENTED}


def test_les_codes_informationnels_ne_comptent_ni_pour_ni_contre():
    """`lens_analysis_undetermined` est un aveu, pas une affirmation.

    Le compter en faux positif punirait l'honnêteté ; le compter en vrai
    positif récompenserait un détecteur qui ne répondrait jamais rien.
    """
    score = scoring.score_image(expected=set(), emitted=set(INFORMATIONAL))

    assert not score.false_positives
    assert not score.detected
    assert score.informational == set(INFORMATIONAL)
    assert score.perfect


def test_la_matrice_a_un_denominateur_explicite():
    """`tn` se compte sur le jeu d'étiquettes, pas sur tous les codes du projet."""
    score = scoring.score_image(expected={Warn.IMAGE_BLURRY}, emitted={Warn.IMAGE_BLURRY})
    totals = scoring.total([score], undetermined_lens=0)

    counts = totals.overall
    total_cells = (
        counts.true_positive + counts.true_negative + counts.false_positive + counts.false_negative
    )
    assert total_cells == len(SCORED)
    assert totals.as_dict()["definitions"]["labelSet"] == sorted(c.value for c in SCORED)


def test_aucune_exactitude_n_est_publiee():
    """Sur un problème multi-label majoritairement négatif, elle flatte un muet."""
    published = scoring.total([], undetermined_lens=0).as_dict()
    assert "accuracy" not in published
    assert "detectedOfExpected" in published
    assert "falseAlarmsPerImage" in published


def test_les_cas_indetermines_sont_comptes_a_part():
    totals = scoring.total([], undetermined_lens=7)
    assert totals.as_dict()["undeterminedLens"] == 7


# --- Le comptage de distorsion ------------------------------------------


def test_le_sens_de_distorsion_est_verifie():
    """Se tromper de sens rendrait la mesure inexploitable au LOT 4."""
    bon = scoring.score_lens(0.15, "distortion_suspected", 0.15, "barrel")
    mauvais = scoring.score_lens(0.15, "distortion_suspected", -0.15, "pincushion")

    assert bon.sign_correct is True
    assert mauvais.sign_correct is False


def test_l_erreur_d_intensite_est_mesuree():
    score = scoring.score_lens(0.20, "distortion_suspected", 0.115, "barrel")
    assert score.k1_absolute_error == pytest.approx(0.085)


def test_le_sens_n_est_pas_juge_sur_une_scene_sans_distorsion():
    score = scoring.score_lens(0.0, "no_distortion_evidence", 0.0, None)
    assert score.sign_correct is None
    assert score.truth_distorted is False


# --- Exécution sur le corpus synthétique --------------------------------


@pytest.fixture(scope="module")
def report(tmp_path_factory):
    return run(synthetic_cases(), tmp_path_factory.mktemp("bench"), "synthetic")


def test_le_banc_analyse_tout_le_corpus(report):
    assert report["corpus"]["images"] > 30
    assert report["corpus"]["graded"] > 0
    assert report["corpus"]["ungraded"] > 0


def test_le_rapport_embarque_la_configuration_des_algorithmes(report):
    """Sans elle, deux rapports ne sont pas comparables."""
    config = report["algorithmConfig"]
    assert config["blur_method"]
    assert config["lens_method"]
    assert "blur_edge_width_sharp_max" in config
    assert "lens_k1_suspect_min" in config


def test_le_rapport_est_versionne_et_date(report):
    assert report["schema"] == BENCHMARK_SCHEMA
    assert report["ranAt"]
    assert report["corpusSeed"] is not None
    assert report["environment"]["python"]


def test_le_banc_compte_les_faux_positifs_et_les_faux_negatifs(report):
    """Les quatre compteurs existent, et la configuration retenue est propre.

    Un corpus propre ne prouve pas qu'un détecteur est bon — il prouve qu'il
    passe *ce* corpus. Les limites du lot ne sont pas dans cette matrice mais
    dans `test_la_candidate_ecartee_rate_le_bouge_aligne_sur_un_axe`, dans le
    biais d'intensité du recadrage décentré, et dans le domaine de résolution
    de la mesure de netteté. Voir docs/quality-methodology.md.
    """
    scores = report["scores"]
    assert set(scores["overall"]) == {"tp", "fp", "fn", "tn"}
    assert scores["imagesWithFalsePositive"] == 0
    assert scores["imagesWithFalseNegative"] == 0
    # Un corpus qui n'attend rien passerait aussi : il faut de vraies attentes.
    assert scores["overall"]["tp"] > 30


def test_le_banc_prendrait_une_sur_detection_en_faute(report):
    """Contrôle du contrôle : le compteur doit pouvoir condamner.

    Vérifie sur le corpus réel — pas sur un cas fabriqué — qu'un détecteur
    déclarant tout serait bien pris en faute. Sans cela, `fp: 0` pourrait
    n'être qu'un compteur qui ne compte rien.
    """
    from app.core.warnings import SCORED

    rows = [row for row in report["rows"] if row.get("graded")]
    inflated = [
        scoring.score_image(
            expected={Warn(code) for code in (row["expected"] or "").split("|") if code},
            emitted=set(SCORED),
        )
        for row in rows
    ]
    totals = scoring.total(inflated, undetermined_lens=0)
    assert totals.overall.false_positive > 100
    assert totals.perfect_images == 0


def test_la_distorsion_est_mesuree_contre_la_verite_terrain(report):
    lens = report["lens"]
    assert lens["distortedCases"] >= 6
    assert lens["cleanCases"] >= 5
    assert lens["detectedWhenDistorted"] == lens["distortedCases"]
    assert lens["detectedWhenClean"] == 0
    assert lens["signCorrectWhenDetected"] == lens["distortedCases"]


def test_les_durees_par_etape_sont_rapportees(report):
    timings = report["timings"]
    for stage in ("load_image_ms", "quality_analysis_ms", "lens_analysis_ms", "total_ms"):
        assert timings[stage]["mean"] is not None
        assert timings[stage]["max"] is not None


def test_chaque_ligne_est_reproductible(report):
    """Les colonnes sans lesquelles on ne sait pas ce qui a été mesuré."""
    row = next(r for r in report["rows"] if r["id"] == "sharp-textured")
    for column in ("id", "difficulty", "graded", "status", "blur_method", "lens_method"):
        assert row[column] is not None, column


def test_les_deux_rapports_sont_ecrits(tmp_path):
    run(synthetic_cases(), tmp_path, "synthetic")

    written = json.loads((tmp_path / "benchmark.json").read_text(encoding="utf-8"))
    assert written["schema"] == BENCHMARK_SCHEMA

    with (tmp_path / "benchmark.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    # Colonnes fixes : deux rapports doivent rester comparables même si le
    # contenu des corpus diffère.
    assert tuple(rows[0]) == CSV_COLUMNS
    assert len(rows) == written["corpus"]["images"]


def test_le_csv_expose_faux_positifs_et_faux_negatifs(tmp_path):
    run(synthetic_cases(), tmp_path, "synthetic")
    with (tmp_path / "benchmark.csv").open(encoding="utf-8") as handle:
        columns = next(csv.reader(handle))
    assert "false_positives" in columns
    assert "false_negatives" in columns


# --- Le manifeste des photos réelles ------------------------------------


def test_le_manifeste_reel_est_valide():
    """Vide au terme du LOT 1, et déclaré vide — voir datasets/README.md."""
    from pathlib import Path

    manifest = load_manifest(Path("datasets"))
    assert manifest.dataset_schema == DATASET_SCHEMA
    for photo in manifest.photos:
        # La provenance est obligatoire par le schéma ; ce qui se vérifie ici
        # est qu'aucune entrée n'a été ajoutée à la main sans licence nommée.
        assert photo.provenance.source
        assert photo.provenance.license


def test_un_manifeste_absent_est_une_erreur_claire(tmp_path):
    with pytest.raises(FileNotFoundError, match="Manifeste absent"):
        load_manifest(tmp_path)


def test_les_quatre_difficultes_sont_un_vocabulaire_ferme():
    assert {d.value for d in Difficulty} == {"easy", "medium", "hard", "rejected"}


def test_un_corpus_reel_vide_ne_plante_pas(tmp_path):
    """Le cas de départ du projet : la structure existe, les photos pas encore."""
    from benchmarks.run_benchmark import dataset_cases

    (tmp_path / "manifest.json").write_text(
        json.dumps({"schema": DATASET_SCHEMA, "photos": []}), encoding="utf-8"
    )
    result = run(dataset_cases(tmp_path), tmp_path / "out", "dataset")
    assert result["corpus"]["images"] == 0
