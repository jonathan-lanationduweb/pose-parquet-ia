"""Bounded, image-supported contour snapping; no learned model or global growth."""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class BoundaryResult:
    mask: np.ndarray
    radius_px: int
    moved_points: int
    mean_displacement_px: float
    max_displacement_px: float


def guided_boundary_seed(mask: np.ndarray, image_rgb: np.ndarray) -> np.ndarray:
    """Regularize coarse stairs only inside an image-supported uncertainty band."""
    radius = int(np.clip(round(max(mask.shape)/256), 6, 12))
    binary = mask.astype(np.uint8)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (radius*2+1,)*2)
    band = cv2.dilate(binary, kernel) != cv2.erode(binary, kernel)
    ys, xs = np.nonzero(band)
    if not len(xs):
        return mask.copy()
    h, w = mask.shape
    x0, x1 = max(0, int(xs.min())-radius*3), min(w, int(xs.max())+radius*3+1)
    y0, y1 = max(0, int(ys.min())-radius*3), min(h, int(ys.max())+radius*3+1)
    guide = cv2.cvtColor(image_rgb[y0:y1, x0:x1], cv2.COLOR_RGB2GRAY)
    guide = guide.astype(np.float32)/255
    prediction = mask[y0:y1, x0:x1].astype(np.float32)
    def mean(values: np.ndarray) -> np.ndarray:
        return cv2.boxFilter(values, -1, (radius*2+1,)*2)
    mi, mp = mean(guide), mean(prediction)
    variance = np.maximum(0, mean(guide*guide)-mi*mi)
    slope = (mean(guide*prediction)-mi*mp)/(variance+.001)
    guided = mean(slope)*guide+mean(mp-slope*mi)
    supported = band[y0:y1, x0:x1] & (variance > .001)
    result = mask.copy()
    result[y0:y1, x0:x1][supported] = guided[supported] > .5
    # Keep semantic holes before subsequent contour snapping.
    _, labels, stats, _ = cv2.connectedComponentsWithStats((~mask).astype(np.uint8),
                                                         connectivity=4)
    protected = np.zeros(len(stats), dtype=bool)
    for i in range(1, len(stats)):
        x, y, cw, ch, _ = stats[i]
        protected[i] = x > 0 and y > 0 and x+cw < w and y+ch < h
    result[protected[labels]] = False
    return result


