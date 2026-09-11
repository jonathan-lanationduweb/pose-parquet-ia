"""Le pipeline d'analyse : l'ordre des étages, et la décision finale.

C'est le seul module qui connaît l'enchaînement complet. Chaque étage est
appelé ici, chronométré ici, et son verdict remonte ici. Les étages, eux, ne
se connaissent pas entre eux : on doit pouvoir remplacer un modèle de
segmentation sans toucher à autre chose que sa propre fonction.

L'ordre n'est pas arbitraire. Le redressement EXIF vient en premier parce que
tout le reste mesure sur l'image droite. L'analyse d'objectif vient avant
toute géométrie parce qu'une distorsion non détectée entre dans tous les
relevés suivants sans plus rien qui la distingue.
"""

# Annotations differees : `numpy` et le schema experimental ne sont importes
# que pour la verification de types, et ce module doit rester importable sans
# torch ni transformers.
from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.timing import Timings
from app.core.warnings import BLOCKING, Warn
from app.schemas.analysis import AnalysisResult, AnalysisStatus, ImageInfo
from app.services import image_quality, lens_analysis, scene_builder
from app.services.image_loader import LoadedImage, load_image, luma

if TYPE_CHECKING:
    import numpy as np

    from app.schemas.analysis import ExperimentalOutputs

log = get_logger("services.pipeline")


@dataclass(frozen=True, slots=True)
class Analysis:
    """Résultat, plus ce que l'appelant a le droit de journaliser.

    Le résultat part au client, `log_fields` part dans les logs. Les séparer
    évite qu'on journalise un jour l'objet entier « parce qu'il est là » —
    avec, demain, une carte de masque en base64 dedans.
    """

    result: AnalysisResult
    log_fields: dict[str, object]


def _image_info(image: LoadedImage) -> ImageInfo:
    """Dimensions et format, après redressement."""
    return ImageInfo(
        width=image.width,
        height=image.height,
        aspect_ratio=round(image.width / image.height, 5),
        megapixels=round(image.width * image.height / 1e6, 3),
        format=image.format,
        exif_orientation_applied=image.exif_orientation_applied,
    )


def _decide_status(warnings: list[Warn], scene_present: bool) -> AnalysisStatus:
    """Traduit l'état des étages et des avertissements en un statut.

    La hiérarchie est volontairement pessimiste :

    * un avertissement bloquant (photo inexploitable) ferme le dossier —
      `rejected` ;
    * sans scène, on ne prétend pas avoir analysé la pièce —
      `analysis_incomplete` ;
    * avec une scène mais des avertissements, on demande une relecture
      humaine — `needs_manual_adjustment`.

    Le cas `success` n'est donc atteignable qu'avec une scène et aucun
    avertissement. C'est strict, et c'est le but : il est bien plus facile de
    détendre ce critère plus tard que de rattraper une géométrie fausse déjà
    montrée à quelqu'un.
    """
    if any(warning in BLOCKING for warning in warnings):
        return AnalysisStatus.REJECTED
    if not scene_present:
        return AnalysisStatus.ANALYSIS_INCOMPLETE
    return AnalysisStatus.NEEDS_MANUAL_ADJUSTMENT if warnings else AnalysisStatus.SUCCESS


