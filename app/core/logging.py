"""Journalisation structurée.

Ce qui est autorisé dans un log : un identifiant de requête, un nom d'étape,
une durée, des dimensions, un code d'erreur générique.

Ce qui ne l'est **jamais** : l'image, un extrait d'image, du base64, un nom de
fichier fourni par l'utilisateur, un chemin absolu du serveur. Le nom de
fichier est une donnée personnelle en puissance (« salon-rue-des-lilas.jpg »)
et n'apprend rien sur l'analyse. Le service ne le lit pas et ne le garde pas.
"""

import json
import logging
import sys
from typing import Any

from app.core.config import SERVICE_NAME, get_settings

#: Attributs posés par `logging` lui-même : tout le reste d'un `LogRecord`
#: vient de `extra=` et part dans la charge utile JSON.
_RESERVED = frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {
    "message",
    "asctime",
    "taskName",
}


def _extras(record: logging.LogRecord) -> dict[str, Any]:
    return {
        key: value
        for key, value in record.__dict__.items()
        if key not in _RESERVED and not key.startswith("_")
    }


class JsonFormatter(logging.Formatter):
    """Une ligne JSON par événement, pour un collecteur de logs."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "service": SERVICE_NAME,
            "logger": record.name,
            "message": record.getMessage(),
        }
        payload.update(_extras(record))
        if record.exc_info and record.exc_info[0] is not None:
            # Le type de l'exception, pas la trace : une trace peut exposer
            # des valeurs de variables locales, dont des octets d'image.
            payload["error_type"] = record.exc_info[0].__name__
        return json.dumps(payload, ensure_ascii=False, default=str)


class TextFormatter(logging.Formatter):
    """Même information, lisible à l'œil en développement."""

    def format(self, record: logging.LogRecord) -> str:
        base = f"{record.levelname:<7} {record.name} — {record.getMessage()}"
        extras = " ".join(f"{k}={v}" for k, v in _extras(record).items())
        return f"{base} | {extras}" if extras else base


def configure_logging() -> None:
    """Installe le formateur sur la racine. Idempotent."""
    settings = get_settings()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if settings.log_format == "json" else TextFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())


def get_logger(name: str) -> logging.Logger:
    """Journal du module, préfixé par le nom du service."""
    return logging.getLogger(f"{SERVICE_NAME}.{name}")