class BoundaryRefiner:
    """Move only outer contour points with locally stronger image evidence.

    Long/tangent-consistent edges are favoured over isolated texture. The search
    radius is resolution bounded, offsets are regularized along the contour,
    corners and interior holes remain protected. No metric accuracy is claimed.
    """

    def refine(self, coarse: np.ndarray, image_rgb: np.ndarray) -> BoundaryResult:
        h, w = image_rgb.shape[:2]
        mask = cv2.resize(coarse.astype(np.uint8), (w, h),
                          interpolation=cv2.INTER_NEAREST).astype(bool)
        radius = int(np.clip(round(max(h, w) / 256), 3, 8))
        if not mask.any():
            return BoundaryResult(mask, radius, 0, 0., 0.)
        gray = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255
        unblurred = gray.copy()
        gray = cv2.GaussianBlur(gray, (3, 3), 0).astype(np.float32)
        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        line_support = np.zeros(mask.shape, np.float32)
        scale = min(1., 900/max(h, w))
        small = cv2.resize((gray*255).astype(np.uint8),
                           (round(w*scale), round(h*scale)))
        lines = cv2.createLineSegmentDetector().detect(small)[0]
        if lines is not None:
            for segment in lines.reshape(-1, 4):
                x0, y0, x1, y1 = segment/scale
                if np.hypot(x1-x0, y1-y0) < .05*min(h, w):
                    continue
                cv2.line(line_support, (round(x0), round(y0)),
                         (round(x1), round(y1)), 1., 2)
        line_support = cv2.GaussianBlur(line_support, (3, 3), 0).astype(np.float32)
        contours, hierarchy = cv2.findContours(mask.astype(np.uint8), cv2.RETR_CCOMP,
                                              cv2.CHAIN_APPROX_NONE)
        result = mask.astype(np.uint8).copy()
        movements: list[np.ndarray] = []
        if hierarchy is None:
            return BoundaryResult(mask, radius, 0, 0., 0.)
        def sample(field: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
            return cv2.remap(field, x.astype(np.float32).reshape(1, -1),
                             y.astype(np.float32).reshape(1, -1), cv2.INTER_LINEAR,
                             borderMode=cv2.BORDER_REPLICATE).ravel()
        for index, contour in enumerate(contours):
            if (hierarchy[0, index, 3] != -1 or len(contour) < 40
                    or cv2.contourArea(contour) < mask.size * .002):
                continue
            pts = contour[:, 0].astype(np.float32)
            before, after = np.roll(pts, 7, axis=0), np.roll(pts, -7, axis=0)
            tangent = after - before
            norm = np.linalg.norm(tangent, axis=1)
            normal = np.column_stack((-tangent[:, 1], tangent[:, 0])) / np.maximum(1, norm[:, None])
            # Do not round away a corner, threshold recess or slender object.
            va, vb = pts - before, after - pts
            straight = (va * vb).sum(axis=1) / np.maximum(1, np.linalg.norm(va, axis=1)
                                                        * np.linalg.norm(vb, axis=1)) > .8
            safe = straight & (pts[:, 0] > radius + 2) & (pts[:, 0] < w-radius-3)
            safe &= (pts[:, 1] > radius+2) & (pts[:, 1] < h-radius-3)
            # Which side belongs to the semantic floor? A candidate must land
            # on the floor side of a contrasting edge, not on the bright plinth.
            plus_ref = pts + normal*(radius+3)
            minus_ref = pts - normal*(radius+3)
            floor_sign = np.where(sample(mask.astype(np.float32), *plus_ref.T)
                                  >= sample(mask.astype(np.float32), *minus_ref.T), 1., -1.)
            floor_ref = sample(unblurred, *(pts+normal*floor_sign[:, None]*(radius+3)).T)
            other_ref = sample(unblurred, *(pts-normal*floor_sign[:, None]*(radius+3)).T)
            scores = []
            offsets = np.arange(-radius, radius+1)
            for delta in offsets:
                xy = pts + normal * delta
                # Gradient aligned with boundary normal, averaged along tangent:
                # a continuous plinth scores above a crossing board joint.
                values = []
                for shift in (-3, 0, 3):
                    q = xy + tangent / np.maximum(1, norm[:, None]) * shift
                    values.append(np.abs(sample(gx, *q.T)*normal[:, 0]
                                         + sample(gy, *q.T)*normal[:, 1]))
                continuity = np.minimum(np.minimum(values[0], values[1]), values[2])
                plus, minus = xy + normal*2, xy-normal*2
                discontinuity = np.abs(sample(gray, *plus.T)-sample(gray, *minus.T))
                value = sample(unblurred, *xy.T)
                floor_side = (np.abs(value-floor_ref) <= np.abs(value-other_ref)+.005)
                floor_side |= np.abs(floor_ref-other_ref) < .04
                candidate_score = (continuity*.7 + discontinuity*.3
                                   + .1*sample(line_support, *xy.T) - .012*abs(delta))
                scores.append(np.where(floor_side | (delta == 0), candidate_score, -1.))
            score = np.stack(scores)
            best = score.argmax(axis=0)
            selected = offsets[best].astype(np.float32)
            supported = (score[best, np.arange(len(pts))] > score[radius]+.035)
            supported &= (score[best, np.arange(len(pts))] > .10) & safe
            selected[~supported] = 0
            # Circular median removes isolated jumps without flattening corners.
            selected = np.median(np.stack([np.roll(selected, k) for k in range(-2, 3)]), axis=0)
            selected[~safe] = 0
            shifted = np.rint(pts + normal*selected[:, None]).astype(np.int32).reshape(-1, 1, 2)
            # Replace this connected exterior, preserving the semantic holes below.
            cv2.drawContours(result, [contour], -1, 0, cv2.FILLED)
            cv2.drawContours(result, [shifted], -1, 1, cv2.FILLED)
            movements.append(np.abs(selected))
        # Every original interior non-floor component (legs, furniture, rug) stays out.
        holes = np.zeros(mask.shape, np.uint8)
        for index, contour in enumerate(contours):
            if hierarchy[0, index, 3] != -1:
                cv2.drawContours(holes, [contour], -1, 1, cv2.FILLED)
        result[(holes != 0) & ~mask] = 0
        moved = np.concatenate(movements) if movements else np.zeros(1)
        return BoundaryResult(result.astype(bool), radius, int((moved > 0).sum()),
                              float(moved.mean()), float(moved.max()))
