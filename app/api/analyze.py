"""POST /v1/analyze-room — contrôles techniques d'une photo de pièce.

**Ce que fait cet endpoint aujourd'hui, exactement :** il valide et redresse
la photo, mesure sa qualité, mesure la courbure de ses arêtes verticales, et
renvoie ces mesures. Il ne cherche pas le sol, n'estime aucune profondeur,
aucune perspective, et ne renvoie donc **jamais** de `sceneData`. Le statut
`analysis_incomplete` le dit, et le nom de l'endpoint est déjà celui de la
version complète pour que le contrat ne bouge pas quand elle arrivera.

La photo n'est ni écrite sur le disque ni conservée : elle est lue en mémoire,
analysée, et les octets sont oubliés à la fin de la requête.
"""

from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from starlette.concurrency import run_in_threadpool

from app.core.config import ALLOWED_MIME_TYPES, get_settings
from app.core.errors import ImageRejected, too_large
from app.core.logging import get_logger
from app.schemas.analysis import AnalysisResult
from app.services.pipeline import analyse_room

router = APIRouter(prefix="/v1", tags=["analyse"])
log = get_logger("api.analyze")

#: Taille des morceaux lus. La lecture est plafonnée en cours de route : un
#: client qui annonce 5 Mo et en envoie 5 Go ne doit pas remplir la mémoire
#: avant qu'on s'en aperçoive.
_CHUNK_BYTES = 256 * 1024

#: Formats annoncés dans la documentation OpenAPI.
_ACCEPTED = ", ".join(ALLOWED_MIME_TYPES)


async def _read_capped(upload: UploadFile, limit: int) -> bytes:
    """Lit l'upload sans jamais dépasser `limit` octets en mémoire."""
    chunks: list[bytes] = []
    total = 0
    while chunk := await upload.read(_CHUNK_BYTES):
        total += len(chunk)
        if total > limit:
            raise too_large(limit)
        chunks.append(chunk)
    return b"".join(chunks)


@router.post(
    "/analyze-room",
    response_model=AnalysisResult,
    summary="Contrôles techniques d'une photo de pièce",
    responses={
        413: {"description": "Fichier trop volumineux"},
        415: {"description": f"Format non pris en charge ; acceptés : {_ACCEPTED}"},
        422: {"description": "Fichier vide ou image indécodable"},
    },
)
async def analyze_room(
    request: Request,
    image: Annotated[UploadFile, File(description="Photo de la pièce : JPEG, PNG ou WebP")],
) -> AnalysisResult:
    """Analyse une photo et renvoie ses mesures techniques."""
    settings = get_settings()
    request_id = getattr(request.state, "request_id", None)

    try:
        data = await _read_capped(image, settings.max_upload_bytes)
        # Le pipeline est purement calculatoire : le sortir de la boucle
        # d'événements évite qu'une photo de 20 Mo bloque toutes les autres
        # requêtes pendant son analyse.
        analysis = await run_in_threadpool(analyse_room, data)
    except ImageRejected as rejected:
        log.info("photo refusée", extra={"request_id": request_id, "reason": rejected.code})
        raise HTTPException(
            status_code=rejected.http_status,
            detail={"code": rejected.code, "message": rejected.detail},
        ) from rejected
    except Exception:
        # Rien du contenu de l'image ne doit fuir dans un message d'erreur.
        log.exception("échec d'analyse", extra={"request_id": request_id})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "analysis_failed", "message": "Analyse impossible."},
        ) from None

    log.info("photo analysée", extra={"request_id": request_id, **analysis.log_fields})
    return analysis.result
