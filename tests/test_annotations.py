"""Annotations : format, statuts, contrôles, et la chaîne complète.

Deux tests portent le préambule :

* `test_seules_les_annotations_approuvees_entrent_au_banc_d_essai` — sans lui,
  un brouillon oublié deviendrait de la vérité terrain ;
* `test_un_trace_fait_sur_d_autres_dimensions_est_refuse` — le garde-fou EXIF,
  seul endroit où un masque silencieusement faux peut encore être arrêté.
"""

import json
from datetime import date
from pathlib import Path

import numpy as np
import pytest

from app.schemas.annotation import (
    ANNOTATION_SCHEMA,
    AnnotationStatus,
    BoundaryKind,
    FloorAnnotation,
    MaskFiles,
    Review,
    UncertainReason,
)
from benchmarks.annotations import Check, corpus_report, load_corpus, load_scene
from benchmarks.dataset import (
    Difficulty,
    Provenance,
    SceneTrait,
    Usage,
    load_manifest,
    sha256_of,
)
from benchmarks.run_segmentation import available, run
from benchmarks.segmentation import load_mask, save_mask
from corpus import patterns
from scripts import add_photo, import_annotation

WIDTH, HEIGHT = 640, 480


# --- Un corpus complet, monté de zéro -----------------------------------


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    """Corpus minimal : une image privée enregistrée avec sa provenance.

    Monté par les vrais scripts, pas par des fichiers écrits à la main : ce
    qui est éprouvé ici est la chaîne que l'utilisateur suivra.
    """
    root = tmp_path / "datasets"
    (root / "private-real").mkdir(parents=True)
    (root / "manifest.json").write_text(
        json.dumps({"schema": "pose-parquet-ai/dataset@2", "photos": []}), encoding="utf-8"
    )

    image = patterns.mid_tone_checkerboard((WIDTH, HEIGHT))
    (root / "private-real" / "piece.png").write_bytes(patterns.encode(image, "PNG"))

    assert (
        add_photo.main(
            [
                "--dataset",
                str(root),
                "--file",
                "private-real/piece.png",
                "--id",
                "piece-01",
                "--difficulty",
                "medium",
                "--source",
                "image de test",
                "--license",
                "aucune (synthétique)",
                "--verified-on",
                "2026-09-07",
                "--traits",
                "furnished,rug",
            ]
        )
        == 0
    )
    return root


def _draw(root: Path, **overrides: object) -> Path:
    """Écrit un tracé plausible, tel que l'outil HTML le produirait."""
    draw: dict[str, object] = {
        "schema": import_annotation.DRAW_SCHEMA,
        "photoId": "piece-01",
        "width": WIDTH,
        "height": HEIGHT,
        # Le tiers bas : un sol plausible.
        "floorPolygons": [
            [{"x": 0.0, "y": 0.6}, {"x": 1.0, "y": 0.6}, {"x": 1.0, "y": 1.0}, {"x": 0.0, "y": 1.0}]
        ],
        "floorHoles": [
            [{"x": 0.3, "y": 0.7}, {"x": 0.5, "y": 0.7}, {"x": 0.5, "y": 0.9}, {"x": 0.3, "y": 0.9}]
        ],
        "uncertainZones": [
            {
                "reason": UncertainReason.HIDDEN_CORNER.value,
                "polygon": [
                    {"x": 0.0, "y": 0.58},
                    {"x": 0.12, "y": 0.58},
                    {"x": 0.12, "y": 0.66},
                    {"x": 0.0, "y": 0.66},
                ],
            }
        ],
        "boundary": [
            {
                "kind": BoundaryKind.WALL_FLOOR.value,
                "points": [{"x": 0.0, "y": 0.6}, {"x": 1.0, "y": 0.6}],
            }
        ],
        "notes": None,
    }
    draw.update(overrides)
    path = root / "piece.draw.json"
    path.write_text(json.dumps(draw), encoding="utf-8")
    return path


# --- Le format ------------------------------------------------------------


