"""Reference-formula and wire-format tests for the requested V4 lighting."""

import base64

import cv2
import numpy as np
import pytest

from app.services.lighting_layers import build_lighting_layers, encode_lighting_layers


@pytest.mark.parametrize("level", [0, 20, 128, 240])
def test_valid_dark_bright_and_finite(level):
    photo = np.full((100, 120, 3), level, np.uint8)
    mask = np.zeros((100, 120), np.float32)
    mask[30:90, 20:100] = 1
    result = build_lighting_layers(photo, mask, mask * 0)
    layer = result["lightLayer"]
    assert layer.shape == photo.shape and layer.dtype == np.float32
    assert np.isfinite(layer).all()
    assert layer.min() >= 0.4 - 1e-6 and layer.max() <= 1.8 + 1e-6
    expected_luma = level / 255
    assert result["gain"] == pytest.approx(expected_luma, abs=1e-6)
    np.testing.assert_allclose(layer[:, :, 0], layer[:, :, 2])


def test_small_mask_neutral_and_shape_error():
    photo = np.zeros((60, 80, 3), np.uint8)
    mask = np.zeros((60, 80), np.float32)
    mask[:5] = 1
    result = build_lighting_layers(photo, mask, mask)
    assert result["gain"] == 1
    assert (result["lightLayer"] == 1).all()
    with pytest.raises(ValueError):
        build_lighting_layers(photo, mask[:-1], mask)


def test_matches_supplied_formula_not_mask_normalized_replacement():
    y, x = np.mgrid[:120, :160]
    photo = np.stack([x % 255, y % 255, (x + y) % 255], axis=-1).astype(np.uint8)
    mask = ((x > 30) & (y > 30)).astype(np.float32)
    result = build_lighting_layers(photo, mask, mask * 0)
    img = photo.astype(np.float32) / 255
    luma = 0.2126 * img[:, :, 2] + 0.7152 * img[:, :, 1] + 0.0722 * img[:, :, 0]
    blurred = cv2.GaussianBlur(luma, (0, 0), sigmaX=25.0)
    mask_blur = np.clip(cv2.GaussianBlur(mask, (0, 0), sigmaX=15.0), 1e-3, 1.0)
    expected = np.clip(blurred / max(float(luma[mask > 0.5].mean()), 1e-3), 0.4, 1.8)
    expected = expected * mask_blur + 1 - mask_blur
    np.testing.assert_allclose(result["lightLayer"][:, :, 0], expected, atol=2e-7)


def test_old_fine_tile_joints_suppressed_and_outside_neutral():
    photo = np.full((400, 400, 3), 180, np.uint8)
    photo[:, ::12] = 30
    photo[::12] = 30
    mask = np.zeros((400, 400), np.float32)
    mask[150:350, 50:350] = 1
    result = build_lighting_layers(photo, mask, mask * 0)
    central = result["lightLayer"][200:300, 100:300, 0]
    assert np.ptp(central) < 0.01
    np.testing.assert_allclose(result["lightLayer"][:30], 1, atol=0.001)


def test_lossless_transport_gains_above_one_and_color_stats():
    photo = np.full((80, 100, 3), 160, np.uint8)
    photo[:, 50:] = 240
    mask = np.ones((80, 100), np.float32)
    result = build_lighting_layers(photo, mask, mask * 0)
    wire = encode_lighting_layers(result, mask)
    png = base64.b64decode(wire.data.split(",")[1])
    bgra = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_UNCHANGED)
    rgba = cv2.cvtColor(bgra, cv2.COLOR_BGRA2RGBA).astype(np.float32)
    decoded = (rgba[:, :, 0] + 256 * rgba[:, :, 1]) / wire.scale
    np.testing.assert_allclose(decoded, result["lightLayer"][:, :, 0], atol=0.000051)
    assert decoded.max() > 1
    assert set(wire.color_stats) == {"meanFloorBGR", "stdFloorBGR", "meanFloorLab", "stdFloorLab"}
