"""Properties of relative-depth fusion; no model or private photo in unit tests."""
import copy

import numpy as np
import pytest

from app.services.depth_geometry import compare_depth_candidates, fit_depth_floor


def plane():
    yy, xx = np.mgrid[:240, :320]
    return (5 + .003 * xx + .04 * yy).astype(np.float32)


def test_relative_affine_changes_cannot_change_floor_roll():
    depth = plane()
    mask = np.ones(depth.shape, bool)
    first = fit_depth_floor(depth, mask)
    second = fit_depth_floor(depth * 3 + 50, mask)
    assert first.usable and second.usable
    assert first.roll_deg == pytest.approx(second.roll_deg, abs=1e-4)
    assert first.zero_horizon != pytest.approx(second.zero_horizon)


def test_depth_plane_resists_objects_wrongly_included_in_floor():
    depth = plane()
    original = fit_depth_floor(depth, np.ones(depth.shape, bool))
    depth[120:150, 50:150] += 100
    fitted = fit_depth_floor(depth, np.ones(depth.shape, bool))
    assert fitted.usable
    assert fitted.roll_deg == pytest.approx(original.roll_deg, abs=.2)


@pytest.mark.parametrize("depth", [np.ones((240, 320)), -plane()])
def test_no_plane_is_claimed_for_constant_or_reverse_depth(depth):
    assert not fit_depth_floor(depth, np.ones(depth.shape, bool)).usable


def test_an_insufficient_floor_is_rejected():
    depth = plane()
    assert not fit_depth_floor(depth, np.zeros(depth.shape, bool)).usable
    assert not fit_depth_floor(depth, np.ones((10, 10), bool)).usable


def test_two_measured_directions_are_not_overwritten_by_relative_depth():
    from app.services.floor_scene import build_experimental_scene

    mask = np.zeros((240, 320), bool)
    mask[140:] = True
    current = build_experimental_scene(mask, 320, 240).scene
    assert current is not None
    raw = current.model_dump(by_alias=True, exclude_none=True)
    original = copy.deepcopy(raw)
    fit = fit_depth_floor(plane(), mask)
    comparison = compare_depth_candidates(raw,
        {"focalPx": 230, "camera": {"horizonSource": "lines-2vp"}}, fit)
    assert comparison["selected"] == "current"
    assert comparison["metricScaleMeasured"] is False
    assert raw == original
    if comparison["fused"]:
        assert comparison["fused"]["floorZones"] == raw["floorZones"]
        assert comparison["fused"]["occluders"] == raw["occluders"]


def test_missing_vanishing_points_cannot_invent_a_diagonal_material_direction():
    from app.services.floor_scene import build_experimental_scene

    mask = np.zeros((240, 320), bool)
    mask[140:] = True
    current = build_experimental_scene(mask, 320, 240).scene
    assert current is not None
    raw = current.model_dump(by_alias=True, exclude_none=True)
    raw["camera"]["vanishingPoints"] = []
    fit = fit_depth_floor(plane(), mask)
    result = compare_depth_candidates(raw, {"focalPx": 230}, fit)
    if result["fused"]:
        assert abs(result["fused"]["camera"]["vanishingPoints"][0]["x"]) > 1000
