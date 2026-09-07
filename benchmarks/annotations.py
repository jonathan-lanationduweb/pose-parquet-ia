"""Chargement, jointure et contrôle des annotations humaines.

Une annotation seule ne suffit pas à mesurer quoi que ce soit : elle dit où est
le sol, pas d'où vient la photo ni ce qu'elle vaut. Ce module joint chaque
relevé à son entrée de manifeste et **refuse** la paire quand elle est
incomplète.

Ce refus est le mécanisme central du préambule. Il remplace un champ
« provenance » recopié dans l'annotation, qui aurait pu diverger du manifeste
sans que rien ne le signale : ici, une annotation dont la photo n'est pas
décrite ne peut pas entrer au banc d'essai, parce qu'elle n'a pas de photo.

## Ce qui bloque, et ce qui avertit

Un **error** empêche l'entrée au banc d'essai officiel. Un **warning** est une
chose qu'il faut savoir sans qu'elle invalide la mesure. La frontière tient à
une question : est-ce que le chiffre calculé voudrait encore dire quelque
chose ? Un masque aux mauvaises dimensions, non. Un recouvrement de dix pixels
entre le sol et une zone incertaine, oui — les pixels concernés sont exclus de
toute façon.
"""

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import numpy as np

from app.schemas.annotation import AnnotationStatus, FloorAnnotation
from benchmarks.dataset import Difficulty, Manifest, Photo, load_manifest, sha256_of
from benchmarks.segmentation import MaskError, load_mask

#: Dossier des annotations, relatif à la racine du corpus.
ANNOTATIONS_DIR = "annotations"

#: Part de l'image au-delà de laquelle une zone incertaine rend la scène
#: inexploitable. À moitié incertaine, une image ne mesure plus grand-chose, et
#: un IoU calculé dessus se comparerait mal à celui d'une scène nette.
MAX_UNCERTAIN_FRACTION = 0.5


class Check(StrEnum):
    """Codes de contrôle, déclarés une fois.

    Comme les avertissements du service : un code machine, pas une phrase. Un
    rapport de validation doit pouvoir être compté, pas seulement lu.
    """

    PHOTO_NOT_IN_MANIFEST = "photo_not_in_manifest"
    IMAGE_FILE_MISSING = "image_file_missing"
    IMAGE_HASH_MISMATCH = "image_hash_mismatch"
    IMAGE_HASH_MISSING = "image_hash_missing"
    DIMENSIONS_MISMATCH = "dimensions_mismatch"
    MASK_UNREADABLE = "mask_unreadable"
    MASK_HASH_MISMATCH = "mask_hash_mismatch"
    MASK_HASH_MISSING = "mask_hash_missing"
    FLOOR_MASK_EMPTY = "floor_mask_empty"
    UNCERTAIN_TOO_LARGE = "uncertain_too_large"
    NOTHING_LEFT_TO_EVALUATE = "nothing_left_to_evaluate"
    FLOOR_OVERLAPS_UNCERTAIN = "floor_overlaps_uncertain"
    PROVENANCE_INCOMPLETE = "provenance_incomplete"
    LICENSE_UNVERIFIED = "license_unverified"
    APPROVED_WITHOUT_REVIEW = "approved_without_review"
    NOT_APPROVED = "not_approved"
    UNCERTAIN_ZONE_WITHOUT_MASK = "uncertain_zone_without_mask"


@dataclass(frozen=True, slots=True)
class Issue:
    level: str
    code: Check
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"level": self.level, "code": self.code.value, "message": self.message}


def _error(code: Check, message: str) -> Issue:
    return Issue("error", code, message)


def _warning(code: Check, message: str) -> Issue:
    return Issue("warning", code, message)


@dataclass(frozen=True, slots=True)
class AnnotatedScene:
    """Une annotation, sa photo, et le verdict du contrôle.

    C'est l'unité que le banc d'essai consomme. `masks_loaded` reste `None`
    quand un masque n'a pas pu être lu : on veut pouvoir rapporter le problème
    sans faire tomber toute l'exécution.
    """

    annotation: FloorAnnotation
    photo: Photo
    image_path: Path
    floor_visible: np.ndarray | None
    uncertain: np.ndarray | None
    issues: tuple[Issue, ...]

    @property
    def errors(self) -> tuple[Issue, ...]:
        return tuple(issue for issue in self.issues if issue.level == "error")

    @property
    def warnings(self) -> tuple[Issue, ...]:
        return tuple(issue for issue in self.issues if issue.level == "warning")

    @property
    def usable(self) -> bool:
        """Exploitable par le banc d'essai **officiel**.

        Trois conditions, et la troisième est celle qui compte : le statut doit
        être `approved`. Un masque techniquement parfait mais jamais relu n'est
        pas une référence — c'est un brouillon qui en a l'air.
        """
        return (
            not self.errors
            and self.floor_visible is not None
            and self.annotation.usable_as_ground_truth
        )


