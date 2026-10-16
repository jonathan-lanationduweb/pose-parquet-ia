"""Replay the private twelve-photo suite without rerunning segmentation or depth."""
from __future__ import annotations

import json
import time
from pathlib import Path

import cv2
import numpy as np

from app.services.floor_scene import build_experimental_scene, refine_mask


def edge(mask: np.ndarray) -> np.ndarray:
    return np.asarray(mask != cv2.erode(
        mask.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool))


def main() -> None:
    cv2.setNumThreads(1)
    root = Path('review/room-understanding-v2-1')
    rows = []
    for folder in sorted(root.iterdir()):
        if not folder.is_dir() or not (folder/'raw-mask.png').exists():
            continue
        if (folder/'prepared.json').exists():
            rows.append(json.loads((folder/'prepared.json').read_text(encoding='utf-8')))
            continue
        image = cv2.imread(str(folder/'original.jpg'))
        original = Path('review/room-understanding-v2')/folder.name/'original.png'
        if original.exists():
            image = cv2.imread(str(original))
        if image is None:
            raise ValueError(folder)
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        raw_image = cv2.imread(str(folder/'raw-mask.png'), 0)
        if raw_image is None:
            raise ValueError(folder)
        raw = raw_image > 127
        durations = []
        for _ in range(3):
            start = time.perf_counter()
            refined = refine_mask(raw, image_rgb=rgb)
            durations.append((time.perf_counter()-start)*1000)
        cv2.imwrite(str(folder/'refined-mask.png'), refined.astype(np.uint8)*255)
        before, after = edge(raw), edge(refined)
        distances = cv2.distanceTransform((~before).astype(np.uint8), cv2.DIST_L2, 5)[after]
        start = time.perf_counter()
        scene = build_experimental_scene(raw, rgb.shape[1], rgb.shape[0], image_rgb=rgb)
        ms = (time.perf_counter()-start)*1000
        if scene.scene:
            (folder/'scene-after.json').write_text(scene.scene.model_dump_json(
                by_alias=True, exclude_none=True), encoding='utf-8')
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        detected = cv2.Canny(gray, 60, 140)
        distance = cv2.distanceTransform((detected == 0).astype(np.uint8), cv2.DIST_L2, 5)
        baseline_image = cv2.imread(str(folder/'baseline-mask.png'), 0)
        if baseline_image is None:
            raise ValueError(folder)
        baseline = edge(baseline_image > 127)
        diagnostic = image.copy()
        diagnostic[after] = (40, 220, 40)
        diagnostic[before & ~after] = (30, 30, 220)
        cv2.imwrite(str(folder/'final-boundary.jpg'), diagnostic)
        row = {'id':folder.name, 'boundaryMs':float(np.median(durations)),
               'boundaryMeanDisplacementPx':float(distances.mean()) if distances.size else 0,
               'boundaryMaxDisplacementPx':float(distances.max()) if distances.size else 0,
               'edgeDistanceBeforePx':float(distance[baseline].mean()) if baseline.any() else None,
               'edgeDistanceAfterPx':float(distance[after].mean()) if after.any() else None,
               'sceneBuildMs':ms, 'geometryMs':scene.provenance['timingsMs'].get('camera_geometry'),
               'manualRequired':scene.status in {'no_floor','needs_manual_adjustment'},
               'manualRecommended':scene.status=='approximate_render', 'status':scene.status,
               'perspective':scene.perspective,
               'note':'Displacement and Canny distance are diagnostics, not ground-truth accuracy.'}
        rows.append(row)
        (folder/'measurement.json').write_text(json.dumps(row,indent=2),encoding='utf-8')
        (root/'matrix.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in row.items()
                          if k not in {'perspective','note'}}),flush=True)


if __name__ == '__main__':
    main()
