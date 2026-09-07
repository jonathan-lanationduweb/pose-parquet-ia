"""Accord humain : nommage, tolérances, localisation du désaccord, temps.

Le test qui porte le lot est `test_le_nom_de_la_mesure_suit_qui_a_annote` :
appeler une répétabilité intra-annotateur un « accord inter-annotateurs »
gonflerait le chiffre qui servira de plafond aux exigences posées aux modèles.
"""

import json
from datetime import date

import numpy as np
import pytest

from app.schemas.annotation import (
    AnnotationStatus,
    AnnotationTiming,
    BoundaryKind,
    BoundarySegment,
    FloorAnnotation,
    MaskFiles,
    Point,
)
from benchmarks.agreement import (
    DEFAULT_TOLERANCES,
    AgreementKind,
    compare,
    disagreement_profile,
    render_comparison,
    summarise,
)
from benchmarks.annotations import load_corpus, paired_scenes, primary_scenes
from benchmarks.run_pilot import run
from benchmarks.segmentation import MaskError
from scripts import import_annotation
from tests.conftest import draw_file

HEIGHT, WIDTH = 400, 600


def _annotation(
    who: str,
    label: str | None = None,
    independent: bool = True,
    segments: list[BoundarySegment] | None = None,
) -> FloorAnnotation:
    return FloorAnnotation(
        photo_id="p1",
        width=WIDTH,
        height=HEIGHT,
        masks=MaskFiles(floor_visible="m.png"),
        annotator=who,
        annotated_on=date(2026, 9, 7),
        pass_label=label,
        independent_pass=independent,
        boundary=segments or [],
    )


def _floor() -> np.ndarray:
    mask = np.zeros((HEIGHT, WIDTH), dtype=bool)
    mask[250:, :] = True
    return mask


# --- Le nom de la mesure -------------------------------------------------


def test_le_nom_de_la_mesure_suit_qui_a_annote():
    """Deux personnes → accord. Une personne deux fois → répétabilité.

    La seconde est une **borne optimiste** : personne ne reproduit ses propres
    hésitations aussi mal que celles d'un autre. Les confondre gonflerait le
    plafond qu'on opposera aux modèles.
    """
    floor = _floor()
    other = np.roll(floor, 4, axis=0)

    two_people = compare(_annotation("jo", "A"), floor, None, _annotation("alex", "B"), other, None)
    same_person = compare(_annotation("jo", "A"), floor, None, _annotation("jo", "B"), other, None)

    assert two_people.kind == AgreementKind.INTER
    assert same_person.kind == AgreementKind.INTRA


def test_une_passe_non_declaree_independante_est_signalee():
    """L'outil ne peut pas vérifier l'indépendance : il enregistre la déclaration.

    Un accord élevé entre deux passes non indépendantes peut ne mesurer que la
    mémoire de celui qui a dessiné. Le champ doit donc voyager avec le score.
    """
    floor = _floor()
    declared = compare(_annotation("jo", "A"), floor, None, _annotation("alex", "B"), floor, None)
    undeclared = compare(
        _annotation("jo", "A"),
        floor,
        None,
        _annotation("alex", "B", independent=False),
        floor,
        None,
    )

    assert declared.both_independent is True
    assert undeclared.both_independent is False


def test_des_natures_melangees_ne_se_moyennent_pas():
    """Une moyenne d'accord inter et intra ne veut rien dire."""
    floor = _floor()
    other = np.roll(floor, 4, axis=0)
    mixed = summarise(
        [
            compare(_annotation("jo", "A"), floor, None, _annotation("alex", "B"), other, None),
            compare(_annotation("jo", "A"), floor, None, _annotation("jo", "B"), other, None),
        ]
    )
    assert mixed["kind"] == "mixed"


def test_une_nature_unique_est_nommee():
    floor = _floor()
    single = summarise(
        [compare(_annotation("jo", "A"), floor, None, _annotation("alex", "B"), floor, None)]
    )
    assert single["kind"] == AgreementKind.INTER


# --- Tolérances multiples ------------------------------------------------


