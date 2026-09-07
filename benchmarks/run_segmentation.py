"""Banc d'essai de segmentation du sol. Prêt, et **vide de tout modèle**.

Il attend des candidats. Il n'en contient aucun, et les trois seules
« segmentations » qu'il embarque sont triviales par construction : un masque
vide, un masque plein, un rectangle dans le tiers bas. Elles ne prétendent
rien segmenter — elles servent à vérifier que la balance donne bien les
résultats qu'on peut prévoir à la main.

C'est la même discipline que le LOT 0 pour les métriques d'image : construire
l'instrument avant ce qu'il mesure, et le vérifier sur des cas dont on connaît
la réponse.

## Enregistrer un candidat

Un candidat est une fonction qui reçoit l'image chargée et renvoie un masque
booléen aux dimensions de cette image :

    @register("mon-approche")
    def mon_approche(image: LoadedImage) -> np.ndarray:
        ...

Aucune contrainte de plus. Le LOT 2 en enregistrera plusieurs et les comparera
sur ce même rapport.

## Ce que le rapport permet de distinguer

Trois choses que la moyenne d'un IoU mélange, et qu'il faut séparer pour
décider quoi que ce soit :

* **la performance du candidat** — ses métriques par image et agrégées ;
* **la difficulté de l'image** — agrégats par difficulté et par trait de
  scène, pour répondre à « échoue-t-il sur les tapis ou sur les sols
  sombres ? » ;
* **la fiabilité de la vérité terrain** — part de pixels incertains, statut
  de l'annotation, désaccord inter-annotateur quand il existera. Un IoU de
  0,80 sur une scène dont 30 % est déclarée indécidable ne dit pas la même
  chose que 0,80 sur une scène nette.

Les scènes rangées en `rejected` ne sont **pas** agrégées avec les autres :
on n'attend pas qu'elles soient segmentables, et les compter tirerait une
moyenne vers le bas sans rien apprendre.

Usage
-----
    python -m benchmarks.run_segmentation
    python -m benchmarks.run_segmentation --candidates empty,full --out benchmarks/out/seg
"""

import argparse
import json
import platform
import sys
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from app.schemas.annotation import ANNOTATION_SCHEMA
from app.services.image_loader import LoadedImage, load_image
from benchmarks.annotations import AnnotatedScene, corpus_report, load_corpus
from benchmarks.dataset import DATASET_SCHEMA, Difficulty
from benchmarks.segmentation import METRICS_SCHEMA, MetricConfig, SegmentationMetrics, evaluate

#: Version du format de rapport de segmentation.
BENCHMARK_SCHEMA = "pose-parquet-ai/segmentation-benchmark@1"

#: Un candidat : image chargée → masque booléen.
Candidate = Callable[[LoadedImage], np.ndarray]

_CANDIDATES: dict[str, Candidate] = {}


def register(name: str) -> Callable[[Candidate], Candidate]:
    """Enregistre un candidat de segmentation sous un nom."""

    def decorate(function: Candidate) -> Candidate:
        if name in _CANDIDATES:
            raise ValueError(f"candidat déjà enregistré : {name}")
        _CANDIDATES[name] = function
        return function

    return decorate


def available() -> tuple[str, ...]:
    return tuple(_CANDIDATES)


# --- Les trois références triviales -------------------------------------
# Aucune ne segmente. Elles bornent la mesure : ce que donne le pire cas
# possible, et ce que donne une forme grossièrement plausible. Un candidat qui
# ne battrait pas `bottom-third` n'apporterait rien.


@register("empty")
def _empty(image: LoadedImage) -> np.ndarray:
    """Rien n'est du sol. Rappel nul, IoU nul, et aucun faux positif."""
    return np.zeros((image.height, image.width), dtype=bool)


@register("full")
def _full(image: LoadedImage) -> np.ndarray:
    """Tout est du sol. Rappel parfait, précision égale à la part de sol.

    Utile précisément parce que son rappel est parfait : elle montre pourquoi
    un rappel publié sans sa précision ne veut rien dire.
    """
    return np.ones((image.height, image.width), dtype=bool)


