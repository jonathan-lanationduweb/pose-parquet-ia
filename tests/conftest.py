"""Contexte commun aux tests."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


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
