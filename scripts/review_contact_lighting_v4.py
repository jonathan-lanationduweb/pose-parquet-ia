"""Prepare private review inputs without changing segmentation/camera/catalogue."""

import json
from pathlib import Path
from shutil import copyfile

import cv2
import numpy as np

from app.services.lighting_layers import build_lighting_layers, encode_lighting_layers

ROOT = Path("review/contact-shadow-lighting-v4")
CASES = {
    "empty": "piece-claire",
    "sofa": "owner-photo",
    "thin-legs": "salle-a-manger-meublee",
    "rug": "premibel-entree",
    "dark": "couloir-enfilade",
    "bright": "cuisine-ilot",
    "old-floor": "bureau-meuble",
    "plant": "premibel-chambre",
}


def main() -> None:
    for name, source in CASES.items():
        src = Path("review/scene-understanding-v3") / source
        dest = ROOT / name
        dest.mkdir(parents=True, exist_ok=True)
        raw = json.loads((src / "quality.json").read_text(encoding="utf8"))
        image = cv2.imread(str(src / "01-original.png"))
        mask = cv2.imread(str(src / "02-floor-mask.png"), cv2.IMREAD_GRAYSCALE)
        mask = mask.astype(np.float32) / 255
        occlusion = cv2.imread(str(src / "03-foreground-mask.png"), cv2.IMREAD_GRAYSCALE)
        occlusion = occlusion.astype(np.float32) / 255
        layers = build_lighting_layers(image, mask, occlusion)
        raw["light"]["lightLayer"] = encode_lighting_layers(layers, mask).model_dump(by_alias=True)
        (dest / "scene.json").write_text(json.dumps(raw), encoding="utf8")
        copyfile(src / "01-original.png", dest / "01-original.png")
        stats = {
            "source": source,
            "size": list(image.shape[:2][::-1]),
            "gain": layers["gain"],
            "min": float(layers["lightLayer"].min()),
            "max": float(layers["lightLayer"].max()),
        }
        (dest / "lighting.json").write_text(json.dumps(stats, indent=2), encoding="utf8")
        print(name, stats)


if __name__ == "__main__":
    main()
