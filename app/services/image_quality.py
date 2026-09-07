"""Contrôle qualité photo. Aucun modèle, que des mesures.

Ce module ne dit pas si une photo est « bonne ». Il dit ce qu'elle est :
combien de pixels, quelle luminance, quel contraste, combien d'information
écrêtée, et — via `blur_analysis` — quelle netteté et avec quel support.

La classification est un service rendu par-dessus, pilotée par des seuils
configurables, et la mesure brute reste toujours dans la réponse. La séparation
n'est pas cosmétique : elle permet à un benchmark de rejouer d'autres seuils
sur des mesures déjà enregistrées, sans réanalyser le corpus.

## Ce que l'exposition ne peut pas dire

Une scène naturellement sombre et une photo sous-exposée ont la même luminance
moyenne. Les distinguer demanderait de savoir ce que la scène *devrait* valoir,
ce qu'aucune mesure d'une image seule ne sait. Le lot ne prétend donc pas
trancher : les métriques restent continues, l'avertissement reste large, et
c'est `clipped_*_ratio` — l'information réellement **détruite** — qui porte le
seul jugement solide qu'on puisse faire sans connaître la scène.
"""

import cv2
import numpy as np

from app.core.config import get_settings
from app.core.warnings import Warn
from app.schemas.analysis import BlurMetrics, ExposureMetrics, QualityMetrics
from app.services import blur_analysis

#: Luma au-delà / en deçà de laquelle un pixel est considéré **écrêté**.
#: Définitionnel plutôt que réglable : à un pas de quantification 8 bits près,
#: c'est le blanc et le noir absolus. Un pixel à 255 n'est pas « clair », il
#: est sans valeur — la scène y était peut-être deux fois plus lumineuse, et
#: rien dans le fichier ne permet de le savoir.
_CLIP_HIGH = 254.0 / 255.0
_CLIP_LOW = 1.0 / 255.0


def measure_blur(luma01: np.ndarray) -> BlurMetrics:
    """Netteté et support, via les trois candidates de `blur_analysis`."""
    reading = blur_analysis.measure(luma01)
    sharp, low_texture = blur_analysis.classify(reading)
    return BlurMetrics(
        strong_gradient_ratio=reading.strong_gradient_ratio,
        laplacian_variance=reading.laplacian_variance,
        reblur_ratio=reading.reblur_ratio,
        edge_width_px=reading.edge_width_px,
        edge_width_normalized=reading.edge_width_normalized,
        edge_count=reading.edge_count,
        working_side=reading.working_side,
        method=get_settings().blur_method.value,
        sharp=sharp,
        low_texture=low_texture,
    )


def measure_exposure(luma01: np.ndarray) -> ExposureMetrics:
    """Luminance, contraste et écrêtage globaux.

    Deux mesures de contraste, parce qu'elles ne disent pas la même chose :
    l'écart-type résume toute la distribution, l'étendue p5–p95 ignore les
    quelques pour cent d'extrêmes. Une photo par ailleurs plate avec un spot
    brûlé a un écart-type flatteur et une étendue honnête.
    """
    settings = get_settings()
    flat = luma01.reshape(-1)
    p5, p95 = np.percentile(flat, [5.0, 95.0])
    return ExposureMetrics(
        luma_mean=round(float(flat.mean()), 5),
        luma_median=round(float(np.median(flat)), 5),
        contrast_std=round(float(flat.std()), 5),
        contrast_ratio=round(float(flat.std()) / max(float(flat.mean()), 1e-6), 5),
        contrast_p5_p95=round(float(p95 - p5), 5),
        dark_pixel_ratio=round(float((flat < settings.dark_luma_max).mean()), 5),
        bright_pixel_ratio=round(float((flat > settings.bright_luma_min).mean()), 5),
        clipped_high_ratio=round(float((flat >= _CLIP_HIGH).mean()), 5),
        clipped_low_ratio=round(float((flat <= _CLIP_LOW).mean()), 5),
    )


def analyse_quality(luma01: np.ndarray) -> QualityMetrics:
    """Toutes les mesures de qualité de l'image."""
    return QualityMetrics(blur=measure_blur(luma01), exposure=measure_exposure(luma01))


def quality_warnings(quality: QualityMetrics, width: int, height: int) -> list[Warn]:
    """Traduit les mesures en codes machine, selon les seuils configurés.

    Deux distinctions structurent cette fonction, et toutes deux corrigent une
    confusion du LOT 0 :

    * `IMAGE_BLURRY` n'est émis que si la netteté a pu être **jugée** et
      qu'elle est mauvaise. Une image sans support suffisant reçoit
      `IMAGE_LOW_TEXTURE`, qui dit « je n'ai pas de quoi conclure » — et un mur
      parfaitement net le déclenche légitimement ;
    * `IMAGE_CLIPPED` est séparé de `IMAGE_OVEREXPOSED`. Une photo claire se
      rattrape ; une photo dont les hautes lumières sont écrêtées a perdu
      l'information, définitivement.
    """
    settings = get_settings()
    found: list[Warn] = []

    if max(width, height) < settings.min_long_side:
        found.append(Warn.IMAGE_TOO_SMALL)

    ratio = max(width, height) / min(width, height)
    if ratio > settings.max_aspect_ratio:
        found.append(Warn.IMAGE_EXTREME_ASPECT_RATIO)

    blur = quality.blur
    if blur.sharp is False:
        found.append(Warn.IMAGE_BLURRY)
    if blur.low_texture:
        found.append(Warn.IMAGE_LOW_TEXTURE)

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
    if (
        exposure.clipped_high_ratio > settings.clipped_high_ratio_max
        or exposure.clipped_low_ratio > settings.clipped_low_ratio_max
    ):
        found.append(Warn.IMAGE_CLIPPED)
    # Contraste **relatif** : l'écart-type absolu est proportionnel à la
    # luminance, et une photo sombre l'a mécaniquement bas. S'y fier faisait
    # émettre `image_low_contrast` sur toute image sous-exposée, en plus de
    # `image_too_dark` — deux avertissements pour un seul défaut, dont un faux.
    if exposure.contrast_ratio < settings.contrast_ratio_min:
        found.append(Warn.IMAGE_LOW_CONTRAST)

    return found


def resize_long_side(gray: np.ndarray, target: int) -> np.ndarray:
    """Ramène le côté long à `target`. N'agrandit jamais.

    Agrandir fabriquerait du flou d'interpolation : une photo petite mais nette
    serait déclarée floue.
    """
    height, width = gray.shape[:2]
    long_side = max(height, width)
    if long_side <= target:
        return gray
    scale = target / long_side
    size = (max(1, round(width * scale)), max(1, round(height * scale)))
    return cv2.resize(gray, size, interpolation=cv2.INTER_AREA)
