"""Les deux contrats : `SceneData` (celui du front) et `AnalysisResult` (le nôtre)."""

import json
import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.warnings import Warn
from app.schemas.analysis import (
    ANALYSIS_SCHEMA,
    AnalysisResult,
    AnalysisStatus,
    ImageInfo,
)
from app.schemas.scene_data import SCENE_SCHEMA, SceneData, major_of

#: Une scène minimale valide, écrite à la main d'après le contrat du front.
MINIMAL_SCENE: dict = {
    "schema": SCENE_SCHEMA,
    "id": "upload-test",
    "source": "ai",
    "image": {"width": 1600, "height": 1067},
    "surfaces": [{"id": "sol", "label": "Sol", "continuous": True}],
    "floorZones": [
        {
            "id": "zone-1",
            "label": "Sol",
            "surfaceId": "sol",
            "order": 0,
            "plane": {
                "quad": [
                    {"x": 0.18, "y": 0.66},
                    {"x": 0.84, "y": 0.66},
                    {"x": 1.02, "y": 1.0},
                    {"x": -0.02, "y": 1.0},
                ],
                "meters": {"width": 5.0, "depth": 4.5},
            },
            "mask": {"polygon": [{"x": 0.0, "y": 0.7}, {"x": 1.0, "y": 0.7}, {"x": 1.0, "y": 1.0}]},
        }
    ],
}


# --- SceneData -----------------------------------------------------------


def test_une_scene_minimale_est_valide():
    scene = SceneData.model_validate(MINIMAL_SCENE)
    assert scene.scene_schema == SCENE_SCHEMA
    assert len(scene.floor_zones) == 1


def test_les_coordonnees_hors_bornes_sont_permises():
    """Un plan de sol se prolonge très souvent au-delà du cadre.

    Borner ces champs à [0, 1] casserait des scènes valides — celle-ci en est
    une, et elle vient du front.
    """
    scene = SceneData.model_validate(MINIMAL_SCENE)
    quad = scene.floor_zones[0].plane.quad
    assert min(point.x for point in quad) < 0.0
    assert max(point.x for point in quad) > 1.0


def test_un_quad_de_trois_points_est_refuse():
    broken = json.loads(json.dumps(MINIMAL_SCENE))
    broken["floorZones"][0]["plane"]["quad"].pop()
    with pytest.raises(ValidationError):
        SceneData.model_validate(broken)


def test_une_scene_sans_zone_est_refusee():
    """Le front lève dans ce cas ; refuser ici évite d'envoyer l'impossible."""
    broken = json.loads(json.dumps(MINIMAL_SCENE))
    broken["floorZones"] = []
    with pytest.raises(ValidationError):
        SceneData.model_validate(broken)


def test_un_plane_ref_est_resolu():
    """La forme employée par presque toutes les scènes réelles du front."""
    scene_dict = {
        **MINIMAL_SCENE,
        "planes": {"rez": MINIMAL_SCENE["floorZones"][0]["plane"]},
        "floorZones": [
            {
                "id": "zone-1",
                "label": "Salon",
                "planeRef": "rez",
                "mask": MINIMAL_SCENE["floorZones"][0]["mask"],
            }
        ],
    }
    scene = SceneData.model_validate(scene_dict)
    assert scene.floor_zones[0].plane is not None
    assert scene.floor_zones[0].plane.meters.width == 5.0


def test_un_plane_ref_mort_est_refuse():
    broken = {
        **MINIMAL_SCENE,
        "floorZones": [
            {
                "id": "zone-1",
                "label": "Salon",
                "planeRef": "inexistant",
                "mask": MINIMAL_SCENE["floorZones"][0]["mask"],
            }
        ],
    }
    with pytest.raises(ValidationError, match="introuvable"):
        SceneData.model_validate(broken)


def test_une_zone_sans_plan_ni_ref_est_refusee():
    broken = {
        **MINIMAL_SCENE,
        "floorZones": [
            {"id": "zone-1", "label": "Salon", "mask": MINIMAL_SCENE["floorZones"][0]["mask"]}
        ],
    }
    with pytest.raises(ValidationError, match="ni plane ni planeRef"):
        SceneData.model_validate(broken)


def test_la_scene_se_serialise_en_camel_case():
    """C'est ce que `normalizeScene()` lit côté front."""
    dumped = SceneData.model_validate(MINIMAL_SCENE).model_dump(by_alias=True)
    assert dumped["schema"] == SCENE_SCHEMA
    assert "floorZones" in dumped
    assert "surfaceId" in dumped["floorZones"][0]
    assert "rotationDeg" in dumped["floorZones"][0]["plane"]
    assert "blurRadius" in dumped["light"]


