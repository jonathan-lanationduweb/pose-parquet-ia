"""Le pipeline : ordre des étages, chronométrage, et la décision de statut."""

import pytest

from app.core.timing import STAGES, Timings
from app.core.warnings import Warn
from app.schemas.analysis import AnalysisStatus
from app.services.pipeline import _decide_status, analyse_room
from app.services.scene_builder import build_scene_data, missing_stage_warnings
from tests import factories


def test_une_photo_correcte_donne_analysis_incomplete():
    """Rien ne cloche, et pourtant ce n'est pas un succès : aucune scène."""
    result = analyse_room(factories.encode(factories.checkerboard(), "JPEG")).result

    assert result.status is AnalysisStatus.ANALYSIS_INCOMPLETE
    assert result.scene_data is None
    assert result.quality is not None
    assert result.lens is not None


def test_une_photo_trop_petite_est_rejetee():
    data = factories.encode(factories.checkerboard(size=(320, 240)), "JPEG")
    result = analyse_room(data).result

    assert result.status is AnalysisStatus.REJECTED
    assert Warn.IMAGE_TOO_SMALL in result.warnings


def test_une_photo_rejetee_ne_paye_pas_l_analyse_d_objectif():
    """L'étage le plus coûteux du LOT 0 n'a pas à tourner pour rien."""
    data = factories.encode(factories.checkerboard(size=(320, 240)), "JPEG")
    result = analyse_room(data).result

    assert result.lens is None
    assert result.timings["lens_analysis_ms"] is None


def test_les_logs_ne_contiennent_que_des_champs_autorises():
    """Ni image, ni base64, ni nom de fichier, ni chemin."""
    analysis = analyse_room(factories.encode(factories.checkerboard(), "JPEG"))

    assert set(analysis.log_fields) == {
        "status",
        "width",
        "height",
        "format",
        "exif_applied",
        "warnings",
        "total_ms",
    }


def test_l_analyse_travaille_sur_l_image_redressee():
    """Le fichier est paysage, l'EXIF dit portrait : c'est le portrait qui compte."""
    result = analyse_room(factories.portrait_with_exif_rotation()).result

    assert (result.image.width, result.image.height) == (720, 960)
    assert result.image.exif_orientation_applied is True
    assert result.image.aspect_ratio == pytest.approx(0.75, abs=0.01)


# --- Décision de statut --------------------------------------------------


def test_sans_scene_le_statut_ne_pretend_rien():
    assert _decide_status([], scene_present=False) is AnalysisStatus.ANALYSIS_INCOMPLETE


def test_un_warning_bloquant_rejette_meme_avec_une_scene():
    status = _decide_status([Warn.IMAGE_TOO_SMALL], scene_present=True)
    assert status is AnalysisStatus.REJECTED


def test_une_scene_avec_warnings_demande_une_relecture():
    status = _decide_status([Warn.PERSPECTIVE_UNCERTAIN], scene_present=True)
    assert status is AnalysisStatus.NEEDS_MANUAL_ADJUSTMENT


def test_le_succes_exige_une_scene_et_aucun_warning():
    assert _decide_status([], scene_present=True) is AnalysisStatus.SUCCESS


# --- Étages absents ------------------------------------------------------


def test_le_scene_builder_ne_fabrique_rien_au_lot_0():
    assert build_scene_data() is None


def test_un_etage_absent_le_dit_plutot_que_de_se_taire():
    """« Rien à signaler » et « je n'ai pas regardé » ne sont pas la même chose."""
    assert missing_stage_warnings() == [Warn.STAGE_NOT_IMPLEMENTED]


# --- Chronométrage -------------------------------------------------------


def test_un_etage_inconnu_est_refuse():
    with pytest.raises(ValueError, match="Étage inconnu"), Timings().measure("teleportation"):
        pass


def test_un_etage_qui_leve_est_quand_meme_chronometre():
    """Une étape qui échoue au bout de 4 secondes est une information."""
    timings = Timings()
    with pytest.raises(RuntimeError), timings.measure("depth"):
        raise RuntimeError("panne")
    assert timings.stages["depth"] is not None


def test_tous_les_etages_sont_declares_dans_la_sortie():
    reported = Timings().as_dict()
    assert set(reported) == {f"{stage}_ms" for stage in STAGES} | {"total_ms"}
