"""GET /health — le service répond-il ?

Volontairement pauvre. Un point de santé public ne dit ni la version de l'OS,
ni un chemin, ni un nom de machine, ni la liste des modèles chargés : ce sont
des renseignements gratuits pour qui cherche une prise.

Le front s'en sert pour une seule décision : proposer ou non l'analyse
automatique. Si le service ne répond pas, l'interface ne mentionne pas la
fonction — elle n'existe pas ce jour-là.

## LOT PHOTO.2 : `experimentalFloor`

Quand — et seulement quand — le service tourne avec `PPAI_EXPERIMENTAL_FLOOR`,
la réponse gagne un mot : `loading`, `ready` ou `error`. Pas le nom du
modèle, pas ses durées : seulement de quoi savoir si la première photo
attendra. Sans le drapeau, la réponse est exactement celle d'avant.
"""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import SERVICE_NAME, get_settings
from app.services import model_warmup

router = APIRouter(tags=["service"])


class Health(BaseModel):
    """Réponse de `/health`."""

    model_config = ConfigDict(populate_by_name=True)

    status: Literal["ok"] = "ok"
    service: str = SERVICE_NAME
    experimental_floor: Literal["loading", "ready", "error", "idle"] | None = Field(
        default=None, alias="experimentalFloor"
    )


@router.get(
    "/health",
    response_model=Health,
    response_model_exclude_none=True,
    response_model_by_alias=True,
    summary="État du service",
)
def health() -> Health:
    if not get_settings().experimental_floor:
        return Health()
    etat = model_warmup.status()
    # `disabled` côté préchauffage avec le drapeau allumé : préchauffage
    # désactivé, le modèle se chargera à la première photo.
    return Health.model_validate({"experimentalFloor": "idle" if etat == "disabled" else etat})
