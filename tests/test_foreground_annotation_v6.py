"""Synthetic UI/storage fixtures; never presented as human foreground GT."""

import copy
from threading import Thread

import httpx
import numpy as np
import pytest
from PIL import Image

from scripts.foreground_annotation_v6 import SCHEMA, AnnotationServer, masks, validate


@pytest.fixture
def server(tmp_path):
    photo = tmp_path / "sources/sofa/01-original.png"
    photo.parent.mkdir(parents=True)
    Image.new("RGB", (32, 24), (180, 180, 180)).save(photo)
    app = AnnotationServer(("127.0.0.1", 0), tmp_path / "sources", tmp_path / "private")
    thread = Thread(target=app.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{app.server_port}"
    with httpx.Client(base_url=origin, headers={"Origin": origin}) as client:
        yield app, client
    app.shutdown()
    app.server_close()
    thread.join(timeout=2)


def record(scene):
    return {
        "schema": SCHEMA,
        "scene": scene["id"],
        "sourceSha256": scene["sha256"],
        "width": 32,
        "height": 24,
        "annotator": "synthetic-test-fixture",
        "status": "reviewed-regions",
        "humanConfirmed": True,
        "emptySceneConfirmed": False,
        "objects": [
            {
                "id": "test-object",
                "category": "thin-leg",
                "region": [3, 2, 20, 22],
                "reviewed": True,
                "notes": "synthetic only",
                "drawings": [
                    {
                        "mode": "foreground",
                        "kind": "polygon",
                        "radius": 1,
                        "points": [[7, 5], [12, 5], [12, 19], [7, 19]],
                    }
                ],
            }
        ],
    }


def test_new_real_annotation_starts_null_and_no_files(server):
    app, client = server
    assert client.get("/api/annotation/sofa").json() is None
    assert not app.private.exists()
    assert len(client.get("/api/manifest").json()["scenes"]) == 1


def test_draft_is_not_gt_and_reviewed_exports_binary_source_masks(server):
    app, client = server
    payload = record(app.scenes["sofa"])
    draft = {**payload, "status": "draft", "humanConfirmed": False}
    assert client.post("/api/annotation/sofa", json=draft).status_code == 200
    assert not list(app.private.rglob("*.png"))
    assert client.get("/api/annotation/sofa").json()["maskRevision"] is None
    assert client.post("/api/annotation/sofa", json=payload).status_code == 200
    saved = client.get("/api/annotation/sofa").json()
    folder = app.private / "sofa/revisions" / saved["maskRevision"]
    assert saved["scope"] == "reviewed-regions-only"
    foreground = np.asarray(Image.open(folder / "foreground.png"))
    valid = np.asarray(Image.open(folder / "valid.png"))
    assert foreground.shape == (24, 32)
    assert set(np.unique(foreground)) == {0, 255}
    assert foreground[8, 9] == 255 and foreground[8, 22] == 0
    assert valid[8, 9] == 255 and valid[0, 0] == 0
    # Returning to draft cannot silently keep a reference to approved GT.
    assert client.post("/api/annotation/sofa", json=draft).status_code == 200
    assert client.get("/api/annotation/sofa").json()["maskRevision"] is None


@pytest.mark.parametrize(
    "patch",
    [
        {"humanConfirmed": False},
        {"annotator": ""},
        {"sourceSha256": "wrong"},
        {"width": 31},
        {"status": "approved-by-ai"},
        {"objects": []},
    ],
)
def test_reject_unconfirmed_stale_or_invalid_gt(server, patch):
    app, client = server
    payload = {**record(app.scenes["sofa"]), **patch}
    assert client.post("/api/annotation/sofa", json=payload).status_code == 400
    assert not list(app.private.rglob("*.png"))


def test_invalid_later_object_leaves_previous_revision_unchanged(server):
    app, client = server
    payload = record(app.scenes["sofa"])
    assert client.post("/api/annotation/sofa", json=payload).status_code == 200
    saved = client.get("/api/annotation/sofa").json()
    files = {str(p): p.read_bytes() for p in app.private.rglob("*") if p.is_file()}
    bad = copy.deepcopy(payload)
    bad["objects"][0]["drawings"][0]["points"][0] = [4, 4]
    second = copy.deepcopy(payload["objects"][0])
    second["id"] = "another-object"
    second["region"] = [25, 2, 30, 20]  # no foreground in this reviewed region
    bad["objects"].append(second)
    assert client.post("/api/annotation/sofa", json=bad).status_code == 400
    assert client.get("/api/annotation/sofa").json() == saved
    assert files == {str(p): p.read_bytes() for p in app.private.rglob("*") if p.is_file()}


def test_foreign_origins_and_private_path_traversal_are_refused(server):
    app, client = server
    payload = record(app.scenes["sofa"])
    assert (
        client.post(
            "/api/annotation/sofa", json=payload, headers={"Origin": "https://example.com"}
        ).status_code
        == 403
    )
    assert client.get("/photo/../private/annotation.json").status_code == 404
    assert client.get("/datasets/private-real/anything").status_code == 404
    assert client.get("/photo/sofa", headers={"Host": "untrusted.example"}).status_code == 403
    assert client.get("/photo/sofa").headers["content-type"] == "image/png"
    assert client.get("/").status_code == 200


def test_unknown_pixels_and_holes_remain_excluded():
    scene = {"id": "test", "sha256": "hash", "width": 32, "height": 24}
    payload = record(scene)
    obj = payload["objects"][0]
    obj["drawings"] += [
        {"kind": "brush", "mode": "uncertain", "radius": 1, "points": [[9, 8], [9, 11]]},
        {
            "kind": "polygon",
            "mode": "erase",
            "radius": 1,
            "points": [[8, 15], [11, 15], [11, 17], [8, 17]],
        },
    ]
    fg, valid, unsure = masks(payload, obj)
    assert unsure[9, 9] and not fg[9, 9] and not valid[9, 9]
    assert not fg[16, 9] and valid[16, 9]
    assert fg[6, 9]


def test_explicit_empty_scene_and_uncertainty_union(server):
    app, client = server
    payload = record(app.scenes["sofa"])
    payload["objects"] = []
    payload["emptySceneConfirmed"] = True
    assert client.post("/api/annotation/sofa", json=payload).status_code == 200
    saved = client.get("/api/annotation/sofa").json()
    folder = app.private / "sofa/revisions" / saved["maskRevision"]
    assert not np.asarray(Image.open(folder / "foreground.png")).any()
    assert np.asarray(Image.open(folder / "valid.png")).all()
    payload = record(app.scenes["sofa"])
    second = copy.deepcopy(payload["objects"][0])
    second["id"] = "second-object"
    second["drawings"].append(
        {"kind": "brush", "mode": "uncertain", "radius": 1, "points": [[9, 8], [9, 11]]}
    )
    payload["objects"].append(second)
    assert client.post("/api/annotation/sofa", json=payload).status_code == 200
    saved = client.get("/api/annotation/sofa").json()
    folder = app.private / "sofa/revisions" / saved["maskRevision"]
    assert np.asarray(Image.open(folder / "valid.png"))[9, 9] == 0
    assert np.asarray(Image.open(folder / "foreground.png"))[9, 9] == 0


def test_reject_nan_path_injection_and_unreviewed_object():
    scene = {"id": "test", "sha256": "hash", "width": 32, "height": 24}
    for mutate in ["nan", "path", "review"]:
        payload = record(scene)
        if mutate == "nan":
            payload["objects"][0]["drawings"][0]["points"][0][0] = float("nan")
        if mutate == "path":
            payload["objects"][0]["id"] = "../../outside"
        if mutate == "review":
            payload["objects"][0]["reviewed"] = False
        with pytest.raises(ValueError):
            validate(payload, scene)


def test_pixel_center_raster_has_no_extra_polygon_row_or_thin_leg_width():
    scene = {"id": "test", "sha256": "hash", "width": 32, "height": 24}
    payload = record(scene)
    obj = payload["objects"][0]
    fg, _, _ = masks(payload, obj)
    assert fg.sum() == 5 * 14  # [7,12) x [5,19), source pixel centres
    obj["drawings"] = [
        {
            "kind": "brush",
            "mode": "foreground",
            "radius": 0.5,
            "points": [[10.5, 5.5], [10.5, 15.5]],
        }
    ]
    fg, _, _ = masks(payload, obj)
    assert fg[:, 10].sum() == 11
    assert not fg[:, 9].any() and not fg[:, 11].any()


def test_empty_confirmation_cannot_contradict_existing_objects():
    scene = {"id": "test", "sha256": "hash", "width": 32, "height": 24}
    payload = record(scene)
    payload["emptySceneConfirmed"] = True
    with pytest.raises(ValueError, match="déclarée vide"):
        validate(payload, scene)
