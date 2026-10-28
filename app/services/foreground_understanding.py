"""V5 bounded original-resolution foreground refinement, independent of geometry/light."""

from dataclasses import dataclass
from time import perf_counter
from typing import Any

import cv2
import numpy as np


@dataclass
class ForegroundUnderstanding:
    mask: np.ndarray
    thin: np.ndarray
    report: dict[str, Any]


def _nearest_colors(seeds: np.ndarray, image: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    distance, labels = cv2.distanceTransformWithLabels(
        (~seeds).astype(np.uint8), cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL
    )
    colors = np.zeros((int(labels.max()) + 1, 3), np.float32)
    colors[labels[seeds]] = image[seeds]
    return colors[labels], distance


def understand_foreground(
    image_rgb: np.ndarray,
    floor_domain: np.ndarray,
    coarse: np.ndarray,
) -> ForegroundUnderstanding:
    """Only reclassify a bounded edge band with decisive local colour evidence.

    No opening/closing, global blur, area-only filtering or floor-plane input.
    Existing narrow ridges are immutable; ambiguous pixels retain their prior.
    """
    started = perf_counter()
    if (
        image_rgb.ndim != 3
        or image_rgb.shape[2] != 3
        or image_rgb.shape[:2] != floor_domain.shape
        or coarse.shape != floor_domain.shape
    ):
        raise ValueError("Foreground inputs must share source image dimensions")
    if image_rgb.dtype != np.uint8 or not np.isfinite(image_rgb).all():
        raise ValueError("Foreground requires finite original uint8 RGB pixels")
    if not np.isfinite(coarse).all() or not np.isfinite(floor_domain).all():
        raise ValueError("Foreground masks must be finite")
    prior = coarse.astype(bool)
    domain = floor_domain.astype(bool)
    output = prior.copy()
    radius = int(np.clip(round(max(prior.shape) / 90), 6, 18))
    inside = cv2.distanceTransform(prior.astype(np.uint8), cv2.DIST_L2, 5)
    outside = cv2.distanceTransform((~prior).astype(np.uint8), cv2.DIST_L2, 5)
    ridge = (
        (inside > 0)
        & (inside <= max(3.1, min(5.5, max(prior.shape) / 220)))
        & (inside >= cv2.dilate(inside, np.ones((3, 3), np.uint8)) - 0.01)
    )
    thin_ms = (perf_counter() - started) * 1000
    t = perf_counter()
    foreground_seeds = (inside > radius) | ridge
    background_seeds = domain & (outside > radius)
    verified_fraction = 0.0
    if foreground_seeds.any() and background_seeds.any():
        # Lab separates illumination and chroma; no colour is written to the photo.
        guide = cv2.cvtColor(cv2.bilateralFilter(image_rgb, 5, 20, 2), cv2.COLOR_RGB2LAB).astype(
            np.float32
        )
        foreground, fd = _nearest_colors(foreground_seeds, guide)
        background, bd = _nearest_colors(background_seeds, guide)
        band = domain & (inside + outside <= radius)
        yy, xx = np.nonzero(band)
        pixels = guide[yy, xx]

        # A single spatial nearest seed may be a different part of the same
        # multicolour object (green stem beside a grey pot). Compare nearby
        # seed regions too, within the same bounded source-image neighbourhood.
        def best_seed(colors: np.ndarray, distances: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
            best = np.full(len(xx), np.inf, np.float32)
            chosen = np.zeros((len(xx), 3), np.float32)
            for dy in [-radius, 0, radius]:
                for dx in [-radius, 0, radius]:
                    sy = (yy + dy).clip(0, prior.shape[0] - 1)
                    sx = (xx + dx).clip(0, prior.shape[1] - 1)
                    candidate = colors[sy, sx]
                    error = np.sum((pixels - candidate) ** 2, axis=1)
                    error[distances[sy, sx] + np.hypot(dx, dy) > radius * 3] = np.inf
                    take = error < best
                    chosen[take] = candidate[take]
                    best[take] = error[take]
            return chosen, best

        fg_color, df = best_seed(foreground, fd)
        bg_color, db = best_seed(background, bd)
        separation = np.sum((fg_color - bg_color) ** 2, axis=1)
        clear = (separation > 400) & np.isfinite(df) & np.isfinite(db)
        verified_fraction = float(clear.mean()) if len(clear) else 0.0
        add = np.zeros(prior.shape, bool)
        remove = add.copy()
        add[yy, xx] = ~prior[yy, xx] & clear & (df < db * 0.35) & (fd[yy, xx] <= radius * 3)
        remove[yy, xx] = (
            prior[yy, xx] & ~ridge[yy, xx] & clear & (db < df * 0.35) & (bd[yy, xx] <= radius * 3)
        )
        # Local evidence consensus suppresses texture specks. It only gates
        # proposed changes, never erodes the logical prior or its thin ridges.
        add &= cv2.boxFilter(add.astype(np.float32), -1, (3, 3)) > 0.55
        remove &= cv2.boxFilter(remove.astype(np.float32), -1, (3, 3)) > 0.55
        output[add] = True
        output[remove] = False
    # Changed islands need a topological anchor, never an area-only filter.
    # Prevent floor grain specks and isolated holes in upholstery/rugs.
    for changed, anchor, value in [
        (output & ~prior, prior, True),
        (prior & ~output, ~prior, False),
    ]:
        if not changed.any():
            continue
        count, components = cv2.connectedComponents(
            (changed | anchor).astype(np.uint8), connectivity=8
        )
        anchored = np.zeros(count, bool)
        anchored[np.unique(components[anchor])] = True
        unanchored = changed & ~anchored[components]
        output[unanchored] = not value
    output[ridge] = True
    edge_ms = (perf_counter() - t) * 1000
    t = perf_counter()
    bridges = _thin_bridges(image_rgb, domain, prior, ridge, radius)
    output |= bridges
    bridge_ms = (perf_counter() - t) * 1000
    report = {
        "method": "V5 local Lab seeds / bounded original-photo edge evidence",
        "sourceSize": list(prior.shape[::-1]),
        "radiusPx": radius,
        "thinSeedPixels": int(ridge.sum()),
        "changedPixels": int((prior != output).sum()),
        "thinRecoveredPixels": int((bridges & ~prior).sum()),
        "addedPixels": int((output & ~prior).sum()),
        "removedPixels": int((prior & ~output).sum()),
        "confidenceCalibrated": False,
        "foregroundQuality": round(0.4 + 0.35 * verified_fraction, 3)
        if (prior & domain).any()
        else None,
        "qualityMeaning": "bounded local colour evidence; not IoU or calibrated object recall",
        "criticalObjectUncertain": bool((prior & domain).any()),
        "timingsMs": {
            "thinPreservation": round(thin_ms, 3),
            "edgeRefinement": round(edge_ms, 3),
            "thinRecovery": round(bridge_ms, 3),
        },
    }
    return ForegroundUnderstanding(output, ridge, report)


def _thin_bridges(
    image: np.ndarray, domain: np.ndarray, prior: np.ndarray, ridge: np.ndarray, radius: int
) -> np.ndarray:
    """Recover short photo-supported line gaps attached to an existing thin seed.

    Both ends must meet the existing object proposal and one an existing thin
    branch. This cannot invent a fully missing cable/object without evidence.
    """
    recovered = np.zeros(prior.shape, np.uint8)
    if not ridge.any() or not domain.any():
        return recovered.astype(bool)
    h, w = prior.shape
    ys = np.nonzero(domain.any(axis=1))[0]
    y0 = max(0, int(ys[0]) - radius * 3)
    gray = cv2.cvtColor(image[y0:], cv2.COLOR_RGB2GRAY)
    detected = cv2.createLineSegmentDetector().detect(gray)
    if detected[0] is None:
        return recovered.astype(bool)
    distance = cv2.distanceTransform((~prior).astype(np.uint8), cv2.DIST_L2, 5)
    thin_distance = cv2.distanceTransform((~ridge).astype(np.uint8), cv2.DIST_L2, 5)
    lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB).astype(np.float32)
    widths = detected[1].reshape(-1)
    for segment, width in zip(detected[0].reshape(-1, 4), widths, strict=True):
        x1, sy1, x2, sy2 = segment
        y1, y2 = sy1 + y0, sy2 + y0
        length = float(np.hypot(x2 - x1, y2 - y1))
        if width > 5 or length < 6 or length > radius * 8:
            continue
        samples = max(8, int(length))
        xx = np.rint(np.linspace(x1, x2, samples)).astype(int).clip(0, w - 1)
        yy = np.rint(np.linspace(y1, y2, samples)).astype(int).clip(0, h - 1)
        if not domain[yy, xx].any() or prior[yy, xx].mean() > 0.9:
            continue
        if max(distance[yy[0], xx[0]], distance[yy[-1], xx[-1]]) > radius / 2:
            continue
        if min(thin_distance[yy[0], xx[0]], thin_distance[yy[-1], xx[-1]]) > 3:
            continue
        if int(np.count_nonzero(~prior[yy, xx])) > radius * 3:
            continue
        nx, ny = -(y2 - y1) / length, (x2 - x1) / length
        sides = []
        for sign in [-1, 1]:
            sx = np.rint(xx + sign * nx * 4).astype(int).clip(0, w - 1)
            sy = np.rint(yy + sign * ny * 4).astype(int).clip(0, h - 1)
            sides.append(lab[sy, sx])
        center = lab[yy, xx]
        contrast = np.minimum(
            np.linalg.norm(center - sides[0], axis=1), np.linalg.norm(center - sides[1], axis=1)
        )
        if np.mean(contrast > 12) < 0.8:
            continue
        endpoints = center[[0, -1]].mean(axis=0)
        if np.mean(np.linalg.norm(center - endpoints, axis=1) < 30) < 0.85:
            continue
        # Image evidence for the line center only; no wide dilation of the floor.
        good = (contrast > 12) & domain[yy, xx]
        recovered[yy[good], xx[good]] = 1
    return recovered.astype(bool)
