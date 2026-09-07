"""Rapport du corpus pilote : temps d'annotation et accord humain.

Ce banc d'essai ne mesure **aucun modèle**. Il mesure les humains et le
protocole, ce qui doit venir avant : sans savoir de combien deux personnes
diffèrent sur la même photo, on ne sait pas quelle exigence poser à une
machine.

## Ce qu'il produit

* par scène : difficulté, traits, annotateur, passe, **durée**, part
  incertaine, statut ;
* par photo annotée deux fois : IoU, Dice, précision, rappel, F-mesure de
  contour **à plusieurs tolérances**, et la localisation du désaccord ;
* des agrégats de temps et d'accord, et les deux scènes extrêmes — la plus
  ambiguë et la plus stable.

## Ce qu'il refuse de produire

Aucun écart-type, aucun intervalle de confiance, aucun seuil de réussite. Sur
huit à douze images, un écart-type donnerait une précision statistique que
l'échantillon ne porte pas, et un seuil tiré de si peu de données deviendrait
une exigence produit par simple inertie.

Le rapport publie donc des **valeurs observées**, en les nommant ainsi. La
distinction entre ce qu'on a mesuré, ce qu'on a provisoirement réglé et ce
qu'on visera un jour est écrite dans la sortie elle-même.

Usage
-----
    python -m benchmarks.run_pilot
    python -m benchmarks.run_pilot --tolerances 0.0025,0.005,0.01 --render
"""

import argparse
import json
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from app.schemas.annotation import ANNOTATION_SCHEMA
from app.services.image_loader import load_image, luma
from benchmarks.agreement import (
    AGREEMENT_SCHEMA,
    DEFAULT_TOLERANCES,
    compare,
    render_comparison,
    summarise,
)
from benchmarks.annotations import AnnotatedScene, corpus_report, load_corpus, paired_scenes
from benchmarks.dataset import DATASET_SCHEMA

#: Version du format de rapport pilote.
PILOT_SCHEMA = "pose-parquet-ai/pilot-report@1"


def _durations(scenes: list[AnnotatedScene]) -> dict[str, Any]:
    """Statistiques de temps, et le nombre de relevés qui en portent.

    `counted` compte les annotations **chronométrées**, pas les annotations.
    Une moyenne sur trois relevés minutés parmi douze ne dit pas ce que coûte
    le corpus, et le rapport doit permettre de s'en apercevoir.
    """
    timed = [scene.annotation.timing for scene in scenes if scene.annotation.timing]
    if not timed:
        return {
            "counted": 0,
            "note": "aucune annotation chronométrée — voir --seconds à l'import",
        }

    totals = [timing.total_seconds for timing in timed]
    firsts = [timing.first_pass_seconds for timing in timed]
    reviews = [timing.review_seconds for timing in timed if timing.review_seconds > 0]

    def stats(values: list[float]) -> dict[str, float | int | None]:
        if not values:
            return {"counted": 0, "mean": None, "median": None, "min": None, "max": None}
        return {
            "counted": len(values),
            "mean": round(float(np.mean(values)), 1),
            "median": round(float(np.median(values)), 1),
            "min": round(float(min(values)), 1),
            "max": round(float(max(values)), 1),
        }

    return {
        "counted": len(timed),
        "totalSeconds": stats(totals),
        "firstPassSeconds": stats(firsts),
        "reviewSeconds": stats(reviews),
        "correctionCounts": [
            timing.correction_count for timing in timed if timing.correction_count is not None
        ],
    }


def _by_difficulty(scenes: list[AnnotatedScene]) -> dict[str, Any]:
    """Temps par difficulté — seulement là où l'échantillon existe."""
    groups: dict[str, list[float]] = {}
    for scene in scenes:
        timing = scene.annotation.timing
        if timing is not None:
            groups.setdefault(scene.photo.difficulty.value, []).append(timing.total_seconds)
    return {
        name: {
            "scenes": len(durations),
            "meanTotalSeconds": round(float(np.mean(durations)), 1),
        }
        for name, durations in sorted(groups.items())
    }


def _scene_row(scene: AnnotatedScene) -> dict[str, Any]:
    annotation = scene.annotation
    timing = annotation.timing
    uncertain = scene.uncertain
    ignored = (
        None
        if scene.floor_visible is None
        else round(
            0.0 if uncertain is None else int(np.count_nonzero(uncertain)) / float(uncertain.size),
            6,
        )
    )
    return {
        "photoId": annotation.photo_id,
        "difficulty": scene.photo.difficulty.value,
        "traits": [trait.value for trait in scene.photo.traits],
        "annotator": annotation.annotator,
        "passLabel": annotation.pass_label,
        "independentPass": annotation.independent_pass,
        "status": annotation.status.value,
        "revision": annotation.revision,
        "ignoredFraction": ignored,
        "uncertainReasons": sorted({zone.reason.value for zone in annotation.uncertain_zones}),
        "boundarySegments": {
            kind: sum(1 for s in annotation.boundary if s.kind.value == kind)
            for kind in sorted({s.kind.value for s in annotation.boundary})
        },
        "totalSeconds": None if timing is None else round(timing.total_seconds, 1),
        "firstPassSeconds": None if timing is None else timing.first_pass_seconds,
        "reviewSeconds": None if timing is None else timing.review_seconds,
        "notes": annotation.notes,
        "errors": [issue.code.value for issue in scene.errors],
    }


