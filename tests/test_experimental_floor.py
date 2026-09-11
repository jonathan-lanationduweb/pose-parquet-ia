"""La sortie expérimentale de segmentation — LOT C.0.

    EXPLORATOIRE · AUCUNE VÉRITÉ TERRAIN · AUCUN MODÈLE RETENU

Ce que ces tests protègent n'est pas la qualité du masque — elle n'est pas
mesurable aujourd'hui — mais **le contrat**. Deux promesses, et elles sont
plus importantes que le masque :

* sans le drapeau, la réponse est **exactement** celle d'avant ce lot. Un
  client écrit la semaine dernière ne voit rien de nouveau ;
* avec le drapeau, ce qui arrive est clairement nommé `experimental`, ne
  remplit jamais `sceneData`, et porte sa mention dans les données
  elles-mêmes. Un masque exploratoire qui se ferait passer pour une scène
  déclencherait un rendu — c'est-à-dire un faux parquet sur la photo de
  quelqu'un.

Aucun de ces tests ne charge un modèle appris : ils passent par le candidat
géométrique, qui ne télécharge rien. Le contrat se vérifie donc sur n'importe
quelle machine, y compris sans `torch`.
"""

from __future__ import annotations

import base64
from collections.abc import Iterator

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app
from app.services.floor_segmentation import (
    ADE20K_FLOOR,
    ADE20K_RUG,
    ADE20K_WALL,
    mask_to_png_bytes,
    semantic_to_floor_visible,
)
from corpus import patterns


@pytest.fixture(autouse=True)
def _reglages_neufs() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _photo() -> bytes:
    """Une image synthétique : ces tests jugent le contrat, pas le rendu."""
    return patterns.encode(patterns.mid_tone_checkerboard((640, 480)), "JPEG")


# --- L'adaptation de la classe académique -------------------------------


def test_le_sol_predit_exclut_le_tapis() -> None:
    """La seule soustraction faite, et elle est générale.

    ADE20K distingue `floor` de `rug;carpet` : c'est ce qui permet de retirer
    un tapis sans le reconnaître soi-même. Notre `floorVisible` l'exige, et
    cette fonction est l'endroit exact où l'exigence s'applique.
    """
    labels = np.full((4, 4), ADE20K_WALL, dtype=np.int32)
    labels[2:, :] = ADE20K_FLOOR
    labels[3, 0] = ADE20K_RUG

    masque = semantic_to_floor_visible(labels)
    assert masque[2, 0], "le sol est du sol"
    assert not masque[3, 0], "le tapis n'est pas du sol remplaçable"
    assert not masque[0, 0], "le mur n'est pas du sol"


def test_l_adaptation_ne_devine_rien_d_autre() -> None:
    """Aucune classe n'est ajoutée au sol par charité.

    La tentation serait d'inclure `earth` ou `path` pour « rattraper » une
    pièce mal prédite. Ce serait fabriquer une correction que le modèle n'a
    pas faite, et la comparaison suivante en deviendrait fausse.
    """
    labels = np.array([[6, 13, 29, 52]], dtype=np.int32)  # earth, terre, champ, chemin
    assert not semantic_to_floor_visible(labels).any()


def test_le_masque_s_encode_en_png_relisible() -> None:
    """Format retenu pour cette passe : quelques kilo-octets, relisible."""
    import cv2

    masque = np.zeros((40, 60), dtype=bool)
    masque[20:, :] = True
    octets = mask_to_png_bytes(masque)
    relu = cv2.imdecode(np.frombuffer(octets, np.uint8), cv2.IMREAD_GRAYSCALE)
    assert relu.shape == masque.shape
    assert np.array_equal(relu > 127, masque), "aller-retour sans perte"
    assert len(octets) < 4096, "un masque binaire est petit"


# --- Le contrat, avec et sans le drapeau --------------------------------


