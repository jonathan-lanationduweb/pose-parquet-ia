"""La campagne pilote : quatre scènes, huit relevés, et ce que le rapport doit rendre.

Deux tests portent le lot. `test_les_quatre_scenes_ne_se_ressemblent_pas` refuse
une sélection qui remplirait les catégories avec quatre pièces presque
identiques — le corpus est petit, et quatre scènes redondantes n'apprendraient
rien. `test_les_deux_decisions_humaines_sont_mises_a_l_epreuve` vérifie que les
règles décidées après le rapport du LOT 2A sont réellement testées par la
campagne, plutôt qu'écrites et jamais éprouvées.
"""

import json
from pathlib import Path

import pytest

from app.schemas.annotation import AnnotationStatus
from benchmarks.agreement import DEFAULT_TOLERANCES, summarise
from benchmarks.campaign import CAMPAIGN, PASSES, expected_annotations, progress
from benchmarks.dataset import load_manifest
from benchmarks.run_pilot import run
from tests.conftest import draw_file

CORPUS = Path("datasets")


# --- La sélection --------------------------------------------------------


def test_les_quatre_scenes_existent_dans_le_corpus():
    """Une campagne qui nomme une photo absente ne démarre jamais."""
    known = {photo.id for photo in load_manifest(CORPUS).photos}
    for selection in CAMPAIGN:
        assert selection.photo_id in known, selection.photo_id


def test_les_roles_couvrent_les_trois_difficultes_et_l_ambiguite():
    """Un `easy`, un `medium`, un `hard`, et la scène la plus ambiguë."""
    assert [selection.role for selection in CAMPAIGN] == [
        "easy",
        "medium",
        "hard",
        "most_ambiguous",
    ]


def test_les_roles_correspondent_a_la_difficulte_du_manifeste():
    """Le rôle annoncé ne doit pas contredire la difficulté enregistrée."""
    difficulty = {photo.id: photo.difficulty.value for photo in load_manifest(CORPUS).photos}
    for selection in CAMPAIGN:
        if selection.role == "most_ambiguous":
            # Libre par construction, mais pas sur une scène facile : la
            # scène la plus ambiguë du corpus n'est pas une pièce vide.
            assert difficulty[selection.photo_id] in {"medium", "hard"}
        else:
            assert difficulty[selection.photo_id] == selection.role


def test_les_quatre_scenes_ne_se_ressemblent_pas():
    """Le critère de sélection est la diversité réelle, pas le quota.

    Quatre pièces vides bien réparties en easy/medium/hard rempliraient les
    catégories sans rien apprendre. Chaque scène doit donc apporter au moins un
    trait qu'aucune autre de la campagne ne porte.
    """
    traits = {
        photo.id: {trait.value for trait in photo.traits} for photo in load_manifest(CORPUS).photos
    }
    chosen = {selection.photo_id: traits[selection.photo_id] for selection in CAMPAIGN}

    for photo_id, own in chosen.items():
        others = set().union(*(value for key, value in chosen.items() if key != photo_id))
        assert own - others, f"{photo_id} n'apporte aucun trait propre"


def test_la_campagne_couvre_les_difficultes_qui_comptent():
    """Les criteres utiles listés doivent être représentés."""
    traits = {
        photo.id: {trait.value for trait in photo.traits} for photo in load_manifest(CORPUS).photos
    }
    covered = set().union(*(traits[selection.photo_id] for selection in CAMPAIGN))

    for required in (
        "furnished",  # mobilier
        "low_wall_floor_contrast",  # frontière mur/sol difficile
        "doors",  # encadrement ou seuil
        "reflective_floor",  # réflexion
        "hidden_corners",  # zones partiellement cachées
        "thin_furniture_legs",  # pieds fins
        "exterior_visible",  # surface extérieure — décision 1
    ):
        assert required in covered, required


def test_les_deux_decisions_humaines_sont_mises_a_l_epreuve():
    """Extérieur exclu et élément encastré exclu doivent être testés.

    Une règle écrite et jamais éprouvée est une règle qu'on découvrira
    inapplicable au pire moment. `chambre` porte les deux, et ses consignes
    doivent les rappeler à l'annotateur.
    """
    watch = {selection.photo_id: " ".join(selection.watch_for).lower() for selection in CAMPAIGN}
    assert "chambre" in watch
    assert "dehors" in watch["chambre"] or "extérieur" in watch["chambre"]
    assert "grille" in watch["chambre"]


def test_chaque_scene_porte_sa_raison():
    """Une sélection dont on a perdu le motif se refait au hasard."""
    for selection in CAMPAIGN:
        assert len(selection.rationale) > 80
        assert selection.watch_for


# --- L'avancement --------------------------------------------------------


