"""Préchauffage du candidat expérimental et `/health` — LOT PHOTO.2.

Ce que ces tests protègent : que `/health` ne change pas sans le drapeau, qu'il
réponde PENDANT un préchauffage lent, et qu'il dise `ready` ou `error` ensuite.
Aucun modèle appris n'est chargé : le candidat `opencv` ou un faux lent suffit.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app
from app.services import model_warmup


@pytest.fixture(autouse=True)
def _neuf() -> Iterator[None]:
    get_settings.cache_clear()
    model_warmup._reset_for_tests()
    yield
    model_warmup.wait_ready(timeout=10)
    model_warmup._reset_for_tests()
    get_settings.cache_clear()


def test_sans_le_drapeau_health_est_inchange(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PPAI_EXPERIMENTAL_FLOOR", "0")
    with TestClient(create_app()) as client:
        assert client.get("/health").json() == {"status": "ok", "service": "pose-parquet-ai"}
    assert model_warmup.status() == "disabled"


def test_health_repond_pendant_le_prechauffage(monkeypatch: pytest.MonkeyPatch) -> None:
    """Le point du lot : le serveur répond pendant que le modèle se charge."""
    monkeypatch.setenv("PPAI_EXPERIMENTAL_FLOOR", "1")
    monkeypatch.setenv("PPAI_EXPERIMENTAL_FLOOR_CANDIDATE", "opencv")
    libere = threading.Event()

    class Lent:
        def segment(self, _image: object) -> None:
            libere.wait(5)

    monkeypatch.setattr(model_warmup, "segmenter_pour", lambda _c: Lent())
    with TestClient(create_app()) as client:
        t0 = time.perf_counter()
        corps = client.get("/health").json()
        assert time.perf_counter() - t0 < 1.0, "la santé ne bloque pas"
        assert corps["experimentalFloor"] == "loading"
        libere.set()
        assert model_warmup.wait_ready(timeout=5)
        assert client.get("/health").json()["experimentalFloor"] == "ready"


def test_un_prechauffage_qui_echoue_se_dit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PPAI_EXPERIMENTAL_FLOOR", "1")

    class Casse:
        def segment(self, _image: object) -> None:
            raise RuntimeError("panne simulée")

    monkeypatch.setattr(model_warmup, "segmenter_pour", lambda _c: Casse())
    with TestClient(create_app()) as client:
        assert model_warmup.wait_ready(timeout=5)
        corps = client.get("/health").json()
        assert corps["experimentalFloor"] == "error"
        assert "panne" not in str(corps), "aucun détail d'erreur dans la santé"


def test_le_prechauffage_ne_se_lance_qu_une_fois(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PPAI_EXPERIMENTAL_FLOOR", "1")
    monkeypatch.setenv("PPAI_EXPERIMENTAL_FLOOR_CANDIDATE", "opencv")
    assert model_warmup.start_warmup("opencv") is True
    assert model_warmup.start_warmup("opencv") is False
    assert model_warmup.wait_ready(timeout=10)
    assert model_warmup.report()["timingsMs"]["total"] >= 0