def test_sans_le_drapeau_la_reponse_est_celle_d_avant(monkeypatch: pytest.MonkeyPatch) -> None:
    """La promesse la plus importante de ce lot."""
    monkeypatch.setenv("PPAI_EXPERIMENTAL_FLOOR", "0")
    client = TestClient(create_app())
    reponse = client.post("/v1/analyze-room", files={"image": ("p.jpg", _photo(), "image/jpeg")})
    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["experimental"] is None
    assert corps["sceneData"] is None
    assert corps["schema"] == "pose-parquet/analysis@2", "le schéma ne change pas"
    assert corps["timings"]["segmentation_ms"] is None, "l'étage n'a pas tourné"


def test_le_defaut_du_drapeau_est_faux() -> None:
    """Et c'est ce défaut qui va en production.

    Vérifié sur la classe, fichier d'environnement neutralisé : un `.env` de
    poste de travail ne doit pas faire passer ce test pour la mauvaise raison.
    """
    from app.core.config import Settings

    assert Settings(_env_file=None).experimental_floor is False  # type: ignore[call-arg]


def test_le_champ_experimental_est_additif() -> None:
    """Ajouter un champ optionnel n'est pas rompre un contrat.

    `analysis@2` reste `analysis@2` : un client qui ne connaît pas ce champ lit
    la même réponse qu'avant. La rupture viendrait du jour où quelque chose
    ici deviendrait obligatoire, ou entrerait dans `sceneData` — et ce jour-là
    il faudra une version majeure.
    """
    from app.schemas.analysis import AnalysisResult

    champ = AnalysisResult.model_fields["experimental"]
    assert champ.default is None
    assert not champ.is_required()


def test_avec_le_drapeau_la_sortie_est_nommee_et_inoffensive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Le masque arrive, et il ne peut rien déclencher.

    Candidat `opencv` exprès : il ne télécharge rien et ne demande pas torch,
    donc ce test vérifie le CHEMIN, sur toute machine, sans dépendre d'un
    modèle appris.
    """
    monkeypatch.setenv("PPAI_EXPERIMENTAL_FLOOR", "1")
    monkeypatch.setenv("PPAI_EXPERIMENTAL_FLOOR_CANDIDATE", "opencv")
    client = TestClient(create_app())
    corps = client.post(
        "/v1/analyze-room", files={"image": ("p.jpg", _photo(), "image/jpeg")}
    ).json()

    sol = corps["experimental"]["floor"]
    assert sol["candidate"] == "opencv-baseline"
    assert corps["sceneData"] is None, "jamais une scène : aucun rendu ne se déclenche"
    assert "EXPERIMENTAL" in sol["disclaimer"]
    assert 0.0 <= sol["coverage"] <= 1.0
    assert sol["maskWidth"] == 640 and sol["maskHeight"] == 480
    #: Le masque est un PNG réel, pas une chaîne décorative.
    octets = base64.b64decode(sol["maskPngBase64"])
    assert octets[:8] == b"\x89PNG\r\n\x1a\n"
    assert corps["timings"]["segmentation_ms"] is not None, "l'étage a tourné"


def test_un_candidat_qui_echoue_ne_casse_pas_l_analyse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """L'analyse normale a déjà réussi : une sortie hors contrat ne l'emporte pas.

    On force l'échec par un candidat dont le chargement jette, et on vérifie
    que la réponse reste un 200 complet, `experimental` simplement absent.
    """
    monkeypatch.setenv("PPAI_EXPERIMENTAL_FLOOR", "1")
    monkeypatch.setenv("PPAI_EXPERIMENTAL_FLOOR_CANDIDATE", "opencv")

    def tombe(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("panne simulée du candidat")

    monkeypatch.setattr(
        "app.services.floor_geometric.GeometricFloorBaseline.segment", tombe, raising=True
    )
    client = TestClient(create_app())
    reponse = client.post("/v1/analyze-room", files={"image": ("p.jpg", _photo(), "image/jpeg")})
    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["experimental"] is None
    assert corps["quality"] is not None, "l'analyse normale est intacte"
