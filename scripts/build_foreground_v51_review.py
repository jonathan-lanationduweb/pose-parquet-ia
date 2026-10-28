# ruff: noqa: E501
"""Assemble the private V5.1 photo/coarse/refined/crop comparison and timings."""

import html
import json
from pathlib import Path
from time import perf_counter

import cv2
import numpy as np

from app.services.foreground import OBJECT_CLASSES, RUG, polygons


def main() -> None:
    cv2.setNumThreads(2)
    root = Path("review/foreground-mask-v5-1")
    rows = json.loads((root / "paired.json").read_text(encoding="utf8"))
    annotations = json.loads(
        Path("review/foreground-mask-v5/annotations.json").read_text(encoding="utf8")
    )
    cards = []
    encoding = []
    matrix = []
    for row in rows:
        name = row["scene"]
        dest = root / name
        src = Path("review/foreground-mask-v5") / name
        rgb = cv2.cvtColor(cv2.imread(str(src / "01-original.png")), cv2.COLOR_BGR2RGB)
        labels = np.load(src / "labels.npy")
        mask = np.load(dest / "v51.npy")
        old = np.load(dest / "v5.npy")
        np.testing.assert_array_equal(mask, old)
        coarse = np.isin(labels, [*OBJECT_CLASSES, RUG])
        overlay = rgb.copy()
        overlay[coarse] = (rgb[coarse] * 0.55 + np.array([255, 0, 0]) * 0.45).astype(np.uint8)
        cv2.imwrite(str(dest / "coarse-overlay.png"), cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR))
        h, w = labels.shape
        ratio = min(352 / h, 512 / w) if w / h >= 1.25 else min(512 / h, 512 / w)
        small = cv2.resize(rgb, (round(w * ratio), round(h * ratio)), interpolation=cv2.INTER_AREA)
        sampled = cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)
        cv2.imwrite(str(dest / "sampled-photo.png"), cv2.cvtColor(sampled, cv2.COLOR_RGB2BGR))
        cv2.imwrite(str(dest / "01-original.png"), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
        raw = json.loads((src / "after.json").read_text(encoding="utf8"))
        before = json.dumps(raw)
        (dest / "before.json").write_text(before, encoding="utf8")
        durations = []
        for _ in range(6):
            t = perf_counter()
            # Geometry, fixture exclusions and V4 light are immutable baseline data.
            objects = [o for o in raw["occluders"] if o["kind"] == "fixture"]
            objects += [
                o.model_dump(by_alias=True)
                for o in polygons(mask & (labels == RUG), kind="rug", prefix="rug")
            ]
            objects += [
                o.model_dump(by_alias=True)
                for o in polygons(mask & ~(labels == RUG), kind="furniture", prefix="foreground")
            ]
            updated = {**raw, "occluders": objects}
            encoded = json.dumps(updated)
            durations.append((perf_counter() - t) * 1000)
        (dest / "after.json").write_text(encoded, encoding="utf8")
        for key in ["camera", "planes", "floorZones", "light"]:
            assert raw[key] == updated[key]
        encoding.append(
            {"scene": name, "timesMs": durations, "jsonBytes": len(encoded.encode("utf8"))}
        )
        columns = [
            ("Source", "01-original.png"),
            ("Photo après réduction / remontée", "sampled-photo.png"),
            ("Coarse semantic rouge", "coarse-overlay.png"),
            ("V5", "v5-overlay.png"),
            ("V5.1 optimisé", "v51-overlay.png"),
            ("Tuiles : ajouts cyan — AUDIT", "tiles-seeds.png"),
            ("Bande contact : ajouts cyan — AUDIT", "contact-seeds.png"),
        ]
        figures = "".join(
            "<figure><figcaption>"
            + title
            + '</figcaption><img loading="lazy" src="'
            + name
            + "/"
            + file
            + '"></figure>'
            for title, file in columns
        )
        crops = []
        for label, box in annotations[name][2].items():
            x0, y0, x1, y1 = box
            imgs = [
                rgb,
                overlay,
                cv2.cvtColor(cv2.imread(str(dest / "v5-overlay.png")), cv2.COLOR_BGR2RGB),
                cv2.cvtColor(cv2.imread(str(dest / "v51-overlay.png")), cv2.COLOR_BGR2RGB),
            ]
            crop = np.hstack([im[y0:y1, x0:x1] for im in imgs])
            file = "crop-" + label + ".png"
            cv2.imwrite(
                str(dest / file),
                cv2.cvtColor(
                    cv2.resize(crop, None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST),
                    cv2.COLOR_RGB2BGR,
                ),
            )
            crops.append(
                "<p>"
                + html.escape(label)
                + ' : source / coarse / V5 / V5.1</p><img class="crop" loading="lazy" src="'
                + name
                + "/"
                + file
                + '">'
            )
        times = {
            v: float(np.median([r["totalMs"] for r in row["runs"][v][1:]])) for v in ["v5", "v51"]
        }
        cards.append(
            "<section><h2>"
            + name
            + "</h2><p>Masques identiques. Médiane V5 "
            + str(round(times["v5"], 1))
            + " ms ; V5.1 "
            + str(round(times["v51"], 1))
            + ' ms.</p><div class="grid">'
            + figures
            + "</div>"
            + "".join(crops)
            + '<p>Rendu V4, avant / après</p><div class="grid"><img loading="lazy" src="'
            + name
            + '/04-final-before.png"><img loading="lazy" src="'
            + name
            + '/05-final-after.png"></div></section>'
        )
        matrix.append(
            {
                "scene": name,
                "smallInputSize": list(small.shape[1::-1]),
                "maskV5": "baseline",
                "maskV51": "bit-identical",
                "thinObjects": "unchanged",
                "missingSeeds": "see missing-seed-cases report",
                "falsePositives": "no new useful-floor pixels vs V5",
                "qualityTimeMs": times,
                "finalResult": "non-regression; missing-seed product objective unmet",
            }
        )
    (root / "mask-encode.json").write_text(json.dumps(encoding, indent=2), encoding="utf8")
    (root / "matrix.json").write_text(json.dumps(matrix, indent=2), encoding="utf8")
    (root / "index.html").write_text(
        '<!doctype html><meta charset="utf-8"><title>V5.1 — private review</title><style>body{font:16px system-ui;background:#f5f3ef;margin:24px}section{background:white;padding:20px;margin:24px 0}.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}figure{margin:0}img{width:100%;height:auto}.crop{max-width:1600px}figcaption{font-weight:bold} @media(max-width:700px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}}</style><h1>Foreground V5.1</h1><p>Optimisations uniquement en production. Tuiles/bande contact : expériences non intégrées. Aucun score global de vérité terrain.</p>'
        + "".join(cards),
        encoding="utf8",
    )


if __name__ == "__main__":
    main()
