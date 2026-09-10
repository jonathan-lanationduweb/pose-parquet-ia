"""Promotion de statut — LOT B.4.

Ce que ces tests protègent tient en une phrase : **promouvoir ne doit jamais
falsifier l'auteur d'un relevé.** Un tracé produit par une machine et relu par
une personne est un tracé de la machine, relu par elle. La tentation inverse
est facile — réimporter en passant son propre nom — et elle produirait un
corpus où plus personne ne sait qui a dessiné quoi.

Les trois propriétés éprouvées, et la faute que chacune empêche :

* la promotion ne touche que le statut et la revue — sinon la date du relevé
  glisse vers la date de la revue, et un relevé du 10 relu le 15 se présente
  comme dessiné le 15 ;
* elle refuse un masque désynchronisé — sinon on approuve des octets qu'on n'a
  pas regardés ;
* elle enregistre l'indépendance telle qu'elle est — sinon une auto-relecture
  se lit comme un second regard.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.schemas.annotation import AnnotationStatus, FloorAnnotation
from benchmarks.annotations import corpus_report, load_corpus
from scripts import import_annotation, review_annotation
from tests.conftest import TEST_HEIGHT, TEST_WIDTH


def _trace(root: Path) -> Path:
    draw = {
        "schema": import_annotation.DRAW_SCHEMA,
        "photoId": "p1",
        "passLabel": "AI",
        "width": TEST_WIDTH,
        "height": TEST_HEIGHT,
        "floorPolygons": [
            [{"x": 0.0, "y": 0.6}, {"x": 1.0, "y": 0.6}, {"x": 1.0, "y": 1.0}, {"x": 0.0, "y": 1.0}]
        ],
        "floorHoles": [
            [{"x": 0.3, "y": 0.7}, {"x": 0.5, "y": 0.7}, {"x": 0.5, "y": 0.9}, {"x": 0.3, "y": 0.9}]
        ],
        "floorHoleRoles": ["occluder"],
        "drawSeconds": 300,
    }
    chemin = root / "trace.draw.json"
    chemin.write_text(json.dumps(draw), encoding="utf-8")
    return chemin


@pytest.fixture
def brouillon(corpus: Path) -> Path:
    """Un brouillon produit par « claude-ai », comme les quatre du pilote."""
    return import_annotation.build(
        _trace(corpus), corpus, "claude-ai", AnnotationStatus.DRAFT, None, None
    )


def _lire(path: Path) -> FloorAnnotation:
    return FloorAnnotation.model_validate(json.loads(path.read_text(encoding="utf-8")))


# --- Ce que la promotion ne doit pas toucher -----------------------------


def test_la_promotion_ne_reecrit_pas_l_annotateur(brouillon: Path) -> None:
    """Le cœur du lot : le tracé reste attribué à qui l'a dessiné."""
    avant = _lire(brouillon)
    review_annotation.promote(brouillon, "jonathan", AnnotationStatus.APPROVED)
    apres = _lire(brouillon)

    assert apres.annotator == "claude-ai", "l'auteur du tracé ne se réécrit pas"
    assert apres.review is not None and apres.review.reviewer == "jonathan"
    assert apres.status is AnnotationStatus.APPROVED
    assert avant.annotator == apres.annotator


def test_la_promotion_ne_deplace_ni_la_date_ni_la_revision(brouillon: Path) -> None:
    """C'est ce que la réimportation faisait, et pourquoi elle ne convient pas."""
    avant = _lire(brouillon)
    review_annotation.promote(brouillon, "jonathan", AnnotationStatus.REVIEWED)
    apres = _lire(brouillon)

    assert apres.annotated_on == avant.annotated_on
    assert apres.revision == avant.revision
    assert apres.pass_label == avant.pass_label == "AI"


