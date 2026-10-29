"""Bounded offline local-observation experiment. No GT, scene ID or object ID input."""

from __future__ import annotations

import os
from time import perf_counter
from typing import Any

import cv2
import numpy as np

from app.services.foreground import OBJECT_CLASSES, RUG
from app.services.foreground_understanding import understand_foreground


def automatic_rois(
    rgb: np.ndarray, domain: np.ndarray, foreground: np.ndarray, limit: int = 3
) -> list[tuple[int, int, int, int]]:
    """Rank vertical image structure near floor/foreground, never human GT."""
    if rgb.shape[:2] != domain.shape or foreground.shape != domain.shape:
        raise ValueError("ROI inputs must share source coordinates")
    if not domain.any():
        return []
    h, w = domain.shape
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)
    gx = np.abs(cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3))
    gy = np.abs(cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3))
    boundary = cv2.morphologyEx(
        (domain | foreground).astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)
    )
    contact = cv2.dilate(boundary, np.ones((max(3, h // 12), max(3, w // 24)), np.uint8)) > 0
    useful = cv2.dilate(domain.astype(np.uint8), np.ones((max(3, h // 8), 3), np.uint8)) > 0
    score = gx * (gx > gy * 1.5) * useful * (1 + contact * 2)
    if float(score.max()) < 24:
        return []
    cw, ch = min(w, max(192, w // 3)), min(h, max(256, h // 2))
    rois = []
    for _ in range(limit):
        y, x = np.unravel_index(np.argmax(score), score.shape)
        if score[y, x] < 24:
            break
        x0 = max(0, min(w - cw, int(x) - cw // 2))
        y0 = max(0, min(h - ch, int(y) - ch * 2 // 3))
        rois.append((x0, y0, x0 + cw, y0 + ch))
        score[
            max(0, y - ch // 2) : min(h, y + ch // 2), max(0, x - cw // 2) : min(w, x + cw // 2)
        ] = 0
    return rois


def proposal_consensus(
    observations: list[np.ndarray], domain: np.ndarray, coarse: np.ndarray
) -> tuple[np.ndarray, dict[str, Any]]:
    """Class agreement and small connected proposals; never a blind crop union."""
    accepted = np.zeros_like(domain, dtype=bool)
    if len(observations) < 2:
        return accepted, {"reason": "two_observations_required", "acceptedPixels": 0}
    first, second = observations[:2]
    if first.shape != domain.shape or second.shape != domain.shape:
        raise ValueError("Local observations must map back to source pixels")
    candidates = (first == second) & np.isin(first, [*OBJECT_CLASSES, RUG]) & domain & ~coarse
    count, components, stats, _ = cv2.connectedComponentsWithStats(
        candidates.astype(np.uint8), connectivity=8
    )
    maximum = max(16, int(domain.sum() * 0.01))
    rejected = 0
    for i in range(1, count):
        x, y, cw, ch, area = stats[i]
        if area < 2 or area > maximum or cw * ch > domain.size * 0.08:
            rejected += 1
            continue
        # A crop's huge rug/furniture hallucination cannot pass the size budget.
        accepted |= components == i
    return accepted, {
        "method": "two-crop exact class agreement / domain / component budget",
        "acceptedPixels": int(accepted.sum()),
        "rejectedComponents": rejected,
        "maximumComponentPixels": maximum,
        "confidenceCalibrated": False,
    }


def run_local(
    rgb: np.ndarray,
    domain: np.ndarray,
    coarse: np.ndarray,
    prior: np.ndarray,
    baseline: np.ndarray,
    engine: Any = None,
) -> dict[str, Any]:
    started = perf_counter()
    rois = automatic_rois(rgb, domain, coarse)
    roi_ms = (perf_counter() - started) * 1000
    h, w = domain.shape
    additions = np.zeros_like(domain, dtype=bool)
    raw_foreground = np.zeros_like(domain, dtype=bool)
    calls = []
    gates = []
    if rois and engine is None:
        # Existing cached model only. No network fallback or new checkpoint.
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ["PPAI_INFERENCE_BACKEND"] = "openvino"
        from app.services.floor_semantic import OneFormerFloor

        engine = OneFormerFloor()
    for x0, y0, x1, y1 in rois:
        observations = []
        for delta in [-1, 1]:
            dx = delta * max(2, (x1 - x0) // 20)
            dy = delta * max(2, (y1 - y0) // 20)
            ax = max(0, min(w - (x1 - x0), x0 + dx))
            ay = max(0, min(h - (y1 - y0), y0 + dy))
            bx, by = ax + x1 - x0, ay + y1 - y0
            t = perf_counter()
            result = engine.segment(rgb[ay:by, ax:bx])
            labels = result.labels
            if labels is None or labels.shape != (by - ay, bx - ax):
                raise ValueError("Local semantic labels unavailable or incorrectly sized")
            mapped = np.full(domain.shape, -1, np.int32)
            margin = max(2, (bx - ax) // 32)
            mapped[ay + margin : by - margin, ax + margin : bx - margin] = labels[
                margin:-margin, margin:-margin
            ]
            observations.append(mapped)
            raw_foreground |= np.isin(mapped, [*OBJECT_CLASSES, RUG]) & domain
            calls.append(
                {
                    "box": [ax, ay, bx, by],
                    "totalMs": (perf_counter() - t) * 1000,
                    "timingsMs": result.timings,
                    "metadata": result.metadata,
                }
            )
        t = perf_counter()
        addition, gate = proposal_consensus(observations, domain, coarse)
        gate["ms"] = (perf_counter() - t) * 1000
        gates.append(gate)
        additions |= addition
    t = perf_counter()
    merged = prior | additions
    fusion_ms = (perf_counter() - t) * 1000
    t = perf_counter()
    if additions.any():
        refined = understand_foreground(rgb, domain, merged)
        neighbourhood = cv2.dilate(additions.astype(np.uint8), np.ones((37, 37), np.uint8)) > 0
        final = baseline | (refined.mask & neighbourhood & domain)
    else:
        final = baseline.copy()
    refinement_ms = (perf_counter() - t) * 1000
    return {
        "candidateMask": final,
        "rawForeground": raw_foreground,
        "additions": additions,
        "mergedSeeds": coarse | additions,
        "timingsMs": {
            "roiGeneration": roi_ms,
            "fusion": fusion_ms,
            "v5Refinement": refinement_ms,
            "total": (perf_counter() - started) * 1000,
        },
        "calls": calls,
        "gates": gates,
        "rois": [list(box) for box in rois],
        "productionIntegrated": False,
        "gtUsedForRoi": False,
    }
