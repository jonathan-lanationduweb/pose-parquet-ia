"""Second local candidate: official MiDaS v2.1 Small OpenVINO export."""
from __future__ import annotations

import json
import math
import shutil
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.services.depth_geometry import compare_depth_candidates, fit_depth_floor
from scripts.benchmark_room_depth import peak_memory_mb


def main() -> None:
    import openvino as ov

    cv2.setNumThreads(1)
    root = Path("review/room-understanding-v2")
    out = root / "midas"
    out.mkdir(exist_ok=True)
    source = json.loads((root / "matrix.json").read_text(encoding="utf-8"))
    core = ov.Core()
    started = time.perf_counter()
    model = core.read_model("models/midas-small/model.xml")
    engines = {}
    for device in ("CPU", "GPU"):
        options: dict[str, Any] = {"PERFORMANCE_HINT": "LATENCY",
            "CACHE_DIR": "models/openvino-cache",
            "INFERENCE_PRECISION_HINT": "f32" if device == "CPU" else "f16"}
        if device == "CPU":
            options["INFERENCE_NUM_THREADS"] = 4
        engines[device] = core.compile_model(model, device, options)
    setup_ms = (time.perf_counter() - started) * 1000
    dummy = np.zeros((1, 3, 256, 256), np.float32)
    for engine in engines.values():
        for _ in range(2):
            engine([dummy])
    rows = []
    for row in source:
        name = row["id"]
        original = root / name
        scene_file = original / "scene-current.json"
        if not scene_file.exists():
            continue
        case = out / name
        case.mkdir(exist_ok=True)
        for file in ("original.jpg", "floor-mask.png", "scene-current.json"):
            shutil.copy2(original / file, case / file)
        image_bgr = cv2.imread(str(original / "original.png"))
        if image_bgr is None:
            raise ValueError("Private source image is not decodable")
        image = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        h, w = image.shape[:2]
        small = cv2.resize(image.astype(np.float32) / 255, (256, 256),
                           interpolation=cv2.INTER_CUBIC)
        normalized = (small - [.485, .456, .406]) / [.229, .224, .225]
        inputs = np.ascontiguousarray(normalized.transpose(2, 0, 1)[None], np.float32)
        measurements, values = {}, {}
        for device, engine in engines.items():
            times = []
            for _ in range(3):
                start = time.perf_counter()
                prediction = engine([inputs])[engine.output(0)]
                times.append((time.perf_counter() - start) * 1000)
            measurements[device] = float(np.median(times))
            values[device] = prediction.squeeze().copy()
        depth = cv2.resize(values["GPU"], (w, h), interpolation=cv2.INTER_CUBIC)
        np.save(case / "depth-relative.npy", depth)
        lo, hi = np.percentile(depth, [2, 98])
        preview = np.clip((depth - lo) / max(1e-6, hi - lo) * 255, 0, 255).astype(np.uint8)
        cv2.imwrite(str(case / "depth.jpg"), cv2.applyColorMap(preview, cv2.COLORMAP_TURBO))
        decoded_mask = cv2.imread(str(case / "floor-mask.png"), 0)
        if decoded_mask is None:
            raise ValueError("Private floor mask is not decodable")
        mask = decoded_mask > 127
        scene = json.loads(scene_file.read_text(encoding="utf-8"))
        # Current camera evidence is kept identical between the two model experiments.
        previous = json.loads((original / "measurement.json").read_text(encoding="utf-8"))
        cached = Path(f"review/roomvo-core/verified/{name}-response-private.json")
        if cached.exists():
            cached_analysis = json.loads(cached.read_text(encoding="utf-8"))
            perspective = cached_analysis["experimental"]["floor"]["perspective"]
        else:
            perspective = previous.get("currentPerspective") or {
                "focalPx": w / (2 * math.tan(math.radians(scene["camera"]["fovDeg"]) / 2)),
                "camera": {"horizonSource": "lines-2vp" if
                    previous["comparison"]["candidates"][0]["score"] == 1. else "lines-1vp"}}

        fit = fit_depth_floor(depth, mask)
        comparison = compare_depth_candidates(scene, perspective, fit)
        for label, data in (("depth-only", comparison["depthOnly"]),
                            ("depth-assisted", comparison["fused"])):
            if data is not None:
                (case / f"scene-{label}.json").write_text(json.dumps(data), encoding="utf-8")
        result = {"id": name, "model": "MiDaS-v2.1-Small-official-OpenVINO",
                  "cpuMs": measurements["CPU"], "gpuMedianMs": measurements["GPU"],
                  "inputShape": [1, 3, 256, 256],
                  "gpuRelativeMeanErrorAgainstCpu": float(
                      np.abs(values["GPU"] - values["CPU"]).mean()
                      / max(1e-6, float(np.abs(values["CPU"]).mean()))),
                  "comparison": {k: v for k, v in comparison.items()
                                 if k not in {"fused", "depthOnly"}},
                  "category": previous["category"], "peakRssMb": peak_memory_mb()}
        rows.append(result)
        (case / "measurement.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        (out / "matrix.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
        print(json.dumps({"id": name, "cpuMs": round(measurements["CPU"]),
                          "gpuMs": round(measurements["GPU"]), "fit": fit.as_dict()}), flush=True)
    (out / "run.json").write_text(json.dumps({"setupMs": setup_ms,
        "modelBytes": Path("models/midas-small/model.bin").stat().st_size,
        "shape": [1, 3, 256, 256], "productionIntegration": False}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
