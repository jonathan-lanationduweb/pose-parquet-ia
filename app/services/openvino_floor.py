"""Optional local Intel runtime for the same OneFormer checkpoint.

The exported graph has a fixed square input. Replicated padding preserves the
photo aspect ratio; predictions are cropped before returning to original pixels.
No model download or export happens during a user's request.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

MODEL_PATH = Path('models/oneformer-openvino-512-square.xml')


def available(checkpoint: str) -> bool:
    """Only select a reviewed graph with a matching checkpoint/shape manifest."""
    paths = ((MODEL_PATH, [1, 3, 512, 512]),
             (Path('models/oneformer-openvino-512x352.xml'), [1, 3, 352, 512]))
    for model_path, shape in paths:
        manifest = model_path.with_suffix('.json')
        if (not model_path.is_file() or not model_path.with_suffix('.bin').is_file()
                or not manifest.is_file()):
            return False
        try:
            data = json.loads(manifest.read_text(encoding='utf-8'))
            if (data.get('checkpoint') != checkpoint or data.get('inputShape') != shape
                    or data.get('validated') is not True):
                return False
        except (OSError, ValueError):
            return False
    return True


class OpenVinoOneFormer:
    """The minimal tensor interface used by the existing segmentation adapter."""

    canonical_side = 512
    backend = 'openvino-cpu'

    def __init__(self) -> None:
        import openvino as ov
        import torch

        self.device = torch.device('cpu')
        threads = max(1, min(8, int(os.environ.get('PPAI_TORCH_THREADS', '4'))))
        core = ov.Core()
        requested_device = os.environ.get('PPAI_OPENVINO_DEVICE', 'GPU')
        if requested_device not in {'CPU', 'GPU'}:
            raise ValueError('PPAI_OPENVINO_DEVICE must be CPU or GPU')
        target = requested_device if requested_device in core.available_devices else 'CPU'
        options: dict[str, Any] = {
            'PERFORMANCE_HINT': 'LATENCY', 'CACHE_DIR': 'models/openvino-cache',
                   'INFERENCE_PRECISION_HINT': 'f16' if target == 'GPU' else 'f32'}
        if target == 'CPU':
            options['INFERENCE_NUM_THREADS'] = threads
        self.backend = f'openvino-{target.lower()}'
        self.core, self.target, self.options = core, target, options
        self.compiled_profiles: dict[tuple[int, int], Any] = {}
        self.post_profiles: dict[tuple[int, int], Any] = {}
        self.post_backend = "openvino-cpu-f32"
        self.select_shape((480, 640))

    def select_shape(self, image_shape: tuple[int, int]) -> tuple[int, int]:
        height, width = image_shape
        shape = (352, 512) if width / height >= 1.25 else (512, 512)
        base = '512x352' if shape == (352, 512) else '512'
        fused = Path(f'models/oneformer-openvino-{base}-semantic.xml')
        raw = (Path('models/oneformer-openvino-512x352.xml') if shape == (352, 512)
               else MODEL_PATH)
        # Fused postprocessing is selected only after its local conformance check.
        manifest = fused.with_suffix('.json')
        try:
            data = json.loads(manifest.read_text(encoding='utf-8'))
            valid = (data.get('validated') is True
                     and data.get('inputShape') == [1, 3, *shape]
                     and data.get('checkpoint') == 'shi-labs/oneformer_ade20k_swin_tiny')
        except (OSError, ValueError):
            valid = False
        self.fused_post = bool(fused.is_file() and valid)
        selected = fused if self.fused_post else raw
        if shape not in self.compiled_profiles:
            self.compiled_profiles[shape] = (self.core.compile_model(
                str(selected), self.target, self.options
            ), self.fused_post)
        self.compiled, self.fused_post = self.compiled_profiles[shape]
        self.active_shape = shape
        if not self.fused_post and shape not in self.post_profiles:
            import numpy as np
            import openvino as ov
            from openvino import opset13 as op

            from app.services.openvino_post import add_semantic_postprocessing

            classes = op.parameter([1, -1, 151], np.float32)
            masks = op.parameter([1, -1, -1, -1], np.float32)
            base = ov.Model([classes, masks], [classes, masks])
            post = add_semantic_postprocessing(base, *shape)
            self.post_profiles[shape] = self.core.compile_model(
                post, 'CPU', {'PERFORMANCE_HINT': 'LATENCY', 'INFERENCE_NUM_THREADS': 4,
                              'INFERENCE_PRECISION_HINT': 'f32'}
            )
        return shape

    def __call__(self, **inputs: Any) -> Any:
        import time

        started = time.perf_counter()
        result = self.compiled([inputs['pixel_values'].cpu().numpy(),
                                inputs['task_inputs'].cpu().numpy()])
        inference_ms = (time.perf_counter() - started) * 1000
        if self.fused_post:
            return SimpleNamespace(semantic_labels=result[self.compiled.output(0)],
                                   floor_probability=result[self.compiled.output(1)])
        started = time.perf_counter()
        post = self.post_profiles[self.active_shape]
        outputs = post([result[self.compiled.output(0)], result[self.compiled.output(1)]])
        return SimpleNamespace(semantic_labels=outputs[post.output(0)],
                               floor_probability=outputs[post.output(1)],
                               inference_ms=inference_ms,
                               postprocess_ms=(time.perf_counter() - started) * 1000)
