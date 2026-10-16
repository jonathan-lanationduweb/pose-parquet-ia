import cv2
import numpy as np

from app.services.wall_regions import wall_regions


def test_semantic_walls_keep_openings_furniture_and_floor_out():
    labels = np.full((240, 360), 3, dtype=np.int32)
    labels[10:180, 10:350] = 0
    labels[40:150, 125:195] = 8  # window
    labels[120:180, 240:300] = 19  # furniture
    image = np.full((240, 360, 3), 160, dtype=np.uint8)
    result = wall_regions(labels, image)
    assert result["zones"]
    actual = np.zeros(labels.shape, np.uint8)
    for zone in result["zones"]:
        poly = np.array(
            [[round(p["x"] * 360), round(p["y"] * 240)] for p in zone["polygon"]], np.int32
        )
        cv2.fillPoly(actual, [poly], 1)
        for hole in zone["holes"]:
            poly = np.array([[round(p["x"] * 360), round(p["y"] * 240)] for p in hole], np.int32)
            cv2.fillPoly(actual, [poly], 0)
    assert actual[25:35, 20:110].all()
    assert not actual[45:145, 130:190].any()
    assert not actual[125:175, 245:295].any()
    assert not actual[185:, :].any()


def test_no_semantic_prediction_does_not_invent_walls():
    assert wall_regions(None, np.zeros((50, 80, 3), np.uint8))["zones"] == []


def test_a_real_wall_corner_can_split_two_selectable_regions():
    labels = np.zeros((240, 360), np.int32)
    image = np.full((240, 360, 3), (80, 100, 120), np.uint8)
    image[:, 180:] = (180, 190, 200)
    result = wall_regions(labels, image)
    assert len(result["zones"]) == 2


def test_subtle_corner_between_similarly_painted_walls_is_selectable():
    labels = np.zeros((240, 360), np.int32)
    image = np.full((240, 360, 3), (80, 100, 120), np.uint8)
    image[:, 180:] = (84, 104, 124)
    assert len(wall_regions(labels, image)["zones"]) == 2