@register("bottom-third")
def _bottom_third(image: LoadedImage) -> np.ndarray:
    """Le tiers bas de l'image, sans rien regarder.

    Grossière, et pourtant pas absurde : sur une photo d'intérieur prise
    debout, le sol occupe souvent cette zone. C'est le plancher de comparaison
    qu'un vrai segmenteur doit dépasser franchement pour mériter son coût.
    """
    mask = np.zeros((image.height, image.width), dtype=bool)
    mask[int(image.height * 2 / 3) :, :] = True
    return mask


# --- Exécution ----------------------------------------------------------


def _aggregate(values: Iterable[float | None]) -> dict[str, float | int | None]:
    """Moyenne et médiane des valeurs définies, et combien l'étaient.

    `counted` n'est pas décoratif : une moyenne d'IoU sur trois images ne se
    lit pas comme la même moyenne sur trente, et les métriques peuvent être
    indéfinies (scène sans sol visible).
    """
    defined = [value for value in values if value is not None]
    if not defined:
        return {"counted": 0, "mean": None, "median": None}
    return {
        "counted": len(defined),
        "mean": round(float(np.mean(defined)), 6),
        "median": round(float(np.median(defined)), 6),
    }


def _scene_row(
    scene: AnnotatedScene, candidate: str, metrics: SegmentationMetrics
) -> dict[str, Any]:
    annotation = scene.annotation
    return {
        "candidate": candidate,
        "photoId": annotation.photo_id,
        "difficulty": scene.photo.difficulty.value,
        "traits": [trait.value for trait in scene.photo.traits],
        # Traçabilité de la référence, pas seulement du résultat.
        "annotationRevision": annotation.revision,
        "annotationStatus": annotation.status.value,
        "annotator": annotation.annotator,
        "maskSha256": dict(annotation.mask_sha256),
        "imageSha256": scene.photo.provenance.sha256,
        "area": metrics.area.as_dict(),
        "boundary": metrics.boundary.as_dict(),
    }


