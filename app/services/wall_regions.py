"""Selectable wall regions from the existing semantic prediction; no extra inference."""

from __future__ import annotations

from time import perf_counter
from typing import Any

import cv2
import numpy as np

from app.services.floor_segmentation import ADE20K_WALL


def wall_regions(labels: np.ndarray | None, image_rgb: np.ndarray) -> dict[str, Any]:
    start = perf_counter()
    if labels is None:
        return {"status": "unavailable", "zones": [], "method": "no-semantic-labels"}
    height, width = image_rgb.shape[:2]
    scale = min(1.0, 720 / width)
    w, h = round(width * scale), round(height * scale)
    image = cv2.resize(image_rgb, (w, h), interpolation=cv2.INTER_AREA)
    semantic = cv2.resize(
        (labels == ADE20K_WALL).astype(np.uint8), (w, h), interpolation=cv2.INTER_NEAREST
    )
    mask = cv2.erode(semantic, np.ones((3, 3), np.uint8))
    edges = cv2.Canny(cv2.cvtColor(image, cv2.COLOR_RGB2GRAY), 35, 100)
    lines = cv2.HoughLinesP(
        edges, 1, np.pi / 360, threshold=max(25, h // 8), minLineLength=h // 4, maxLineGap=12
    )
    # Room corners can be too subtle for Canny, particularly on matching paint.
    subtle = cv2.createLineSegmentDetector(0, 1.0, 0.6, 0.5, 22.5, 0.0, 0.5, 1024).detect(
        cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    )[0]
    groups = [np.asarray(group).reshape(-1, 4) for group in (lines, subtle) if group is not None]
    lines = np.vstack(groups) if groups else None
    lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB).astype(np.float32)
    cuts: list[tuple[int, int, int, int]] = []
    if lines is not None:
        for x1, y1, x2, y2 in np.asarray(lines).reshape(-1, 4):
            if abs(float(y2 - y1)) < h * 0.22 or abs(float(x1 - x2)) > w * 0.02:
                continue
            lo, hi = sorted((int(y1), int(y2)))
            rows = np.arange(lo, hi + 1)
            xs = np.rint(x1 + (x2 - x1) * (rows - y1) / (y2 - y1)).astype(int)
            valid = (xs > 5) & (xs < w - 6)
            rows, xs = rows[valid], xs[valid]
            if not len(rows):
                continue
            both = (semantic[rows, xs - 4] > 0) & (semantic[rows, xs + 4] > 0)
            if both.mean() < 0.8:
                continue
            contrast = np.linalg.norm(
                lab[rows[both], xs[both] - 4] - lab[rows[both], xs[both] + 4], axis=1
            )
            if float(np.median(contrast)) < 2:
                continue
            cuts.append((int(x1), int(y1), int(x2), int(y2)))
    for x1, y1, x2, y2 in cuts:
        # Continue a verified corner through the wall only. Openings stay excluded.
        dx = (x2 - x1) / (y2 - y1)
        a, b = round(x1 - y1 * dx), round(x1 + (h - y1) * dx)
        cv2.line(mask, (a, 0), (b, h - 1), 0, 2)
    n, components, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    candidates = sorted(range(1, n), key=lambda i: int(stats[i, cv2.CC_STAT_AREA]), reverse=True)
    zones: list[dict[str, Any]] = []
    for component in candidates[:8]:
        area = int(stats[component, cv2.CC_STAT_AREA])
        if area < w * h * 0.008:
            continue
        contour_mask = (components == component).astype(np.uint8)
        contours, hierarchy = cv2.findContours(
            contour_mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE
        )
        if hierarchy is None:
            continue
        for i, contour in enumerate(contours):
            if hierarchy[0, i, 3] != -1 or cv2.contourArea(contour) < w * h * 0.008:
                continue

            def points(c: np.ndarray) -> list[dict[str, float]]:
                approx = cv2.approxPolyDP(c, 0.7, True)[:, 0]
                return [
                    {"x": round(float(x) / w, 6), "y": round(float(y) / h, 6)} for x, y in approx
                ]

            polygon = points(contour)
            if len(polygon) < 3:
                continue
            holes = []
            child = int(hierarchy[0, i, 2])
            while child != -1:
                hole = points(contours[child])
                if len(hole) >= 3:
                    holes.append(hole)
                child = int(hierarchy[0, child, 0])
            zones.append(
                {
                    "id": f"mur-auto-{len(zones) + 1}",
                    "label": f"Mur {len(zones) + 1}",
                    "polygon": polygon,
                    "holes": holes,
                    "detected": True,
                }
            )
    return {
        "status": "proposed" if zones else "no_wall",
        "method": "semantic-wall-with-corner-separation",
        "zones": zones,
        "timingMs": round((perf_counter() - start) * 1000, 1),
    }
