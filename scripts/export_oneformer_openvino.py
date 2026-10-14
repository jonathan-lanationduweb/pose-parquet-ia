"""Reproducible local OneFormer exports; no photo, weights or graph enters Git.

Install the inference dependencies and OpenVINO first. Export examples are
synthetic; --validation-photo can privately check conformance on a real room.
The manifest records numerical conformance, not ground-truth segmentation quality.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import cv2
import numpy as np
from PIL import Image

from app.services.openvino_post import add_semantic_postprocessing


def main() -> None:
    """Export two general aspect profiles and validate each before selecting it."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device', choices=('CPU', 'GPU'), default='GPU')
    parser.add_argument('--validation-photo', type=Path)
    parser.add_argument('--reuse-raw', action='store_true')
    parser.add_argument('--fuse-postprocessing', action='store_true')
    args = parser.parse_args()
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['PPAI_INFERENCE_BACKEND'] = 'torch'
    import openvino as ov
    import torch
    from torch import nn

    from app.services.floor_semantic import OneFormerFloor, semantic_labels_chunked

    torch.set_num_threads(4)
    cv2.setNumThreads(1)
    engine = OneFormerFloor()
    processor, model, _ = engine._charger()

    class Wrapper(nn.Module):
        def __init__(self, network: Any) -> None:
            super().__init__()
            self.network = network

        def forward(self, pixels: Any, task: Any) -> tuple[Any, Any]:
            output = self.network(pixel_values=pixels, task_inputs=task)
            return output.class_queries_logits, output.masks_queries_logits

    core = ov.Core()
    options: dict[str, Any] = {'PERFORMANCE_HINT': 'LATENCY',
                               'INFERENCE_PRECISION_HINT': 'f16' if args.device == 'GPU' else 'f32',
                               'CACHE_DIR': 'models/openvino-cache'}
    if args.device == 'CPU':
        options['INFERENCE_NUM_THREADS'] = 4
    for height, width, name, fused_name in ((352, 512, '512x352', '512x352'),
                                           (512, 512, '512-square', '512')):
        # Every conversion uses synthetic pixels, never a private photo constant.
        synthetic = np.random.default_rng(42).integers(0, 255, (height, width, 3), np.uint8)
        inputs = processor(images=Image.fromarray(synthetic), task_inputs=['semantic'],
                           return_tensors='pt', do_resize=False)
        example = (inputs['pixel_values'], inputs['task_inputs'])
        raw_path = Path(f'models/oneformer-openvino-{name}.xml')
        if args.reuse_raw and raw_path.is_file():
            converted = core.read_model(str(raw_path))
        else:
            converted = ov.convert_model(Wrapper(model).eval(), example_input=example)
            ov.save_model(converted, str(raw_path), compress_to_fp16=False)
        fused_path = Path(f'models/oneformer-openvino-{fused_name}-semantic.xml')
        fused = add_semantic_postprocessing(converted, height, width)
        ov.save_model(fused, str(fused_path), compress_to_fp16=False)
        validation = synthetic
        if args.validation_photo:
            image = np.array(Image.open(args.validation_photo).convert('RGB'))
            ratio = min(height / image.shape[0], width / image.shape[1], 1)
            small = cv2.resize(image, (round(image.shape[1] * ratio),
                                      round(image.shape[0] * ratio)), interpolation=cv2.INTER_AREA)
            validation = cv2.copyMakeBorder(small, 0, height - small.shape[0], 0,
                                           width - small.shape[1], cv2.BORDER_REPLICATE)
        inputs = processor(images=Image.fromarray(validation), task_inputs=['semantic'],
                           return_tensors='pt', do_resize=False)
        with torch.inference_mode():
            reference = semantic_labels_chunked(model(**inputs), (height, width))[0].numpy()
        selected_model = fused if args.fuse_postprocessing else converted
        compiled = core.compile_model(selected_model, args.device, options)
        values = compiled([inputs['pixel_values'].numpy(), inputs['task_inputs'].numpy()])
        if args.fuse_postprocessing:
            labels = values[compiled.output(0)][0]
        else:
            raw_outputs = SimpleNamespace(
                class_queries_logits=torch.from_numpy(values[compiled.output(0)]),
                masks_queries_logits=torch.from_numpy(values[compiled.output(1)]),
            )
            labels = semantic_labels_chunked(raw_outputs, (height, width))[0].numpy()
        a, b = labels == 3, reference == 3
        union = int(np.logical_or(a, b).sum())
        floor_iou = float(np.logical_and(a, b).sum() / union) if union else 1.
        agreement = float((labels == reference).mean())
        floor_tolerance = 0.995 if args.fuse_postprocessing else 0.99
        valid = floor_iou >= floor_tolerance and agreement >= 0.95
        manifest = {'checkpoint': engine.checkpoint, 'inputShape': [1, 3, height, width],
                    'validated': valid, 'device': args.device, 'openvino': ov.__version__,
                    'floorIoUAgainstTorch': floor_iou, 'labelAgreement': agreement,
                    'validationKind': 'numerical conformance, not ground-truth quality'}
        if args.fuse_postprocessing:
            fused_path.with_suffix('.json').write_text(
                json.dumps(manifest, indent=2), encoding='utf-8'
            )
        raw_path.with_suffix('.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        print(json.dumps({'profile': name, **manifest}), flush=True)
        if not valid:
            raise RuntimeError('Export conformance failed; this profile is not validated')


if __name__ == '__main__':
    main()
