"""Replay actual imported-photo scene compilation using cached semantic labels.

No catalogue geometry/annotations are fed to the compiler. No inference is
claimed here: cold/warm model timings require the separate live API test.
Images and generated artifacts remain in ignored review/ only.
"""

import argparse
import json
import subprocess
import sys
import types
from pathlib import Path
from time import perf_counter

import cv2
import numpy as np

from app.schemas.scene_data import SceneData
from app.services.floor_scene import build_experimental_scene
from app.services.floor_segmentation import clean_mask, semantic_to_floor_visible
from scripts.apply_scene_mask_review import raster


def masked(scene: SceneData | None, shape: tuple[int, int]) -> tuple[np.ndarray, np.ndarray]:
    support = np.zeros(shape, bool)
    blocked = support.copy()
    if scene is not None:
        for z in scene.floor_zones:
            support |= raster(  # type: ignore[no-untyped-call]
                shape, [p.model_dump() for p in z.mask.polygon], []
            )
        for o in scene.occluders:
            blocked |= raster(  # type: ignore[no-untyped-call]
                shape,
                [p.model_dump() for p in o.polygon],
                [[p.model_dump() for p in hole] for hole in o.holes or []],
            )
    return support, blocked


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--output", type=Path, default=Path("review/scene-understanding-v3"))
    args = parser.parse_args()
    cv2.setNumThreads(2)
    root = args.output
    root.mkdir(parents=True, exist_ok=True)
    baseline = types.ModuleType("v3_baseline")
    sys.modules[baseline.__name__] = baseline
    code = subprocess.check_output(
        ["git", "show", "8e03fea:app/services/floor_scene.py"], text=True
    )
    exec(compile(code, "<baseline-floor-scene>", "exec"), baseline.__dict__)
    cases = []
    for directory in sorted(Path("review/semantic-catalogue-review").iterdir()):
        if not (directory / "labels.npy").exists():
            continue
        scene = json.loads((Path("web/data/scenes") / (directory.name + ".json")).read_text("utf8"))
        cases.append(
            (
                directory.name,
                Path("web/assets/images") / scene["image"]["file"],
                directory / "labels.npy",
            )
        )
    for name, folder in [
        ("piece-claire", "piece-claire"),
        ("contraste", "contraste"),
        ("salon", "salon"),
        ("sejour", "sejour"),
        ("owner-photo", "owner"),
    ]:
        cases.append(
            (
                name,
                Path("review/room-understanding-v2") / folder / "original.png",
                Path("review/room-occlusion-v2-2") / name / "labels.npy",
            )
        )
    results = []
    for name, image_path, labels_path in cases:
        if not image_path.exists() or not labels_path.exists():
            raise FileNotFoundError(str(image_path) + " / " + str(labels_path))
        directory = root / name
        directory.mkdir(exist_ok=True)
        start = perf_counter()
        bgr = cv2.imread(str(image_path))
        assert bgr is not None, image_path
        image = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        decode_ms = (perf_counter() - start) * 1000
        labels = np.load(labels_path)
        assert labels.shape == image.shape[:2], name
        h, w = labels.shape
        mask = clean_mask(semantic_to_floor_visible(labels))
        before = vars(baseline)["build_experimental_scene"](
            mask, w, h, labels=labels, image_rgb=image
        )
        samples = []
        final = None
        for _run in range(args.runs):
            start = perf_counter()
            fast = build_experimental_scene(
                mask, w, h, labels=labels, image_rgb=image, quality_pass=False
            )
            first_ms = (perf_counter() - start) * 1000
            final = build_experimental_scene(
                mask, w, h, labels=labels, image_rgb=image, stable_perspective=fast.geometry
            )
            samples.append(
                {
                    "firstSceneMs": first_ms,
                    "finalSceneMs": (perf_counter() - start) * 1000,
                    "fastStages": fast.provenance.get("timingsMs", {}),
                    "qualityStages": final.provenance.get("timingsMs", {}),
                }
            )
        assert final is not None, "At least one run required"
        for revision, result in [("before", before), ("fast", fast), ("quality", final)]:
            if result.scene:
                (directory / (revision + ".json")).write_text(
                    result.scene.model_dump_json(by_alias=True, exclude_none=True), encoding="utf8"
                )
        support, fg = masked(final.scene, labels.shape)
        oldsupport, oldfg = masked(before.scene, labels.shape)
        cv2.imwrite(str(directory / "01-original.png"), cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
        for filename, m in [
            ("02-floor-mask.png", support),
            ("03-foreground-mask.png", fg),
            ("before-visible.png", oldsupport & ~oldfg),
            ("quality-visible.png", support & ~fg),
        ]:
            cv2.imwrite(str(directory / filename), m.astype(np.uint8) * 255)
        layout = image.copy()
        for p in final.provenance.get("roomLayout", {}).get("floorWallBoundary", []):
            cv2.circle(layout, (int(p["x"] * w), int(p["y"] * h)), 2, (0, 255, 140), -1)
        cv2.imwrite(str(directory / "04-room-layout.png"), cv2.cvtColor(layout, cv2.COLOR_RGB2BGR))
        record = {
            "id": name,
            "size": [w, h],
            "decodeMs": decode_ms,
            "runs": samples,
            "modelInference": "not run: cached labels, not an end-to-end latency benchmark",
            "decision": final.provenance.get("sceneQuality", {}),
            "reasons": final.provenance.get("decision", {}).get("reasons", []),
            "refinement": final.provenance.get("foregroundRefinement", {}),
            "changedVisiblePixels": int(np.count_nonzero((support & ~fg) != (oldsupport & ~oldfg))),
            "cameraStable": bool(
                fast.scene
                and final.scene
                and fast.scene.camera == final.scene.camera
                and fast.scene.planes == final.scene.planes
            ),
            "oldCameraChanged": bool(
                before.scene and final.scene and before.scene.camera != final.scene.camera
            ),
            "S1": "NOT_EVALUABLE",
            "S2": "PARTIAL",
            "S3": "NOT_EVALUABLE",
            "S4": "NOT_EVALUABLE",
            "S5": "NOT_EVALUABLE",
            "S6": "NOT_EVALUABLE",
            "S7": "NOT_EVALUABLE",
            "S8": "NOT_EVALUABLE",
        }
        record["benchmark"] = (
            {
                k: {
                    "firstProcessRun": samples[0][k],
                    "warmMedian": float(np.median([r[k] for r in samples[1:]])),
                    "warmP95": float(np.percentile([r[k] for r in samples[1:]], 95)),
                    "max": max(r[k] for r in samples),
                }
                for k in ["firstSceneMs", "finalSceneMs"]
            }
            if len(samples) > 1
            else {}
        )
        (directory / "report.json").write_text(json.dumps(record, indent=2), encoding="utf8")
        results.append(record)
        (root / "matrix.json").write_text(json.dumps(results, indent=2), encoding="utf8")
        print(
            json.dumps(
                {
                    k: record[k]
                    for k in ["id", "changedVisiblePixels", "cameraStable", "decision", "benchmark"]
                }
            ),
            flush=True,
        )


if __name__ == "__main__":
    main()