def run(
    root: Path,
    out_dir: Path,
    tolerances: tuple[float, ...] = DEFAULT_TOLERANCES,
    render: bool = False,
) -> dict[str, Any]:
    """Analyse le corpus pilote et écrit `pilot.json`."""
    scenes = load_corpus(root)
    pairs_of_scenes = paired_scenes(scenes)

    comparisons = []
    for first, second in pairs_of_scenes:
        assert first.floor_visible is not None and second.floor_visible is not None
        pair = compare(
            first.annotation,
            first.floor_visible,
            first.uncertain,
            second.annotation,
            second.floor_visible,
            second.uncertain,
            tolerances,
        )
        comparisons.append(pair)

        if render:
            image = load_image(first.image_path.read_bytes())
            grey = (np.clip(luma(image.rgb), 0.0, 1.0) * 255.0).astype(np.uint8)
            union = (
                first.uncertain
                if second.uncertain is None
                else second.uncertain
                if first.uncertain is None
                else first.uncertain | second.uncertain
            )
            render_comparison(
                grey,
                first.floor_visible,
                second.floor_visible,
                union,
                out_dir / f"{pair.photo_id}.compare.png",
            )

    report: dict[str, Any] = {
        "schema": PILOT_SCHEMA,
        "ranAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(terse=True),
            "numpy": np.__version__,
        },
        "formats": {
            "dataset": DATASET_SCHEMA,
            "annotation": ANNOTATION_SCHEMA,
            "agreement": AGREEMENT_SCHEMA,
        },
        "tolerancesTested": list(tolerances),
        "corpus": {
            "root": root.name,
            "photosAnnotated": len({scene.annotation.photo_id for scene in scenes}),
            "annotations": len(scenes),
            "doublyAnnotated": len(pairs_of_scenes),
            "approved": sum(1 for scene in scenes if scene.usable),
        },
        "validation": corpus_report(scenes),
        "annotationTime": _durations(scenes),
        "annotationTimeByDifficulty": _by_difficulty(scenes),
        "humanAgreement": summarise(comparisons),
        "pairs": [pair.as_dict() for pair in comparisons],
        "scenes": [_scene_row(scene) for scene in scenes],
        # Écrit dans la sortie, pas seulement dans la documentation : un
        # rapport qu'on relit dans six mois doit porter ses propres réserves.
        "caveats": [
            "Valeurs OBSERVÉES sur un échantillon pilote. Aucun seuil de réussite "
            "produit n'en découle.",
            "Aucun écart-type ni intervalle de confiance : sur une douzaine "
            "d'images, ils donneraient une précision que l'échantillon ne porte pas.",
            "La cible IoU > 0,92 héritée du front n'est PAS validée. Comparer "
            "d'abord à l'accord humain observé ci-dessus.",
            "La tolérance de contour reste un réglage provisoire. Le rapport "
            "montre sa sensibilité, il ne la fixe pas.",
            "`independentPass` est une déclaration de l'annotateur, invérifiable par l'outil.",
        ],
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "pilot.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    parser.add_argument("--dataset", type=Path, default=Path("datasets"))
    parser.add_argument("--out", type=Path, default=Path("benchmarks/out/pilot"))
    parser.add_argument(
        "--tolerances",
        default=",".join(str(value) for value in DEFAULT_TOLERANCES),
        help="fractions de diagonale, séparées par des virgules",
    )
    parser.add_argument(
        "--render", action="store_true", help="écrire une comparaison PNG par paire"
    )
    args = parser.parse_args(argv)

    try:
        tolerances = tuple(float(value) for value in args.tolerances.split(",") if value.strip())
        report = run(args.dataset, args.out, tolerances, args.render)
    except (FileNotFoundError, KeyError, ValueError) as failure:
        print(f"Erreur : {failure}", file=sys.stderr)
        return 2

    corpus = report["corpus"]
    print(
        f"{corpus['photosAnnotated']} photo(s) annotée(s), "
        f"{corpus['annotations']} relevé(s), {corpus['doublyAnnotated']} paire(s)"
    )

    if corpus["annotations"] == 0:
        print(
            "\nAucune annotation. Le dispositif est prêt ; les relevés humains "
            "restent à faire.\nVoir docs/annotation-protocol.md, et "
            "docs/pilot-runbook.md pour la marche à suivre.",
            file=sys.stderr,
        )
        return 0

    time_stats = report["annotationTime"]
    if time_stats["counted"]:
        totals = time_stats["totalSeconds"]
        print(
            f"temps total : moy {totals['mean']} s · méd {totals['median']} s · "
            f"min {totals['min']} s · max {totals['max']} s "
            f"({time_stats['counted']} relevé(s) chronométré(s))"
        )

    agreement = report["humanAgreement"]
    if agreement.get("pairs"):
        print(f"accord humain — nature : {agreement['kind']}")
        print(f"  IoU  {agreement['iou']}")
        for key, value in agreement["boundaryF1ByTolerance"].items():
            print(f"  contour F1 @ {key} : {value}")
        print(f"  désaccord réparti : {agreement['disagreementShare']}")
        print(f"  moins stable : {agreement['leastStableScene']}")
    print(f"Rapport : {args.out / 'pilot.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
