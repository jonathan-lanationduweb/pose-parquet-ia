"""V3 invariants: support is physical, visibility is foreground, uncertainty is explicit."""

from threading import Event
from time import sleep

import numpy as np
import pytest

from app.services import scene_refinement_jobs as jobs
from app.services.floor_scene import build_experimental_scene
from app.services.room_layout import estimate_room_layout
from app.services.scene_quality import scene_quality_gate


def sample():
    labels = np.zeros((160, 240), np.uint8)
    labels[65:] = 3
    labels[90:115, 70:170] = 15
    labels[115:145, 75:77] = 19
    labels[115:145, 163:165] = 19
    rgb = np.full((160, 240, 3), 180, np.uint8)
    rgb[labels != 3] = 35
    return labels, rgb


def test_floor_support_continues_under_table_but_not_through_wall():
    labels, _ = sample()
    result = estimate_room_layout(labels == 3, labels)
    assert result.support[100, 100]
    assert result.foreground[100, 100]
    assert not result.support[30, 100]
    assert result.report["supportRecoveredPixels"] > 0
    assert result.report["floorWallBoundary"]


def test_unknown_recess_is_not_extrapolated_as_visible_floor():
    labels, _ = sample()
    labels[65:90, 180:200] = 0
    result = estimate_room_layout(labels == 3, labels)
    assert not result.support[75, 190]
    assert result.envelope[75, 190]


def test_quality_update_keeps_camera_plane_and_two_pixel_legs():
    labels, rgb = sample()
    fast = build_experimental_scene(
        labels == 3, 240, 160, labels=labels, image_rgb=rgb, quality_pass=False
    )
    final = build_experimental_scene(
        labels == 3, 240, 160, labels=labels, image_rgb=rgb, stable_perspective=fast.geometry
    )
    assert fast.scene and final.scene
    assert fast.scene.camera == final.scene.camera
    assert fast.scene.planes == final.scene.planes
    from scripts.apply_scene_mask_review import raster

    blocked = np.zeros(labels.shape, bool)
    for o in final.scene.occluders:
        blocked |= raster(
            labels.shape,
            [p.model_dump() for p in o.polygon],
            [[p.model_dump() for p in hole] for hole in o.holes or []],
        )
    assert blocked[115:145, 75:77].all()
    assert not blocked[135, 120]
    assert final.provenance["sceneQuality"]["decision"] != "AUTO_RENDER"


def quality():
    return dict.fromkeys(
        (
            "imageQuality",
            "floorQuality",
            "boundaryQuality",
            "layoutQuality",
            "cameraQuality",
            "scaleQuality",
            "foregroundQuality",
            "illuminationQuality",
        ),
        0.95,
    )


@pytest.mark.parametrize("visual", [{"S1": "FAIL"}, {"S2": "FAIL"}, {"S4": "BLOCKING"}])
def test_blocking_visual_evidence_overrides_high_scores(visual):
    assert scene_quality_gate(quality(), visual=visual).decision == "MANUAL_REQUIRED"


def test_unmeasured_foreground_cannot_auto_render():
    q = quality()
    assert scene_quality_gate(q).decision == "AUTO_RENDER"
    q["foregroundQuality"] = None
    assert scene_quality_gate(q).decision == "APPROXIMATE_RENDER"
    q["foregroundQuality"] = 0.2
    assert scene_quality_gate(q).decision == "MANUAL_REQUIRED"
    q["foregroundQuality"] = float("nan")
    assert scene_quality_gate(q).decision == "FAILED_GRACEFULLY"


def test_quality_job_is_nonblocking_bounded_and_discardable():
    event = Event()

    def work():
        event.wait(3)
        return {"floor": {"revision": 2}}

    a = jobs.submit(work)
    b = jobs.submit(work)
    try:
        assert a and b
        assert jobs.snapshot(a) == {"status": "pending"}
        assert jobs.submit(work) is None
        event.set()
        for _ in range(100):
            if jobs.snapshot(a)["status"] == "ready":
                break
            sleep(0.01)
        assert jobs.snapshot(a)["experimental"]["floor"]["revision"] == 2
    finally:
        event.set()
        if a:
            jobs.discard(a)
        if b:
            jobs.discard(b)
    assert jobs.snapshot(a) is None


def test_photo_refinement_recovers_object_concavity_without_filling_open_floor():
    from app.services.photo_mask_refiner import refine_photo_mask

    image = np.full((160, 240, 3), 190, np.uint8)
    image[60:120, 70:170] = 35
    coarse = np.zeros((160, 240), bool)
    coarse[60:120, 70:170] = True
    coarse[80:120, 110:145] = False  # Coarse model cuts inside a dark cushion.
    result = refine_photo_mask(image, np.ones(coarse.shape, bool), coarse)
    assert not result.visible_floor[105, 125]
    assert result.visible_floor[130, 125]
    # The same concavity can be real floor between table legs; RGB must decide.
    image[80:120, 110:145] = 190
    result = refine_photo_mask(image, np.ones(coarse.shape, bool), coarse)
    assert result.visible_floor[105, 125]


