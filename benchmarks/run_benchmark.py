"""Parcourt un corpus, analyse chaque photo, écrit un rapport.

C'est l'outil qui rendra possible le choix des modèles. Il n'en choisit aucun :
il mesure, dans un format stable, ce qu'un pipeline donné produit sur un
corpus donné. Comparer deux approches, ce sera comparer deux rapports.

Deux sorties, parce qu'elles ne servent pas la même chose :

* **JSON** — tout, y compris les tracés d'arêtes. C'est la trace qu'on rejoue
  plus tard avec d'autres seuils, sans réanalyser les photos ;
* **CSV** — une ligne par photo, les colonnes qu'on veut trier à l'œil ou
  ouvrir dans un tableur.

Usage
-----
    python -m benchmarks.run_benchmark --dataset datasets/synthetic
    python -m benchmarks.run_benchmark --dataset datasets --out benchmarks/out
"""

import argparse
import csv
import json
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.errors import ImageRejected
from app.services.pipeline import analyse_room
from benchmarks.dataset import Photo, load_manifest

#: Colonnes du CSV, dans l'ordre. Explicites plutôt que déduites d'un dict :
#: une colonne qui apparaît ou disparaît selon le contenu du corpus rend deux
#: rapports incomparables.
CSV_COLUMNS: tuple[str, ...] = (
    "id",
    "difficulty",
    "status",
    "width",
    "height",
    "aspect_ratio",
    "megapixels",
    "format",
    "exif_applied",
    "blur_laplacian_variance",
    "blur_sharp",
    "luma_mean",
    "contrast_std",
    "dark_pixel_ratio",
    "bright_pixel_ratio",
    "lens_verdict",
    "lens_usable_edges",
    "lens_max_sagitta_px",
    "warnings",
    "expected_issues",
    "missed_issues",
    "load_image_ms",
    "quality_analysis_ms",
    "lens_analysis_ms",
    "scene_builder_ms",
    "total_ms",
)


def _row(photo: Photo, result: Any) -> dict[str, Any]:
    """Aplatit un `AnalysisResult` en une ligne de tableau."""
    quality = result.quality
    lens = result.lens
    found = {w.value for w in result.warnings}
    expected = {w.value for w in photo.expected_issues}
    return {
        "id": photo.id,
        "difficulty": photo.difficulty.value,
        "status": result.status.value,
        "width": result.image.width,
        "height": result.image.height,
        "aspect_ratio": result.image.aspect_ratio,
        "megapixels": result.image.megapixels,
        "format": result.image.format,
        "exif_applied": result.image.exif_orientation_applied,
        "blur_laplacian_variance": quality.blur.laplacian_variance if quality else None,
        "blur_sharp": quality.blur.sharp if quality else None,
        "luma_mean": quality.exposure.luma_mean if quality else None,
        "contrast_std": quality.exposure.contrast_std if quality else None,
        "dark_pixel_ratio": quality.exposure.dark_pixel_ratio if quality else None,
        "bright_pixel_ratio": quality.exposure.bright_pixel_ratio if quality else None,
        "lens_verdict": lens.verdict.value if lens else None,
        "lens_usable_edges": lens.usable_edges if lens else None,
        "lens_max_sagitta_px": lens.max_sagitta_px if lens else None,
        "warnings": "|".join(sorted(found)),
        "expected_issues": "|".join(sorted(expected)),
        # Ce que le corpus annonçait et que l'analyse n'a pas vu. C'est la
        # colonne qu'on lit en premier : elle mesure un manque, pas une durée.
        "missed_issues": "|".join(sorted(expected - found)),
        **{
            key: result.timings.get(key)
            for key in (
                "load_image_ms",
                "quality_analysis_ms",
                "lens_analysis_ms",
                "scene_builder_ms",
                "total_ms",
            )
        },
    }


def _rejected_row(photo: Photo, rejected: ImageRejected) -> dict[str, Any]:
    """Ligne d'une photo refusée avant analyse.

    Une photo du bac `rejected` **doit** finir ici : c'est son résultat
    attendu, pas un échec du banc d'essai.
    """
    row: dict[str, Any] = dict.fromkeys(CSV_COLUMNS)
    row.update(
        id=photo.id,
        difficulty=photo.difficulty.value,
        status=f"refused:{rejected.code}",
        expected_issues="|".join(sorted(w.value for w in photo.expected_issues)),
        warnings="",
        missed_issues="",
    )
    return row


def run(dataset_dir: Path, out_dir: Path) -> dict[str, Any]:
    """Analyse tout le corpus et écrit `benchmark.json` et `benchmark.csv`."""
    manifest = load_manifest(dataset_dir)
    rows: list[dict[str, Any]] = []
    details: list[dict[str, Any]] = []

    for photo in manifest.photos:
        path = dataset_dir / photo.file
        if not path.is_file():
            print(f"  ! absente, ignorée : {photo.id} ({photo.file})", file=sys.stderr)
            continue
        data = path.read_bytes()
        try:
            result = analyse_room(data).result
        except ImageRejected as rejected:
            rows.append(_rejected_row(photo, rejected))
            details.append({"id": photo.id, "refused": rejected.code})
            continue
        rows.append(_row(photo, result))
        details.append({"id": photo.id, "result": result.model_dump(by_alias=True, mode="json")})

    report = {
        "schema": "pose-parquet-ai/benchmark@1",
        "ranAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(terse=True),
        },
        "dataset": {
            "path": dataset_dir.name,
            "photos": len(manifest.photos),
            "analysed": len(rows),
        },
        "summary": _summarise(rows),
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


def _summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Les quelques chiffres qu'on veut voir sans ouvrir le tableau."""
    timings = [row["total_ms"] for row in rows if row.get("total_ms") is not None]
    statuses: dict[str, int] = {}
    for row in rows:
        statuses[row["status"]] = statuses.get(row["status"], 0) + 1
    return {
        "byStatus": statuses,
        "withMissedIssues": sum(1 for row in rows if row.get("missed_issues")),
        "totalMs": {
            "mean": round(sum(timings) / len(timings), 2) if timings else None,
            "max": max(timings) if timings else None,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--dataset", type=Path, default=Path("datasets"), help="dossier contenant manifest.json"
    )
    parser.add_argument("--out", type=Path, default=Path("benchmarks/out"))
    args = parser.parse_args(argv)

    try:
        report = run(args.dataset, args.out)
    except FileNotFoundError as missing:
        print(f"Erreur : {missing}", file=sys.stderr)
        return 2

    analysed = report["dataset"]["analysed"]
    if analysed == 0:
        print(
            "Aucune photo analysée. Le corpus est vide — voir datasets/README.md,\n"
            "ou générez les fixtures : python scripts/make_fixtures.py",
            file=sys.stderr,
        )
    print(f"{analysed} photo(s) analysée(s) — rapport dans {args.out}")
    print(json.dumps(report["summary"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
