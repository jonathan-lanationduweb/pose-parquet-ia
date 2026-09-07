"""Compare les candidates de netteté sur le corpus, et mesure leur **marge**.

Un détecteur qui classe correctement toutes les images d'un corpus n'est pas
pour autant robuste : si la plus nette et la plus floue ne sont séparées que
d'un pour cent de l'échelle de mesure, le premier cas réel les mélangera. Ce
qui compte n'est donc pas le nombre de bonnes réponses mais **l'écart entre
les deux groupes**, rapporté à leur dispersion.

C'est ce que cet outil calcule, pour chaque candidate :

* `max_sharp` — la valeur la plus « floue » atteinte par une image **nette** ;
* `min_blurred` — la plus « nette » atteinte par une image **floue** ;
* `margin` — l'écart entre les deux. Négatif : les groupes se chevauchent, et
  aucun seuil ne peut les séparer ;
* `separation` — la marge rapportée à l'étendue totale des valeurs observées.
  Sans dimension, donc comparable entre candidates qui ne partagent ni unité
  ni échelle : la variance du Laplacien va de 1 à 1000, le rapport de reflou de
  0 à 1, la largeur d'arête de 3 à 25 px.

Les groupes viennent de la vérité terrain du catalogue, jamais de la sortie
d'un détecteur. Les images sans support suffisant sont écartées des deux
groupes : leur netteté n'est pas décidable, donc elles ne peuvent ni valider ni
invalider une candidate. Les images **rééchantillonnées** par une distorsion le
sont aussi — l'interpolation les adoucit réellement, elles ne sont donc ni
nettes ni floues au sens de ce test.

Usage
-----
    python -m benchmarks.compare_candidates
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.services import blur_analysis
from app.services.image_loader import luma
from corpus.catalogue import CATALOGUE, Entry

#: Les trois candidates, et le sens dans lequel la valeur croît.
#: `higher_is_blurrier` fixe le sens de la comparaison sans quoi les marges se
#: calculeraient à l'envers pour la variance du Laplacien.
CANDIDATES: tuple[tuple[str, str, bool], ...] = (
    ("laplacian_variance", "variance du Laplacien", False),
    ("reblur_ratio", "rapport de reflou", True),
    ("edge_width_px", "largeur d'arête (px)", True),
)


@dataclass(frozen=True, slots=True)
class Sample:
    entry_id: str
    group: str
    values: dict[str, float | None]
    strong_gradient_ratio: float


def _group_of(entry: Entry) -> str:
    """« net », « flou », ou hors groupe — d'après la vérité terrain seule."""
    truth = entry.truth
    if "k1" in truth and float(truth.get("k1", 0.0)) != 0.0:
        # Rééchantillonnée : réellement adoucie par l'interpolation. Ni nette
        # ni floue, et la compter d'un côté ou de l'autre fausserait la marge.
        return "resampled"
    if "blur_sigma" in truth:
        return "blurred" if float(truth["blur_sigma"]) >= 1.5 else "borderline"
    if "motion_length" in truth:
        return "blurred"
    if not entry.graded:
        return "ungraded"
    return "sharp"


def collect() -> list[Sample]:
    """Mesure les trois candidates sur tout le corpus."""
    settings = get_settings()
    samples: list[Sample] = []
    for entry in CATALOGUE:
        reading = blur_analysis.measure(luma(entry.build()))
        group = _group_of(entry)
        # Sans support, la netteté n'est pas décidable : l'image ne peut ni
        # valider ni invalider une candidate.
        if reading.strong_gradient_ratio < settings.blur_min_strong_gradient_ratio:
            group = "no-support"
        samples.append(
            Sample(
                entry_id=entry.id,
                group=group,
                values={
                    "laplacian_variance": reading.laplacian_variance,
                    "reblur_ratio": reading.reblur_ratio,
                    "edge_width_px": reading.edge_width_px,
                },
                strong_gradient_ratio=reading.strong_gradient_ratio,
            )
        )
    return samples


def _values(samples: list[Sample], group: str, key: str) -> list[float]:
    """Valeurs mesurées d'un groupe, celles qui existent."""
    return [
        value
        for sample in samples
        if sample.group == group and (value := sample.values[key]) is not None
    ]


def margins(samples: list[Sample]) -> dict[str, Any]:
    """Marge de séparation de chaque candidate entre nettes et floues."""
    report: dict[str, Any] = {}
    for key, label, higher_is_blurrier in CANDIDATES:
        sharp = _values(samples, "sharp", key)
        blurred = _values(samples, "blurred", key)
        if not sharp or not blurred:
            report[key] = {"label": label, "usable": False}
            continue

        # Côté « flou » de chaque groupe, selon le sens de la mesure.
        sharp_edge = max(sharp) if higher_is_blurrier else min(sharp)
        blurred_edge = min(blurred) if higher_is_blurrier else max(blurred)
        margin = (blurred_edge - sharp_edge) if higher_is_blurrier else (sharp_edge - blurred_edge)

        observed = [*sharp, *blurred]
        span = max(observed) - min(observed)
        report[key] = {
            "label": label,
            "usable": True,
            "higherIsBlurrier": higher_is_blurrier,
            "sharpCount": len(sharp),
            "blurredCount": len(blurred),
            "sharpEdge": round(sharp_edge, 5),
            "blurredEdge": round(blurred_edge, 5),
            "margin": round(margin, 5),
            "separation": round(margin / span, 5) if span > 0 else None,
            "suggestedThreshold": round((sharp_edge + blurred_edge) / 2.0, 5),
            "separable": margin > 0,
        }
    return report


def main() -> int:
    samples = collect()
    report: dict[str, Any] = {
        "schema": "pose-parquet-ai/candidate-comparison@1",
        "algorithmConfig": get_settings().algorithm_config(),
        "margins": margins(samples),
        "samples": [
            {
                "id": s.entry_id,
                "group": s.group,
                "strongGradientRatio": s.strong_gradient_ratio,
                **s.values,
            }
            for s in samples
        ],
    }

    out = Path("benchmarks/out")
    out.mkdir(parents=True, exist_ok=True)
    (out / "candidates.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(
        f"{'candidate':22} {'nets':>5} {'flous':>5} {'bord net':>10} {'bord flou':>10} "
        f"{'marge':>9} {'separation':>10} {'seuil sugg.':>12}"
    )
    margin_report: dict[str, Any] = report["margins"]
    for key, info in margin_report.items():
        if not info.get("usable"):
            print(f"{key:22} inexploitable")
            continue
        print(
            f"{key:22} {info['sharpCount']:5d} {info['blurredCount']:5d} "
            f"{info['sharpEdge']:10.4f} {info['blurredEdge']:10.4f} {info['margin']:9.4f} "
            f"{(info['separation'] or 0):10.4f} {info['suggestedThreshold']:12.4f}"
        )
    print(f"\nRapport complet : {out / 'candidates.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
