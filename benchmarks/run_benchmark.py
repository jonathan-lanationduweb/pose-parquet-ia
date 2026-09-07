"""Parcourt un corpus, analyse chaque image, écrit un rapport reproductible.

C'est l'outil qui rend le choix des méthodes possible. Il n'en choisit aucune :
il mesure, dans un format stable, ce qu'une configuration donnée produit sur un
corpus donné. Comparer deux approches, c'est comparer deux rapports.

## Reproductibilité

Chaque rapport embarque de quoi être rejoué : version du banc d'essai, source
et graine du corpus, environnement, et **l'instantané complet des réglages
d'algorithme** (`Settings.algorithm_config()`). Sans ce dernier, deux rapports
ne sont pas comparables : on lit deux séries de chiffres sans savoir lequel des
deux seuils était en vigueur.

Chaque ligne porte l'identifiant d'image, sa difficulté, si elle est gradée, la
méthode qui a conclu, les défauts attendus, ceux détectés, les **faux
positifs**, les faux négatifs, les codes informationnels, le statut, et les
durées par étape.

## Deux sources

* `synthetic` — le corpus de `corpus/catalogue.py`, construit en mémoire.
  Reproductible au bit près, avec vérité terrain imposée ;
* `dataset` — un dossier de photos réelles et son `manifest.json`.

Les deux passent par le même comptage et le même format de sortie, pour qu'un
rapport synthétique et un rapport réel se lisent côte à côte.

Usage
-----
    python -m benchmarks.run_benchmark
    python -m benchmarks.run_benchmark --source dataset --dataset datasets
    python -m benchmarks.run_benchmark --out benchmarks/out/k1
"""

import argparse
import csv
import json
import platform
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from app.core.config import get_settings
from app.core.errors import ImageRejected
from app.core.warnings import Warn
from app.schemas.analysis import AnalysisResult
from app.services.pipeline import analyse_room
from benchmarks import scoring
from benchmarks.dataset import load_manifest
from corpus import patterns
from corpus.catalogue import CATALOGUE, SEED

#: Version du format de rapport. À incrémenter dès qu'une colonne change de
#: sens — deux rapports de versions différentes ne se comparent pas ligne à
#: ligne, et il faut que cela se voie.
BENCHMARK_SCHEMA = "pose-parquet-ai/benchmark@2"

#: Colonnes du CSV, dans l'ordre. Explicites plutôt que déduites du contenu :
#: une colonne qui apparaît ou disparaît selon le corpus rendrait deux rapports
#: incomparables.
CSV_COLUMNS: tuple[str, ...] = (
    "id",
    "difficulty",
    "graded",
    "status",
    "blur_method",
    "lens_method",
    "width",
    "height",
    "expected",
    "detected",
    "false_positives",
    "false_negatives",
    "informational",
    "strong_gradient_ratio",
    "laplacian_variance",
    "reblur_ratio",
    "edge_width_px",
    "blur_sharp",
    "blur_low_texture",
    "luma_mean",
    "contrast_std",
    "clipped_high_ratio",
    "clipped_low_ratio",
    "lens_verdict",
    "lens_suspected_sign",
    "lens_usable_edges",
    "lens_total_track_px",
    "lens_spatial_coverage",
    "lens_sign_agreement",
    "lens_k1_estimate",
    "lens_k1_residual_gain",
    "truth_k1",
    "truth_sign",
    "truth_blur_sigma",
    "truth_exposure_gain",
    "k1_absolute_error",
    "sign_correct",
    "load_image_ms",
    "quality_analysis_ms",
    "lens_analysis_ms",
    "total_ms",
)


@dataclass(frozen=True, slots=True)
class Case:
    """Une image à analyser, quelle que soit sa provenance."""

    id: str
    difficulty: str
    graded: bool
    data: bytes
    expected: set[Warn]
    truth: dict[str, Any]
    note: str


def _encode(entry: Any) -> bytes:
    """Encode une entrée du catalogue, orientation EXIF comprise."""
    image = entry.build()
    if entry.image_format == "JPEG-EXIF6":
        return patterns.encode_with_exif_orientation(image, 6)
    return patterns.encode(image, entry.image_format)


def synthetic_cases() -> Iterator[Case]:
    """Le corpus synthétique, construit en mémoire."""
    for entry in CATALOGUE:
        yield Case(
            id=entry.id,
            difficulty=entry.difficulty,
            graded=entry.graded,
            data=_encode(entry),
            expected=set(entry.expected),
            truth=dict(entry.truth),
            note=entry.note,
        )


