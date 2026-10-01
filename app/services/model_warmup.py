"""Préchauffage du candidat de segmentation expérimental — LOT PHOTO.2.

    EXPERIMENTAL PRODUCT PIPELINE · AUCUN MODÈLE RETENU

## Le problème

La revue a mesuré que la PREMIÈRE photo analysée payait tout : lecture des
poids, construction du modèle, puis une première inférence elle-même bien plus
lente que les suivantes (allocation des tampons, choix des noyaux de calcul).
Sur ce poste : 37 s de segmentation pour la première photo, 7 à 8 s ensuite,
et jusqu'à 95 s quand le cache disque était froid. Une personne qui importe sa
première photo n'a aucune raison d'attendre que le serveur finisse de démarrer.

## La réponse

Au démarrage du service — et seulement quand `PPAI_EXPERIMENTAL_FLOOR` est
vrai — un fil d'arrière-plan charge le candidat puis lui fait segmenter une
image synthétique. Le serveur répond pendant ce temps : `/health` dit
`experimentalFloor: loading`, puis `ready` (ou `error`). Une analyse qui
arrive avant la fin attend le préchauffage déjà en cours au lieu d'en lancer
un second.

Rien n'est téléchargé de plus que ce que l'analyse aurait téléchargé : le
chargement passe par `_depuis_le_cache`, qui lit le disque d'abord. Aucune
photo n'est utilisée — l'image de préchauffage est un dégradé fabriqué ici.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np

from app.core.logging import get_logger

log = get_logger("services.model_warmup")

WarmupState = Literal["disabled", "loading", "ready", "error"]

#: Taille de l'image de préchauffage. Assez grande pour que l'inférence suive
#: le même chemin qu'une vraie photo (le processeur la redimensionne de toute
#: façon), assez petite pour ne pas coûter plus que nécessaire.
WARMUP_SIZE = (640, 480)


@dataclass
class _Etat:
    state: WarmupState = "disabled"
    candidate: str | None = None
    started_at: float | None = None
    timings_ms: dict[str, float] = field(default_factory=dict)
    error: str | None = None
    fini: threading.Event = field(default_factory=threading.Event)
    verrou: threading.Lock = field(default_factory=threading.Lock)


_etat = _Etat()


def _image_synthetique() -> np.ndarray:
    """Un dégradé de « mur » au-dessus d'un « sol » : aucune photo réelle."""
    largeur, hauteur = WARMUP_SIZE
    y = np.linspace(0, 1, hauteur, dtype=np.float32)[:, None]
    x = np.linspace(0, 1, largeur, dtype=np.float32)[None, :]
    mur = np.stack([200 + 20 * x + 0 * y, 196 + 0 * x + 0 * y, 188 + 0 * x + 0 * y], -1)
    sol = np.stack([150 + 30 * y + 0 * x, 110 + 20 * y + 0 * x, 70 + 0 * x + 0 * y], -1)
    image = np.where((y > 0.55)[..., None], sol, mur)
    return np.clip(image, 0, 255).astype(np.uint8)


def segmenter_pour(candidat: str) -> Any:
    """Le segmenteur nommé. Même choix que le pipeline, au même endroit."""
    if candidat == "opencv":
        from app.services.floor_geometric import GeometricFloorBaseline

        return GeometricFloorBaseline()
    if candidat == "upernet":
        from app.services.floor_semantic import UperNetFloor

        return UperNetFloor()
    from app.services.floor_semantic import OneFormerFloor

    return OneFormerFloor()


def _prechauffer(candidat: str) -> None:
    t0 = time.perf_counter()
    try:
        moteur = segmenter_pour(candidat)
        charger = getattr(moteur, "_charger", None)
        if callable(charger):
            charger()
        t1 = time.perf_counter()
        moteur.segment(_image_synthetique())
        t2 = time.perf_counter()
        with _etat.verrou:
            _etat.timings_ms = {
                "load": round((t1 - t0) * 1000, 1),
                "firstInference": round((t2 - t1) * 1000, 1),
                "total": round((t2 - t0) * 1000, 1),
            }
            _etat.state = "ready"
        log.info("candidat expérimental prêt", extra={"candidate": candidat, **_etat.timings_ms})
    except Exception as exc:  # noqa: BLE001 — l'échec est un état, pas un plantage
        with _etat.verrou:
            _etat.state = "error"
            _etat.error = type(exc).__name__
        log.exception("préchauffage du candidat expérimental impossible")
    finally:
        _etat.fini.set()


def start_warmup(candidat: str) -> bool:
    """Lance le préchauffage en arrière-plan. Rend faux s'il est déjà lancé."""
    with _etat.verrou:
        if _etat.state in ("loading", "ready"):
            return False
        _etat.state = "loading"
        _etat.candidate = candidat
        _etat.started_at = time.time()
        _etat.error = None
        _etat.fini.clear()
    threading.Thread(target=_prechauffer, args=(candidat,), name="ppai-warmup", daemon=True).start()
    return True


def wait_ready(timeout: float | None = None) -> bool:
    """Attend la fin d'un préchauffage en cours ; vrai si rien n'est en cours."""
    if _etat.state != "loading":
        return True
    return _etat.fini.wait(timeout)


def status() -> WarmupState:
    return _etat.state


def report() -> dict[str, Any]:
    """Pour les mesures et les journaux — pas pour `/health`, qui reste pauvre."""
    with _etat.verrou:
        return {
            "state": _etat.state,
            "candidate": _etat.candidate,
            "timingsMs": dict(_etat.timings_ms),
            "error": _etat.error,
        }


def _reset_for_tests() -> None:
    global _etat
    _etat = _Etat()
