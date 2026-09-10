"""Rôles d'exclusion — LOT B.2.

Le manque que ces tests verrouillent : on savait qu'une zone était exclue du
sol, pas **ce qu'elle était**. Sans le rôle, « parquet peint sur un meuble » et
« parquet peint sur un tapis » ne se distinguent pas, alors que le second est
bien plus grave et bien plus fréquent.

Trois propriétés sont éprouvées ici, et chacune correspond à une manière de se
tromper :

* une annotation écrite **avant** ce champ doit rester valide — une extension
  qui invalide l'existant n'est pas une extension ;
* une exclusion dont personne n'a déclaré le rôle doit valoir `unknown`, et non
  se voir ranger d'office dans une catégorie plausible ;
* la finesse doit se **mesurer** et non se déclarer, sinon deux personnes
  qualifieront différemment le même pied de chaise.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.annotation import (
    AnnotationStatus,
    Exclusion,
    ExclusionRole,
    FloorAnnotation,
    MaskFiles,
    Point,
)
from benchmarks.annotations import corpus_report, load_corpus
from corpus import patterns
from scripts import add_photo, import_annotation
from tests.conftest import TEST_HEIGHT, TEST_WIDTH

CARRE = [Point(x=0.1, y=0.1), Point(x=0.4, y=0.1), Point(x=0.4, y=0.4), Point(x=0.1, y=0.4)]


def _trace(root: Path, roles: list[str] | None = None) -> Path:
    """Un trace avec UN trou, tel que l'outil le produirait."""
    draw: dict[str, object] = {
        "schema": import_annotation.DRAW_SCHEMA,
        "photoId": "p1",
        "width": TEST_WIDTH,
        "height": TEST_HEIGHT,
        "floorPolygons": [
            [{"x": 0.0, "y": 0.6}, {"x": 1.0, "y": 0.6}, {"x": 1.0, "y": 1.0}, {"x": 0.0, "y": 1.0}]
        ],
        "floorHoles": [
            [{"x": 0.3, "y": 0.7}, {"x": 0.5, "y": 0.7}, {"x": 0.5, "y": 0.9}, {"x": 0.3, "y": 0.9}]
        ],
        "drawSeconds": 120,
    }
    if roles is not None:
        draw["floorHoleRoles"] = roles
    chemin = root / "trace.draw.json"
    chemin.write_text(json.dumps(draw), encoding="utf-8")
    return chemin


@pytest.fixture
def corpus_outil(tmp_path: Path) -> Path:
    """Un corpus aux dimensions exactes de la fixture de sortie d'outil.

    La finesse se mesure en pixels : rejouer un trace 640x480 sur une photo
    600x400 changerait le verdict sans que le trace ait bouge.
    """
    root = tmp_path / "datasets"
    (root / "private-real").mkdir(parents=True)
    (root / "manifest.json").write_text(
        json.dumps({"schema": "pose-parquet-ai/dataset@2", "photos": []}), encoding="utf-8"
    )
    image = patterns.mid_tone_checkerboard((640, 480))
    (root / "private-real" / "piece.png").write_bytes(patterns.encode(image, "PNG"))
    assert (
        add_photo.main(
            # fmt: off
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
            # fmt: on
        )
        == 0
    )
    return root


def _bande(x1: float, x2: float, y1: float, y2: float) -> list[dict[str, float]]:
    """Un rectangle vertical, decrit par ses deux bords."""
    return [{"x": x1, "y": y1}, {"x": x2, "y": y1}, {"x": x2, "y": y2}, {"x": x1, "y": y2}]


def _annotation(**kwargs: object) -> FloorAnnotation:
    base: dict[str, object] = {
        "photo_id": "p",
        "width": 200,
        "height": 100,
        "masks": MaskFiles(floor_visible="m.png"),
        "annotator": "claude-ai",
        "annotated_on": date(2026, 9, 10),
    }
    base.update(kwargs)
    return FloorAnnotation.model_validate(base)


# --- La taxonomie --------------------------------------------------------