def test_le_score_de_contour_est_rendu_pour_chaque_tolerance():
    """Le but du balayage : voir de combien le choix de tolérance déplace le score."""
    floor = _floor()
    pair = compare(
        _annotation("jo", "A"),
        floor,
        None,
        _annotation("alex", "B"),
        np.roll(floor, 5, axis=0),
        None,
    )

    assert set(pair.boundary_by_tolerance) == {f"{value:.4f}" for value in DEFAULT_TOLERANCES}
    for entry in pair.boundary_by_tolerance.values():
        assert entry["tolerancePx"] is not None


def test_une_tolerance_plus_large_ne_peut_pas_baisser_le_score():
    """Propriété attendue : pardonner davantage ne punit jamais plus.

    Elle attrape une inversion de signe ou un mauvais ordre de dilatation, que
    des scores plausibles cacheraient.
    """
    floor = _floor()
    pair = compare(
        _annotation("jo", "A"),
        floor,
        None,
        _annotation("alex", "B"),
        np.roll(floor, 6, axis=0),
        None,
        tolerances=(0.0025, 0.005, 0.01, 0.02),
    )

    scores = [
        pair.boundary_by_tolerance[f"{value:.4f}"]["f1"] for value in (0.0025, 0.005, 0.01, 0.02)
    ]
    defined = [value for value in scores if value is not None]
    assert defined == sorted(defined), scores


def test_le_choix_de_tolerance_peut_tout_changer():
    """Un tremblement de 5 px passe de « faux » à « juste » selon la tolérance.

    C'est la raison d'être du balayage : si le score dépend plus du réglage que
    de l'annotation, le réglage doit être discuté avant d'être utilisé.
    """
    floor = _floor()
    pair = compare(
        _annotation("jo", "A"),
        floor,
        None,
        _annotation("alex", "B"),
        np.roll(floor, 5, axis=0),
        None,
        tolerances=(0.0025, 0.01),
    )

    tight = pair.boundary_by_tolerance["0.0025"]["f1"]
    loose = pair.boundary_by_tolerance["0.0100"]["f1"]
    assert tight is not None and loose is not None
    assert loose - tight > 0.5, "le balayage doit exposer cette sensibilité"


# --- Comparaison A/B ----------------------------------------------------


def test_les_incertitudes_des_deux_releves_sont_unies():
    """Ce qu'un seul déclare indécidable sort de la comparaison.

    On ne peut reprocher ni à l'un d'avoir tranché ni à l'autre s'être abstenu :
    il n'y avait pas de bonne réponse.
    """
    floor = _floor()
    disagreeing = floor.copy()
    disagreeing[250:280, :] = False

    zone = np.zeros((HEIGHT, WIDTH), dtype=bool)
    zone[240:290, :] = True

    excused = compare(
        _annotation("jo", "A"), floor, zone, _annotation("alex", "B"), disagreeing, None
    )
    assert excused.area.iou == 1.0
    assert excused.ignored_fraction_first > 0
    assert excused.ignored_fraction_second == 0.0
    assert excused.ignored_fraction_delta > 0


def test_le_desaccord_sur_l_incertitude_est_lui_meme_mesure():
    """Deux personnes qui ne renoncent pas aux mêmes endroits ne lisent pas la même image."""
    floor = _floor()
    zone = np.zeros((HEIGHT, WIDTH), dtype=bool)
    zone[:100, :] = True

    pair = compare(_annotation("jo", "A"), floor, zone, _annotation("alex", "B"), floor, None)
    assert pair.ignored_fraction_delta == pytest.approx(0.25, abs=0.01)


def test_comparer_deux_photos_differentes_est_refuse():
    floor = _floor()
    other = _annotation("alex", "B")
    object.__setattr__(other, "photo_id", "autre")
    with pytest.raises(MaskError, match="photos différentes"):
        compare(_annotation("jo", "A"), floor, None, other, floor, None)


def test_comparer_des_cadres_differents_est_refuse():
    """Redimensionner l'un des deux fabriquerait l'accord qu'on mesure."""
    with pytest.raises(MaskError, match="[Cc]adres différents"):
        compare(
            _annotation("jo", "A"),
            _floor(),
            None,
            _annotation("alex", "B"),
            np.zeros((10, 10), dtype=bool),
            None,
        )


# --- Localisation du désaccord ------------------------------------------


def test_un_tremblement_de_jonction_est_impute_a_la_jonction():
    floor = _floor()
    profile = disagreement_profile(floor, np.roll(floor, 6, axis=0), None, tolerance_px=5)

    assert profile.total_pixels > 0
    assert profile.along_junction > profile.interior_region