def _group(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    """Agrégats par valeur d'une clé de ligne."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(str(row[key]), []).append(row)
    return {
        name: {
            "scenes": len(items),
            "iou": _aggregate(item["area"]["iou"] for item in items),
            "boundaryF1": _aggregate(item["boundary"]["f1"] for item in items),
        }
        for name, items in sorted(groups.items())
    }


def _by_trait(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Agrégats par trait de scène — la lecture qui décidera du modèle.

    Une scène porte plusieurs traits, donc les groupes se recouvrent. C'est
    voulu : la question n'est pas « combien de scènes à tapis » mais « comment
    se comporte le candidat quand il y a un tapis ».
    """
    traits: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        for trait in row["traits"]:
            traits.setdefault(trait, []).append(row)
    return {
        trait: {
            "scenes": len(items),
            "iou": _aggregate(item["area"]["iou"] for item in items),
            "boundaryF1": _aggregate(item["boundary"]["f1"] for item in items),
        }
        for trait, items in sorted(traits.items())
    }


def run(
    root: Path, out_dir: Path, candidates: tuple[str, ...], config: MetricConfig | None = None
) -> dict[str, Any]:
    """Évalue les candidats sur les scènes **approuvées** du corpus."""
    settings = config or MetricConfig()
    scenes = load_corpus(root)
    usable = [scene for scene in scenes if scene.usable]

    rows: list[dict[str, Any]] = []
    for name in candidates:
        segment = _CANDIDATES[name]
        for scene in usable:
            assert scene.floor_visible is not None  # garanti par `usable`
            image = load_image(scene.image_path.read_bytes())
            metrics = evaluate(segment(image), scene.floor_visible, scene.uncertain, settings)
            rows.append(_scene_row(scene, name, metrics))

    # Les scènes qu'on n'attend pas segmentables sortent des agrégats.
    scored = [row for row in rows if row["difficulty"] != Difficulty.REJECTED.value]

    report: dict[str, Any] = {
        "schema": BENCHMARK_SCHEMA,
        "ranAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(terse=True),
            "numpy": np.__version__,
        },
        "formats": {
            "dataset": DATASET_SCHEMA,
            "annotation": ANNOTATION_SCHEMA,
            "metrics": METRICS_SCHEMA,
        },
        "metricConfig": settings.as_dict(),
        "corpus": {
            "root": root.name,
            "scenesAnnotated": len(scenes),
            "scenesApproved": len(usable),
            "scenesScored": len({row["photoId"] for row in scored}),
            "scenesRejectedExcluded": len(
                {row["photoId"] for row in rows if row["difficulty"] == Difficulty.REJECTED.value}
            ),
        },
        "validation": corpus_report(scenes),
        "candidates": {
            name: {
                "overall": {
                    "iou": _aggregate(
                        row["area"]["iou"] for row in scored if row["candidate"] == name
                    ),
                    "dice": _aggregate(
                        row["area"]["dice"] for row in scored if row["candidate"] == name
                    ),
                    "precision": _aggregate(
                        row["area"]["precision"] for row in scored if row["candidate"] == name
                    ),
                    "recall": _aggregate(
                        row["area"]["recall"] for row in scored if row["candidate"] == name
                    ),
                    "boundaryF1": _aggregate(
                        row["boundary"]["f1"] for row in scored if row["candidate"] == name
                    ),
                },
                "byDifficulty": _group(
                    [row for row in scored if row["candidate"] == name], "difficulty"
                ),
                "byTrait": _by_trait([row for row in scored if row["candidate"] == name]),
            }
            for name in candidates
        },
        # Fiabilité de la référence, à côté de la performance et jamais mêlée.
        "groundTruthReliability": {
            "ignoredFraction": _aggregate(row["area"]["ignored_fraction"] for row in scored),
            "note": (
                "Part de pixels exclus des métriques faute d'être décidables. "
                "Un IoU calculé sur 60 % d'une image ne se lit pas comme le même "
                "IoU sur 99 %. Le désaccord inter-annotateur viendra ici quand "
                "des doubles annotations existeront."
            ),
        },
        "rows": rows,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "segmentation.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    parser.add_argument("--dataset", type=Path, default=Path("datasets"))
    parser.add_argument("--out", type=Path, default=Path("benchmarks/out/segmentation"))
    parser.add_argument(
        "--candidates",
        default=",".join(available()),
        help=f"noms séparés par des virgules ; disponibles : {', '.join(available())}",
    )
    args = parser.parse_args(argv)

    names = tuple(name.strip() for name in args.candidates.split(",") if name.strip())
    unknown = [name for name in names if name not in _CANDIDATES]
    if unknown:
        print(f"Candidat inconnu : {', '.join(unknown)}", file=sys.stderr)
        print(f"Disponibles : {', '.join(available())}", file=sys.stderr)
        return 2

    try:
        report = run(args.dataset, args.out, names)
    except FileNotFoundError as missing:
        print(f"Erreur : {missing}", file=sys.stderr)
        return 2

    corpus = report["corpus"]
    print(
        f"{corpus['scenesAnnotated']} scène(s) annotée(s), {corpus['scenesApproved']} approuvée(s)"
    )
    if corpus["scenesApproved"] == 0:
        print(
            "Aucune scène approuvée : le banc d'essai est prêt et le corpus réel "
            "reste à constituer. Voir datasets/README.md et "
            "docs/annotation-protocol.md.",
            file=sys.stderr,
        )
    for name, results in report["candidates"].items():
        overall = results["overall"]
        print(
            f"  {name:14} IoU {overall['iou']['mean']}  contour F1 {overall['boundaryF1']['mean']}"
        )
    print(f"Rapport : {args.out / 'segmentation.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
