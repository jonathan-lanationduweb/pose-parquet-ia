"""Private paired V5/V5.1 mask and timing audit; frozen Git baseline, no network."""

import importlib.util
import json
import subprocess
from pathlib import Path
from time import perf_counter

import cv2
import numpy as np

from app.services.floor_scene import refine_mask
from app.services.floor_segmentation import clean_mask, semantic_to_floor_visible
from app.services.foreground import build_foreground
from app.services.foreground_understanding import understand_foreground


def main() -> None:
    cv2.setNumThreads(2)
    root = Path("review/foreground-mask-v5-1")
    root.mkdir(parents=True, exist_ok=True)
    baseline = root / "baseline.py"
    baseline.write_text(
        subprocess.check_output(
            ["git", "show", "d87781f:app/services/foreground_understanding.py"], encoding="utf8"
        ),
        encoding="utf8",
    )
    spec = importlib.util.spec_from_file_location("v5baseline", baseline)
    module = importlib.util.module_from_spec(spec)
    import sys

    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    rows = []
    for folder in sorted(Path("review/foreground-mask-v5").iterdir()):
        if not (folder / "labels.npy").exists():
            continue
        rgb = cv2.cvtColor(cv2.imread(str(folder / "01-original.png")), cv2.COLOR_BGR2RGB)
        domain = np.load(folder / "support.npy")
        labels = np.load(folder / "labels.npy")
        coarse = build_foreground(
            labels,
            refine_mask(clean_mask(semantic_to_floor_visible(labels)), image_rgb=rgb),
            None,
            serialize=False,
        ).refined.copy()
        prior = coarse.copy()
        prior[domain] = np.load(folder / "before.npy")[domain]
        dest = root / folder.name
        dest.mkdir(exist_ok=True)
        np.save(dest / "prior.npy", prior)
        results, times = {}, {}
        # Alternate the order to avoid assigning all cold overhead to one version.
        for run in range(6):
            for name, fn in (
                [("v5", module.understand_foreground), ("v51", understand_foreground)]
                if run % 2 == 0
                else [("v51", understand_foreground), ("v5", module.understand_foreground)]
            ):
                start = perf_counter()
                result = fn(rgb, domain, prior)
                times.setdefault(name, []).append(
                    {"totalMs": (perf_counter() - start) * 1000, **result.report["timingsMs"]}
                )
                results[name] = result
        a, b = results["v5"], results["v51"]
        np.testing.assert_array_equal(a.mask, b.mask)
        np.testing.assert_array_equal(a.thin, b.thin)
        assert a.report["foregroundQuality"] == b.report["foregroundQuality"]
        if folder.name == "plant":
            points = json.loads((folder.parent / "annotated-stem.json").read_text(encoding="utf8"))[
                "pointsXY"
            ]
            assert all(b.mask[y, x] for x, y in points), "V5 stem recovery regressed"

        row = {
            "scene": folder.name,
            "sourceSize": list(rgb.shape[1::-1]),
            "changedVsV5": int(np.count_nonzero(a.mask != b.mask)),
            "changedInFloor": int(np.count_nonzero((a.mask != b.mask) & domain)),
            "qualityV5": a.report["foregroundQuality"],
            "qualityV51": b.report["foregroundQuality"],
            "runs": times,
        }
        for name, result in results.items():
            np.save(dest / (name + ".npy"), result.mask)
            overlay = rgb.copy()
            overlay[result.mask] = (rgb[result.mask] * 0.55 + np.array([255, 0, 0]) * 0.45).astype(
                np.uint8
            )
            cv2.imwrite(
                str(dest / (name + "-overlay.png")), cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR)
            )
        rows.append(row)
        print(
            folder.name,
            row["changedVsV5"],
            {k: round(np.median([x["totalMs"] for x in v[1:]]), 1) for k, v in times.items()},
            flush=True,
        )
        (root / "paired.json").write_text(json.dumps(rows, indent=2), encoding="utf8")


if __name__ == "__main__":
    main()