def test_un_tapis_oublie_est_impute_a_une_surface():
    """Le désaccord le plus instructif : il porte sur la DÉFINITION, pas sur la main.

    Une surface entière, loin de toute frontière, qu'un annotateur a comptée
    comme sol et l'autre pas — un tapis, une ombre, un reflet.
    """
    floor = _floor()
    without_rug = floor.copy()
    without_rug[320:380, 200:400] = False

    profile = disagreement_profile(floor, without_rug, None, tolerance_px=5)
    assert profile.interior_region > profile.along_junction
    assert profile.hotspots
    assert profile.hotspots[0].category == "interior_region"


def test_les_foyers_sont_localises_pour_qu_on_aille_voir():
    floor = _floor()
    other = floor.copy()
    other[320:380, 200:400] = False

    spot = disagreement_profile(floor, other, None, tolerance_px=5).hotspots[0]
    left, top, right, bottom = spot.box
    assert 0.0 <= left < right <= 1.01
    assert 0.0 <= top < bottom <= 1.01
    assert spot.pixels > 0


def test_le_desaccord_est_impute_aux_natures_de_contour_annotees():
    """Quand les contours sont relevés, on sait quelle nature souffre."""
    floor = _floor()
    segments = [
        BoundarySegment(
            kind=BoundaryKind.WALL_FLOOR,
            points=[Point(x=0.0, y=0.625), Point(x=1.0, y=0.625)],
        )
    ]
    profile = disagreement_profile(floor, np.roll(floor, 6, axis=0), None, 5, [*segments])
    assert profile.by_boundary_kind.get(BoundaryKind.WALL_FLOOR.value, 0) > 0


def test_un_accord_parfait_n_a_aucun_desaccord_a_localiser():
    profile = disagreement_profile(_floor(), _floor(), None, tolerance_px=5)
    assert profile.total_pixels == 0
    assert profile.hotspots == ()


# --- Revue visuelle -----------------------------------------------------


def test_la_comparaison_visuelle_s_ecrit(tmp_path):
    """Un corpus qu'on ne peut pas regarder est un corpus qu'on croit sur parole."""
    floor = _floor()
    photo = np.full((HEIGHT, WIDTH), 128, dtype=np.uint8)
    zone = np.zeros((HEIGHT, WIDTH), dtype=bool)
    zone[:60, :] = True

    path = tmp_path / "cmp.png"
    render_comparison(photo, floor, np.roll(floor, 8, axis=0), zone, path)

    assert path.is_file()
    from benchmarks.segmentation import load_mask  # noqa: PLC0415

    with pytest.raises(Exception):  # noqa: B017 - ce n'est pas un masque binaire
        load_mask(path, WIDTH, HEIGHT)


# --- Agrégats -----------------------------------------------------------


def test_les_agregats_donnent_moyenne_mediane_et_minimum():
    """Le minimum est le plus parlant : la scène la moins consensuelle."""
    floor = _floor()
    pairs = [
        compare(
            _annotation("jo", "A"),
            floor,
            None,
            _annotation("alex", "B"),
            np.roll(floor, shift, axis=0),
            None,
        )
        for shift in (2, 10, 30)
    ]
    for index, pair in enumerate(pairs):
        object.__setattr__(pair, "photo_id", f"p{index}")

    summary = summarise(pairs)
    assert summary["iou"]["counted"] == 3
    assert summary["iou"]["min"] <= summary["iou"]["median"] <= 1.0
    assert summary["leastStableScene"]["photoId"] != summary["mostStableScene"]["photoId"]


def test_aucun_ecart_type_n_est_publie():
    """Sur une douzaine d'images, il donnerait une précision qu'on n'a pas."""
    floor = _floor()
    summary = summarise(
        [compare(_annotation("jo", "A"), floor, None, _annotation("alex", "B"), floor, None)]
    )
    assert "std" not in summary
    assert "confidenceInterval" not in summary


def test_des_agregats_vides_ne_plantent_pas():
    assert summarise([])["pairs"] == 0


# --- Chronométrage ------------------------------------------------------


def test_le_temps_total_additionne_les_trois_phases():
    timing = AnnotationTiming(
        first_pass_seconds=300.0, corrections_seconds=90.0, review_seconds=60.0
    )
    assert timing.total_seconds == 450.0


