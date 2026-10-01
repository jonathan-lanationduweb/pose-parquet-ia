"""Application FastAPI.

Le service n'a ni base de données, ni état persistant, ni file d'attente. Il
reçoit une photo, la mesure, et l'oublie. Cette absence est un choix
d'architecture, pas un manque : les demandes des utilisateurs seront gérées
ailleurs (voir docs/architecture.md), et ce service reste un pur analyseur —
donc réplicable et remplaçable sans migration.
"""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from PIL import Image
from starlette.types import Scope

from app.api import analyze, health
from app.core.config import SERVICE_NAME, get_settings
from app.core.logging import configure_logging
from app.services import model_warmup

#: En-tête de corrélation, posé sur chaque réponse.
REQUEST_ID_HEADER = "X-Request-ID"

#: En-têtes posés sur chaque réponse.
#:
#: Trois seulement, et chacun répond à une question précise :
#:
#:   nosniff        un JSON que le navigateur déciderait de lire comme du
#:                  HTML est un XSS ; l'en-tête interdit la devinette ;
#:   no-referrer    une photo de domicile s'analyse à une URL qui n'a pas à
#:                  voyager dans le `Referer` d'une requête suivante ;
#:   DENY           ce service n'a aucune raison d'être encadré ailleurs.
#:
#: **Pas de Content-Security-Policy ici, et c'est délibéré.** Le visualiseur
#: servi en développement porte aujourd'hui son script en ligne — trois mille
#: lignes dans `tools/product-concept.html`. Une CSP honnête les refuserait et
#: casserait la page ; une CSP avec `unsafe-inline` ne protégerait de rien tout
#: en cochant la case. La politique arrivera quand le code en ligne sera sorti
#: du HTML : voir `CSP_DEFERRED_UNTIL_INLINE_CODE_REMOVED` dans
#: docs/architecture.md.
#: Les seuls dossiers que le montage de développement peut servir.
#:
#: `datasets/` n'y est pas : il contient `private-real/`, c'est-à-dire des
#: photos de domicile. Voir `_monter_fichiers_de_dev`.
DOSSIERS_DE_DEV: tuple[str, ...] = ("tools", "web")

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
}


def create_app() -> FastAPI:
    """Construit l'application. Une fonction, pour que les tests l'isolent."""
    configure_logging()
    settings = get_settings()

    # Garde-fou anti bombe de décompression, posé une fois pour le processus :
    # Pillow refuse au-delà, sans quoi un PNG de 40 ko peut réclamer plusieurs
    # gigaoctets de mémoire au décodage.
    Image.MAX_IMAGE_PIXELS = settings.max_image_pixels

    # La documentation interactive est une carte de l'API : utile sur un poste
    # de travail, inutile à un service qui n'a qu'un seul client connu. Elle
    # suit donc le même drapeau que les fichiers statiques — le drapeau « je
    # suis sur une machine de développement ».
    exposer_docs = settings.dev_serve_static

    @asynccontextmanager
    async def cycle_de_vie(_app: FastAPI) -> AsyncIterator[None]:
        """Préchauffe le candidat expérimental SANS bloquer le démarrage.

        LOT PHOTO.2 : le chargement du modèle et sa première inférence
        coûtaient 37 à 95 s à la première photo. Ils partent ici dans un fil
        d'arrière-plan ; uvicorn accepte les requêtes aussitôt, et `/health`
        dit où en est le préchauffage.
        """
        reglages = get_settings()
        if reglages.experimental_floor and reglages.experimental_floor_warmup:
            model_warmup.start_warmup(reglages.experimental_floor_candidate)
        yield

    app = FastAPI(
        lifespan=cycle_de_vie,
        title=SERVICE_NAME,
        version="0.1.0",
        docs_url="/docs" if exposer_docs else None,
        redoc_url="/redoc" if exposer_docs else None,
        openapi_url="/openapi.json" if exposer_docs else None,
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
        for nom, valeur in SECURITY_HEADERS.items():
            response.headers.setdefault(nom, valeur)
        return response

    app.include_router(health.router)
    app.include_router(analyze.router)

    if settings.dev_serve_static:
        _monter_fichiers_de_dev(app)

    return app


class _FichiersDeDev(StaticFiles):
    """`StaticFiles`, sans cache de navigateur.

    Starlette envoie `etag` et `last-modified` mais aucun `cache-control` :
    le navigateur applique alors sa fraîcheur heuristique et peut servir un
    module JS depuis son cache sans rien redemander. Sur un poste de travail
    c'est une perte de temps déguisée en mystère — on modifie un fichier, la
    page ne change pas, et l'on cherche le bug dans le code.

    Le cas s'est produit pendant le LOT PERF.1 : une instrumentation posée
    dans `web/scene/renderer.js` n'apparaissait dans aucune mesure parce que
    le navigateur exécutait encore la version précédente.

    `no-store` ne concerne que ce montage, qui n'existe qu'en développement.
    """

    #: Ce qu'on réécrit sans cesse, et qu'on veut donc toujours relire.
    CODE = (".js", ".css", ".html", ".json", ".mjs")

    def is_not_modified(self, *_args: object, **_kwargs: object) -> bool:
        """Jamais « non modifié » : on veut toujours l'octet frais."""
        return False

    async def get_response(self, path: str, scope: Scope) -> Response:
        reponse = await super().get_response(path, scope)
        # Le code seulement. Les photos de scène et les vignettes produit ne
        # changent pas pendant qu'on développe, elles pèsent deux cents kilo-
        # octets, et les redemander à chaque rechargement fausse toute mesure
        # de démarrage — c'est arrivé en mesurant ce lot : le premier rendu
        # variait de 154 à 1 694 ms selon que le préchauffage avait eu ou non
        # le temps de partir.
        if path.lower().endswith(self.CODE):
            reponse.headers["Cache-Control"] = "no-store, must-revalidate"
        return reponse


def _monter_fichiers_de_dev(app: FastAPI) -> None:
    """Sert le visualiseur depuis ce processus — développement seulement.

    Le montage vient **après** les routes : `/health` et `/v1/*` sont résolus
    avant, et rien ne les masque. Ce qui reste tombe sur les fichiers.

    ## Liste blanche, et une seule ligne à lire pour la vérifier

    `DOSSIERS_DE_DEV` est la liste complète de ce qui peut être servi. Le code
    Python, les tests, la configuration, `.git` et **les photos privées** n'y
    sont pas, et l'absence est le mécanisme : il n'y a pas de filtre à
    contourner, il y a des dossiers qui ne sont jamais montés.

    ## `datasets/` a été retiré, et c'était un vrai trou

    Le montage précédent servait `datasets/` en entier, donc
    `GET /datasets/private-real/chambre.jpg` renvoyait 200 et 175 ko de photo
    de domicile à quiconque devinait le nom. Le drapeau était faux par défaut,
    la porte n'en existait pas moins. Le visualiseur n'en avait pas besoin :
    ses images viennent de `web/assets/` et de `tools/local-demo-assets/`.

    Si un jour un corpus doit être servi, ce sera `datasets/public/` nommé
    explicitement ici — jamais le dossier parent.
    """
    racine = Path(__file__).resolve().parent.parent
    for chemin in DOSSIERS_DE_DEV:
        dossier = racine / chemin
        if dossier.is_dir():
            app.mount(f"/{chemin}", _FichiersDeDev(directory=dossier), name=f"dev-{chemin}")


app = create_app()