def test_le_sol_visible_exclut_ce_qui_le_cache(corpus):
    """Un tapis n'est pas du sol visible : il le cache.

    C'est la définition sur laquelle tout le lot repose, et elle se vérifie
    sur les pixels : le trou tracé doit être absent du masque.
    """
    import_annotation.build(_draw(corpus), corpus, "testeur", AnnotationStatus.DRAFT, None, None)
    mask = load_mask(corpus / "annotations" / "masks" / "piece-01.floor-visible.png", WIDTH, HEIGHT)

    assert mask[int(HEIGHT * 0.8), int(WIDTH * 0.05)], "le sol dégagé doit être marqué"
    assert not mask[int(HEIGHT * 0.8), int(WIDTH * 0.4)], "le tapis ne doit pas l'être"
    assert not mask[int(HEIGHT * 0.2), int(WIDTH * 0.5)], "le mur ne doit pas l'être"


def test_l_etendue_geometrique_n_est_pas_annotee(corpus):
    """La surface derrière les meubles ne se voit pas, donc ne s'annote pas.

    Le champ existe pour que personne ne range cette notion dans
    `floor_visible` — mesurer un segmenteur contre une cible que l'image ne
    contient pas serait l'erreur la plus coûteuse du projet.
    """
    path = import_annotation.build(
        _draw(corpus), corpus, "testeur", AnnotationStatus.DRAFT, None, None
    )
    annotation = FloorAnnotation.model_validate(json.loads(path.read_text(encoding="utf-8")))

    assert annotation.masks.floor_extent is None
    with pytest.raises(ValueError):
        MaskFiles(floor_visible="a.png", floor_extent="b.png")  # type: ignore[arg-type]


def test_les_zones_incertaines_produisent_un_masque_et_restent_lisibles(corpus):
    path = import_annotation.build(
        _draw(corpus), corpus, "testeur", AnnotationStatus.DRAFT, None, None
    )
    annotation = FloorAnnotation.model_validate(json.loads(path.read_text(encoding="utf-8")))

    assert annotation.masks.uncertain is not None
    assert len(annotation.uncertain_zones) == 1
    assert annotation.uncertain_zones[0].reason is UncertainReason.HIDDEN_CORNER


def test_le_contour_est_conserve_avec_sa_nature(corpus):
    """Distinguer les natures permettra de mesurer là où ça compte."""
    path = import_annotation.build(
        _draw(corpus), corpus, "testeur", AnnotationStatus.DRAFT, None, None
    )
    annotation = FloorAnnotation.model_validate(json.loads(path.read_text(encoding="utf-8")))

    assert annotation.boundary[0].kind is BoundaryKind.WALL_FLOOR
    assert len(annotation.boundary[0].points) == 2


def test_le_json_est_stable_et_versionne(corpus):
    """Deux imports du même tracé doivent donner le même fichier, aux dates près."""
    first = import_annotation.build(
        _draw(corpus), corpus, "testeur", AnnotationStatus.DRAFT, None, None
    ).read_text(encoding="utf-8")
    second = import_annotation.build(
        _draw(corpus), corpus, "testeur", AnnotationStatus.DRAFT, None, None
    ).read_text(encoding="utf-8")

    assert first == second
    assert json.loads(first)["schema"] == ANNOTATION_SCHEMA


# --- Le garde-fou EXIF ---------------------------------------------------


def test_un_trace_fait_sur_d_autres_dimensions_est_refuse(corpus):
    """Le seul endroit où un masque silencieusement faux peut être arrêté.

    Un tracé fait sur une image affichée en portrait et rastérisé sur la même
    image décodée en paysage aurait de bonnes dimensions nulle part, et ne
    lèverait aucune erreur sans ce contrôle.
    """
    draw = _draw(corpus, width=HEIGHT, height=WIDTH)

    with pytest.raises(import_annotation.ImportError_, match="pipeline charge"):
        import_annotation.build(draw, corpus, "testeur", AnnotationStatus.DRAFT, None, None)


def test_un_trace_sans_polygone_de_sol_est_refuse(corpus):
    draw = _draw(corpus, floorPolygons=[])
    with pytest.raises(import_annotation.ImportError_, match="aucun polygone"):
        import_annotation.build(draw, corpus, "testeur", AnnotationStatus.DRAFT, None, None)


