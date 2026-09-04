"""Contrôle qualité photo. Aucun modèle, que des mesures.

Ce module ne dit pas si une photo est « bonne ». Il dit ce qu'elle est :
combien de pixels, quelle luminance, quel contraste, quelle netteté mesurée
et à quelle résolution. La classification (`sharp`, les avertissements) est
un service rendu par-dessus, pilotée par des seuils configurables, et la
mesure brute reste toujours dans la réponse.

Cette prudence n'est pas de la coquetterie. Un mur nu bien éclairé donne une
variance de Laplacien très basse sans être flou ; une photo bruitée en donne
une haute sans être nette. Le seuil utile se mesurera sur le corpus, pas
avant (voir docs/dataset.md).
"""

import cv2
import numpy as np

from app.core.config import get_settings
from app.core.warnings import Warn
from app.schemas.analysis import BlurMetrics, ExposureMetrics, QualityMetrics


def _resize_long_side(gray: np.ndarray, target: int) -> np.ndarray:
    """Ramène le côté long à `target`. Ne grossit jamais une petite image.

    Agrandir fabriquerait du flou d'interpolation et ferait chuter la variance
    du Laplacien : une photo petite mais nette serait déclarée floue.
    """
    height, width = gray.shape[:2]
    long_side = max(height, width)
    if long_side <= target:
        return gray
    scale = target / long_side
    new_size = (max(1, round(width * scale)), max(1, round(height * scale)))
    return cv2.resize(gray, new_size, interpolation=cv2.INTER_AREA)


def measure_blur(luma01: np.ndarray) -> BlurMetrics:
    """Variance du Laplacien, à résolution de travail fixe.

    Le Laplacien est la dérivée seconde : il répond aux transitions franches.
    Sa variance sur toute l'image résume « combien de détail net » elle
    contient. La mesure est faite sur une luma ramenée en 0 → 255 pour que
    les valeurs restent dans les ordres de grandeur publiés dans la
    littérature (quelques dizaines à quelques milliers).
    """
    settings = get_settings()
    gray = (np.clip(luma01, 0.0, 1.0) * 255.0).astype(np.uint8)
    working = _resize_long_side(gray, settings.blur_working_side)
    variance = float(cv2.Laplacian(working, cv2.CV_64F).var())
    return BlurMetrics(
        laplacian_variance=round(variance, 3),
        working_side=int(max(working.shape[:2])),
        sharp=variance >= settings.blur_sharp_min,
    )


def measure_exposure(luma01: np.ndarray) -> ExposureMetrics:
    """Luminance et contraste globaux.

    Deux mesures de contraste, parce qu'elles ne disent pas la même chose :
    l'écart-type résume toute la distribution, l'étendue p5–p95 ignore les
    quelques pour cent d'extrêmes. Une photo par ailleurs plate avec un
    spot brûlé a un écart-type flatteur et une étendue honnête.
    """
    settings = get_settings()
    flat = luma01.reshape(-1)
    p5, p95 = np.percentile(flat, [5.0, 95.0])
    return ExposureMetrics(
        luma_mean=round(float(flat.mean()), 5),
        luma_median=round(float(np.median(flat)), 5),
        contrast_std=round(float(flat.std()), 5),
        contrast_p5_p95=round(float(p95 - p5), 5),
        dark_pixel_ratio=round(float((flat < settings.dark_luma_max).mean()), 5),
        bright_pixel_ratio=round(float((flat > settings.bright_luma_min).mean()), 5),
    )


def analyse_quality(luma01: np.ndarray) -> QualityMetrics:
    """Toutes les mesures de qualité de l'image."""
    return QualityMetrics(blur=measure_blur(luma01), exposure=measure_exposure(luma01))


def quality_warnings(quality: QualityMetrics, width: int, height: int) -> list[Warn]:
    """Traduit les mesures en codes machine, selon les seuils configurés.

    Séparé des mesures exprès : changer un seuil ne doit pas toucher au code
    qui mesure, et un benchmark doit pouvoir rejouer d'autres seuils sur des
    mesures déjà enregistrées.
    """
    settings = get_settings()
    found: list[Warn] = []

    if max(width, height) < settings.min_long_side:
        found.append(Warn.IMAGE_TOO_SMALL)

    ratio = max(width, height) / min(width, height)
    if ratio > settings.max_aspect_ratio:
        found.append(Warn.IMAGE_EXTREME_ASPECT_RATIO)

    if not quality.blur.sharp:
        found.append(Warn.IMAGE_BLURRY)

    exposure = quality.exposure
    if (
        exposure.luma_mean < settings.luma_mean_min
        or exposure.dark_pixel_ratio > settings.dark_ratio_max
    ):
        found.append(Warn.IMAGE_TOO_DARK)
    if (
        exposure.luma_mean > settings.luma_mean_max
        or exposure.bright_pixel_ratio > settings.bright_ratio_max
    ):
        found.append(Warn.IMAGE_OVEREXPOSED)
    if exposure.contrast_std < settings.contrast_min:
        found.append(Warn.IMAGE_LOW_CONTRAST)

    return found