def test_les_defauts_de_lumiere_sont_ceux_du_front():
    """Ces nombres ne sont pas décoratifs : ils viennent de js/scene/schema.js.

    En diverger produirait un rendu différent de celui des pièces calibrées,
    pour la même photo.
    """
    light = SceneData.model_validate(MINIMAL_SCENE).light
    assert (light.blur_radius, light.ambient, light.tint, light.contact) == (
        0.035,
        0.22,
        0.5,
        0.35,
    )


def test_la_majeure_du_schema_est_extraite():
    assert major_of("pose-parquet/scene@1") == "pose-parquet/scene"
    assert major_of(SCENE_SCHEMA) == major_of("pose-parquet/scene@2")


# --- Contrat contre les scènes réelles du front --------------------------

#: Dépôt du front, en **lecture seule**. Absent en CI et dans Docker : le test
#: est alors ignoré, jamais en échec. Surchargeable par `POSE_PARQUET_FRONT`.
FRONT_SCENES = (
    Path(os.environ.get("POSE_PARQUET_FRONT", r"C:\Users\jonat\Desktop\pose-parquet.com"))
    / "data/scenes"
)


def _real_scenes() -> list[Path]:
    if not FRONT_SCENES.is_dir():
        return []
    return sorted(p for p in FRONT_SCENES.glob("*.json") if p.name != "index.json")


@pytest.mark.skipif(not _real_scenes(), reason="dépôt front absent")
@pytest.mark.parametrize("path", _real_scenes(), ids=lambda p: p.stem)
def test_les_scenes_reelles_du_front_valident(path):
    """Le seul test qui prouve que le schéma Pydantic n'a rien inventé.

    Ces fichiers sont la vérité terrain géométrique du projet : douze pièces
    calibrées à la main. Si le modèle les refuse, c'est le modèle qui a tort.
    Aucun fichier du front n'est modifié — lecture seule.
    """
    scene = SceneData.model_validate(json.loads(path.read_text(encoding="utf-8")))
    assert scene.floor_zones
    for zone in scene.floor_zones:
        assert zone.plane is not None, "plane non résolu"
        assert len(zone.plane.quad) == 4


# --- AnalysisResult ------------------------------------------------------

MINIMAL_IMAGE = ImageInfo(
    width=1600,
    height=1067,
    aspect_ratio=1.5,
    megapixels=1.71,
    format="JPEG",
    exif_orientation_applied=False,
)


def test_un_resultat_minimal_est_valide():
    result = AnalysisResult(status=AnalysisStatus.ANALYSIS_INCOMPLETE, image=MINIMAL_IMAGE)
    assert result.analysis_schema == ANALYSIS_SCHEMA
    assert result.confidence is None
    assert result.scene_data is None
    assert result.warnings == []


def test_une_confiance_hors_bornes_est_refusee():
    for bad in (-0.1, 1.1):
        with pytest.raises(ValidationError):
            AnalysisResult(status=AnalysisStatus.PARTIAL, image=MINIMAL_IMAGE, confidence=bad)


def test_un_statut_inconnu_est_refuse():
    with pytest.raises(ValidationError):
        AnalysisResult(status="presque_bon", image=MINIMAL_IMAGE)


def test_un_champ_inconnu_est_refuse():
    """`extra="forbid"` sur notre contrat : une faute de frappe doit se voir."""
    with pytest.raises(ValidationError):
        AnalysisResult(status=AnalysisStatus.REJECTED, image=MINIMAL_IMAGE, confidance=0.5)


def test_les_warnings_sont_des_codes_connus():
    result = AnalysisResult(
        status=AnalysisStatus.REJECTED,
        image=MINIMAL_IMAGE,
        warnings=[Warn.IMAGE_TOO_SMALL, Warn.IMAGE_BLURRY],
    )
    dumped = result.model_dump(by_alias=True, mode="json")
    assert dumped["warnings"] == ["image_too_small", "image_blurry"]


def test_un_warning_inconnu_est_refuse():
    with pytest.raises(ValidationError):
        AnalysisResult(status=AnalysisStatus.REJECTED, image=MINIMAL_IMAGE, warnings=["oups"])


def test_les_codes_de_warning_sont_uniques():
    """Deux membres de même valeur seraient un alias silencieux."""
    values = [w.value for w in Warn]
    assert len(values) == len(set(values))