def test_huit_releves_sont_attendus():
    assert len(expected_annotations()) == len(CAMPAIGN) * len(PASSES) == 8


def test_un_corpus_vide_annonce_les_huit_manquants():
    state = progress(set())
    assert state["collected"] == 0
    assert state["expected"] == 8
    assert len(state["missing"]) == 8
    assert state["complete"] is False


def test_une_passe_presente_ne_manque_plus():
    state = progress({("couloir", "A")})
    assert state["collected"] == 1
    assert {"photoId": "couloir", "pass": "A"} not in state["missing"]
    assert {"photoId": "couloir", "pass": "B"} in state["missing"]


def test_la_campagne_complete_est_reconnue():
    assert progress(set(expected_annotations()))["complete"] is True


def test_une_passe_hors_campagne_ne_compte_pas():
    """Annoter `bureau-vide` est utile, mais n'avance pas cette campagne."""
    assert progress({("bureau-vide", "A")})["collected"] == 0


# --- Ce que le rapport doit rendre --------------------------------------


@pytest.fixture
def paired(corpus: Path) -> Path:
    """Une photo, deux passes indépendantes du même annotateur."""
    from scripts import import_annotation

    for label, top in (("A", 0.60), ("B", 0.63)):
        import_annotation.build(
            draw_file(corpus, top),
            corpus,
            "jo",
            AnnotationStatus.APPROVED,
            "jo",
            None,
            pass_label=label,
            independent=True,
        )
    return corpus


def test_le_rapport_donne_les_trois_tolerances_par_scene(paired, tmp_path):
    """Aucune des trois ne doit pouvoir disparaître d'un rapport de calibration."""
    report = run(paired, tmp_path / "out", DEFAULT_TOLERANCES)
    keys = set(report["pairs"][0]["boundaryByTolerance"])
    assert keys == {"0.0025", "0.0050", "0.0100"}
    assert set(report["humanAgreement"]["boundaryF1ByTolerance"]) == keys


def test_le_rapport_donne_les_deux_durees_et_la_part_incertaine(paired, tmp_path):
    """Par paire : qui, quelle passe, quand, combien de temps, quelle part exclue."""
    row = run(paired, tmp_path / "out")["pairs"][0]

    assert row["difficulty"] == "hard"
    assert row["passes"]["first"]["passLabel"] == "A"
    assert row["passes"]["second"]["passLabel"] == "B"
    assert row["passes"]["first"]["totalSeconds"] == 240.0
    assert row["passes"]["second"]["totalSeconds"] == 240.0
    assert row["passes"]["first"]["annotatedOn"]
    assert row["passes"]["first"]["revision"] == 1
    assert row["ignoredFractionFirst"] == 0.0
    assert row["ignoredFractionSecond"] == 0.0


def test_deux_passes_d_une_meme_main_ne_sont_jamais_un_accord(paired, tmp_path):
    """Le nom de la mesure décide du plafond qu'on opposera aux modèles."""
    report = run(paired, tmp_path / "out")
    assert report["humanAgreement"]["kind"] == "intra_annotator_repeatability"


def test_la_repetabilite_est_rendue_par_difficulte(paired, tmp_path):
    """Et une difficulté représentée par une seule paire le dit."""
    entry = run(paired, tmp_path / "out")["repeatabilityByDifficulty"]["hard"]
    assert entry["scenes"] == 1
    assert entry["minIou"] == entry["meanIou"]
    assert "une seule paire" in entry["note"]


def test_les_agregats_donnent_aussi_le_maximum(paired, tmp_path):
    """Moyenne, médiane, minimum ET maximum : les quatre sont demandés."""
    iou = run(paired, tmp_path / "out")["humanAgreement"]["iou"]
    assert set(iou) == {"counted", "mean", "median", "min", "max"}


def test_des_agregats_vides_gardent_le_maximum():
    assert summarise([])["pairs"] == 0


def test_le_rapport_suit_l_avancement_de_la_campagne(paired, tmp_path):
    """La commande d'analyse doit dire elle-même ce qui manque encore."""
    state = run(paired, tmp_path / "out")["campaign"]
    assert state["expected"] == 8
    # La photo du corpus de test n'est pas une scène de campagne : rien
    # n'avance, et le rapport doit le dire plutôt que de le déduire.
    assert state["collected"] == 0
    assert state["complete"] is False


def test_le_rapport_reste_lisible_sans_annotation(corpus, tmp_path):
    """Sans relevé, la campagne s'annonce vide — et rien ne plante."""
    report = run(corpus, tmp_path / "out")
    assert report["campaign"]["collected"] == 0
    assert report["repeatabilityByDifficulty"] == {}
    assert report["pairs"] == []


