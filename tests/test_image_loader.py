"""Chargement, refus et redressement EXIF."""

import numpy as np
import pytest
from PIL import Image

from app.core.errors import ImageRejected
from app.services.image_loader import load_image, luma
from tests import factories


def test_dimensions_lues_apres_decodage():
    data = factories.encode(factories.checkerboard(size=(800, 600)), "JPEG")
    image = load_image(data)
    assert (image.width, image.height) == (800, 600)


def test_fichier_vide_leve():
    with pytest.raises(ImageRejected) as raised:
        load_image(b"")
    assert raised.value.code == "empty_file"
    assert raised.value.http_status == 422


def test_octets_aleatoires_levent():
    with pytest.raises(ImageRejected) as raised:
        load_image(b"\x00\x01\x02\x03" * 500)
    assert raised.value.code == "undecodable_image"


def test_jpeg_tronque_leve():
    """Un fichier coupé en deux a un en-tête valide et un contenu impossible."""
    data = factories.encode(factories.noise(), "JPEG")
    with pytest.raises(ImageRejected) as raised:
        load_image(data[: len(data) // 2])
    assert raised.value.code == "undecodable_image"


def test_trop_de_pixels_leve(monkeypatch):
    monkeypatch.setenv("PPAI_MAX_IMAGE_PIXELS", "1000")
    from app.core.config import get_settings

    get_settings.cache_clear()
    data = factories.encode(factories.checkerboard(size=(800, 600)), "PNG")
    with pytest.raises(ImageRejected) as raised:
        load_image(data)
    assert raised.value.code == "image_too_many_pixels"
    assert raised.value.http_status == 413


# --- Orientation EXIF ----------------------------------------------------


def test_orientation_exif_6_redresse_en_portrait():
    """Une image paysage marquée « tournée » doit ressortir en portrait.

    C'est le test qui compte : le fichier fait 960 × 720, la balise dit qu'il
    faut le tourner, l'image analysée doit donc faire 720 × 960.
    """
    image = load_image(factories.portrait_with_exif_rotation())
    assert (image.width, image.height) == (720, 960)
    assert image.exif_orientation_applied is True


def test_paysage_sans_exif_reste_paysage():
    data = factories.encode(factories.checkerboard(size=(960, 720)), "JPEG")
    image = load_image(data)
    assert (image.width, image.height) == (960, 720)
    assert image.exif_orientation_applied is False


def test_portrait_sans_exif_reste_portrait():
    data = factories.encode(factories.checkerboard(size=(720, 960)), "JPEG")
    image = load_image(data)
    assert (image.width, image.height) == (720, 960)
    assert image.exif_orientation_applied is False


def test_orientation_1_ne_transforme_rien():
    """Orientation déclarée « déjà droite » : rien ne bouge, et on le dit."""
    array = factories.checkerboard(size=(640, 480))
    pil = Image.fromarray(array, mode="RGB")
    exif = pil.getexif()
    exif[0x0112] = 1
    from io import BytesIO

    buffer = BytesIO()
    pil.save(buffer, format="JPEG", exif=exif)

    image = load_image(buffer.getvalue())
    assert (image.width, image.height) == (640, 480)
    assert image.exif_orientation_applied is False


def test_le_contenu_est_bien_pivote_pas_seulement_les_dimensions():
    """Vérifie la rotation sur les pixels, pas sur les métadonnées.

    Un bandeau clair est posé en haut d'une image marquée orientation 8, qui
    veut dire « tournée de 90° dans le sens antihoraire ». Après
    redressement, ce bandeau doit se retrouver sur le bord **gauche** : un
    test qui ne regarderait que les dimensions passerait aussi bien avec une
    rotation dans le mauvais sens.
    """
    from io import BytesIO

    array = np.full((400, 600, 3), 30, dtype=np.uint8)
    array[:40, :, :] = 240  # bandeau clair en haut

    pil = Image.fromarray(array, mode="RGB")
    exif = pil.getexif()
    exif[0x0112] = 8
    buffer = BytesIO()
    pil.save(buffer, format="PNG", exif=exif)

    image = load_image(buffer.getvalue())
    assert (image.width, image.height) == (400, 600)
    gray = luma(image.rgb)
    assert gray[:, :20].mean() > 0.8  # le bandeau est passé à gauche
    assert gray[:, -20:].mean() < 0.2


# --- Luma ----------------------------------------------------------------


def test_luma_est_normalisee():
    white = luma(factories.flat(255, size=(64, 64)))
    black = luma(factories.flat(0, size=(64, 64)))
    assert white.mean() == pytest.approx(1.0, abs=1e-4)
    assert black.mean() == pytest.approx(0.0, abs=1e-4)


def test_luma_pondere_le_vert_plus_que_le_bleu():
    """Rec. 709, pas une moyenne des canaux : le vert pèse dix fois le bleu."""
    green = np.zeros((8, 8, 3), dtype=np.uint8)
    green[:, :, 1] = 255
    blue = np.zeros((8, 8, 3), dtype=np.uint8)
    blue[:, :, 2] = 255
    assert luma(green).mean() > luma(blue).mean() * 5
