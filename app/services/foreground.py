"""Foreground protection from existing labels and semantic floor openings."""

from __future__ import annotations

import time
from dataclasses import dataclass

import cv2
import numpy as np

from app.schemas.scene_data import Occluder, Point
from app.services.boundary_refiner import guided_boundary_seed
from app.services.mask_contours import cell_polygons

# Explicit ids from the installed ADE20K config. No new inference.
OBJECT_CLASSES = {
    7, 10, 12, 15, 17, 19, 23, 24, 30, 31, 33, 35, 36, 37,
    39, 40, 41, 44, 45, 50, 55, 56, 57, 62, 64, 65, 69, 71,
    73, 75, 89, 92, 97, 99, 107, 108, 110, 111, 112, 115, 117,
    118, 119, 125, 126, 127, 129, 131, 132, 135, 138, 139, 146,
}
# Names verified against the installed ADE20K id2label. Ground, shadows,
# walls and outdoor surfaces are intentionally absent. Previously omitted
# cushions, poufs, boxes and pots must not depend on incidental floor holes.
RUG = 28
_CLASS_LOOKUP = np.zeros(256, bool)
_CLASS_LOOKUP[[*OBJECT_CLASSES, RUG]] = True


@dataclass
class ForegroundResult:
    objects: list[Occluder]
    coarse: np.ndarray
    refined: np.ndarray
    timings_ms: dict[str, float]


def polygons(mask: np.ndarray, *, kind: str, prefix: str) -> list[Occluder]:
    """Preserve exact occupied pixel cells, holes and single-pixel supports."""
    return [
        Occluder(id=f"{prefix}-{i}",label=f"{kind} (semantic proposal)",
                 kind=kind,polygon=outer,holes=holes,casts_shadow=False,feather=0)
        for i,(outer,holes,_area) in enumerate(cell_polygons(mask))
    ]


def interior_openings(floor: np.ndarray) -> np.ndarray:
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        (~floor.astype(bool)).astype(np.uint8), connectivity=4
    )
    h, w = floor.shape
    protected = np.zeros(count, bool)
    for i in range(1, count):
        x, y, cw, ch, _ = stats[i]
        protected[i] = x > 0 and y > 0 and x + cw < w and y + ch < h
    return np.asarray(protected[labels])


def build_foreground(
    labels: np.ndarray | None,
    raw_floor: np.ndarray,
    image_rgb: np.ndarray | None = None,
    *,
    opening_polygons: list[list[Point]] | None = None,
) -> ForegroundResult:
    started = time.perf_counter()
    shape = raw_floor.shape
    semantic = np.zeros(shape, bool)
    if labels is not None:
        if labels.shape != shape:
            labels = cv2.resize(labels, (shape[1], shape[0]), interpolation=cv2.INTER_NEAREST)
        semantic = np.take(_CLASS_LOOKUP, labels.astype(np.int32, copy=False), mode="clip")
    # Openings are independent exclusions, even when their semantic class is unknown.
    if opening_polygons is None:
        holes = interior_openings(raw_floor)
    else:
        raster = np.zeros(shape, np.uint8)
        for polygon in opening_polygons:
            points = np.array(
                [[round(p.x * (shape[1] - 1)), round(p.y * (shape[0] - 1))] for p in polygon],
                np.int32,
            )
            cv2.fillPoly(raster, [points], 1)
        holes = raster.astype(bool)
    coarse = semantic | holes
    coarse_ms = (time.perf_counter() - started) * 1000
    started = time.perf_counter()
    refined = semantic.copy()
    if image_rgb is not None and image_rgb.shape[:2] == shape and semantic.any():
        # Only refine the foreground near the floor: upper-wall furniture
        # cannot affect the composite and need not pay a second full-image pass.
        ys = np.nonzero(raw_floor.any(axis=1))[0]
        y0 = max(0, int(ys.min()) - 24) if len(ys) else 0
        refined[y0:] = guided_boundary_seed(semantic[y0:], image_rgb[y0:])
        # Preserve thin branches attached to a massive object as well as isolated legs.
        padded = np.pad(semantic, 2)
        h, w = shape
        narrow_x = ~padded[2 : 2 + h, :w] & ~padded[2 : 2 + h, 4 : 4 + w]
        narrow_y = ~padded[:h, 2 : 2 + w] & ~padded[4 : 4 + h, 2 : 2 + w]
        refined |= semantic & (narrow_x | narrow_y)
    refinement_ms = (time.perf_counter() - started) * 1000
    started = time.perf_counter()
    # A refined rug retains its own kind; the full union is authoritative for coverage.
    rugs = refined & (labels == RUG) if labels is not None else np.zeros(shape, bool)
    objects = polygons(refined & ~rugs, kind="furniture", prefix="foreground")
    objects += polygons(rugs, kind="rug", prefix="rug")
    if opening_polygons is None:
        objects += polygons(holes & ~refined, kind="mask-opening", prefix="opening")
    else:
        objects += [
            Occluder(
                id=f"opening-{i}",
                label="Mask opening (role unknown)",
                kind="mask-opening",
                polygon=polygon,
                casts_shadow=False,
                feather=0,
            )
            for i, polygon in enumerate(opening_polygons)
        ]
    return ForegroundResult(
        objects,
        coarse,
        refined | holes,
        {
            "occlusionCoarse": round(coarse_ms, 3),
            "occlusionRefinement": round(refinement_ms, 3),
            "occlusionPolygons": round((time.perf_counter() - started) * 1000, 3),
        },
    )
