"""Photo-guided refinement of an existing visible-floor mask.

Classical graph cut using the existing foreground instances as bounded seeds. No model,
no camera/plane/material input. Runs once in the scene quality pass (and catalogue authoring), never
part of rotation, product change or a rendering frame.
"""

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class PhotoMaskResult:
    visible_floor: np.ndarray
    radius_px: int
    changed_pixels: int
    instances_refined: int


def refine_photo_mask(
    image_rgb: np.ndarray,
    floor_domain: np.ndarray,
    occluders: np.ndarray,
    immutable: np.ndarray | None = None,
) -> PhotoMaskResult:
    shape = image_rgb.shape[:2]
    if floor_domain.shape != shape or occluders.shape != shape:
        raise ValueError("Masks must match original photo dimensions")
    domain = np.asarray(floor_domain, bool)
    prior = domain & ~np.asarray(occluders, bool)
    if not prior.any() or prior.all():
        return PhotoMaskResult(prior.copy(), 0, 0, 0)
    radius = max(8, min(24, round(max(shape) / 64)))
    protected = np.asarray(occluders, bool).copy()
    h, w = shape
    count, components, stats, _ = cv2.connectedComponentsWithStats(
        protected.astype(np.uint8), connectivity=8
    )
    fixed = np.zeros(shape, bool) if immutable is None else np.asarray(immutable, bool)
    instances = 0
    # Fit colours per connected foreground instance. A global foreground GMM
    # learns brown cabinets/boxes and then incorrectly retains brown old floor
    # around a white bed or pouf as if it belonged to those objects.
    for label in range(1, count):
        x, y, cw, ch, area = stats[label]
        if area < 4:
            continue
        x0 = max(0, x - radius * 2)
        y0 = max(0, y - radius * 2)
        x1 = min(w, x + cw + radius * 2)
        y1 = min(h, y + ch + radius * 2)
        local = components[y0:y1, x0:x1] == label
        visible_domain = domain[y0:y1, x0:x1]
        if not np.any(
            local
            & cv2.dilate(visible_domain.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
        ):
            continue
        if np.all(fixed[y0:y1, x0:x1][local]):
            continue
        din = cv2.distanceTransform(local.astype(np.uint8), cv2.DIST_L2, 5)
        dout = cv2.distanceTransform((~local).astype(np.uint8), cv2.DIST_L2, 5)
        trimap = np.where(local, cv2.GC_PR_FGD, cv2.GC_PR_BGD).astype(np.uint8)
        trimap[din > 6] = cv2.GC_FGD
        # Coarse semantic masks can cut a concavity INTO a cushion/seat.
        # Treat its own convex envelope as uncertain, rather than hard floor.
        # Actual image colours still decide: open floor between legs is NOT filled.
        contours, _ = cv2.findContours(
            local.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        envelope = np.zeros(local.shape, np.uint8)
        if contours:
            cv2.fillConvexPoly(envelope, cv2.convexHull(np.concatenate(contours)), 1)
        trimap[(dout > radius) & (envelope == 0)] = cv2.GC_BGD
        ridge = (din > 0) & (din <= 3) & (din >= cv2.dilate(din, np.ones((3, 3), np.uint8)) - 0.01)
        trimap[ridge] = cv2.GC_FGD
        trimap[fixed[y0:y1, x0:x1]] = cv2.GC_FGD
        if not np.any(trimap == cv2.GC_FGD) or not np.any(trimap == cv2.GC_BGD):
            continue
        cv2.setRNGSeed(0)
        cv2.grabCut(
            image_rgb[y0:y1, x0:x1],
            trimap,
            (0, 0, 0, 0),
            np.zeros((1, 65)),
            np.zeros((1, 65)),
            1,
            cv2.GC_INIT_WITH_MASK,
        )
        instances += 1
        refined = np.isin(trimap, [cv2.GC_FGD, cv2.GC_PR_FGD])
        # Only this instance's prior or its bounded uncertain exterior may move;
        # another foreground instance in the ROI remains independently protected.
        other = (components[y0:y1, x0:x1] != 0) & ~local
        refined &= ~other
        layer = protected[y0:y1, x0:x1]
        layer[local] = False
        layer |= refined
    protected |= fixed
    visible = domain & ~protected
    return PhotoMaskResult(visible, radius, int(np.count_nonzero(visible != prior)), instances)