def dataset_cases(directory: Path) -> Iterator[Case]:
    """Un corpus de photos réelles, décrit par son manifeste."""
    manifest = load_manifest(directory)
    for photo in manifest.photos:
        path = directory / photo.file
        if not path.is_file():
            print(f"  ! absente, ignorée : {photo.id} ({photo.file})", file=sys.stderr)
            continue
        truth: dict[str, Any] = {}
        lens = photo.ground_truth.lens
        if lens and "k1" in lens:
            truth["k1"] = float(lens["k1"])
            truth["sign"] = str(lens.get("provenance", "unknown"))
        yield Case(
            id=photo.id,
            difficulty=photo.difficulty.value,
            graded=photo.graded,
            data=path.read_bytes(),
            expected=set(photo.expected_issues),
            truth=truth,
            note=photo.notes or "",
        )


def _join(codes: frozenset[Warn] | set[Warn]) -> str:
    return "|".join(sorted(code.value for code in codes))


def _row(case: Case, result: AnalysisResult, score: scoring.ImageScore) -> dict[str, Any]:
    """Aplatit une analyse en une ligne de tableau."""
    blur = result.quality.blur if result.quality else None
    exposure = result.quality.exposure if result.quality else None
    lens = result.lens
    support = lens.support if lens else None
    k1 = lens.k1 if lens else None

    row: dict[str, Any] = dict.fromkeys(CSV_COLUMNS)
    row.update(
        id=case.id,
        difficulty=case.difficulty,
        graded=case.graded,
        status=result.status.value,
        blur_method=blur.method if blur else None,
        lens_method=lens.method if lens else None,
        width=result.image.width,
        height=result.image.height,
        expected=_join(score.expected),
        detected=_join(score.detected),
        false_positives=_join(score.false_positives),
        false_negatives=_join(score.false_negatives),
        informational=_join(score.informational),
        strong_gradient_ratio=blur.strong_gradient_ratio if blur else None,
        laplacian_variance=blur.laplacian_variance if blur else None,
        reblur_ratio=blur.reblur_ratio if blur else None,
        edge_width_px=blur.edge_width_px if blur else None,
        blur_sharp=blur.sharp if blur else None,
        blur_low_texture=blur.low_texture if blur else None,
        luma_mean=exposure.luma_mean if exposure else None,
        contrast_std=exposure.contrast_std if exposure else None,
        clipped_high_ratio=exposure.clipped_high_ratio if exposure else None,
        clipped_low_ratio=exposure.clipped_low_ratio if exposure else None,
        lens_verdict=lens.verdict.value if lens else None,
        lens_suspected_sign=lens.suspected_sign if lens else None,
        lens_usable_edges=support.usable_edges if support else None,
        lens_total_track_px=support.total_track_px if support else None,
        lens_spatial_coverage=support.spatial_coverage if support else None,
        lens_sign_agreement=support.sign_agreement if support else None,
        lens_k1_estimate=k1.k1 if k1 else None,
        lens_k1_residual_gain=k1.residual_gain if k1 else None,
        truth_k1=case.truth.get("k1"),
        truth_sign=case.truth.get("sign"),
        truth_blur_sigma=case.truth.get("blur_sigma"),
        truth_exposure_gain=case.truth.get("exposure_gain"),
        **{
            key: result.timings.get(key)
            for key in ("load_image_ms", "quality_analysis_ms", "lens_analysis_ms", "total_ms")
        },
    )
    return row


def _refused_row(case: Case, rejected: ImageRejected) -> dict[str, Any]:
    """Ligne d'une image refusée avant analyse.

    Une image du bac `rejected` **doit** finir ici : c'est son résultat
    attendu, pas un échec du banc d'essai.
    """
    row: dict[str, Any] = dict.fromkeys(CSV_COLUMNS)
    row.update(
        id=case.id,
        difficulty=case.difficulty,
        graded=case.graded,
        status=f"refused:{rejected.code}",
        expected=_join(case.expected),
        detected="",
        false_positives="",
        false_negatives=_join(case.expected),
        informational="",
    )
    return row


