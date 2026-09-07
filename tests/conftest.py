"""Contexte commun aux tests."""

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app
from corpus import patterns
from scripts import add_photo, import_annotation

#: Dimensions du corpus de test à une seule photo. Assez grand pour que la
#: tolérance de contour la plus fine reste supérieure à un pixel.
TEST_WIDTH, TEST_HEIGHT = 600, 400


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    """Client HTTP de test, sur une application construite une seule fois."""
    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    """Vide le cache de configuration après chaque test.

    Sans cela, un test qui surcharge un seuil par variable d'environnement
    contaminerait tous les suivants — et le sens de l'échec serait ailleurs
    que la cause.
    """
    yield
    get_settings.cache_clear()


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    """Un corpus jetable à une photo `hard`, prêt à recevoir des annotations.

    Partagé par les tests d'accord et de campagne : les deux ont besoin d'une
    photo réelle sur disque, d'un manifeste valide et d'une difficulté connue,
    et dupliquer ce montage ferait dériver les deux copies.
    """
    root = tmp_path / "datasets"
    (root / "private-real").mkdir(parents=True)
    (root / "manifest.json").write_text(
        json.dumps({"schema": "pose-parquet-ai/dataset@2", "photos": []}), encoding="utf-8"
    )
    (root / "private-real" / "p.png").write_bytes(
        patterns.encode(patterns.mid_tone_checkerboard((TEST_WIDTH, TEST_HEIGHT)), "PNG")
    )
    assert (
        add_photo.main(
            [
                "--dataset",
                str(root),
                "--file",
                "private-real/p.png",
                "--id",
                "p1",
                "--difficulty",
                "hard",
                "--source",
                "test",
                "--license",
                "aucune",
                "--verified-on",
                "2026-09-07",
                "--traits",
                "rug,thin_furniture_legs",
            ]
        )
        == 0
    )
    return root


def draw_file(root: Path, top: float) -> Path:
    """Écrit un tracé d'outil couvrant le bas de l'image à partir de `top`.

    Deux valeurs de `top` proches simulent deux passes qui divergent sur la
    seule jonction — le désaccord le plus courant entre deux relevés.
    """
    draw = {
        "schema": import_annotation.DRAW_SCHEMA,
        "photoId": "p1",
        "width": TEST_WIDTH,
        "height": TEST_HEIGHT,
        "floorPolygons": [
            [
                {"x": 0.0, "y": top},
                {"x": 1.0, "y": top},
                {"x": 1.0, "y": 1.0},
                {"x": 0.0, "y": 1.0},
            ]
        ],
        "drawSeconds": 240,
    }
    path = root / f"p1-{top}.draw.json"
    path.write_text(json.dumps(draw), encoding="utf-8")
    return path