def test_les_six_roles_et_pas_un_de_plus() -> None:
    """Chaque rôle correspond à une conséquence différente pour le rendu ; un
    septième n'en apporterait aucune."""
    assert [r.value for r in ExclusionRole] == [
        "occluder",
        "floor_covering",
        "structural",
        "opening",
        "other",
        "unknown",
    ]


def test_une_exclusion_sans_role_vaut_inconnu() -> None:
    """On ne range pas d'office une zone dont on n'a rien dit."""
    assert Exclusion(polygon=CARRE).role is ExclusionRole.UNKNOWN


def test_un_role_invalide_est_refuse() -> None:
    with pytest.raises(ValidationError):
        Exclusion(polygon=CARRE, role="canape")  # type: ignore[arg-type]


def test_une_exclusion_demande_un_polygone_ferme() -> None:
    with pytest.raises(ValidationError):
        Exclusion(polygon=CARRE[:2])


# --- Compatibilité -------------------------------------------------------


def test_une_annotation_anterieure_au_champ_reste_valide() -> None:
    """L'extension est additive : un fichier écrit avant ce champ se relit."""
    annotation = _annotation()
    assert annotation.exclusions == []


def test_un_json_sans_exclusions_se_relit() -> None:
    brut = json.loads(_annotation().model_dump_json(by_alias=True))
    del brut["exclusions"]
    assert FloorAnnotation.model_validate(brut).exclusions == []


def test_le_role_survit_a_l_aller_retour_json() -> None:
    annotation = _annotation(
        exclusions=[Exclusion(polygon=CARRE, role=ExclusionRole.FLOOR_COVERING)]
    )
    copie = FloorAnnotation.model_validate(json.loads(annotation.model_dump_json(by_alias=True)))
    assert copie.exclusions[0].role is ExclusionRole.FLOOR_COVERING


# --- La finesse se mesure ------------------------------------------------


def test_la_finesse_est_derivee_de_la_geometrie() -> None:
    """Seuil : la tolérance de contour médiane du projet. Une forme dont la
    demi-épaisseur est sous une tolérance peut disparaître dans une erreur qui
    reste « dans la tolérance »."""
    fin = _bande(0.500, 0.505, 0.1, 0.9)
    epais = _bande(0.300, 0.700, 0.1, 0.9)
    assert import_annotation._est_fine(fin, 1600, 1067) is True
    assert import_annotation._est_fine(epais, 1600, 1067) is False


def test_l_epaisseur_ne_depend_pas_de_l_inclinaison() -> None:
    """Une boîte englobante grandit avec la pente ; le rayon inscrit non."""
    droit = _bande(0.50, 0.51, 0.2, 0.8)
    penche = [
        {"x": 0.50, "y": 0.2},
        {"x": 0.51, "y": 0.2},
        {"x": 0.61, "y": 0.8},
        {"x": 0.60, "y": 0.8},
    ]
    r_droit = import_annotation._demi_epaisseur(droit, 1600, 1067)
    r_penche = import_annotation._demi_epaisseur(penche, 1600, 1067)
    assert abs(r_droit - r_penche) < 2.5


# --- L'import et le bilan ------------------------------------------------


def test_l_import_conserve_le_role_declare(corpus: Path) -> None:
    """Un rôle déclaré dans le tracé arrive dans l'annotation."""
    sortie = import_annotation.build(
        _trace(corpus, ["floor_covering"]), corpus, "claude-ai", AnnotationStatus.DRAFT, None, None
    )
    annotation = FloorAnnotation.model_validate(json.loads(sortie.read_text(encoding="utf-8")))
    assert annotation.exclusions
    assert all(e.role is ExclusionRole.FLOOR_COVERING for e in annotation.exclusions)


def test_un_trace_sans_roles_donne_des_exclusions_inconnues(corpus: Path) -> None:
    """Le cas des tracés déjà faits : aucun rôle n'est supposé."""
    sortie = import_annotation.build(
        _trace(corpus), corpus, "claude-ai", AnnotationStatus.DRAFT, None, None
    )
    annotation = FloorAnnotation.model_validate(json.loads(sortie.read_text(encoding="utf-8")))
    assert annotation.exclusions
    assert all(e.role is ExclusionRole.UNKNOWN for e in annotation.exclusions)


