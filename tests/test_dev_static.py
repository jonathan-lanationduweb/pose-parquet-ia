"""Le service sert-il des fichiers, et à quelles conditions — LOT AI.INT.1.

Un analyseur d'images qui se met à servir des fichiers gagne un rôle qu'on ne
lui a pas demandé : une surface d'attaque, et un chemin devinable vers
`datasets/private-real/`. Le confort de n'avoir qu'un serveur en
développement le justifie ; l'avoir par défaut, non.

Ces tests verrouillent donc les deux moitiés de la décision : **rien n'est
servi par défaut**, et ce qui est servi quand on le demande explicitement se
limite à trois dossiers — le code Python, les tests et la configuration
restent hors d'atteinte.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


@pytest.fixture(autouse=True)
def _reglages_neufs() -> Iterator[None]:
    """Les réglages sont mis en cache pour le processus : on le vide autour."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_le_defaut_du_reglage_est_faux() -> None:
    """Le défaut est l'analyseur nu, et c'est ce défaut qui va en production.

    Vérifié sur la classe avec le fichier d'environnement neutralisé : un
    `.env` de poste de travail ne doit pas pouvoir faire passer ce test pour
    la mauvaise raison.
    """
    from app.core.config import Settings

    #  est un parametre de pydantic-settings, pas un champ du
    # modele : mypy ne le connait pas, et l'ignorer ici est plus honnete que
    # d'elargir la signature de la configuration pour un test.
    assert Settings(_env_file=None).dev_serve_static is False  # type: ignore[call-arg]


def test_regle_a_faux_aucun_fichier_n_est_servi(monkeypatch: pytest.MonkeyPatch) -> None:
    """Et l'application respecte ce réglage."""
    monkeypatch.setenv("PPAI_DEV_SERVE_STATIC", "0")
    client = TestClient(create_app())

    assert client.get("/health").status_code == 200, "l'API, elle, répond"
    assert client.get("/tools/product-concept.html").status_code == 404
    assert client.get("/web/product/local-renderer.js").status_code == 404


def test_en_developpement_le_visualiseur_est_servi(monkeypatch: pytest.MonkeyPatch) -> None:
    """Une seule commande pour l'interface et l'analyse, donc aucun CORS."""
    monkeypatch.setenv("PPAI_DEV_SERVE_STATIC", "1")
    client = TestClient(create_app())

    assert client.get("/tools/product-concept.html").status_code == 200
    assert client.get("/web/product/local-renderer.js").status_code == 200
    assert client.get("/web/product/room-analysis-client.js").status_code == 200
    # Et l'API n'est pas masquée par le montage : elle est déclarée avant.
    assert client.get("/health").json()["status"] == "ok"


def test_le_code_du_service_n_est_jamais_servi(monkeypatch: pytest.MonkeyPatch) -> None:
    """Trois dossiers, pas la racine du dépôt.

    La faute qu'on évite ici est banale et coûteuse : monter `.` pour aller
    vite, et publier du même geste la configuration, les tests, et l'historique
    Git.
    """
    monkeypatch.setenv("PPAI_DEV_SERVE_STATIC", "1")
    client = TestClient(create_app())

    for interdit in (
        "/app/main.py",
        "/app/core/config.py",
        "/tests/conftest.py",
        "/pyproject.toml",
        "/.env",
    ):
        assert client.get(interdit).status_code == 404, interdit


def test_aucune_origine_cors_par_defaut(monkeypatch: pytest.MonkeyPatch) -> None:
    """`*` n'est jamais le défaut, et n'est jamais écrit nulle part."""
    monkeypatch.delenv("PPAI_CORS_ORIGINS", raising=False)
    settings = get_settings()
    assert settings.cors_origin_list == []

    client = TestClient(create_app())
    reponse = client.get("/health", headers={"Origin": "http://exemple.invalide"})
    assert "access-control-allow-origin" not in {k.lower() for k in reponse.headers}


def test_les_origines_de_developpement_sont_nommees(monkeypatch: pytest.MonkeyPatch) -> None:
    """Deux origines nommées, et l'une d'elles seulement obtient l'en-tête."""
    monkeypatch.setenv("PPAI_CORS_ORIGINS", "http://localhost:8801,http://127.0.0.1:8801")
    client = TestClient(create_app())

    permise = client.get("/health", headers={"Origin": "http://localhost:8801"})
    assert permise.headers.get("access-control-allow-origin") == "http://localhost:8801"

    refusee = client.get("/health", headers={"Origin": "http://ailleurs.invalide"})
    assert refusee.headers.get("access-control-allow-origin") != "*"