def _check_provenance(photo: Photo, issues: list[Issue]) -> None:
    provenance = photo.provenance
    if provenance.license.strip().lower() in {"", "?", "tbd", "à vérifier"}:
        issues.append(
            _error(
                Check.PROVENANCE_INCOMPLETE,
                f"{photo.id} : licence non renseignée — une licence absente ne "
                "doit jamais devenir une licence supposée",
            )
        )
    if provenance.redistributable and provenance.usage.value != "redistributable":
        issues.append(
            _error(
                Check.PROVENANCE_INCOMPLETE,
                f"{photo.id} : redistributable mais usage « {provenance.usage.value} » — "
                "les deux doivent s'accorder",
            )
        )
    if provenance.license.strip().lower().startswith("inconnu") and provenance.redistributable:
        issues.append(
            _error(
                Check.LICENSE_UNVERIFIED,
                f"{photo.id} : licence inconnue et pourtant déclarée redistribuable",
            )
        )


def _check_image(photo: Photo, path: Path, issues: list[Issue]) -> None:
    if not path.is_file():
        issues.append(
            _error(Check.IMAGE_FILE_MISSING, f"{photo.id} : image absente ({photo.file})")
        )
        return
    expected = photo.provenance.sha256
    if expected is None:
        issues.append(
            _warning(
                Check.IMAGE_HASH_MISSING,
                f"{photo.id} : pas de sha256 au manifeste — un rapport ne pourra pas "
                "affirmer sur quels octets il a été calculé",
            )
        )
        return
    actual = sha256_of(path)
    if actual != expected:
        issues.append(
            _error(
                Check.IMAGE_HASH_MISMATCH,
                f"{photo.id} : le fichier a changé (sha256 {actual[:12]}… "
                f"au lieu de {expected[:12]}…)",
            )
        )


def _check_mask_hash(
    annotation: FloorAnnotation, role: str, path: Path, issues: list[Issue]
) -> None:
    expected = annotation.mask_sha256.get(role)
    if expected is None:
        issues.append(
            _warning(
                Check.MASK_HASH_MISSING,
                f"{annotation.photo_id} : masque « {role} » sans sha256",
            )
        )
        return
    actual = sha256_of(path)
    if actual != expected:
        issues.append(
            _error(
                Check.MASK_HASH_MISMATCH,
                f"{annotation.photo_id} : masque « {role} » modifié depuis son relevé "
                f"(sha256 {actual[:12]}… au lieu de {expected[:12]}…) — "
                "incrémentez `revision` si le changement est voulu",
            )
        )


def _check_masks_consistency(
    annotation: FloorAnnotation,
    floor: np.ndarray,
    uncertain: np.ndarray | None,
    photo: Photo,
    issues: list[Issue],
) -> None:
    total = float(floor.size)
    floor_count = int(np.count_nonzero(floor))

    if floor_count == 0:
        # Légitime sur une scène qu'on n'attend pas segmentable ; suspect
        # partout ailleurs.
        if photo.difficulty is Difficulty.REJECTED:
            issues.append(
                _warning(
                    Check.FLOOR_MASK_EMPTY,
                    f"{annotation.photo_id} : masque de sol vide, cohérent avec "
                    "une scène rangée en « rejected »",
                )
            )
        else:
            issues.append(
                _error(
                    Check.FLOOR_MASK_EMPTY,
                    f"{annotation.photo_id} : masque de sol vide sans que la scène soit "
                    "« rejected » — si c'est voulu, changez la difficulté ou expliquez-le "
                    "dans `notes`",
                )
            )

    if uncertain is None:
        if annotation.uncertain_zones:
            issues.append(
                _warning(
                    Check.UNCERTAIN_ZONE_WITHOUT_MASK,
                    f"{annotation.photo_id} : {len(annotation.uncertain_zones)} zone(s) "
                    "incertaine(s) décrite(s) sans masque correspondant — les métriques "
                    "n'excluront rien",
                )
            )
        return

    uncertain_fraction = int(np.count_nonzero(uncertain)) / total
    if uncertain_fraction > MAX_UNCERTAIN_FRACTION:
        issues.append(
            _error(
                Check.UNCERTAIN_TOO_LARGE,
                f"{annotation.photo_id} : {uncertain_fraction:.0%} de l'image est "
                f"incertaine (limite {MAX_UNCERTAIN_FRACTION:.0%}) — il ne reste pas assez "
                "à mesurer pour que le résultat se compare aux autres scènes",
            )
        )

    evaluable_floor = int(np.count_nonzero(floor & ~uncertain))
    if floor_count > 0 and evaluable_floor == 0:
        issues.append(
            _error(
                Check.NOTHING_LEFT_TO_EVALUATE,
                f"{annotation.photo_id} : tout le sol annoté est dans une zone "
                "incertaine — aucune métrique de surface ne serait définie",
            )
        )

    overlap = int(np.count_nonzero(floor & uncertain))
    if overlap:
        issues.append(
            _warning(
                Check.FLOOR_OVERLAPS_UNCERTAIN,
                f"{annotation.photo_id} : {overlap / total:.2%} de l'image est à la fois "
                "sol et incertaine — ces pixels sont exclus des métriques, mais le relevé "
                "affirme un sol qu'il déclare indécidable",
            )
        )