# --- Le schéma suffit-il ? ----------------------------------------------


def test_le_format_enregistre_les_six_informations_de_passe(paired):
    """image, annotateur, passe, date, durée, révision — sans `floor-annotation@2`.

    Vérification demandée avant toute modification de schéma : si les six
    tiennent déjà, le format ne bouge pas.
    """
    written = json.loads((paired / "annotations" / "p1.A.json").read_text(encoding="utf-8"))

    assert written["photoId"] == "p1"  # image
    assert written["annotator"] == "jo"  # annotateur
    assert written["passLabel"] == "A"  # passe
    assert written["independentPass"] is True  # passe indépendante
    assert written["annotatedOn"]  # date
    assert written["timing"]["firstPassSeconds"] == 240  # durée
    assert written["revision"] == 1  # révision
    assert written["schema"] == "pose-parquet-ai/floor-annotation@1"


def test_l_etiquette_de_passe_saisie_dans_l_outil_est_reprise(corpus):
    """Oublier `--pass-label` ne doit pas écraser la passe précédente.

    C'est le mode d'échec silencieux le plus coûteux de la campagne : aucune
    erreur, un relevé perdu, et une paire devenue impossible à mesurer.
    """
    from scripts import import_annotation

    path = draw_file(corpus, 0.60)
    draw = json.loads(path.read_text(encoding="utf-8"))
    draw["passLabel"] = "B"
    path.write_text(json.dumps(draw), encoding="utf-8")

    out = import_annotation.build(path, corpus, "jo", AnnotationStatus.DRAFT, None, None)
    assert out.name == "p1.B.json"
    assert json.loads(out.read_text(encoding="utf-8"))["passLabel"] == "B"


def test_le_drapeau_explicite_prime_sur_l_outil(corpus):
    """Le tracé propose ; la ligne de commande décide."""
    from scripts import import_annotation

    path = draw_file(corpus, 0.60)
    draw = json.loads(path.read_text(encoding="utf-8"))
    draw["passLabel"] = "B"
    path.write_text(json.dumps(draw), encoding="utf-8")

    out = import_annotation.build(
        path, corpus, "jo", AnnotationStatus.DRAFT, None, None, pass_label="A"
    )
    assert json.loads(out.read_text(encoding="utf-8"))["passLabel"] == "A"


def test_un_trace_sans_etiquette_reste_accepte(corpus):
    """`floor-draw@1` ne change pas : le champ est facultatif."""
    from scripts import import_annotation

    out = import_annotation.build(
        draw_file(corpus, 0.60), corpus, "jo", AnnotationStatus.DRAFT, None, None
    )
    assert out.name == "p1.json"
    assert json.loads(out.read_text(encoding="utf-8"))["passLabel"] is None


# --- Relecture : auto-relecture ou revue indépendante ? -----------------


def test_sans_relecteur_nomme_l_annotation_devient_une_auto_relecture(corpus):
    """Le repli est conservateur, mais il doit rester connu.

    `--reviewer` omis sur un statut non-draft inscrit l'annotateur comme
    relecteur : les deux noms coïncident, donc le rapport lit une
    auto-relecture. Le sens de l'erreur ne peut que sous-estimer la relecture,
    jamais la surestimer — mais un lecteur qui croirait le champ obligatoire
    prendrait un oubli pour un choix.
    """
    from scripts import import_annotation

    out = import_annotation.build(
        draw_file(corpus, 0.60), corpus, "jonathan", AnnotationStatus.APPROVED, None, None
    )
    written = json.loads(out.read_text(encoding="utf-8"))

    assert written["review"]["reviewer"] == written["annotator"] == "jonathan"
    assert written["status"] == "approved"


def test_un_relecteur_distinct_reste_une_revue_independante(corpus):
    """Deux noms différents ne doivent jamais être aplatis en un seul."""
    from scripts import import_annotation

    out = import_annotation.build(
        draw_file(corpus, 0.60), corpus, "jonathan", AnnotationStatus.APPROVED, "alex", None
    )
    written = json.loads(out.read_text(encoding="utf-8"))

    assert written["annotator"] == "jonathan"
    assert written["review"]["reviewer"] == "alex"


def test_l_aide_de_la_ligne_de_commande_decrit_le_repli(capsys):
    """L'aide disait « obligatoire de fait » — ce qui n'était pas vrai.

    Un drapeau décrit comme obligatoire mais silencieusement remplacé est le
    genre d'écart qui fait prendre un oubli pour une décision.
    """
    from scripts import import_annotation

    with pytest.raises(SystemExit):
        import_annotation.main(["--help"])
    helped = capsys.readouterr().out.lower()

    assert "auto-relecture" in helped
    assert "obligatoire de fait" not in helped
