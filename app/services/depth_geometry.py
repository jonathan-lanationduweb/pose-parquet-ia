"""Offline relative-depth experiment. No model is selected by the product API.

Relative inverse depth has an unknown positive scale and additive shift.
Its floor gradient can constrain horizon roll; its zero cannot identify a
metric horizon, focal length or camera height without another source.
"""
from __future__ import annotations

import copy
import math
from dataclasses import asdict, dataclass
from typing import Any

import cv2
import numpy as np

from app.services.camera_geometry import CameraEstimate, VanishingPointEstimate
from app.services.floor_scene import camera_floor_reference


@dataclass(frozen=True)
class DepthFloorFit:
    coefficients: tuple[float, float, float]
    inlier_ratio: float
    normalized_residual: float
    roll_deg: float
    zero_horizon: float | None
    usable: bool
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def fit_depth_floor(depth: np.ndarray, mask: np.ndarray) -> DepthFloorFit:
    """Robust inverse-depth plane fit, with eroded floor seeds and bounded samples."""
    invalid = DepthFloorFit((0., 0., 0.), 0., 1., 0., None, False, "insufficient_floor")
    if depth.shape != mask.shape or depth.ndim != 2:
        return invalid
    h, w = depth.shape
    seeds = cv2.erode(mask.astype(np.uint8), np.ones((7, 7), np.uint8)).astype(bool)
    yy, xx = np.nonzero(seeds & np.isfinite(depth))
    if len(xx) < 150:
        return invalid
    take = np.linspace(0, len(xx) - 1, min(12000, len(xx)), dtype=int)
    yy, xx = yy[take], xx[take]
    values = depth[yy, xx].astype(np.float64)
    spread = float(np.percentile(values, 95) - np.percentile(values, 5))
    if spread < 1e-6:
        return DepthFloorFit((0., 0., float(values.mean())), 0., 1., 0., None,
                             False, "constant_depth")
    design = np.column_stack((xx / w - .5, yy / h - .5, np.ones(len(xx))))
    weights = np.ones(len(xx))
    coef = np.linalg.lstsq(design, values, rcond=None)[0]
    for _ in range(8):
        residual = values - design @ coef
        sigma = max(spread * .01, 1.4826 * float(np.median(np.abs(residual))))
        weights = np.minimum(1., 1.5 * sigma / np.maximum(np.abs(residual), 1e-9))
        root = np.sqrt(weights)
        coef = np.linalg.lstsq(design * root[:, None], values * root, rcond=None)[0]
    residual = np.abs(values - design @ coef) / spread
    a, b, c = (float(v) for v in coef)
    roll = math.degrees(math.atan2(-a * h / w, b)) if b > 0 else 0.
    ratio = float((residual < .08).mean())
    usable = b > 0 and abs(roll) <= 6 and ratio >= .65
    return DepthFloorFit((a, b, c), ratio, float(np.median(residual)), roll,
                         .5 - c / b if abs(b) > 1e-8 else None, usable,
                         "relative_plane_supported" if usable else "nonplanar_or_inconsistent")


def project_hypothesis(scene: dict[str, Any], horizon: float, roll_deg: float,
                       focal: float, anchor_x: float | None = None) -> dict[str, Any] | None:
    """Project a reference plane with explicit horizon/focal assumptions."""
    w, h = scene["image"]["width"], scene["image"]["height"]
    if not (0.05 < horizon < .8 and math.isfinite(focal) and focal > 0):
        return None
    slope = math.tan(math.radians(roll_deg))
    dy = (horizon - .5) * h
    x = (anchor_x - .5) * w if anchor_x is not None else -focal
    y = dy + slope * x
    denominator = x + slope * y
    if abs(denominator) < 1e-6:
        return None
    other_x = (-focal * focal - dy * y) / denominator
    points = [VanishingPointEstimate(x + w / 2, y + h / 2, 0., 0),
              VanishingPointEstimate(other_x + w / 2,
                                     dy + slope * other_x + h / 2, 0., 0)]
    cam = CameraEstimate(horizon, "experimental-depth", 0., focal, "assumed_or_geometry",
                         points, 0, selected_pair=(0, 1))
    quad = camera_floor_reference(cam, w, h, focal, scene["camera"].get("heightM", 1.5))
    if quad is None:
        return None
    result = copy.deepcopy(scene)
    result["camera"]["horizon"] = horizon
    result["camera"]["vanishingPoints"] = [
        {"x": p.x / w, "y": p.y / h, "weight": 0., "role": role}
        for p, role in zip(points, ("floor-u", "floor-v"), strict=True)
    ]
    for plane in result["planes"].values():
        plane["quad"] = [{"x": x, "y": y} for x, y in quad]
        plane["meters"] = {"width": 4., "depth": 4.}
    return result


def compare_depth_candidates(scene: dict[str, Any], perspective: dict[str, Any],
                             fit: DepthFloorFit) -> dict[str, Any]:
    """Generate and score research alternatives; the current scene is the safe fallback."""
    w, h = scene["image"]["width"], scene["image"]["height"]
    focal = float(perspective.get("focalPx") or .7 * w)
    current_horizon = float(scene["camera"]["horizon"])
    points = scene["camera"].get("vanishingPoints") or []
    current_roll = 0.
    anchor = None
    if len(points) >= 2:
        a, b = points[:2]
        current_roll = math.degrees(math.atan((b["y"] - a["y"]) * h
                                   / ((b["x"] - a["x"]) * w)))
        anchor = a["x"]
    # Preserve the existing material axes, including when no finite VP was
    # measured. Inventing a finite direction here would rotate the parquet.
    quad = next(iter(scene["planes"].values()))["quad"]
    corners = [np.array([p["x"], p["y"], 1.]) for p in quad]
    direction = np.cross(np.cross(corners[0], corners[1]),
                         np.cross(corners[3], corners[2]))
    anchor = (float(direction[0] / direction[2])
              if abs(float(direction[2])) > 1e-8 else 1e6)
    measured = perspective.get("camera", {}).get("horizonSource") == "lines-2vp"
    # Two independently measured directions outrank a monocular relative cue.
    weight = .15 if measured else .5
    fused_roll = current_roll + weight * (fit.roll_deg - current_roll)
    agreement = abs(fit.roll_deg - current_roll)
    depth_only = (project_hypothesis(scene, fit.zero_horizon, fit.roll_deg, .7 * w)
                  if fit.usable and fit.zero_horizon is not None else None)
    fused = (project_hypothesis(scene, current_horizon, fused_roll, focal, anchor)
             if fit.usable and agreement < 4 else None)
    candidate_score = fit.inlier_ratio * (1 - min(1., fit.normalized_residual * 4))
    accepted = fused is not None and not measured and agreement < 2 and candidate_score > .8
    return {"fit": fit.as_dict(), "currentRollDeg": current_roll,
            "rollAgreementDeg": agreement, "depthOnly": depth_only,
            "fused": fused, "selected": "fused" if accepted else "current",
            "candidates": [
                {"id": "current", "score": 1. if measured else .75, "valid": True},
                {"id": "depth-only-zero-assumed", "score": candidate_score * .5,
                 "valid": depth_only is not None,
                 "warning": "relative-depth zero assumed; metric horizon is not identifiable"},
                {"id": "depth-assisted", "score": candidate_score,
                 "valid": fused is not None}],
            "metricDepth": False, "metricScaleMeasured": False}
