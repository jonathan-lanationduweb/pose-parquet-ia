"""Regressions for photo geometry consistency and small object openings."""
import cv2
import numpy as np

from app.services.camera_geometry import CameraEstimate, VanishingPointEstimate
from app.services.floor_scene import camera_floor_reference, mask_zones, refine_image_edges


def test_thin_leg_hole_survives_scene_polygons():
    mask = np.zeros((400, 600), dtype=bool)
    mask[150:, :] = True
    mask[200:250, 300:305] = False
    zones = mask_zones(mask)
    assert len(zones) == 1
    assert len(zones[0][1]) == 1  # 250 px used to fall below the area-ratio threshold


def test_refinement_recovers_only_an_image_supported_border():
    image = np.zeros((200, 300, 3), dtype=np.uint8)
    image[:100] = (220, 220, 220)
    image[100:] = (120, 75, 35)
    mask = np.zeros((200, 300), dtype=bool)
    mask[102:] = True
    result = refine_image_edges(mask, image)
    assert result[100:102, 10:-10].all()
    assert not result[:100].any()
    assert not refine_image_edges(mask, np.full_like(image, 120))[:102].any()


def test_refinement_cannot_fill_an_interior_leg():
    mask = np.zeros((200, 300), dtype=bool)
    mask[100:] = True
    mask[120:150, 100:103] = False
    image = np.full((200, 300, 3), (130, 90, 40), dtype=np.uint8)
    assert not refine_image_edges(mask, image)[120:150, 100:103].any()


def test_measured_ground_plane_preserves_roll_and_metric_axes():
    cam = CameraEstimate(0.36, 'lines-2vp', 0.8, 650., 'vanishing-points',
                         [VanishingPointEstimate(-500., 400., 3., 20),
                          VanishingPointEstimate(1050., 300., 2., 15)], 35,
                         selected_pair=(0, 1))
    # Derive focal from the orthogonal pair, as estimate_camera does.
    f = float(np.sqrt(-((-500 - 500) * (1050 - 500) + (400 - 350) * (300 - 350))))
    quad = camera_floor_reference(cam, 1000, 700, f, 1.5)
    assert quad is not None
    assert abs(quad[0][1] - quad[1][1]) > 0.01
    corners = np.array(quad, np.float32) * (1000, 700)
    world = np.array([[0, 0], [4, 0], [4, 4], [0, 4]], np.float32)
    homography = cv2.getPerspectiveTransform(world, corners.astype(np.float32))
    assert abs(np.linalg.det(homography)) > 1


def test_camera_scores_all_pairs_instead_of_borrowing_a_focal(monkeypatch):
    from app.services import camera_geometry as geometry

    points = [VanishingPointEstimate(400., 600., 8., 40),
              VanishingPointEstimate(-200., 250., 2., 15),
              VanishingPointEstimate(1400., 250., 1.5, 12)]
    monkeypatch.setattr(geometry, 'detect_segments', lambda _: [])
    monkeypatch.setattr(geometry, 'find_vanishing_points', lambda *_: points)
    mask = np.zeros((700, 1000), dtype=bool)
    mask[450:] = True
    cam = geometry.estimate_camera(np.zeros((700, 1000, 3), dtype=np.uint8), floor_mask=mask)
    assert cam.selected_pair == (1, 2)
    assert cam.horizon == 250 / 700
    assert len(cam.hypotheses) >= 2
    assert cam.focal_px is not None


def test_chunked_semantic_resize_matches_full_class_argmax():
    from types import SimpleNamespace

    import pytest

    torch = pytest.importorskip('torch')
    from app.services.floor_semantic import semantic_labels_chunked

    generator = torch.Generator().manual_seed(23)
    classes = torch.randn((1, 12, 36), generator=generator)
    masks = torch.randn((1, 12, 12, 16), generator=generator)
    scores = torch.einsum('bqc,bqhw->bchw', classes.softmax(-1)[..., :-1], masks.sigmoid())
    expected = torch.nn.functional.interpolate(scores, size=(24, 32), mode='bilinear',
                                               align_corners=False).argmax(1)
    result = semantic_labels_chunked(SimpleNamespace(class_queries_logits=classes,
                                                   masks_queries_logits=masks), (24, 32))
    assert torch.equal(result, expected)


def test_outer_mask_keeps_subpixel_border_detail():
    import cv2
    import numpy as np

    from app.services.floor_scene import mask_zones

    mask = np.zeros((1200, 1600), np.uint8)
    mask[500:, 100:1500] = 1
    mask[500:502, 800:803] = 0
    zones = mask_zones(mask)
    contour = np.array([(p.x * 1600, p.y * 1200) for p in zones[0][0]], np.float32)
    assert abs(cv2.pointPolygonTest(contour, (800., 501.), True)) <= .5


def test_occluders_do_not_restore_stale_semantic_edges_over_refined_floor():
    from app.services.floor_scene import ADE20K_RUG, furniture_occluders, rug_occluders

    labels = np.zeros((200, 300), dtype=np.uint8)
    labels[90:160, 30:130] = ADE20K_RUG
    labels[50:100, 160:260] = 10
    floor = np.zeros_like(labels, dtype=bool)
    floor[150:, :150] = True
    floor[95:, 150:] = True
    for objects, exposed, protected in [
        (rug_occluders(labels, floor_mask=floor), (80., 155.), (80., 120.)),
        (furniture_occluders(labels, floor_mask=floor), (200., 97.), (200., 75.)),
    ]:
        assert objects
        def covered(point, objects=objects):
            return any(cv2.pointPolygonTest(
                np.array([(p.x * 300, p.y * 200) for p in obj.polygon], np.float32),
                point, False,
            ) >= 0 for obj in objects)
        assert not covered(exposed)
        assert covered(protected)


def test_edge_refiner_keeps_light_furniture_above_a_dark_contact_shadow():
    image = np.full((240, 360, 3), (130, 90, 50), dtype=np.uint8)
    image[:100] = (215, 210, 200)
    image[100:108] = (30, 25, 20)
    mask = np.zeros((240, 360), dtype=bool)
    mask[109:] = True
    result = refine_image_edges(mask, image)
    assert not result[:100].any(), "Floor must not creep onto the cabinet"
    assert result[115:].all()


def test_low_metric_confidence_is_never_announced_as_reliable_photo(monkeypatch):
    from dataclasses import replace

    from app.services import floor_scene

    mask = np.zeros((480, 640), dtype=bool)
    polygon = np.array([[150, 240], [490, 240], [639, 479], [0, 479]], np.int32)
    cv2.fillPoly(mask.view(np.uint8), [polygon], 1)
    perspective = floor_scene.estimate_perspective(mask)
    perspective = replace(perspective, metric_scale_confidence="low", confidence=0.9)
    monkeypatch.setattr(floor_scene, "estimate_perspective", lambda *_a, **_kw: perspective)
    result = floor_scene.build_experimental_scene(
        mask, 640, 480, image_rgb=np.full((480, 640, 3), 128, np.uint8),
        floor_confidence=0.95,
    )
    assert result.status == "approximate_render"
    assert "metric_scale_estimated" in result.provenance["decision"]["reasons"]
    assert result.provenance["decision"]["quality"]["scaleQuality"] < 1