def test_un_trace_pour_une_photo_inconnue_est_refuse(corpus):
    draw = _draw(corpus, photoId="jamais-vue")
    with pytest.raises(import_annotation.ImportError_, match="absente"):
        import_annotation.build(draw, corpus, "testeur", AnnotationStatus.DRAFT, None, None)


def test_un_schema_de_trace_inconnu_est_refuse(corpus):
    draw = _draw(corpus, schema="autre-outil@1")
    with pytest.raises(import_annotation.ImportError_, match="schéma"):
        import_annotation.build(draw, corpus, "testeur", AnnotationStatus.DRAFT, None, None)


# --- draft → reviewed → approved -----------------------------------------


def test_un_statut_relu_exige_une_relecture_nommee():
    """Sans ce refus, `approved` ne serait qu'une déclaration d'intention."""
    common = {
        "photo_id": "x",
        "width": 10,
        "height": 10,
        "masks": MaskFiles(floor_visible="m.png"),
        "annotator": "a",
        "annotated_on": date(2026, 9, 7),
    }
    with pytest.raises(ValueError, match="sans bloc review"):
        FloorAnnotation(status=AnnotationStatus.APPROVED, **common)  # type: ignore[arg-type]

    approved = FloorAnnotation(
        status=AnnotationStatus.APPROVED,
        review=Review(reviewer="b", reviewed_on=date(2026, 9, 7)),
        **common,  # type: ignore[arg-type]
    )
    assert approved.usable_as_ground_truth


def test_une_annotation_relue_ne_peut_pas_rester_brouillon():
    with pytest.raises(ValueError, match="ne peut pas rester"):
        FloorAnnotation(
            photo_id="x",
            width=10,
            height=10,
            masks=MaskFiles(floor_visible="m.png"),
            annotator="a",
            annotated_on=date(2026, 9, 7),
            status=AnnotationStatus.DRAFT,
            review=Review(reviewer="b", reviewed_on=date(2026, 9, 7)),
        )


def test_seul_approved_vaut_verite_terrain():
    for status in (AnnotationStatus.DRAFT, AnnotationStatus.REVIEWED):
        review = (
            None
            if status is AnnotationStatus.DRAFT
            else Review(reviewer="b", reviewed_on=date(2026, 9, 7))
        )
        annotation = FloorAnnotation(
            photo_id="x",
            width=10,
            height=10,
            masks=MaskFiles(floor_visible="m.png"),
            annotator="a",
            annotated_on=date(2026, 9, 7),
            status=status,
            review=review,
        )
        assert not annotation.usable_as_ground_truth


# --- Les contrôles -------------------------------------------------------


def _scene(corpus: Path, status: AnnotationStatus = AnnotationStatus.APPROVED):
    import_annotation.build(_draw(corpus), corpus, "testeur", status, "relecteur", None)
    manifest = load_manifest(corpus)
    return load_scene(corpus / "annotations" / "piece-01.json", manifest, corpus)


def test_un_corpus_bien_forme_ne_signale_aucune_erreur(corpus):
    scene = _scene(corpus)
    assert scene.errors == (), scene.errors
    assert scene.usable


def test_seules_les_annotations_approuvees_entrent_au_banc_d_essai(corpus):
    """LE garde-fou du préambule : un brouillon n'est pas une référence."""
    draft = _scene(corpus, AnnotationStatus.DRAFT)
    assert not draft.usable
    assert any(issue.code is Check.NOT_APPROVED for issue in draft.warnings)

    approved = _scene(corpus, AnnotationStatus.APPROVED)
    assert approved.usable


def test_une_image_modifiee_depuis_l_annotation_est_signalee(corpus):
    scene = _scene(corpus)
    assert scene.usable

    other = patterns.mid_tone_checkerboard((WIDTH, HEIGHT))
    other[0, 0] = 0
    (corpus / "private-real" / "piece.png").write_bytes(patterns.encode(other, "PNG"))

    manifest = load_manifest(corpus)
    changed = load_scene(corpus / "annotations" / "piece-01.json", manifest, corpus)
    assert any(issue.code is Check.IMAGE_HASH_MISMATCH for issue in changed.errors)
    assert not changed.usable


