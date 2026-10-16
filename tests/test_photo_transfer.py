"""Exercise the real phone mailbox, including expiry and image delivery."""

from io import BytesIO
from time import monotonic

from fastapi.testclient import TestClient
from PIL import Image

from app.api import photo_transfer
from app.main import create_app


def photo_bytes():
    out = BytesIO()
    Image.new("RGB", (320, 240), (160, 120, 80)).save(out, "JPEG")
    return out.getvalue()


def create(client):
    response = client.post("/v1/photo-transfers", json={"origin": "https://visualiseur.example"})
    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    t = response.json()
    return t, f"/v1/photo-transfers/{t['id']}", {"X-Transfer-Key": t["ownerKey"]}


def test_phone_to_pc_and_delete():
    with TestClient(create_app()) as client:
        transfer, path, headers = create(client)
        assert transfer["phoneUrl"].endswith(f"/tools/phone-upload.html#{transfer['id']}")
        assert client.get(path, headers=headers).json() == {"status": "waiting"}
        assert client.get(path + "/photo", headers=headers).status_code == 204
        assert client.put(path + "/photo", content=photo_bytes()).status_code == 204
        assert client.get(path, headers=headers).json() == {"status": "ready"}
        response = client.get(path + "/photo", headers=headers)
        assert response.headers["content-type"] == "image/jpeg"
        assert Image.open(BytesIO(response.content)).size == (320, 240)
        assert client.delete(path, headers=headers).status_code == 204
        assert client.get(path, headers=headers).status_code == 404
        assert client.put(path + "/photo", content=photo_bytes()).status_code == 404


def test_private_receiver_and_single_upload():
    with TestClient(create_app()) as client:
        _, path, headers = create(client)
        for suffix in ["", "/photo", "/qr.svg"]:
            assert client.get(path + suffix).status_code == 404
            assert client.get(path + suffix, headers={"X-Transfer-Key": "other"}).status_code == 404
        assert client.delete(path).status_code == 404
        assert client.put(path + "/photo", content=photo_bytes()).status_code == 204
        assert client.put(path + "/photo", content=photo_bytes()).status_code == 409
        assert (
            client.get(path + "/qr.svg", headers=headers)
            .headers["content-type"]
            .startswith("image/svg+xml")
        )


def test_invalid_and_oversized_photo(monkeypatch):
    with TestClient(create_app()) as client:
        _, path, _ = create(client)
        assert client.put(path + "/photo", content=b"not an image").status_code == 422
        monkeypatch.setattr(photo_transfer, "MAX_BYTES", 20)
        assert client.put(path + "/photo", content=photo_bytes()).status_code == 413


def test_expiry_and_capacity(monkeypatch):
    with TestClient(create_app()) as client:
        transfer, path, headers = create(client)
        client.app.state.photo_transfers.items[transfer["id"]].expires = monotonic() - 1
        assert client.get(path, headers=headers).status_code == 404
        assert not client.app.state.photo_transfers.items
        monkeypatch.setattr(photo_transfer, "MAX_SESSIONS", 1)
        create(client)
        assert (
            client.post(
                "/v1/photo-transfers", json={"origin": "https://visualiseur.example"}
            ).status_code
            == 429
        )


def test_store_clears_at_shutdown():
    app = create_app()
    with TestClient(app) as client:
        create(client)
    assert not app.state.photo_transfers.items


def test_origin_is_a_web_origin():
    with TestClient(create_app()) as client:
        for origin in [
            "javascript:alert(1)",
            "file:///photo",
            "https://user:pass@example.org",
            "https://example.org/x",
            "http://[",
        ]:
            assert client.post("/v1/photo-transfers", json={"origin": origin}).status_code == 422


def test_pc_keepalive_has_no_fixed_ten_minute_deadline():
    with TestClient(create_app()) as client:
        t, path, headers = create(client)
        item = client.app.state.photo_transfers.items[t["id"]]
        item.expires = monotonic() + 2
        assert client.get(path, headers=headers).status_code == 200
        assert item.expires > monotonic() + 590


def test_local_qr_uses_configured_public_origin(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("PPAI_PUBLIC_URL", "https://test-public.example")
    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as client:
            r = client.post("/v1/photo-transfers", json={"origin": "http://127.0.0.1:8000"})
            assert r.status_code == 201
            assert r.json()["phoneUrl"].startswith(
                "https://test-public.example/tools/phone-upload.html#"
            )
    finally:
        get_settings.cache_clear()