def test_une_duree_negative_est_refusee():
    with pytest.raises(ValueError):
        AnnotationTiming(first_pass_seconds=-1.0)


def test_le_chronometrage_est_facultatif():
    """Une annotation sans temps mesuré reste valide : @1 n'exigeait rien."""
    assert _annotation("jo").timing is None


# --- Passes multiples dans le corpus ------------------------------------


def test_deux_passes_coexistent_sans_s_ecraser(corpus):
    """Sans étiquette de passe, la seconde remplacerait la première."""
    first = import_annotation.build(
        draw_file(corpus, 0.60),
        corpus,
        "jo",
        AnnotationStatus.APPROVED,
        "rev",
        None,
        pass_label="A",
        independent=True,
    )
    second = import_annotation.build(
        draw_file(corpus, 0.63),
        corpus,
        "alex",
        AnnotationStatus.APPROVED,
        "rev",
        None,
        pass_label="B",
        independent=True,
    )

    assert first != second
    assert first.is_file() and second.is_file()
    assert len(paired_scenes(load_corpus(corpus))) == 1


def test_le_banc_de_segmentation_ne_compte_pas_une_photo_deux_fois(corpus):
    """Sinon la même image pèserait double dans les moyennes."""
    import_annotation.build(
        draw_file(corpus, 0.60),
        corpus,
        "jo",
        AnnotationStatus.APPROVED,
        "rev",
        None,
        pass_label="A",
        independent=True,
    )
    import_annotation.build(
        draw_file(corpus, 0.63),
        corpus,
        "alex",
        AnnotationStatus.APPROVED,
        "rev",
        None,
        pass_label="B",
        independent=True,
    )

    scenes = load_corpus(corpus)
    assert len(scenes) == 2
    assert len(primary_scenes(scenes)) == 1
    assert primary_scenes(scenes)[0].annotation.pass_label == "A"


def test_le_temps_mesure_par_l_outil_est_reprise_a_l_import(corpus):
    """Un temps chronométré vaut mieux qu'un temps noté de mémoire."""
    path = import_annotation.build(
        draw_file(corpus, 0.60), corpus, "jo", AnnotationStatus.DRAFT, None, None
    )
    annotation = FloorAnnotation.model_validate(json.loads(path.read_text(encoding="utf-8")))
    assert annotation.timing is not None
    assert annotation.timing.first_pass_seconds == 240.0


def test_le_rapport_pilote_mesure_temps_et_accord(corpus, tmp_path):
    """Chaîne complète : deux passes indépendantes → accord + durées."""
    import_annotation.build(
        draw_file(corpus, 0.60),
        corpus,
        "jo",
        AnnotationStatus.APPROVED,
        "rev",
        None,
        pass_label="A",
        independent=True,
    )
    import_annotation.build(
        draw_file(corpus, 0.63),
        corpus,
        "alex",
        AnnotationStatus.APPROVED,
        "rev",
        None,
        pass_label="B",
        independent=True,
    )

    report = run(corpus, tmp_path / "out", DEFAULT_TOLERANCES, render=True)

    assert report["corpus"]["doublyAnnotated"] == 1
    assert report["annotationTime"]["counted"] == 2
    assert report["annotationTime"]["totalSeconds"]["median"] == 240.0
    assert report["humanAgreement"]["kind"] == AgreementKind.INTER
    assert report["humanAgreement"]["iou"]["counted"] == 1
    assert report["annotationTimeByDifficulty"]["hard"]["scenes"] == 2
    assert (tmp_path / "out" / "p1.compare.png").is_file()
    assert report["caveats"]


def test_le_rapport_pilote_porte_ses_propres_reserves(corpus, tmp_path):
    """Un rapport relu dans six mois doit dire lui-même ce qu'il ne prouve pas."""
    report = run(corpus, tmp_path / "out")
    joined = " ".join(report["caveats"]).lower()

    assert "0,92" in joined or "0.92" in joined
    assert "observ" in joined
    assert report["tolerancesTested"]


def test_un_corpus_sans_annotation_ne_plante_pas(corpus, tmp_path):
    """L'état du corpus pilote à la fin du LOT 2A."""
    report = run(corpus, tmp_path / "out")
    assert report["corpus"]["annotations"] == 0
    assert report["humanAgreement"]["pairs"] == 0
    assert report["annotationTime"]["counted"] == 0
