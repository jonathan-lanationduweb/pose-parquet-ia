"""Private, offline current/depth/fusion experiment. No model download during inference.

Run as a module from the repository root. Outputs must remain under ignored review/.
The default uses stored real model masks where available, rebuilding geometry on
original pixels. Missing masks are obtained from the local API, never a cloud API.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageOps

from app.services.depth_geometry import compare_depth_candidates, fit_depth_floor
from app.services.floor_scene import build_experimental_scene


def peak_memory_mb() -> float | None:
    """Measure the process peak with the platform API, without another dependency."""
    if os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes

    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in
            ("peak", "working", "peakPaged", "paged", "peakNonPaged", "nonPaged",
             "pagefile", "peakPagefile")]
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    call = ctypes.windll.psapi.GetProcessMemoryInfo
    call.argtypes = [ctypes.c_void_p, ctypes.POINTER(Counters), wintypes.DWORD]
    if not call(ctypes.c_void_p(-1), ctypes.byref(counters), counters.cb):
        return None
    return float(counters.peak) / 1024 ** 2


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner-photo", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("review/room-understanding-v2"))
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    out = args.output.resolve()
    if not out.is_relative_to(Path("review").resolve()):
        raise ValueError("Private experiment outputs must stay under ignored review/")
    out.mkdir(parents=True, exist_ok=True)
    os.environ["HF_HUB_OFFLINE"] = "1"
    import openvino as ov
    import torch
    from transformers import AutoImageProcessor, AutoModelForDepthEstimation

    torch.set_num_threads(4)
    cv2.setNumThreads(1)
    model_dir = Path("models/depth-anything-v2-small")
    loaded = time.perf_counter()
    processor_factory: Any = AutoImageProcessor
    processor = processor_factory.from_pretrained(model_dir, local_files_only=True)
    torch_model = AutoModelForDepthEstimation.from_pretrained(
        model_dir, local_files_only=True).eval()
    load_ms = (time.perf_counter() - loaded) * 1000
    core = ov.Core()
    compiled = core.compile_model(str(model_dir / "openvino-392.xml"), "GPU",
                                 {"PERFORMANCE_HINT": "LATENCY",
                                  "INFERENCE_PRECISION_HINT": "f16",
                                  "CACHE_DIR": "models/openvino-cache"})
    def tensor(image: Image.Image) -> Any:
        return processor(images=image, return_tensors="pt",
                         size={"height": 392, "width": 392},
                         keep_aspect_ratio=False)["pixel_values"]

    warm = tensor(Image.fromarray(np.full((392, 392, 3), 128, np.uint8)))
    for _ in range(2):
        compiled([warm.numpy()])
    rows: list[dict[str, Any]] = []
    cases = [("owner", args.owner_photo)] + [
        (p.stem, p) for p in sorted(Path("datasets/private-real").glob("*.jpg"))]
    for name, file in cases:
        case = out / name
        case.mkdir(exist_ok=True)
        with Image.open(file) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
        rgb = np.array(image)
        image.save(case / "original.jpg", quality=95)
        image.save(case / "original.png")
        cached = Path(f"review/roomvo-core/verified/{name}-response-private.json")
        if cached.exists():
            response = json.loads(cached.read_text(encoding="utf-8"))
            source_kind = "stored-real-model-prediction; geometry rebuilt in this run"
        else:
            import httpx
            with httpx.Client(timeout=240) as client:
                r = client.post(args.base + "/v1/analyze-room",
                                headers={"X-Analysis-Profile": "visualizer"},
                                files={"image": ("room.jpg", file.read_bytes(), "image/jpeg")})
                r.raise_for_status()
                response = r.json()
            source_kind = "local-api-real-model-prediction"
        floor = response.get("experimental", {}).get("floor")
        if not floor:
            rows.append({"id": name, "decision": "manual-required", "reason": "no_floor"})
            continue
        decoded_mask = cv2.imdecode(np.frombuffer(base64.b64decode(floor["maskPngBase64"]),
                                                 np.uint8), cv2.IMREAD_GRAYSCALE)
        if decoded_mask is None:
            raise ValueError("Stored floor mask is not decodable")
        raw = decoded_mask > 127
        if raw.shape != rgb.shape[:2]:
            raise ValueError("Stored prediction dimensions do not match the current photo")
        t = time.perf_counter()
        scene = build_experimental_scene(raw, rgb.shape[1], rgb.shape[0], image_rgb=rgb,
                                        floor_confidence=floor.get("sceneProvenance", {})
                                        .get("decision", {}).get("quality", {})
                                        .get("floorConfidence"))
        geometry_ms = (time.perf_counter() - t) * 1000
        cv2.imwrite(str(case / "floor-mask.png"), raw.astype(np.uint8) * 255)
        if scene.scene is None:
            rows.append({"id": name, "decision": "manual-required", "reason": scene.status})
            continue
        current = scene.scene.model_dump(by_alias=True, exclude_none=True)
        inputs = tensor(image)
        t = time.perf_counter()
        with torch.inference_mode():
            cpu_depth = torch_model(pixel_values=inputs).predicted_depth.numpy()
        cpu_ms = (time.perf_counter() - t) * 1000
        times, prediction = [], None
        for _ in range(3):
            t = time.perf_counter()
            prediction = compiled([inputs.numpy()])[compiled.output(0)]
            times.append((time.perf_counter() - t) * 1000)
        prediction = np.asarray(prediction).squeeze()
        agreement = float(np.abs(prediction - cpu_depth.squeeze()).mean()
                          / max(1e-6, float(np.abs(cpu_depth).mean())))
        depth = cv2.resize(prediction, (rgb.shape[1], rgb.shape[0]),
                           interpolation=cv2.INTER_CUBIC)
        np.save(case / "depth-relative.npy", depth)
        lo, hi = np.percentile(depth, [2, 98])
        preview = np.clip((depth - lo) / max(1e-6, hi - lo) * 255, 0, 255).astype(np.uint8)
        cv2.imwrite(str(case / "depth.jpg"), cv2.applyColorMap(preview, cv2.COLORMAP_TURBO))
        fit = fit_depth_floor(depth, raw)
        alternatives = compare_depth_candidates(current, scene.perspective, fit)
        for label, data in [("current", current), ("depth-only", alternatives["depthOnly"]),
                            ("depth-assisted", alternatives["fused"])]:
            if data is not None:
                (case / f"scene-{label}.json").write_text(json.dumps(data), encoding="utf-8")
        details = {k: v for k, v in alternatives.items() if k not in {"fused", "depthOnly"}}
        row = {"id": name, "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
               "segmentationSource": source_kind, "model": "Depth-Anything-V2-Small-hf",
               "shape": list(inputs.shape), "cpuMs": cpu_ms,
               "gpuMedianMs": float(np.median(times)), "gpuRunsMs": times,
               "gpuRelativeMeanErrorAgainstCpu": agreement,
               "geometryCurrentMs": geometry_ms, "currentDecision": scene.status,
               "currentQuality": scene.provenance["decision"]["quality"],
               "currentPerspective": scene.perspective,
               "floorCoverage": float(raw.mean()),
               "originalAnalysisMs": response["timings"]["total_ms"],
               "category": "hard" if scene.status != "auto_render" else "medium",
               "comparison": details,
               "peakRssMb": peak_memory_mb()}
        rows.append(row)
        (case / "measurement.json").write_text(json.dumps(row, indent=2), encoding="utf-8")
        (out / "matrix.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
        print(json.dumps({"id": name, "cpuMs": round(cpu_ms),
                          "gpuMs": round(row["gpuMedianMs"]), "fit": fit.as_dict(),
                          "choice": alternatives["selected"]}), flush=True)
    (out / "run.json").write_text(json.dumps({"loadMs": load_ms, "photos": len(rows),
        "parameters": sum(p.numel() for p in torch_model.parameters()),
        "modelBytes": sum(p.stat().st_size for p in model_dir.glob("*.safetensors")),
        "inputShape": [1, 3, 392, 392], "devices": core.available_devices,
        "productionIntegration": False}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
