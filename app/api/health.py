"""GET /health — le service répond-il ?

Volontairement pauvre. Un point de santé public ne dit ni la version de l'OS,
ni un chemin, ni un nom de machine, ni la liste des modèles chargés : ce sont
des renseignements gratuits pour qui cherche une prise.

Le front s'en sert pour une seule décision : proposer ou non l'analyse
automatique. Si le service ne répond pas, l'interface ne mentionne pas la
fonction — elle n'existe pas ce jour-là.
"""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import SERVICE_NAME

router = APIRouter(tags=["service"])


class Health(BaseModel):
    """Réponse de `/health`."""

    status: Literal["ok"] = "ok"
    service: str = SERVICE_NAME


@router.get("/health", response_model=Health, summary="État du service")
def health() -> Health:
    return Health()
