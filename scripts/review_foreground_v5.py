"""Private original-resolution V5 comparison; no camera/light/material recalculation."""

import argparse
import json
from pathlib import Path
from time import perf_counter

import cv2
import numpy as np

from app.services.floor_scene import refine_mask
from app.services.floor_segmentation import clean_mask, semantic_to_floor_visible
from app.services.foreground import RUG, build_foreground, polygons
from app.services.foreground_understanding import understand_foreground
from app.services.photo_mask_refiner import refine_photo_mask
from app.services.room_layout import estimate_room_layout


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=5)
    args = parser.parse_args()
    cv2.setNumThreads(2)
    root = Path("review/foreground-mask-v5")
    rows = []
    for dest in sorted(root.iterdir()):
        if not dest.is_dir() or not (dest / "labels.npy").exists():
            continue
        image = cv2.imread(str(dest / "01-original.png"))
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        labels = np.load(dest / "labels.npy")
        physical_floor = np.load(dest / "floor.npy")
        visible_floor = refine_mask(clean_mask(semantic_to_floor_visible(labels)), image_rgb=rgb)
        layout = estimate_room_layout(visible_floor, labels)
        physical_floor = layout.envelope
        np.save(dest / "floor.npy", physical_floor)
        cv2.imwrite(str(dest / "floor-mask.png"), physical_floor.astype(np.uint8) * 255)
        domain = layout.support
        np.save(dest / "support.npy", domain)
        # Replay V4's source masks directly, never rasterize normalized pixel
        # cells through the legacy authoring helper's (width-1) convention.
        baseline_foreground = build_foreground(labels, visible_floor, None, serialize=False)
        baseline_visible = refine_photo_mask(rgb, domain, baseline_foreground.refined).visible_floor
        before = ~baseline_visible
        np.save(dest / "before.npy", before)
        cv2.imwrite(str(dest / "02-mask-before.png"), before.astype(np.uint8) * 255)
        prior = baseline_foreground.refined.copy()
        prior[domain] = before[domain]
        overlay_before = image.copy()
        overlay_before[prior] = (image[prior] * 0.55 + np.array([0, 0, 255]) * 0.45).astype(
            np.uint8
        )
        cv2.imwrite(str(dest / "02-overlay-before.png"), overlay_before)
        assert domain.shape == physical_floor.shape
        runs = []
        result = None
        for _ in range(args.runs):
            start = perf_counter()
            result = understand_foreground(rgb, domain, prior)
            runs.append({"totalMs": (perf_counter() - start) * 1000, **result.report["timingsMs"]})
        assert result is not None
        after = before.copy()
        after[domain] = result.mask[domain]
        np.save(dest / "after.npy", after)
        cv2.imwrite(str(dest / "03-mask-after.png"), after.astype(np.uint8) * 255)
        overlay = image.copy()
        overlay[result.mask] = (image[result.mask] * 0.55 + np.array([0, 0, 255]) * 0.45).astype(
            np.uint8
        )
        cv2.imwrite(str(dest / "03-overlay-after.png"), overlay)
        raw = json.loads((dest / "before.json").read_text(encoding="utf8"))
        encode_start = perf_counter()
        # Keep structural matte outside floor exactly unchanged. Only replace
        # foreground inside the physical floor domain; V4 lighting is untouched.
        scene_objects = polygons(before & ~domain, kind="fixture", prefix="structural")
        rug = result.mask & (labels == RUG)
        scene_objects += polygons(rug, kind="rug", prefix="rug")
        scene_objects += polygons(result.mask & ~rug, kind="furniture", prefix="foreground")
        raw["occluders"] = [o.model_dump(by_alias=True) for o in scene_objects]
        encoded = json.dumps(raw)
        encode_ms = (perf_counter() - encode_start) * 1000
        (dest / "after.json").write_text(encoded, encoding="utf8")
        row = {
            "scene": dest.name,
            "sourceSize": list(image.shape[:2][::-1]),
            "maskEncodeMs": encode_ms,
            "jsonBytes": len(encoded),
            **result.report,
            "runs": runs,
        }
        (dest / "refinement.json").write_text(json.dumps(row, indent=2), encoding="utf8")
        rows.append(row)
        print(
            dest.name,
            result.report["addedPixels"],
            result.report["removedPixels"],
            "thin recovered",
            result.report["thinRecoveredPixels"],
        )
    (root / "matrix.json").write_text(json.dumps(rows, indent=2), encoding="utf8")


if __name__ == "__main__":
    main()
