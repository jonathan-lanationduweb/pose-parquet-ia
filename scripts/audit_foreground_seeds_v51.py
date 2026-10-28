"""Offline same-checkpoint crops audit. Proposals are private, never auto-promoted."""

import json
import os
from pathlib import Path
from time import perf_counter

import cv2
import numpy as np

from app.services.floor_semantic import OneFormerFloor
from app.services.foreground import OBJECT_CLASSES, RUG


def main() -> None:
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["PPAI_INFERENCE_BACKEND"] = "openvino"
    cv2.setNumThreads(2)
    root = Path("review/foreground-mask-v5-1")
    root.mkdir(parents=True, exist_ok=True)
    # A: current reviewed static graph cannot be requested at 768 by an env flag.
    # Probe reshape validation, do not export/download a replacement graph.
    import openvino as ov

    probe = {"requestedShape": [1, 3, 768, 768], "compiled": False}
    try:
        model = ov.Core().read_model("models/oneformer-openvino-512-square.xml")
        shapes = {model.input(0): [1, 3, 768, 768]}
        model.reshape(shapes)
        probe["reshapeSupported"] = True
        probe["note"] = "Graph validation accepts reshape; inference not yet benchmarked"
    except Exception as error:
        probe["reshapeSupported"] = False
        probe["reason"] = str(error)[:1600]
    (root / "higher-resolution.json").write_text(json.dumps(probe, indent=2), encoding="utf8")
    del model
    engine = OneFormerFloor()
    rows = []
    for folder in sorted(Path("review/foreground-mask-v5").iterdir()):
        if not (folder / "labels.npy").exists():
            continue
        rgb = cv2.cvtColor(cv2.imread(str(folder / "01-original.png")), cv2.COLOR_BGR2RGB)
        labels = np.load(folder / "labels.npy")
        domain = np.load(folder / "support.npy")
        h, w = labels.shape
        ys = np.nonzero(domain.any(axis=1))[0]
        y0 = max(0, int(ys[0]) - max(32, round(h * 0.06))) if len(ys) else h
        cw = min(w, max(384, round(w * 0.65)))
        # B: overlapping crops at increased effective spatial sampling.
        # C: one full-width contact/floor strip, with surrounding object context.
        boxes = {"tiles": [(0, y0, cw, h), (w - cw, y0, w, h)], "contact": [(0, y0, w, h)]}
        dest = root / folder.name
        dest.mkdir(exist_ok=True)
        base = np.isin(labels, [*OBJECT_CLASSES, RUG])
        row = {
            "scene": folder.name,
            "sourceSize": [w, h],
            "coarseObjectPixelsInDomain": int((base & domain).sum()),
            "modes": {},
        }
        for mode, regions in boxes.items():
            times = []
            proposal = base.copy()
            per = []
            for _run in range(5):
                start = perf_counter()
                proposal = base.copy()
                per = []
                for x0, ty0, x1, y1 in regions:
                    result = engine.segment(rgb[ty0:y1, x0:x1])
                    seeds = np.isin(result.labels, [*OBJECT_CLASSES, RUG])
                    # Discard crop-border predictions; retain original seeds everywhere.
                    margin = max(2, round((x1 - x0) / 32))
                    if x0 > 0:
                        seeds[:, :margin] = False
                    if x1 < w:
                        seeds[:, -margin:] = False
                    proposal[ty0:y1, x0:x1] |= seeds & domain[ty0:y1, x0:x1]
                    per.append(
                        {
                            "box": [x0, ty0, x1, y1],
                            "timingsMs": result.timings,
                            "metadata": result.metadata,
                        }
                    )
                times.append((perf_counter() - start) * 1000)
            added = proposal & ~base & domain
            np.save(dest / (mode + "-seeds.npy"), proposal)
            overlay = rgb.copy()
            overlay[base] = (rgb[base] * 0.55 + np.array([255, 0, 0]) * 0.45).astype(np.uint8)
            overlay[added] = (rgb[added] * 0.4 + np.array([0, 255, 255]) * 0.6).astype(np.uint8)
            cv2.imwrite(str(dest / (mode + "-seeds.png")), cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR))
            row["modes"][mode] = {
                "timesMs": times,
                "addedPixels": int(added.sum()),
                "regions": per,
                "integration": "audit only; uncalibrated; not merged into runtime",
            }
            print(
                folder.name,
                mode,
                int(added.sum()),
                round(float(np.median(times[1:])), 1),
                flush=True,
            )
        rows.append(row)
        (root / "seeds.json").write_text(json.dumps(rows, indent=2), encoding="utf8")


if __name__ == "__main__":
    main()
