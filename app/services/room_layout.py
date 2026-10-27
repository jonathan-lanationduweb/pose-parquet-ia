"""Structural floor support, separate from visible object silhouettes.

The envelope is a render support, never a measured room rectangle. Unknown
non-floor regions remain protected by the boundary matte. No depth inference.
"""

from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np

from app.services.foreground import OBJECT_CLASSES, RUG, interior_openings
from app.services.mask_contours import cell_polygons


@dataclass
class RoomLayout:
    support: np.ndarray
    envelope: np.ndarray
    foreground: np.ndarray
    structural: np.ndarray
    report: dict[str, Any]


def estimate_room_layout(visible: np.ndarray, labels: np.ndarray | None) -> RoomLayout:
    """Recover only semantic foreground inside the observed floor envelope.

    Never extrapolate new visible floor through an unknown wall/recess. The
    camera may use recovered support rather than tracing furniture as walls.
    """
    h, w = visible.shape
    foreground = interior_openings(visible)
    structural = np.zeros_like(visible)
    if labels is not None:
        if labels.shape != visible.shape:
            raise ValueError("Layout labels must match original image dimensions")
        foreground |= np.isin(labels, [*OBJECT_CLASSES, RUG])
        structural = np.isin(labels, [0, 1, 8, 14, 42])
    contours, _ = cv2.findContours(
        visible.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    envelope = np.zeros_like(visible, dtype=np.uint8)
    if contours:
        cv2.fillConvexPoly(envelope, cv2.convexHull(np.concatenate(contours)), 1)
    envelope = envelope.astype(bool)
    support = visible | (foreground & envelope)
    # Structural adjacency is evidence; an object boundary is not a wall.
    adjacency = cv2.dilate(structural.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    edge = visible & ~cv2.erode(visible.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    boundary = edge & adjacency & ~foreground
    yy, xx = np.nonzero(boundary)
    step = max(1, len(xx) // 256)
    polygons = cell_polygons(envelope)
    confidence = (
        min(0.8, float(boundary.sum()) / max(1, int(edge.sum()))) if labels is not None else 0.0
    )
    diagonal = float(np.hypot(w, h))
    lines = cv2.HoughLinesP(
        boundary.astype(np.uint8) * 255,
        1,
        np.pi / 180,
        threshold=max(10, int(diagonal * 0.02)),
        minLineLength=diagonal * 0.06,
        maxLineGap=diagonal * 0.015,
    )
    wall_directions = []
    if lines is not None:
        for x0, y0, x1, y1 in lines.reshape(-1, 4)[:16]:
            wall_directions.append(
                {
                    "start": [float(x0 / w), float(y0 / h)],
                    "end": [float(x1 / w), float(y1 / h)],
                    "angleDeg": float(np.degrees(np.arctan2(y1 - y0, x1 - x0))),
                }
            )
    report = {
        "wallDirections": wall_directions,
        "method": "semantic structural adjacency + observed floor envelope",
        "floorWallBoundary": [
            {"x": float(x / w), "y": float(y / h)}
            for x, y in zip(xx[::step], yy[::step], strict=True)
        ],
        "floorPolygon": ([p.model_dump() for p in polygons[0][0]] if polygons else []),
        "layoutConfidence": round(confidence, 3),
        "supportRecoveredPixels": int(np.count_nonzero(support & ~visible)),
        "scaleMeasured": False,
        "limitations": ["single-image scale is assumed", "unknown recesses remain protected"],
    }
    return RoomLayout(support, envelope, foreground, structural, report)
