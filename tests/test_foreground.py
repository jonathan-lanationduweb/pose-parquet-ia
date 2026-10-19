import cv2
import numpy as np

from app.services.foreground import build_foreground, interior_openings


def test_semantic_object_overrides_overlapping_floor():
    labels = np.full((160, 240), 3, np.uint8)
    labels[80:130, 60:140] = 23
    floor = np.ones(labels.shape, bool)
    result = build_foreground(labels, floor)
    assert result.refined[100, 90]
    assert result.objects and not result.refined[145, 90]


def test_thin_leg_and_rug_are_protected_at_original_resolution():
    labels = np.full((600, 800), 3, np.uint8)
    labels[200:500, 398:400] = 19
    labels[400:550, 500:750] = 28
    rgb = np.full((600, 800, 3), 180, np.uint8)
    rgb[200:500, 398:400] = 35
    result = build_foreground(labels, labels == 3, rgb)
    assert result.refined[200:500, 398:400].all()
    assert result.refined[450, 600]
    assert any(o.kind == "rug" for o in result.objects)


def test_unknown_hole_protects_grille_without_semantic_guess():
    floor = np.zeros((180, 240), bool)
    floor[60:] = True
    floor[120:126, 40:160] = False
    result = build_foreground(None, floor)
    assert result.refined[122, 100]
    assert any(o.kind == "mask-opening" for o in result.objects)
    assert not result.refined[20].any()


def test_open_floor_between_legs_does_not_become_foreground():
    labels = np.full((200, 300), 3, np.uint8)
    labels[90:140, 80:220] = 15
    labels[110:130, 100:200] = 3
    result = build_foreground(labels, labels == 3)
    assert not result.refined[120, 150]
    assert result.objects[0].holes


def test_one_pixel_opening_is_not_deleted():
    floor = np.ones((120, 160), bool)
    floor[60:90, 80] = False
    assert interior_openings(floor)[60:90, 80].all()
    result = build_foreground(None, floor)
    assert result.objects
    polygon = np.array([(p.x * 159, p.y * 119) for p in result.objects[0].polygon], np.float32)
    assert cv2.pointPolygonTest(polygon, (80.0, 75.0), False) >= 0


def test_precomputed_openings_preserve_geometry_independent_exclusion():
    from app.schemas.scene_data import Point

    floor = np.ones((120, 160), bool)
    opening = [Point(x=0.4, y=0.5), Point(x=0.42, y=0.5), Point(x=0.42, y=0.8), Point(x=0.4, y=0.8)]
    result = build_foreground(None, floor, opening_polygons=[opening])
    assert result.refined[75, 65]
    assert result.objects[0].kind == "mask-opening"
    assert result.objects[0].polygon == opening
    assert floor.all(), "Occlusion construction must not mutate the floor mask"
