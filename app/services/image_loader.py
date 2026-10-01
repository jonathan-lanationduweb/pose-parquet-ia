"""Décodage, validation et redressement de la photo reçue.

Un principe, écrit une fois ici et vrai partout ensuite : **l'image qui sort
de ce module est déjà droite**. Toute mesure faite en aval — flou, luminance,
arêtes, et demain segmentation et perspective — travaille sur l'orientation
visuelle réelle. Redresser plus tard obligerait chaque étage à se demander
dans quel sens il regarde, et un seul oubli suffirait à faire chercher
l'horizon dans une image couchée.

Rien n'est écrit sur le disque. Les octets sont décodés en mémoire, le tableau
NumPy vit le temps de la requête, et le contrat côté front est clair :
« aucune conservation, la photo est traitée en mémoire et jetée ».
"""

from dataclasses import dataclass
from io import BytesIO
from typing import Literal, cast

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import ALLOWED_FORMATS, get_settings
from app.core.errors import (
    empty_upload,
    too_large,
    too_many_pixels,
    undecodable,
    unsupported_format,
)

#: Balise EXIF d'orientation.
_EXIF_ORIENTATION = 0x0112
#: Sous-répertoire EXIF (« Exif IFD ») et balise « FocalLengthIn35mmFilm ».
#: La seule focale réellement mesurée dont la chaîne de géométrie puisse
#: disposer : quand l'appareil l'écrit, on la lit ; sinon on l'estime.
_EXIF_IFD = 0x8769
_EXIF_FOCAL_35MM = 0xA405

#: Valeurs d'orientation qui impliquent une transformation.
#: 1 = déjà droite ; absente = rien de déclaré.
_ORIENTATIONS_TO_APPLY = frozenset({2, 3, 4, 5, 6, 7, 8})

#: Coefficients Rec. 709. La luma perceptuelle, pas la moyenne des canaux :
#: le vert pèse dix fois le bleu dans ce que l'œil appelle « clair ».
_LUMA_WEIGHTS = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)

ImageFormat = Literal["JPEG", "PNG", "WEBP"]


@dataclass(frozen=True, slots=True)
class LoadedImage:
    """Une photo décodée, droite, prête à mesurer."""

    #: H × W × 3, uint8, RGB.
    rgb: np.ndarray
    #: Format réellement décodé, jamais celui annoncé par le client.
    format: ImageFormat
    exif_orientation_applied: bool
    #: Équivalent 35 mm déclaré par l'appareil, en millimètres. `None` quand
    #: la photo ne le porte pas — c'est le cas de la plupart des photos
    #: retouchées ou téléchargées, et de toutes celles dont l'EXIF a été retiré.
    focal_35mm: float | None = None

    @property
    def width(self) -> int:
        return int(self.rgb.shape[1])

    @property
    def height(self) -> int:
        return int(self.rgb.shape[0])


def _declared_orientation(image: Image.Image) -> int | None:
    """Valeur de la balise d'orientation, si l'image en porte une."""
    try:
        value = image.getexif().get(_EXIF_ORIENTATION)
    except Exception:  # noqa: BLE001 — un EXIF corrompu ne doit pas tout arrêter
        return None
    return int(value) if isinstance(value, int) else None


def _declared_focal_35mm(image: Image.Image) -> float | None:
    """Équivalent 35 mm, s'il est déclaré et plausible (3 à 400 mm)."""
    try:
        valeur = image.getexif().get_ifd(_EXIF_IFD).get(_EXIF_FOCAL_35MM)
        focale = float(valeur) if valeur is not None else None
    except Exception:  # noqa: BLE001 — un EXIF corrompu ne doit pas tout arrêter
        return None
    if focale is None or not (3.0 <= focale <= 400.0):
        return None
    return focale


def load_image(data: bytes) -> LoadedImage:
    """Valide et décode des octets d'image.

    Les refus sont volontairement dans cet ordre : le moins coûteux d'abord.
    On rejette sur la taille des octets avant de demander à Pillow de décoder,
    et sur le nombre de pixels annoncé dans l'en-tête avant de décoder
    réellement — un PNG de 40 ko peut annoncer 30 000 × 30 000 pixels.

    :raises ImageRejected: fichier vide, trop gros, format non pris en charge,
        image indécodable ou trop grande à décoder.
    """
    if not data:
        raise empty_upload()

    settings = get_settings()
    if len(data) > settings.max_upload_bytes:
        raise too_large(settings.max_upload_bytes)

    try:
        with Image.open(BytesIO(data)) as probe:
            declared_format = (probe.format or "").upper()
            if declared_format not in ALLOWED_FORMATS:
                raise unsupported_format()

            width, height = probe.size
            if width * height > settings.max_image_pixels:
                raise too_many_pixels()

            orientation = _declared_orientation(probe)
            focal_35mm = _declared_focal_35mm(probe)
            upright = ImageOps.exif_transpose(probe) or probe
            rgb = np.asarray(upright.convert("RGB"), dtype=np.uint8)
            if upright is not probe:
                upright.close()
    except (UnidentifiedImageError, SyntaxError) as exc:
        raise undecodable() from exc
    except Image.DecompressionBombError as exc:
        raise too_many_pixels() from exc
    except OSError as exc:
        # Fichier tronqué, données corrompues en cours de décodage.
        raise undecodable() from exc

    if rgb.ndim != 3 or rgb.shape[2] != 3 or rgb.size == 0:
        raise undecodable()

    return LoadedImage(
        rgb=rgb,
        format=cast(ImageFormat, declared_format),
        exif_orientation_applied=orientation in _ORIENTATIONS_TO_APPLY,
        focal_35mm=focal_35mm,
    )


def luma(rgb: np.ndarray) -> np.ndarray:
    """Luminance perceptuelle en float32, ramenée à 0 → 1.

    Une seule définition de « clair » pour tout le projet : deux modules qui
    mesureraient la luminance différemment donneraient deux contrastes
    incomparables sur la même photo.
    """
    return cast(np.ndarray, (rgb.astype(np.float32) @ _LUMA_WEIGHTS) / 255.0)
