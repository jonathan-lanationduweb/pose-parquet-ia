"""Resolution bounds and removal of technical padding, without loading real weights."""

from contextlib import nullcontext
from types import SimpleNamespace

import numpy as np
import pytest

from app.services import floor_semantic


@pytest.mark.parametrize("height,width", [(240, 320), (1067, 1600), (3000, 4000)])
def test_bounded_model_input_preserves_original_mask_and_removes_padding(
    monkeypatch, height, width
):
    original = np.zeros((height, width, 3), dtype=np.uint8)
    ratio = min(1, 640 / max(height, width))
    small_height = round(height * ratio)
    observed = {}

    class Tensor:
        shape = None

        def to(self, device):
            assert device == "cpu"
            return self

    class Labels:
        def __init__(self, labels):
            self.labels = labels

        def cpu(self):
            return self

        def numpy(self):
            return self.labels

    class Processor:
        def __call__(self, *, images, **kwargs):
            observed["size"] = images.size
            assert kwargs["do_resize"] is False
            tensor = Tensor()
            tensor.shape = [1, 3, images.height, images.width]
            return {"pixel_values": tensor}

        def post_process_semantic_segmentation(self, _outputs, *, target_sizes):
            labels = np.full(target_sizes[0], 3, dtype=np.int32)
            labels[small_height:] = 28
            return [Labels(labels)]

    monkeypatch.setenv("PPAI_INFERENCE_LONG_SIDE", "640")
    monkeypatch.setattr(
        floor_semantic, "_torch", lambda: SimpleNamespace(inference_mode=nullcontext)
    )
    engine = floor_semantic.OneFormerFloor()
    # A callable model exposes its placement, as the real transformers model does.
    class Model:
        device = "cpu"

        def __call__(self, **_kwargs):
            return None

    monkeypatch.setattr(engine, "_charger", lambda: (Processor(), Model(), 0))
    result = engine.segment(original)
    assert max(observed["size"]) <= 640
    assert all(side % 32 == 0 for side in observed["size"])
    assert result.mask.shape == (height, width)
    assert result.mask.all()  # artificial rug in the padding must not leak into the photo
    assert result.labels.dtype == np.int32
