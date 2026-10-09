"""Le preset local active le produit sans exposer le service sur le réseau."""
import sys

from scripts import product_dev


def test_product_dev_preset(monkeypatch):
    env = {}
    monkeypatch.setattr(product_dev.os, "environ", env)
    monkeypatch.setattr(sys, "argv", ["product_dev", "--port", "8143", "--candidate", "opencv"])
    calls = []
    monkeypatch.setattr(product_dev.uvicorn, "run", lambda *a, **kw: calls.append((a, kw)))
    product_dev.main()
    assert env["PPAI_DEV_SERVE_STATIC"] == "1"
    assert env["PPAI_EXPERIMENTAL_FLOOR"] == "1"
    assert env["PPAI_EXPERIMENTAL_FLOOR_WARMUP"] == "1"
    assert env["PPAI_EXPERIMENTAL_FLOOR_CANDIDATE"] == "opencv"
    assert calls == [(("app.main:app",), {"host": "127.0.0.1", "port": 8143})]