def test_la_promotion_ne_touche_pas_la_geometrie(brouillon: Path) -> None:
    avant = _lire(brouillon)
    review_annotation.promote(brouillon, "jonathan", AnnotationStatus.APPROVED)
    apres = _lire(brouillon)

    assert apres.exclusions == avant.exclusions
    assert apres.boundary == avant.boundary
    assert apres.uncertain_zones == avant.uncertain_zones
    assert apres.mask_sha256 == avant.mask_sha256


def test_la_passe_ai_n_est_jamais_renommee_en_a(brouillon: Path) -> None:
    """`AI` et `A` sont deux protocoles : les confondre inventerait une passe
    humaine qui n'a pas eu lieu."""
    review_annotation.promote(brouillon, "jonathan", AnnotationStatus.APPROVED)
    assert _lire(brouillon).pass_label == "AI"
    assert brouillon.name.endswith(".AI.json")


# --- Ce qu'elle refuse ----------------------------------------------------


def test_un_masque_desynchronise_bloque_la_promotion(brouillon: Path) -> None:
    """Approuver des octets qu'on n'a pas regardés est le pire des cas."""
    annotation = _lire(brouillon)
    masque = brouillon.parent / annotation.masks.floor_visible
    masque.write_bytes(masque.read_bytes() + b"\x00")

    with pytest.raises(review_annotation.ReviewError, match="ne correspond plus à son empreinte"):
        review_annotation.promote(brouillon, "jonathan", AnnotationStatus.APPROVED)
    assert _lire(brouillon).status is AnnotationStatus.DRAFT, "rien n'a été écrit"


def test_on_ne_retrograde_pas_vers_draft(brouillon: Path) -> None:
    with pytest.raises(review_annotation.ReviewError, match="n'est pas une promotion"):
        review_annotation.promote(brouillon, "jonathan", AnnotationStatus.DRAFT)


# --- Ce qu'elle enregistre ------------------------------------------------


def test_l_independance_est_enregistree_telle_qu_elle_est(brouillon: Path, corpus: Path) -> None:
    """Un relevé de machine approuvé par une personne est indépendant ; le même
    nom des deux côtés est une auto-relecture, et le bilan le dit."""
    bilan = review_annotation.promote(brouillon, "jonathan", AnnotationStatus.APPROVED)
    assert bilan["revue independante"] is True

    rapport = corpus_report(load_corpus(corpus))
    assert rapport["independentlyReviewed"] == 1
    assert rapport["selfApproved"] == 0


def test_une_auto_relecture_reste_nommee_comme_telle(brouillon: Path, corpus: Path) -> None:
    bilan = review_annotation.promote(brouillon, "claude-ai", AnnotationStatus.APPROVED)
    assert bilan["revue independante"] is False

    rapport = corpus_report(load_corpus(corpus))
    assert rapport["selfApproved"] == 1, "le drapeau d'auto-approbation doit se lever"


def test_la_tracabilite_est_complete_apres_promotion(brouillon: Path) -> None:
    """Les six informations exigées, toutes portées par des champs existants."""
    review_annotation.promote(
        brouillon, "jonathan", AnnotationStatus.APPROVED, note="conforme apres revue visuelle"
    )
    annotation = _lire(brouillon)

    assert annotation.annotator == "claude-ai"  # qui a produit le tracé
    assert annotation.review is not None
    assert annotation.review.reviewer == "jonathan"  # qui l'a revu
    assert annotation.review.reviewed_on is not None  # quand
    assert annotation.review.note == "conforme apres revue visuelle"  # le verdict écrit
    assert annotation.revision >= 1  # quelle révision du tracé
    assert annotation.pass_label == "AI"  # provenance : passe machine
    assert annotation.status is AnnotationStatus.APPROVED


def test_le_cli_refuse_un_releve_absent(corpus: Path) -> None:
    code = review_annotation.main(
        ["--dataset", str(corpus), "--photo", "inconnue", "--reviewer", "x", "--status", "approved"]
    )
    assert code == 1
