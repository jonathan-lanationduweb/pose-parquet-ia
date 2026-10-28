"""V4 lighting: supplied Rec.709/Gaussian algorithm, unchanged constants."""

import base64
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from app.schemas.scene_data import LightLayer


def build_lighting_layers(
    photo_bgr: NDArray[np.uint8],
    floor_mask: NDArray[np.float32],
    occluder_mask: NDArray[np.float32],
) -> dict[str, Any]:
    """Return the prescribed multiplicative RGB light and source colour statistics.

    Masks use [0,1] in the source-image domain. Occluders remain in the
    contract, intentionally unused by the supplied first lighting formula.
    """
    if (
        photo_bgr.ndim != 3
        or photo_bgr.shape[2] != 3
        or floor_mask.ndim != 2
        or occluder_mask.shape != floor_mask.shape
        or photo_bgr.shape[:2] != floor_mask.shape
    ):
        raise ValueError("Photo and masks must share the same image dimensions")
    if not (
        np.isfinite(photo_bgr).all()
        and np.isfinite(floor_mask).all()
        and np.isfinite(occluder_mask).all()
    ):
        raise ValueError("Photo and masks must be finite")
    img = photo_bgr.astype(np.float32) / 255.0
    luma = 0.2126 * img[:, :, 2] + 0.7152 * img[:, :, 1] + 0.0722 * img[:, :, 0]
    h, w = floor_mask.shape[:2]
    m = floor_mask > 0.5
    if m.sum() < 1000:
        return {"lightLayer": np.ones((h, w, 3), np.float32), "gain": 1.0}
    floor_pixels = img[m]
    mean_floor = floor_pixels.mean(axis=0)
    std_floor = floor_pixels.std(axis=0) + 1e-6
    mean_floor_luma = float(luma[m].mean())
    luma_blurred = cv2.GaussianBlur(luma, ksize=(0, 0), sigmaX=25.0)
    mask_blur = cv2.GaussianBlur(floor_mask.astype(np.float32), (0, 0), sigmaX=15.0)
    mask_blur = np.clip(mask_blur, 1e-3, 1.0)
    light_layer = luma_blurred / max(mean_floor_luma, 1e-3)
    light_layer = np.clip(light_layer, 0.4, 1.8)
    light_layer = light_layer * mask_blur + 1.0 * (1.0 - mask_blur)
    light_layer_rgb = np.repeat(light_layer[:, :, None], 3, axis=2)
    lab = cv2.cvtColor(photo_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    return {
        "lightLayer": light_layer_rgb.astype(np.float32),
        "gain": float(mean_floor_luma),
        "meanFloorBGR": mean_floor.astype(np.float32),
        "stdFloorBGR": std_floor.astype(np.float32),
        "lab": lab,
    }


def encode_lighting_layers(layers: dict[str, Any], floor_mask: NDArray[np.float32]) -> LightLayer:
    """PNG RG packs a scalar uint16 at scale 10000 (gain above 1 preserved).

    The supplied light is achromatic (three identical channels), so no RGB
    information is lost. Lab remains internal; its floor statistics travel
    with the existing SceneData.light contract rather than a full Lab photo.
    """
    light = layers["lightLayer"]
    h, w = light.shape[:2]
    scalar = np.rint(light[:, :, 0] * 10000).astype(np.uint16)
    rgba = np.zeros((h, w, 4), np.uint8)
    rgba[:, :, 0] = scalar & 255
    rgba[:, :, 1] = scalar >> 8
    rgba[:, :, 3] = 255
    ok, png = cv2.imencode(".png", cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGRA))
    if not ok:
        raise ValueError("Cannot encode lighting layer")
    stats: dict[str, list[float]] = {
        key: layers[key].tolist() for key in ("meanFloorBGR", "stdFloorBGR") if key in layers
    }
    if "lab" in layers:
        lab_pixels = layers["lab"][floor_mask > 0.5]
        stats["meanFloorLab"] = lab_pixels.mean(axis=0).tolist()
        stats["stdFloorLab"] = lab_pixels.std(axis=0).tolist()
    return LightLayer(
        width=w,
        height=h,
        encoding="png-rg-u16",
        scale=10000,
        data="data:image/png;base64," + base64.b64encode(png).decode("ascii"),
        gain=layers["gain"],
        color_stats=stats,
    )