def load_annotation(path: Path) -> FloorAnnotation:
    """Charge un fichier d'annotation. Lève si le format est invalide."""
    return FloorAnnotation.model_validate(json.loads(path.read_text(encoding="utf-8")))


def load_scene(path: Path, manifest: Manifest, root: Path) -> AnnotatedScene:
    """Charge une annotation, la joint à sa photo, et contrôle l'ensemble."""
    annotation = load_annotation(path)
    issues: list[Issue] = []

    photo = next((entry for entry in manifest.photos if entry.id == annotation.photo_id), None)
    if photo is None:
        raise KeyError(
            f"{path.name} : photo « {annotation.photo_id} » absente du manifeste — "
            "une annotation sans photo décrite n'a pas de provenance"
        )

    _check_provenance(photo, issues)
    image_path = root / photo.file
    _check_image(photo, image_path, issues)

    if annotation.status is not AnnotationStatus.APPROVED:
        issues.append(
            _warning(
                Check.NOT_APPROVED,
                f"{annotation.photo_id} : statut « {annotation.status.value} » — "
                "hors du banc d'essai officiel",
            )
        )

    floor: np.ndarray | None = None
    uncertain: np.ndarray | None = None
    width, height = annotation.width, annotation.height

    floor_path = path.parent / annotation.masks.floor_visible
    try:
        floor = load_mask(floor_path, width, height)
        _check_mask_hash(annotation, "floorVisible", floor_path, issues)
    except MaskError as failure:
        issues.append(_error(Check.MASK_UNREADABLE, f"{annotation.photo_id} : {failure}"))

    if annotation.masks.uncertain is not None:
        uncertain_path = path.parent / annotation.masks.uncertain
        try:
            uncertain = load_mask(uncertain_path, width, height)
            _check_mask_hash(annotation, "uncertain", uncertain_path, issues)
        except MaskError as failure:
            issues.append(_error(Check.MASK_UNREADABLE, f"{annotation.photo_id} : {failure}"))

    if floor is not None:
        _check_masks_consistency(annotation, floor, uncertain, photo, issues)

    return AnnotatedScene(
        annotation=annotation,
        photo=photo,
        image_path=image_path,
        floor_visible=floor,
        uncertain=uncertain,
        issues=tuple(issues),
    )


def load_corpus(root: Path) -> list[AnnotatedScene]:
    """Toutes les scènes annotées d'un corpus, contrôlées, dans un ordre stable."""
    manifest = load_manifest(root)
    directory = root / ANNOTATIONS_DIR
    if not directory.is_dir():
        return []
    return [load_scene(path, manifest, root) for path in sorted(directory.glob("*.json"))]


def corpus_report(scenes: list[AnnotatedScene]) -> dict[str, Any]:
    """Bilan de contrôle, lisible et comptable."""
    return {
        "schema": "pose-parquet-ai/annotation-validation@1",
        "scenes": len(scenes),
        "usable": sum(1 for scene in scenes if scene.usable),
        "withErrors": sum(1 for scene in scenes if scene.errors),
        "withWarnings": sum(1 for scene in scenes if scene.warnings),
        "byStatus": {
            status.value: sum(1 for s in scenes if s.annotation.status is status)
            for status in AnnotationStatus
        },
        "issues": [
            {"photoId": scene.annotation.photo_id, **issue.as_dict()}
            for scene in scenes
            for issue in scene.issues
        ],
    }
