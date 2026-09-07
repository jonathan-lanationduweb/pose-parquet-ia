"""L'API : santé, formats acceptés, refus."""

import pytest

from app.core.config import ALLOWED_FORMATS
from app.main import REQUEST_ID_HEADER
from app.schemas.analysis import AnalysisStatus
from corpus import patterns


def _post(client, data: bytes, filename: str = "piece.jpg", content_type: str = "image/jpeg"):
    return client.post("/v1/analyze-room", files={"image": (filename, data, content_type)})


def test_health_dit_ok_et_rien_de_plus(client):
    response = client.get("/health")
    assert response.status_code == 200
    # Le contenu exact compte : pas de version d'OS, pas de chemin.
    assert response.json() == {"status": "ok", "service": "pose-parquet-ai"}


def test_health_porte_un_identifiant_de_requete(client):
    assert client.get("/health").headers[REQUEST_ID_HEADER]


def test_identifiant_de_requete_fourni_est_repris(client):
    response = client.get("/health", headers={REQUEST_ID_HEADER: "abc123"})
    assert response.headers[REQUEST_ID_HEADER] == "abc123"


@pytest.mark.parametrize("image_format", sorted(ALLOWED_FORMATS))
def test_les_trois_formats_sont_acceptes(client, image_format):
    data = patterns.encode(patterns.checkerboard(), image_format)
    response = _post(client, data, f"piece.{image_format.lower()}")
    assert response.status_code == 200
    assert response.json()["image"]["format"] == image_format


def test_le_format_est_lu_dans_le_contenu_pas_dans_le_content_type(client):
    """Un PNG annoncé comme JPEG reste un PNG : on ne croit pas le client."""
    data = patterns.encode(patterns.checkerboard(), "PNG")
    response = _post(client, data, "menteur.jpg", "image/jpeg")
    assert response.status_code == 200
    assert response.json()["image"]["format"] == "PNG"


def test_fichier_vide_refuse(client):
    response = _post(client, b"")
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "empty_file"


def test_fichier_indecodable_refuse(client):
    response = _post(client, b"ceci n'est pas une image" * 100)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "undecodable_image"


def test_format_non_pris_en_charge_refuse(client):
    """Un GIF est une image valide, mais hors contrat."""
    data = patterns.encode(patterns.checkerboard(size=(320, 240)), "GIF")
    response = _post(client, data, "anim.gif", "image/gif")
    assert response.status_code == 415
    assert response.json()["detail"]["code"] == "unsupported_format"


def test_fichier_trop_gros_refuse(client, monkeypatch):
    monkeypatch.setenv("PPAI_MAX_UPLOAD_BYTES", "2048")
    from app.core.config import get_settings

    get_settings.cache_clear()
    data = patterns.encode(patterns.noise(), "PNG")
    assert len(data) > 2048
    response = _post(client, data, "grosse.png", "image/png")
    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "file_too_large"


def test_image_manquante_est_une_erreur_de_validation(client):
    assert client.post("/v1/analyze-room").status_code == 422


def test_la_reponse_ne_pretend_pas_avoir_analyse_la_piece(client):
    """Le contrat du LOT 0 : des mesures, aucune scène, aucune confiance."""
    data = patterns.encode(patterns.checkerboard(), "JPEG")
    body = _post(client, data).json()

    assert body["status"] == AnalysisStatus.ANALYSIS_INCOMPLETE
    assert body["sceneData"] is None
    assert body["confidence"] is None
    assert "stage_not_implemented" in body["warnings"]


def test_la_reponse_est_en_camel_case(client):
    """Le front lit du camelCase : le contrat est là, pas dans les noms Python."""
    data = patterns.encode(patterns.checkerboard(), "JPEG")
    body = _post(client, data).json()

    assert body["schema"] == "pose-parquet/analysis@2"
    assert "aspectRatio" in body["image"]
    assert "exifOrientationApplied" in body["image"]
    assert "sceneData" in body


def test_les_timings_declarent_tous_les_etages(client):
    """Un étage non exécuté vaut `None`, pas 0 : la distinction se lit."""
    data = patterns.encode(patterns.checkerboard(), "JPEG")
    timings = _post(client, data).json()["timings"]

    assert timings["load_image_ms"] is not None
    assert timings["quality_analysis_ms"] is not None
    assert timings["total_ms"] is not None
    assert timings["segmentation_ms"] is None
    assert timings["depth_ms"] is None
    assert timings["perspective_ms"] is None


def test_openapi_se_construit(client):
    """Les schémas Pydantic doivent rester sérialisables en OpenAPI."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "/v1/analyze-room" in response.json()["paths"]
