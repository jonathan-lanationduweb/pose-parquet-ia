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
