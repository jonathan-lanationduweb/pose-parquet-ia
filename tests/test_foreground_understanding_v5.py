"""Known-shape ground truth; no synthetic IoU claimed for real photographs."""

import cv2
import numpy as np
import pytest

from app.services.foreground_understanding import understand_foreground
from app.services.scene_quality import scene_quality_gate


def dice(a, b):
    return 2 * (a & b).sum() / max(1, int(a.sum() + b.sum()))


@pytest.mark.parametrize("floor,object_color", [(190, 40), (70, 15), (220, 245)])
def test_large_object_boundary_on_original_dark_and_bright_photos(floor, object_color):
    image = np.full((160, 240, 3), floor, np.uint8)
    gt = np.zeros((160, 240), bool)
    gt[40:120, 60:170] = True
    image[gt] = object_color
    coarse = np.zeros_like(gt)
    coarse[40:125, 55:175] = True
    result = understand_foreground(image, np.ones_like(gt), coarse)
    assert dice(result.mask, gt) >= dice(coarse, gt)
    assert result.mask[80, 100]
    assert not result.mask[140, 190]


@pytest.mark.parametrize("width", [1, 3, 5])
@pytest.mark.parametrize("floor,object_color", [(190, 20), (25, 20)])
def test_thin_vertical_and_inclined_supports_never_eroded(width, floor, object_color):
    shape = (160, 240)
    gt = np.zeros(shape, np.uint8)
    cv2.line(gt, (70, 30), (70, 140), 1, width)
    cv2.line(gt, (130, 30), (160, 140), 1, width)
    image = np.full((*shape, 3), floor, np.uint8)
    image[gt > 0] = object_color
    result = understand_foreground(image, np.ones(shape, bool), gt > 0)
    assert (result.mask[gt > 0]).mean() > 0.98


def test_floor_gaps_not_filled_and_new_islands_not_invented():
    image = np.full((160, 240, 3), 185, np.uint8)
    gt = np.zeros((160, 240), bool)
    gt[20:70, 50:180] = True
    gt[70:145, 50:55] = True
    gt[70:145, 175:180] = True
    image[gt] = [40, 55, 70]
    result = understand_foreground(image, np.ones_like(gt), gt)
    assert not result.mask[120, 120]
    assert dice(result.mask, gt) > 0.99


def test_rug_same_colour_floor_ambiguous_edges_keep_prior():
    rng = np.random.default_rng(0)
    image = rng.integers(175, 185, (160, 240, 3), dtype=np.uint8)
    rug = np.zeros((160, 240), bool)
    rug[60:140, 50:180] = True
    result = understand_foreground(image, np.ones_like(rug), rug)
    assert dice(result.mask, rug) > 0.99


def test_empty_room_with_grain_and_empty_domain():
    rng = np.random.default_rng(1)
    image = rng.integers(20, 240, (120, 160, 3), dtype=np.uint8)
    empty = np.zeros((120, 160), bool)
    result = understand_foreground(image, ~empty, empty)
    assert not result.mask.any()
    assert not result.thin.any()
    mask = empty.copy()
    mask[20:70, 30:100] = True
    np.testing.assert_array_equal(understand_foreground(image, empty, mask).mask, mask)


def test_invalid_dimensions_nan_and_non_source_dtype():
    image = np.full((100, 120, 3), 180, np.uint8)
    mask = np.zeros((100, 120), bool)
    with pytest.raises(ValueError):
        understand_foreground(image, mask[:-1], mask)
    with pytest.raises(ValueError):
        understand_foreground(image.astype(float), mask, mask)
    invalid = mask.astype(float)
    invalid[50, 50] = np.nan
    with pytest.raises(ValueError):
        understand_foreground(image, mask, invalid)


def test_uncertain_foreground_blocks_auto_without_hiding_valid_geometry():
    quality = dict.fromkeys(
        [
            "imageQuality",
            "floorQuality",
            "boundaryQuality",
            "layoutQuality",
            "cameraQuality",
            "scaleQuality",
            "foregroundQuality",
            "illuminationQuality",
        ],
        0.95,
    )
    quality["foregroundQuality"] = 0.5
    decision = scene_quality_gate(quality)
    assert decision.decision == "APPROXIMATE_RENDER"
    assert "foregroundQuality_unverified" in decision.reasons


def test_short_missing_stem_gap_recovered_from_existing_green_endpoints():
    image = np.full((160, 240, 3), [190, 165, 125], np.uint8)
    gt = np.zeros((160, 240), bool)
    gt[15:40, 45:85] = True
    gt[35:130, 62:67] = True
    image[gt] = [40, 85, 35]
    prior = gt.copy()
    prior[65:75, 62:67] = False
    result = understand_foreground(image, np.ones_like(gt), prior)
    assert (result.mask & gt).sum() > (prior & gt).sum()
    assert (result.mask & gt).sum() / gt.sum() > .98
    assert (result.mask & gt).sum() / max(1, int(result.mask.sum())) > .98
