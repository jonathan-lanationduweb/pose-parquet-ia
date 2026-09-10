"""Application FastAPI.

Le service n'a ni base de données, ni état persistant, ni file d'attente. Il
reçoit une photo, la mesure, et l'oublie. Cette absence est un choix
d'architecture, pas un manque : les demandes des utilisateurs seront gérées
ailleurs (voir docs/architecture.md), et ce service reste un pur analyseur —
donc réplicable et remplaçable sans migration.
"""

from collections.abc import Awaitable, Callable
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from PIL import Image

from app.api import analyze, health
from app.core.config import SERVICE_NAME, get_settings
from app.core.logging import configure_logging

#: En-tête de corrélation, posé sur chaque réponse.
REQUEST_ID_HEADER = "X-Request-ID"


def create_app() -> FastAPI:
    """Construit l'application. Une fonction, pour que les tests l'isolent."""
    configure_logging()
    settings = get_settings()

    # Garde-fou anti bombe de décompression, posé une fois pour le processus :
    # Pillow refuse au-delà, sans quoi un PNG de 40 ko peut réclamer plusieurs
    # gigaoctets de mémoire au décodage.
    Image.MAX_IMAGE_PIXELS = settings.max_image_pixels

    app = FastAPI(
        title=SERVICE_NAME,
        version="0.1.0",
        summary="Analyse d'une photo de pièce pour le Visualiseur Parquet",
        description=(
            "Service d'analyse d'image. **LOT IA 0** : contrôles techniques "
            "seulement — dimensions, orientation EXIF, netteté, exposition, "
            "courbure des arêtes. Aucune segmentation, aucune profondeur, "
            "aucune `sceneData` renvoyée."
        ),
    )

    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_methods=["GET", "POST"],
            allow_headers=["*"],
        )

    @app.middleware("http")
    async def tag_request(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Attribue un identifiant à chaque requête, pour recoudre les logs.

        Un identifiant fourni par le client est repris tel quel — c'est ce qui
        permet de suivre une requête depuis le front jusqu'ici.
        """
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid4().hex[:12]
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response

    app.include_router(health.router)
    app.include_router(analyze.router)

    if settings.dev_serve_static:
        _monter_fichiers_de_dev(app)

    return app


def _monter_fichiers_de_dev(app: FastAPI) -> None:
    """Sert le visualiseur depuis ce processus — développement seulement.

    Le montage vient **après** les routes : `/health` et `/v1/*` sont résolus
    avant, et rien ne les masque. Ce qui reste tombe sur les fichiers.

    Trois dossiers, et pas la racine du dépôt : le code Python, les tests, la
    configuration et le `.git` n'ont aucune raison d'être servis, même sur un
    poste de travail. `datasets/` l'est parce que le visualiseur y lit les
    photos importées de démonstration ; c'est aussi la raison pour laquelle ce
    drapeau reste faux par défaut.
    """
    racine = Path(__file__).resolve().parent.parent
    for chemin in ("tools", "web", "datasets"):
        dossier = racine / chemin
        if dossier.is_dir():
            app.mount(f"/{chemin}", StaticFiles(directory=dossier), name=f"dev-{chemin}")


app = create_app()
