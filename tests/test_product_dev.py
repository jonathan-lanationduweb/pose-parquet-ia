"""Le preset local active le produit sans exposer le service sur le réseau."""

import sys

from scripts import product_dev


def test_product_dev_preset(monkeypatch):
    monkeypatch.setattr(product_dev, "port_is_available", lambda _port: True)
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


def test_existing_product_server_is_reused(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["product_dev"])
    monkeypatch.setattr(product_dev, "port_is_available", lambda _port: False)
    monkeypatch.setattr(product_dev, "is_product_server", lambda _port: True)
    monkeypatch.setattr(
        product_dev.uvicorn,
        "run",
        lambda *_a, **_kw: (_ for _ in ()).throw(AssertionError("Second server started")),
    )
    product_dev.main()
    assert "déjà démarré" in capsys.readouterr().out


def test_other_service_is_not_treated_as_product(monkeypatch, capsys):
    import pytest

    monkeypatch.setattr(sys, "argv", ["product_dev"])
    monkeypatch.setattr(product_dev, "port_is_available", lambda _port: False)
    monkeypatch.setattr(product_dev, "is_product_server", lambda _port: False)
    with pytest.raises(SystemExit) as error:
        product_dev.main()
    assert error.value.code == 2
    assert "autre service" in capsys.readouterr().err
