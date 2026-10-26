"""The floor-only path must not execute wall post-processing."""

from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from app.core.config import Settings
from app.services import floor_scene, model_warmup, pipeline, wall_regions


def test_walls_are_disabled_by_default(monkeypatch):
    monkeypatch.delenv("PPAI_ENABLE_WALLS", raising=False)
    assert Settings(_env_file=None).enable_walls is False


@pytest.mark.parametrize("enabled", [False, True])
def test_wall_postprocessing_obeys_flag(monkeypatch, enabled):
    mask = np.zeros((64, 64), dtype=bool)
    result = SimpleNamespace(
        mask=mask,
        labels=np.zeros((64, 64), dtype=np.int32),
        candidate="oneformer",
        timings={},
        metadata={},
        coverage=0,
        boundary=[],
    )
    monkeypatch.setattr(
        pipeline,
        "get_settings",
        lambda: SimpleNamespace(
            experimental_floor_candidate="oneformer",
            experimental_floor_min_confidence=0.55,
            enable_walls=enabled,
        ),
    )
    monkeypatch.setattr(model_warmup, "wait_ready", lambda **_kwargs: None)
    monkeypatch.setattr(
        model_warmup,
        "segmenter_pour",
        lambda _candidate: SimpleNamespace(segment=lambda _rgb: result),
    )
    monkeypatch.setattr(floor_scene, "build_experimental_scene", lambda *_args, **_kwargs: None)
    detect = Mock(return_value={"zones": [], "timingMs": 3})
    monkeypatch.setattr(wall_regions, "wall_regions", detect)
    output = pipeline._segmentation_experimentale(np.zeros((64, 64, 3), dtype=np.uint8))
    assert output is not None
    assert detect.call_count == int(enabled)
    assert ("wall_regions" in result.timings) is enabled
    assert (output.walls is not None) is enabled
