"""Private occlusion replay: uses cached outputs from the existing local model."""

from __future__ import annotations

import json
import time
from pathlib import Path

import cv2
import numpy as np

from app.services.floor_scene import build_experimental_scene, mask_zones, refine_mask
from app.services.foreground import build_foreground


def main() -> None:
    cv2.setNumThreads(1)
    root = Path("review/room-occlusion-v2-2")
    rows = []
    for folder in sorted(root.iterdir()):
        if not (folder / "labels.npy").exists():
            continue
        baseline = json.loads((folder / "baseline.json").read_text(encoding="utf-8"))
        original = Path("review/room-understanding-v2") / baseline["id"] / "original.png"
        image = cv2.imread(str(original))
        if image is None:
            raise ValueError(original)
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        labels = np.load(folder / "labels.npy")
        floor = np.load(folder / "floor.npy")
        support = refine_mask(floor, image_rgb=rgb)
        openings = [hole for _, holes in mask_zones(support) for hole in holes]
        begin = time.perf_counter()
        fg = build_foreground(labels, support, rgb, opening_polygons=openings)
        total = (time.perf_counter() - begin) * 1000
        cv2.imwrite(str(folder / "03-occluder-mask.png"), fg.refined.astype(np.uint8) * 255)
        cv2.imwrite(str(folder / "03-coarse-occluder-mask.png"), fg.coarse.astype(np.uint8) * 255)
        scene = build_experimental_scene(
            floor, rgb.shape[1], rgb.shape[0], labels=labels, image_rgb=rgb
        )
        if scene.scene:
            after = scene.scene.model_dump(by_alias=True, exclude_none=True)
            before = json.loads((folder / "scene-before.json").read_text(encoding="utf-8"))
            assert before["planes"] == after["planes"], f"Plane changed: {folder}"
            assert before["camera"] == after["camera"], f"Camera changed: {folder}"
            (folder / "scene-after.json").write_text(json.dumps(after), encoding="utf-8")
        row = {
            "id": folder.name,
            "sourceId": baseline["id"],
            "status": scene.status,
            "manualRequired": scene.status in {"no_floor", "needs_manual_adjustment"},
            "planeUnchanged": True,
            "timingsMs": fg.timings_ms,
            "occlusionTotalMs": total,
            "objectCount": len(fg.objects),
            "rugPixels": int((labels == 28).sum()),
            "radiatorPixels": int((labels == 146).sum()),
            "foregroundPixels": int(fg.refined.sum()),
            "sceneTimingsMs": scene.provenance.get("timingsMs", {}),
            "note": ("Semantic proposal, not ground-truth accuracy. "
                     "Openings protect unknown objects; missed objects need manual correction."),
        }
        rows.append(row)
        (folder / "measurement.json").write_text(json.dumps(row, indent=2), encoding="utf-8")
        (root / "matrix.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
        print(json.dumps(row), flush=True)


if __name__ == "__main__":
    main()