def _segmentation_experimentale(rgb: np.ndarray) -> ExperimentalOutputs | None:
    """Segmentation exploratoire du sol — **hors contrat, sur demande**.

    Trois refus tenus ici, et ils tiennent ensemble :

    * un echec ne casse jamais l'analyse. Un modele absent, une memoire
      insuffisante, une dependance manquante : l'analyse normale a deja
      reussi, et une sortie experimentale ne doit pas l'emporter avec elle ;
    * aucune `sceneData` n'est produite. Ce masque ne devient pas une scene,
      donc aucun parquet ne se pose ;
    * rien n'est renvoye quand le drapeau est faux, et c'est l'appelant qui
      l'a verifie avant d'entrer ici.
    """
    from app.schemas.analysis import ExperimentalFloor, ExperimentalOutputs
    from app.schemas.scene_data import Point

    try:
        candidat = get_settings().experimental_floor_candidate
        if candidat == "opencv":
            from app.services.floor_geometric import GeometricFloorBaseline

            moteur: Any = GeometricFloorBaseline()
        elif candidat == "upernet":
            from app.services.floor_semantic import UperNetFloor

            moteur = UperNetFloor()
        else:
            from app.services.floor_semantic import OneFormerFloor

            moteur = OneFormerFloor()

        from app.services.floor_segmentation import mask_to_png_bytes

        resultat = moteur.segment(rgb)
        png = mask_to_png_bytes(resultat.mask)
        hauteur, largeur = resultat.mask.shape[:2]
        return ExperimentalOutputs(
            floor=ExperimentalFloor(
                candidate=resultat.candidate,
                mask_png_base64=base64.b64encode(png).decode("ascii"),
                mask_width=largeur,
                mask_height=hauteur,
                coverage=round(resultat.coverage, 4),
                boundary=[[Point(x=x, y=y) for x, y in contour] for contour in resultat.boundary],
                timings_ms=resultat.timings,
                metadata=dict(resultat.metadata),
            )
        )
    except Exception:
        # On ne dit rien de plus qu'ici : la sortie experimentale est absente,
        # l'analyse normale est intacte, et la trace reste dans les logs du
        # service — jamais dans la reponse.
        log.exception("segmentation experimentale indisponible")
        return None


def analyse_room(data: bytes) -> Analysis:
    """Analyse une photo de pièce, d'octets bruts à `AnalysisResult`.

    :raises ImageRejected: si la photo n'entre pas dans le pipeline. C'est la
        couche API qui traduit en code HTTP — pas ce module, qui n'a pas à
        savoir qu'il sert une API.
    """
    timings = Timings()

    with timings.measure("load_image"):
        image = load_image(data)
        luma01 = luma(image.rgb)

    info = _image_info(image)
    warnings: list[Warn] = []

    with timings.measure("quality_analysis"):
        quality = image_quality.analyse_quality(luma01)
    warnings += image_quality.quality_warnings(quality, info.width, info.height)

    # Une photo déjà rejetée n'a pas à payer l'analyse d'objectif : le verdict
    # ne changerait rien, et le suivi d'arêtes est l'étage le plus coûteux du
    # LOT 0.
    blocked = any(warning in BLOCKING for warning in warnings)
    lens = None
    if not blocked:
        with timings.measure("lens_analysis"):
            lens = lens_analysis.analyse_lens(luma01)
        warnings += lens_analysis.lens_warnings(lens)

    with timings.measure("scene_builder"):
        scene = scene_builder.build_scene_data()
    warnings += scene_builder.missing_stage_warnings()

    # L'etage experimental, et son defaut : RIEN. Sans le drapeau, le
    # pipeline se termine exactement comme avant le LOT C.0.
    experimental = None
    if get_settings().experimental_floor:
        # L'etage `segmentation` etait declare depuis le LOT 0 et jamais
        # execute : c'est exactement celui-ci. On ne cree pas un nom de plus
        # pour la meme chose, et une duree mesuree ici dit enfin quelque
        # chose. Ce qu'elle ne dit pas : que la segmentation soit livree.
        with timings.measure("segmentation"):
            experimental = _segmentation_experimentale(image.rgb)

    status = _decide_status(warnings, scene is not None)
    result = AnalysisResult(
        status=status,
        # Aucune confiance n'est publiée tant qu'aucun étage de géométrie
        # n'existe : c'est sur ce nombre que le front décide d'ouvrir ou non
        # l'écran de correction, et l'inventer serait le pire mensonge que ce
        # service puisse dire.
        confidence=None,
        warnings=warnings,
        image=info,
        quality=quality,
        lens=lens,
        scene_data=scene,
        timings=timings.as_dict(),
        experimental=experimental,
    )

    return Analysis(
        result=result,
        log_fields={
            "status": status.value,
            "width": info.width,
            "height": info.height,
            "format": info.format,
            "exif_applied": info.exif_orientation_applied,
            "warnings": [w.value for w in warnings],
            "total_ms": result.timings.get("total_ms"),
        },
    )