def test_un_role_inconnu_dans_le_trace_est_refuse(corpus: Path) -> None:
    """Une faute de frappe ne doit pas devenir une catégorie silencieuse."""
    with pytest.raises(import_annotation.ImportError_, match="role d'exclusion inconnu"):
        import_annotation.build(
            _trace(corpus, ["tapis"]), corpus, "claude-ai", AnnotationStatus.DRAFT, None, None
        )


def test_le_bilan_compte_les_roles(corpus: Path) -> None:
    import_annotation.build(
        _trace(corpus, ["occluder"]), corpus, "claude-ai", AnnotationStatus.DRAFT, None, None
    )

    rapport = corpus_report(load_corpus(corpus))
    assert rapport["exclusionsByRole"]["occluder"] >= 1
    assert rapport["exclusionsByRole"]["floor_covering"] == 0


# --- Le corpus livré -----------------------------------------------------


def test_les_quatre_brouillons_portent_leurs_roles() -> None:
    """Contrôle du corpus réel : aucun rôle supposé, et le manque de tapis
    reste visible."""
    racine = Path("datasets")
    if not (racine / "annotations" / "sejour.AI.json").is_file():
        pytest.skip("brouillons absents")
    rapport = corpus_report(load_corpus(racine))
    roles = rapport["exclusionsByRole"]
    assert roles["occluder"] == 5, "les cinq pieds de petite-piece"
    assert roles["structural"] == 2, "les deux grilles encastrees"
    assert roles["unknown"] == 5, "quatre disques de contact + un boitier indecidable"
    assert roles["floor_covering"] == 0, "le corpus n'a aucun tapis : gap du LOT B"
    assert rapport["thinExclusions"] >= 2, "au moins les deux pieds de chaise en laiton"


def test_la_sortie_reelle_de_l_outil_porte_les_roles(corpus_outil: Path) -> None:
    """Le contrat entre les deux moitiés du dispositif, refait pour ce champ.

    `tool-output-roles.draw.json` est la sortie **réelle** de
    `tools/annotate.html` : trois exclusions fermées dans l'outil, dont deux
    dont le rôle a été choisi en cliquant le bouton, et une laissée au défaut.
    Un désaccord entre le libellé cliqué et la valeur attendue par Python ne se
    verrait qu'à l'usage, sur un relevé déjà fait — donc trop tard.
    """
    reference = json.loads(
        (Path(__file__).parent / "fixtures" / "tool-output-roles.draw.json").read_text(
            encoding="utf-8"
        )
    )
    assert reference["schema"] == import_annotation.DRAW_SCHEMA
    assert len(reference["floorHoleRoles"]) == len(reference["floorHoles"]), (
        "la liste de rôles doit rester parallèle aux trous, index par index"
    )

    chemin = corpus_outil / "outil-roles.draw.json"
    chemin.write_text(json.dumps(reference), encoding="utf-8")
    sortie = import_annotation.build(
        chemin, corpus_outil, "claude-ai", AnnotationStatus.DRAFT, None, None
    )

    annotation = FloorAnnotation.model_validate(json.loads(sortie.read_text(encoding="utf-8")))
    assert [e.role for e in annotation.exclusions] == [
        ExclusionRole.FLOOR_COVERING,
        ExclusionRole.OCCLUDER,
        ExclusionRole.UNKNOWN,
    ]
    # Le pied de chaise est le seul assez mince pour qu'une erreur de contour
    # l'avale : rayon inscrit 3 px, contre un seuil de 4 px à cette taille
    # d'image. Le tapis (61 px) et la zone indécidable (31 px) en sont loin.
    # Le seuil suit la diagonale : la même chaise photographiée en 1600 px de
    # large donne un rayon de 7 px pour un seuil de 10 px, et reste fine.
    assert [e.thin for e in annotation.exclusions] == [False, True, False]