def test_single_off_axis_rail_does_not_create_a_sheared_camera_basis(monkeypatch):
    from app.services import floor_scene
    from app.services.floor_scene import _Rails

    labels, _ = sample()
    monkeypatch.setattr(floor_scene, "_rails_vanishing_point", lambda *_: _Rails(-600, 30, 0.8))
    estimate = floor_scene.estimate_perspective(labels == 3)
    assert estimate is not None
    quad = np.array(estimate.quad, np.float32) * [240, 160]
    import cv2

    homography = cv2.getPerspectiveTransform(
        np.array([[0, 0], [1, 0], [1, 1], [0, 1]], np.float32), quad.astype(np.float32)
    )
    inverse_k = np.linalg.inv(
        np.array([[estimate.focal_px, 0, 120], [0, estimate.focal_px, 80], [0, 0, 1]])
    )
    u, v = inverse_k @ homography[:, 0], inverse_k @ homography[:, 1]
    assert abs(np.dot(u, v) / np.linalg.norm(u) / np.linalg.norm(v)) < 0.01


def test_progressive_http_contract_runs_one_inference_and_reuses_geometry(monkeypatch):
    import cv2
    from fastapi.testclient import TestClient

    from app.core.config import get_settings
    from app.main import create_app
    from app.services import floor_scene, model_warmup
    from app.services.floor_segmentation import FloorSegmentationResult

    labels, rgb = sample()
    release = Event()
    calls = []
    original = floor_scene.build_experimental_scene

    def builder(*args, **kwargs):
        if kwargs.get("quality_pass", True):
            assert release.wait(3)
        return original(*args, **kwargs)

    class Segmenter:
        def segment(self, image):
            calls.append(image.shape)
            return FloorSegmentationResult(
                candidate="test",
                mask=labels == 3,
                labels=labels,
                metadata={"floor_confidence": 0.95},
            )

    monkeypatch.setenv("PPAI_EXPERIMENTAL_FLOOR", "1")
    monkeypatch.setenv("PPAI_MIN_LONG_SIDE", "1")
    get_settings.cache_clear()
    monkeypatch.setattr(floor_scene, "build_experimental_scene", builder)
    monkeypatch.setattr(model_warmup, "wait_ready", lambda **_: True)
    monkeypatch.setattr(model_warmup, "segmenter_pour", lambda _: Segmenter())
    client = TestClient(create_app())
    encoded = cv2.imencode(".png", cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))[1].tobytes()
    token = None
    try:
        response = client.post(
            "/v1/analyze-room",
            files={"image": ("test.png", encoded)},
            headers={"X-Analysis-Profile": "visualizer", "X-Scene-Passes": "fast-quality"},
        )
        assert response.status_code == 200
        fast = response.json()["experimental"]["floor"]
        token = fast["sceneProvenance"]["refinement"]["token"]
        assert client.get("/v1/analyze-room/refinements/" + token).json()["status"] == "pending"
        release.set()
        for _ in range(150):
            result = client.get("/v1/analyze-room/refinements/" + token).json()
            if result["status"] != "pending":
                break
            sleep(0.01)
        assert result["status"] == "ready"
        final = result["experimental"]["floor"]
        assert len(calls) == 1
        assert fast["sceneData"]["camera"] == final["sceneData"]["camera"]
        assert fast["sceneData"]["planes"] == final["sceneData"]["planes"]
        assert final["sceneProvenance"]["pass"] == "quality"
        for floor in [fast, final]:
            layer = floor["sceneData"]["light"]["lightLayer"]
            assert layer["encoding"] == "png-rg-u16"
            assert layer["data"].startswith("data:image/png;base64,")
            assert layer["width"] == rgb.shape[1] and layer["height"] == rgb.shape[0]
            assert "meanFloorLab" in layer["colorStats"]

    finally:
        release.set()
        if token:
            client.delete("/v1/analyze-room/refinements/" + token)
            assert client.get("/v1/analyze-room/refinements/" + token).status_code == 404


def test_rejected_photo_never_runs_segmentation(monkeypatch):
    import cv2

    from app.core.config import get_settings
    from app.core.warnings import Warn
    from app.services import pipeline

    _, rgb = sample()
    monkeypatch.setenv("PPAI_EXPERIMENTAL_FLOOR", "1")
    get_settings.cache_clear()
    monkeypatch.setattr(
        pipeline.image_quality, "quality_warnings", lambda *_: [Warn.IMAGE_TOO_SMALL]
    )

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Rejected image must not invoke inference")

    monkeypatch.setattr(pipeline, "_segmentation_experimentale", forbidden)
    encoded = cv2.imencode(".png", cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))[1].tobytes()
    result = pipeline.analyse_room(encoded, fast_preview=True, progressive=True)
    assert result.result.status.value == "rejected"
    assert result.result.experimental is None


def test_high_semantic_confidence_does_not_promote_a_tiny_visible_floor():
    rgb = np.full((200, 300, 3), 150, np.uint8)
    labels = np.zeros((200, 300), np.uint8)
    labels[190:] = 3
    result = build_experimental_scene(
        labels == 3, 300, 200, labels=labels, image_rgb=rgb, floor_confidence=0.99
    )
    assert result.status not in ("auto_render", "approximate_render")


def test_discarded_work_still_counts_toward_real_worker_capacity():
    event = Event()
    started = Event()

    def work():
        started.set()
        event.wait(3)
        return {}

    a = jobs.submit(work)
    assert started.wait(1)
    b = jobs.submit(work)
    try:
        assert a and b
        jobs.discard(a)
        jobs.discard(b)
        assert jobs.submit(work) is None, "Discard must not bypass the real queue bound"
    finally:
        event.set()
    sleep(0.03)
