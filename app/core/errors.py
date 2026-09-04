"""Erreurs métier du service.

Chaque erreur porte un code machine et le statut HTTP qui lui correspond,
pour que la couche API n'ait aucune décision à prendre. Les codes suivent le
tableau de `docs/future-ai-api-contract.md` côté front : 415 pour un format
non pris en charge, 413 pour un fichier trop gros, 422 pour une image
illisible.

Aucun message ne contient de chemin, de nom de fichier ni de contenu
d'image : voir docs/architecture.md, section Journalisation.
"""


class ImageRejected(Exception):
    """L'image ne peut pas entrer dans le pipeline.

    Écrite en classe ordinaire, et pas en `dataclass(frozen=True, slots=True)`
    comme le reste du projet : la combinaison est incompatible avec l'héritage
    de `Exception` — le `__setattr__` généré par `frozen` casse la mécanique de
    propagation dès que l'exception traverse un gestionnaire de contexte.
    """

    def __init__(self, code: str, detail: str, http_status: int) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.http_status = http_status

    def __str__(self) -> str:
        return self.detail


def empty_upload() -> ImageRejected:
    return ImageRejected("empty_file", "Fichier vide.", 422)


def too_large(limit_bytes: int) -> ImageRejected:
    mo = limit_bytes / (1024 * 1024)
    return ImageRejected("file_too_large", f"Fichier trop volumineux (limite {mo:.0f} Mo).", 413)


def unsupported_format() -> ImageRejected:
    return ImageRejected(
        "unsupported_format",
        "Format non pris en charge. Formats acceptés : JPEG, PNG, WebP.",
        415,
    )


def undecodable() -> ImageRejected:
    return ImageRejected("undecodable_image", "Image impossible à décoder.", 422)


def too_many_pixels() -> ImageRejected:
    return ImageRejected("image_too_many_pixels", "Image trop grande à décoder.", 413)