def test_un_masque_modifie_depuis_son_releve_est_signale(corpus):
    _scene(corpus)
    mask_path = corpus / "annotations" / "masks" / "piece-01.floor-visible.png"
    save_mask(np.ones((HEIGHT, WIDTH), dtype=bool), mask_path)

    manifest = load_manifest(corpus)
    scene = load_scene(corpus / "annotations" / "piece-01.json", manifest, corpus)
    assert any(issue.code is Check.MASK_HASH_MISMATCH for issue in scene.errors)


def test_une_image_absente_est_signalee(corpus):
    _scene(corpus)
    (corpus / "private-real" / "piece.png").unlink()

    manifest = load_manifest(corpus)
    scene = load_scene(corpus / "annotations" / "piece-01.json", manifest, corpus)
    assert any(issue.code is Check.IMAGE_FILE_MISSING for issue in scene.errors)


def test_une_zone_incertaine_qui_avale_l_image_est_refusee(corpus):
    draw = _draw(
        corpus,
        uncertainZones=[
            {
                "reason": UncertainReason.LOW_CONTRAST.value,
                "polygon": [
                    {"x": 0.0, "y": 0.0},
                    {"x": 1.0, "y": 0.0},
                    {"x": 1.0, "y": 1.0},
                    {"x": 0.0, "y": 1.0},
                ],
            }
        ],
    )
    import_annotation.build(draw, corpus, "t", AnnotationStatus.APPROVED, "r", None)

    manifest = load_manifest(corpus)
    scene = load_scene(corpus / "annotations" / "piece-01.json", manifest, corpus)
    assert any(issue.code is Check.UNCERTAIN_TOO_LARGE for issue in scene.errors)
    assert not scene.usable


def test_un_masque_de_sol_vide_est_refuse_hors_scene_rejetee(corpus):
    """Vide est légitime sur une scène « rejected », suspect ailleurs."""
    _scene(corpus)
    mask_path = corpus / "annotations" / "masks" / "piece-01.floor-visible.png"
    save_mask(np.zeros((HEIGHT, WIDTH), dtype=bool), mask_path)

    annotation_path = corpus / "annotations" / "piece-01.json"
    data = json.loads(annotation_path.read_text(encoding="utf-8"))
    data["maskSha256"]["floorVisible"] = sha256_of(mask_path)
    annotation_path.write_text(json.dumps(data), encoding="utf-8")

    manifest = load_manifest(corpus)
    scene = load_scene(annotation_path, manifest, corpus)
    assert any(issue.code is Check.FLOOR_MASK_EMPTY for issue in scene.errors)


def test_une_licence_non_renseignee_est_refusee(corpus):
    _scene(corpus)
    manifest_path = corpus / "manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["photos"][0]["provenance"]["license"] = "?"
    manifest_path.write_text(json.dumps(data), encoding="utf-8")

    manifest = load_manifest(corpus)
    scene = load_scene(corpus / "annotations" / "piece-01.json", manifest, corpus)
    assert any(issue.code is Check.PROVENANCE_INCOMPLETE for issue in scene.errors)


def test_une_licence_inconnue_ne_peut_pas_etre_redistribuable(corpus):
    """Une licence absente ne doit jamais devenir une licence supposée."""
    _scene(corpus)
    manifest_path = corpus / "manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["photos"][0]["provenance"].update(
        {"license": "inconnue", "redistributable": True, "usage": Usage.REDISTRIBUTABLE.value}
    )
    manifest_path.write_text(json.dumps(data), encoding="utf-8")

    manifest = load_manifest(corpus)
    scene = load_scene(corpus / "annotations" / "piece-01.json", manifest, corpus)
    assert any(issue.code is Check.LICENSE_UNVERIFIED for issue in scene.errors)


def test_une_annotation_sans_photo_decrite_est_refusee(corpus):
    """Le mécanisme qui remplace un champ « provenance » recopié."""
    _scene(corpus)
    manifest_path = corpus / "manifest.json"
    manifest_path.write_text(
        json.dumps({"schema": "pose-parquet-ai/dataset@2", "photos": []}), encoding="utf-8"
    )

    manifest = load_manifest(corpus)
    with pytest.raises(KeyError, match="provenance"):
        load_scene(corpus / "annotations" / "piece-01.json", manifest, corpus)


