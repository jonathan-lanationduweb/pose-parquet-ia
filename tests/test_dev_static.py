"""Le service sert-il des fichiers, et à quelles conditions — LOT AI.INT.1.

Un analyseur d'images qui se met à servir des fichiers gagne un rôle qu'on ne
lui a pas demandé : une surface d'attaque, et un chemin devinable vers
`datasets/private-real/`. Le confort de n'avoir qu'un serveur en
développement le justifie ; l'avoir par défaut, non.

Ces tests verrouillent donc les deux moitiés de la décision : **rien n'est
servi par défaut**, et ce qui est servi quand on le demande explicitement se
limite à une liste blanche — le code Python, les tests, la configuration et
**les photos privées** restent hors d'atteinte.

Correction du 29 septembre 2026 : le montage servait `datasets/` en entier, et
donc `datasets/private-real/`. Un `GET` sur une photo de domicile répondait
200. `test_les_photos_privees_ne_sont_jamais_servies` est la garde qui manquait
— elle vaut plus que la correction elle-même, parce qu'un dossier se remonte
un jour par commodité et que personne ne s'en souvient.
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


def test_les_photos_privees_ne_sont_jamais_servies(monkeypatch: pytest.MonkeyPatch) -> None:
    """La garde qui manquait, et la seule qui compte vraiment ici.

    Une photo de domicile n'est pas une ressource de développement. Le drapeau
    peut être levé sur un poste partagé, sur une machine exposée au réseau
    local, dans un conteneur avec un port publié : aucune de ces situations ne
    doit rendre `private-real/` atteignable.
    """
    monkeypatch.setenv("PPAI_DEV_SERVE_STATIC", "1")
    client = TestClient(create_app())

    for interdit in (
        "/datasets/private-real/chambre.jpg",
        "/datasets/private-real/",
        "/datasets/annotations/",
        "/datasets/",
    ):
        assert client.get(interdit).status_code == 404, interdit


def test_la_liste_blanche_est_la_liste_complete() -> None:
    """Le mécanisme est l'absence, pas un filtre.

    Vérifier la constante plutôt que seulement ses effets : un dossier ajouté
    ici sans y penser fera tomber ce test, et c'est exactement le moment où
    l'on veut relire la décision.
    """
    from app.main import DOSSIERS_DE_DEV

    assert DOSSIERS_DE_DEV == ("tools", "web")
    assert "datasets" not in DOSSIERS_DE_DEV


def test_la_documentation_est_fermee_hors_developpement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """En production le service n'a qu'un client connu : sa carte est inutile."""
    monkeypatch.setenv("PPAI_DEV_SERVE_STATIC", "0")
    client = TestClient(create_app())

    for ferme in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(ferme).status_code == 404, ferme
    assert client.get("/health").status_code == 200, "l'API reste entière"


def test_la_documentation_est_ouverte_en_developpement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sur un poste de travail, elle reste ce qu'elle a de mieux à être."""
    monkeypatch.setenv("PPAI_DEV_SERVE_STATIC", "1")
    client = TestClient(create_app())

    assert client.get("/openapi.json").status_code == 200
    assert client.get("/docs").status_code == 200


def test_les_en_tetes_de_securite_sont_sur_chaque_reponse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Y compris sur une erreur : un 404 se sniffe aussi bien qu'un 200.

    Pas de CSP dans cette liste, et le rapport le dit : elle attend que le
    script du visualiseur sorte du HTML. Une CSP avec `unsafe-inline` aurait
    fait passer ce test sans rien protéger.
    """
    monkeypatch.setenv("PPAI_DEV_SERVE_STATIC", "0")
    client = TestClient(create_app())

    for chemin in ("/health", "/inexistant"):
        entetes = client.get(chemin).headers
        assert entetes["X-Content-Type-Options"] == "nosniff", chemin
        assert entetes["Referrer-Policy"] == "no-referrer", chemin
        assert entetes["X-Frame-Options"] == "DENY", chemin
        assert "content-security-policy" not in {k.lower() for k in entetes}
