import numpy as np

from app.services.boundary_refiner import BoundaryRefiner


def test_snap_recovers_plinth_without_global_growth():
    rgb = np.zeros((300, 400, 3), np.uint8)
    rgb[:150] = 215
    rgb[150:] = 65
    mask = np.zeros((300, 400), bool)
    mask[152:] = True
    result = BoundaryRefiner().refine(mask, rgb)
    assert result.mask[150:152, 20:380].mean() > .8
    assert not result.mask[:147].any()
    assert result.max_displacement_px <= result.radius_px


def test_uniform_image_does_not_grow_mask_or_close_fine_leg():
    rgb = np.full((300, 400, 3), 120, np.uint8)
    mask = np.zeros((300, 400), bool)
    mask[140:] = True
    mask[180:260, 200:203] = False
    result = BoundaryRefiner().refine(mask, rgb)
    np.testing.assert_array_equal(result.mask, mask)


def test_high_resolution_refinement_upsamples_coarse_mask():
    rgb = np.full((300, 400, 3), 120, np.uint8)
    mask = np.zeros((150, 200), bool)
    mask[70:] = True
    result = BoundaryRefiner().refine(mask, rgb)
    assert result.mask.shape == rgb.shape[:2]
    assert not result.mask[:140].any()
    assert result.mask[140:].all()