def test_le_recouvrement_sol_incertain_avertit_sans_bloquer(corpus):
    """Les pixels sont exclus de toute façon : c'est une remarque, pas une faute."""
    scene = _scene(corpus)
    assert any(issue.code is Check.FLOOR_OVERLAPS_UNCERTAIN for issue in scene.warnings)
    assert scene.usable


def test_le_bilan_de_controle_est_comptable(corpus):
    _scene(corpus)
    report = corpus_report(load_corpus(corpus))

    assert report["scenes"] == 1
    assert report["usable"] == 1
    assert report["byStatus"]["approved"] == 1
    assert isinstance(report["issues"], list)


# --- Provenance et confidentialité ---------------------------------------


def test_une_image_privee_ne_peut_pas_etre_declaree_redistribuable(corpus, capsys):
    """Le garde-fou de la décision conservatrice du projet.

    `public/` est versionné, donc redistribué de fait : y ranger une image
    déclarée non redistribuable la publierait par simple inadvertance.
    """
    code = add_photo.main(
        [
            "--dataset",
            str(corpus),
            "--file",
            "private-real/piece.png",
            "--id",
            "piece-02",
            "--difficulty",
            "easy",
            "--source",
            "s",
            "--license",
            "CC0",
            "--verified-on",
            "2026-09-07",
            "--redistributable",
        ]
    )
    assert code == 2
    assert "private-real" in capsys.readouterr().err


def test_la_provenance_porte_hash_date_et_usage(corpus):
    photo = load_manifest(corpus).photos[0]

    assert photo.provenance.sha256 is not None and len(photo.provenance.sha256) == 64
    assert photo.provenance.verified_on == date(2026, 9, 7)
    assert photo.provenance.usage is Usage.LOCAL_EVALUATION_ONLY
    assert photo.provenance.redistributable is False


def test_une_provenance_sans_licence_est_impossible():
    with pytest.raises(ValueError):
        Provenance(source="s", license="", verified_on=date(2026, 9, 7))


def test_les_traits_sont_un_vocabulaire_ferme(corpus):
    photo = load_manifest(corpus).photos[0]
    assert set(photo.traits) == {SceneTrait.FURNISHED, SceneTrait.RUG}
    with pytest.raises(ValueError):
        SceneTrait("moquette-violette")


# --- Le contrat avec l'outil de tracé -------------------------------------


def test_le_format_du_traceur_est_lu_tel_quel(corpus):
    """Le tracé de référence vient de `tools/annotate.html`, exécuté pour de vrai.

    C'est le contrat entre les deux moitiés du dispositif : le navigateur
    dessine, Python possède le format. Un désaccord entre eux ne se verrait
    qu'à l'usage, sur une annotation déjà faite — donc trop tard. La fixture
    est la sortie réelle de l'outil, et ce test vérifie que l'import
    l'accepte sans retouche.
    """
    reference = json.loads(
        (Path(__file__).parent / "fixtures" / "tool-output.draw.json").read_text(encoding="utf-8")
    )
    assert reference["schema"] == import_annotation.DRAW_SCHEMA
    assert reference["width"] == WIDTH and reference["height"] == HEIGHT

    path = corpus / "outil.draw.json"
    path.write_text(json.dumps(reference), encoding="utf-8")
    written = import_annotation.build(
        path, corpus, "jonathan", AnnotationStatus.APPROVED, "relecteur", None
    )

    annotation = FloorAnnotation.model_validate(json.loads(written.read_text(encoding="utf-8")))
    assert annotation.masks.uncertain is not None, "les zones incertaines doivent survivre"
    assert annotation.boundary[0].kind is BoundaryKind.WALL_FLOOR
    assert annotation.uncertain_zones[0].reason is UncertainReason.HIDDEN_CORNER

    # Le tapis tracé comme « ce qui cache le sol » doit manquer au masque.
    mask = load_mask(corpus / "annotations" / "masks" / "piece-01.floor-visible.png", WIDTH, HEIGHT)
    assert mask[int(HEIGHT * 0.85), int(WIDTH * 0.05)]
    assert not mask[int(HEIGHT * 0.8), int(WIDTH * 0.4)]


