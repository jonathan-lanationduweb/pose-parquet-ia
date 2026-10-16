"""Prepare the reviewed Depth Anything V2 Small export locally, using synthetic input.

Weights must already exist in the directory. The experiment never downloads a
model while processing a photo and never uploads a private image. See the R&D
benchmark for real CPU/GPU conformance and latency measurements.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def main() -> None:
    import openvino as ov
    import torch
    from transformers import AutoModelForDepthEstimation

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, default=Path("models/depth-anything-v2-small"))
    parser.add_argument("--side", type=int, default=392)
    args = parser.parse_args()
    if args.side < 140 or args.side > 700 or args.side % 14:
        raise ValueError("Depth input side must be a multiple of 14 between 140 and 700")
    torch.set_num_threads(4)
    model = AutoModelForDepthEstimation.from_pretrained(
        args.model_dir, local_files_only=True).eval()

    class Export(torch.nn.Module):
        def __init__(self, network: Any) -> None:
            super().__init__()
            self.network = network

        def forward(self, pixels: Any) -> Any:
            return self.network(pixel_values=pixels).predicted_depth

    sample = torch.zeros((1, 3, args.side, args.side))
    graph = ov.convert_model(Export(model).eval(), example_input=sample)
    path = args.model_dir / f"openvino-{args.side}.xml"
    ov.save_model(graph, str(path))
    weights = args.model_dir / "model.safetensors"
    metadata = {"model": "depth-anything/Depth-Anything-V2-Small-hf",
                "license": "Apache-2.0", "inputShape": list(sample.shape),
                "weightsSha256": hashlib.sha256(weights.read_bytes()).hexdigest(),
                "kind": "relative inverse depth, unknown scale and shift",
                "validationRequired": "Validate private CPU/GPU results before integration"}
    path.with_suffix(".json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()