def run(cases: Iterator[Case], out_dir: Path, source: str) -> dict[str, Any]:
    """Analyse tout le corpus et écrit `benchmark.json` et `benchmark.csv`."""
    settings = get_settings()
    rows: list[dict[str, Any]] = []
    details: list[dict[str, Any]] = []
    graded_scores: list[scoring.ImageScore] = []
    lens_scores: list[dict[str, Any]] = []
    undetermined = 0

    for case in cases:
        try:
            result = analyse_room(case.data).result
        except ImageRejected as rejected:
            rows.append(_refused_row(case, rejected))
            details.append({"id": case.id, "refused": rejected.code})
            continue

        emitted = set(result.warnings)
        score = scoring.score_image(case.expected, emitted)
        rows.append(_row(case, result, score))
        details.append(
            {
                "id": case.id,
                "note": case.note,
                "result": result.model_dump(by_alias=True, mode="json"),
            }
        )

        if result.lens and result.lens.verdict.value == "undetermined":
            undetermined += 1
        if case.graded:
            graded_scores.append(score)

        if "k1" in case.truth and result.lens:
            lens_scores.append(
                {
                    "id": case.id,
                    "graded": case.graded,
                    **scoring.score_lens(
                        float(case.truth["k1"]),
                        result.lens.verdict.value,
                        result.lens.k1.k1 if result.lens.k1 else None,
                        result.lens.suspected_sign,
                    ).as_dict(),
                }
            )

    totals = scoring.total(graded_scores, undetermined)
    report: dict[str, Any] = {
        "schema": BENCHMARK_SCHEMA,
        "ranAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": source,
        "corpusSeed": SEED if source == "synthetic" else None,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(terse=True),
            "numpy": np.__version__,
        },
        # L'instantané sans lequel deux rapports ne sont pas comparables.
        "algorithmConfig": settings.algorithm_config(),
        "corpus": {
            "images": len(rows),
            "graded": len(graded_scores),
            "ungraded": len(rows) - len(graded_scores),
        },
        "scores": totals.as_dict(),
        "lens": _lens_summary(lens_scores),
        "timings": _timing_summary(rows),
        "rows": rows,
        "details": details,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "benchmark.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    with (out_dir / "benchmark.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return report


def _lens_summary(lens_scores: list[dict[str, Any]]) -> dict[str, Any]:
    """Bilan de distorsion contre la vérité terrain, quand elle est connue."""
    graded = [score for score in lens_scores if score["graded"]]
    distorted = [score for score in graded if score["truthDistorted"]]
    clean = [score for score in graded if not score["truthDistorted"]]
    errors = [
        score["k1AbsoluteError"]
        for score in distorted
        if score["detected"] and score["k1AbsoluteError"] is not None
    ]
    return {
        "gradedCases": len(graded),
        "distortedCases": len(distorted),
        "cleanCases": len(clean),
        "detectedWhenDistorted": sum(1 for score in distorted if score["detected"]),
        "detectedWhenClean": sum(1 for score in clean if score["detected"]),
        "signCorrectWhenDetected": sum(1 for score in distorted if score["signCorrect"] is True),
        "k1AbsoluteError": {
            "max": max(errors) if errors else None,
            "mean": round(sum(errors) / len(errors), 5) if errors else None,
        },
        "cases": lens_scores,
    }


def _timing_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Durées observées, en millisecondes, sur CPU."""
    summary: dict[str, Any] = {}
    for column in ("load_image_ms", "quality_analysis_ms", "lens_analysis_ms", "total_ms"):
        values = [row[column] for row in rows if row.get(column) is not None]
        summary[column] = {
            "mean": round(sum(values) / len(values), 2) if values else None,
            "max": max(values) if values else None,
        }
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    parser.add_argument("--source", choices=("synthetic", "dataset"), default="synthetic")
    parser.add_argument(
        "--dataset", type=Path, default=Path("datasets"), help="dossier contenant manifest.json"
    )
    parser.add_argument("--out", type=Path, default=Path("benchmarks/out"))
    args = parser.parse_args(argv)

    try:
        cases = synthetic_cases() if args.source == "synthetic" else dataset_cases(args.dataset)
        report = run(cases, args.out, args.source)
    except FileNotFoundError as missing:
        print(f"Erreur : {missing}", file=sys.stderr)
        return 2

    if report["corpus"]["images"] == 0:
        print(
            "Aucune image analysée. Le corpus réel est vide — voir "
            "datasets/README.md, ou lancez la source synthétique.",
            file=sys.stderr,
        )
    print(f"{report['corpus']['images']} image(s) — rapport dans {args.out}")
    print(json.dumps(report["scores"]["overall"], ensure_ascii=False))
    print(json.dumps(report["lens"], ensure_ascii=False)[:400])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