# --- Le banc d'essai ------------------------------------------------------


def test_le_banc_tourne_sur_un_corpus_annote(corpus, tmp_path):
    """Chaîne complète : image → provenance → tracé → masques → métriques."""
    _scene(corpus)
    report = run(corpus, tmp_path / "out", available())

    assert report["corpus"]["scenesApproved"] == 1
    assert set(report["candidates"]) == set(available())
    assert (tmp_path / "out" / "segmentation.json").is_file()


def test_les_references_triviales_donnent_les_resultats_prevus(corpus, tmp_path):
    """Vérification de la balance, sur des candidats dont on sait la réponse."""
    _scene(corpus)
    report = run(corpus, tmp_path / "out", ("empty", "full", "bottom-third"))

    empty = report["candidates"]["empty"]["overall"]
    full = report["candidates"]["full"]["overall"]
    third = report["candidates"]["bottom-third"]["overall"]

    assert empty["iou"]["mean"] == 0.0
    assert empty["recall"]["mean"] == 0.0
    assert full["recall"]["mean"] == 1.0
    assert full["precision"]["mean"] < 1.0
    # Le tiers bas recouvre une partie du sol sans le déborder : mieux que rien.
    assert third["iou"]["mean"] is not None and third["iou"]["mean"] > empty["iou"]["mean"]


def test_le_rapport_est_reproductible(corpus, tmp_path):
    """Tout ce qu'il faut pour rejouer : versions, hashes, config, horodatage."""
    _scene(corpus)
    report = run(corpus, tmp_path / "out", ("empty",))

    assert report["schema"]
    assert report["ranAt"]
    assert report["formats"]["annotation"] == ANNOTATION_SCHEMA
    assert report["metricConfig"]["boundary_tolerance_fraction"] > 0
    row = report["rows"][0]
    assert row["imageSha256"] and row["maskSha256"]["floorVisible"]
    assert row["annotationRevision"] == 1
    assert row["annotationStatus"] == "approved"


def test_le_rapport_separe_performance_difficulte_et_fiabilite(corpus, tmp_path):
    _scene(corpus)
    report = run(corpus, tmp_path / "out", ("empty",))

    assert "byDifficulty" in report["candidates"]["empty"]
    assert "byTrait" in report["candidates"]["empty"]
    assert "rug" in report["candidates"]["empty"]["byTrait"]
    assert report["groundTruthReliability"]["ignoredFraction"]["counted"] == 1


def test_les_brouillons_ne_sont_pas_mesures(corpus, tmp_path):
    _scene(corpus, AnnotationStatus.DRAFT)
    report = run(corpus, tmp_path / "out", ("empty",))

    assert report["corpus"]["scenesAnnotated"] == 1
    assert report["corpus"]["scenesApproved"] == 0
    assert report["rows"] == []


def test_un_corpus_vide_ne_plante_pas(tmp_path):
    """L'état réel du projet à la fin de ce préambule."""
    root = tmp_path / "datasets"
    root.mkdir()
    (root / "manifest.json").write_text(
        json.dumps({"schema": "pose-parquet-ai/dataset@2", "photos": []}), encoding="utf-8"
    )

    report = run(root, tmp_path / "out", available())
    assert report["corpus"]["scenesApproved"] == 0
    assert report["candidates"]["empty"]["overall"]["iou"]["mean"] is None


def test_une_scene_rejetee_sort_des_agregats(corpus, tmp_path):
    """On n'attend pas qu'elle soit segmentable : la compter tirerait vers le bas."""
    _scene(corpus)
    manifest_path = corpus / "manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["photos"][0]["difficulty"] = Difficulty.REJECTED.value
    manifest_path.write_text(json.dumps(data), encoding="utf-8")

    report = run(corpus, tmp_path / "out", ("empty",))
    assert report["corpus"]["scenesRejectedExcluded"] == 1
    assert report["corpus"]["scenesScored"] == 0
    assert report["candidates"]["empty"]["overall"]["iou"]["counted"] == 0
