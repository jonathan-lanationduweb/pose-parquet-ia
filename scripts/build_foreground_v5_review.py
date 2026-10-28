"""Build the private human review; annotations are evidence, never runtime rules."""

# Long HTML literals are intentional in this standalone private review generator.
# ruff: noqa: E501
import html
import json
from pathlib import Path
from time import perf_counter

import cv2
import numpy as np
from PIL import Image

from app.services.foreground import RUG, polygons

ROOT = Path("review/foreground-mask-v5")
# Human review ROIs, not input to ForegroundUnderstanding.
DETAILS = {
    "sofa": (
        "Canapé, meuble TV, tapis — photo fournie",
        "B / D / E / F",
        {
            "sofa-bottom": (1150, 500, 1536, 740),
            "sofa-leg": (1240, 610, 1430, 735),
            "tv-unit-bottom": (540, 405, 930, 495),
            "rug-edge": (565, 475, 850, 610),
        },
    ),
    "thin-legs": (
        "Table et chaises",
        "C / D",
        {"table-leg": (580, 580, 705, 750), "other-critical-object": (230, 400, 400, 600)},
    ),
    "plant": (
        "Lit, plante, coussins, objets au sol",
        "B / C / D",
        {"plant-stem": (120, 270, 205, 410), "other-critical-object": (170, 480, 700, 690)},
    ),
    "rug": ("Tapis clair et plante", "D / F", {"rug-edge": (0, 430, 500, 730)}),
    "old-floor": (
        "Bureau chargé, chaise et câbles visibles",
        "B / D / E",
        {"other-critical-object": (280, 520, 660, 750), "table-leg": (700, 520, 1000, 740)},
    ),
    "bright": ("Cuisine et meubles bas", "B / D", {"other-critical-object": (400, 510, 850, 730)}),
    "empty": (
        "Pièce avec meuble bas et radiateur",
        "D",
        {"other-critical-object": (440, 640, 820, 800)},
    ),
    "dark": ("Couloir sombre sans objet au sol", "Non-régression", {}),
    "empty-room": ("Pièce vide — domaine de sol", "Non-régression", {}),
}


def main() -> None:
    matrix = json.loads((ROOT / "matrix.json").read_text(encoding="utf8"))
    performance = []
    page = """<!doctype html><html lang="fr"><meta charset="utf-8">
<meta name="viewport" content="width=device-width"><title>Foreground V5</title>
<style>body{font:16px system-ui;background:#f5f2ed;color:#28251f;margin:24px}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
img{width:100%;display:block}figure{margin:0}section{margin:36px 0}summary{padding:12px;cursor:pointer}
table{border-collapse:collapse}td,th{padding:8px;border:1px solid #ccc}a{color:#725331}
@media(max-width:700px){.grid{grid-template-columns:1fr}}</style>
<h1>Foreground / occluder V5</h1><p>Revue locale privée. Le masque rouge est la validation
principale, sans parquet. Les pixels hors du sol peuvent garder les contours sémantiques grossiers.
Pas de vérité terrain complète sur ces photos ; ne pas lire les nombres de pixels modifiés comme une précision.</p>
<p><a href="../../docs/foreground-mask-v5.md">Rapport, limites et mesures</a></p>"""
    for row in matrix:
        name = row["scene"]
        title, errors, crops = DETAILS[name]
        directory = ROOT / name
        page += f"<section><h2>{html.escape(title)}</h2><p>Erreurs source observées : {errors}. "
        page += f"Ajouts {row['addedPixels']}, retraits {row['removedPixels']} pixels — ce ne sont pas des scores de justesse.</p>"
        page += '<div class="grid">'
        for filename, label in [
            ("02-overlay-before.png", "Masque source avant"),
            ("03-overlay-after.png", "Masque source après"),
        ]:
            page += f'<figure><figcaption>{label}</figcaption><img loading="lazy" src="{name}/{filename}"></figure>'
        page += '</div><details><summary>Rendus V4 et crops</summary><div class="grid">'
        for filename, label in [
            ("04-final-before.png", "V4 avec masque avant"),
            ("05-final-after.png", "V4 avec masque après"),
        ]:
            page += f'<figure><figcaption>{label}</figcaption><img loading="lazy" src="{name}/{filename}"></figure>'
        page += "</div>"
        for label, box in crops.items():
            files = [
                "01-original.png",
                "02-overlay-before.png",
                "03-overlay-after.png",
                "04-final-before.png",
                "05-final-after.png",
            ]
            images = [Image.open(directory / file).convert("RGB").crop(box) for file in files]
            sheet = Image.new("RGB", (images[0].width * 5, images[0].height), "white")
            for index, image in enumerate(images):
                sheet.paste(image, (index * image.width, 0))
            file = label + "-comparison.png"
            sheet = sheet.resize((sheet.width*2, sheet.height*2), Image.Resampling.NEAREST)
            sheet.save(directory / file)
            page += f'<p>{label} : photo / rouge avant / rouge après / final avant / final après</p><a href="{name}/{file}"><img loading="lazy" src="{name}/{file}"></a>'
        page += f'<p><a href="{name}/01-original.png">Original</a> · <a href="{name}/floor-mask.png">floorMask</a> · <a href="{name}/02-mask-before.png">occluder avant</a> · <a href="{name}/03-mask-after.png">occluder après</a> · <a href="{name}/03-overlay-renderer-390-gl.png">Overlay réel 390</a> · <a href="{name}/05-final-after-390-canvas.png">Canvas 390</a></p></details></section>'
        # Repeated source-mask polygon encode, independent from renderer/light.
        mask = np.load(directory / "after.npy")
        domain = np.load(directory / "support.npy")
        labels = np.load(directory / "labels.npy")
        # Exact pixel-center raster of the emitted cell polygons. The legacy
        # authoring helper uses width-1 and is unsuitable for mask profiling.
        raw = json.loads((directory / "after.json").read_text(encoding="utf8"))
        h, w = mask.shape
        foreground_hi = np.zeros((h * 2, w * 2), np.uint8)
        for obj in raw["occluders"]:
            if obj["kind"] == "fixture":
                continue
            layer = np.zeros_like(foreground_hi)

            def points(
                polygon: list[dict[str, float]], width: int = w, height: int = h
            ) -> np.ndarray:
                return np.rint([[p["x"] * width * 2, p["y"] * height * 2] for p in polygon]).astype(
                    np.int32
                )

            cv2.fillPoly(layer, [points(obj["polygon"])], 1)
            for hole in obj.get("holes") or []:
                cv2.fillPoly(layer, [points(hole)], 0)
            foreground_hi |= layer
        foreground = foreground_hi[1::2, 1::2].astype(bool)
        samples = []
        for _ in range(5):
            start = perf_counter()
            objects = polygons(mask & ~domain, kind="fixture", prefix="structural")
            objects += polygons(foreground & (labels == RUG), kind="rug", prefix="rug")
            objects += polygons(foreground & (labels != RUG), kind="furniture", prefix="foreground")
            encoded = json.dumps([o.model_dump(by_alias=True) for o in objects])
            samples.append((perf_counter() - start) * 1000)
        performance.append(
            {"scene": name, "maskPolygonEncodeMs": samples, "maskJsonBytes": len(encoded)}
        )
    # Ten manually checked source pixels along the visible green stem gap.
    points = [(round(159 + (y - 305) * 0.15), y) for y in range(315, 325)]
    b = np.load(ROOT / "plant/before.npy")
    a = np.load(ROOT / "plant/after.npy")
    evidence = {
        "scope": "10 manually visually verified green-stem center pixels, not full-image GT",
        "expectedForeground": True,
        "pointsXY": points,
        "coveredBefore": sum(bool(b[y, x]) for x, y in points),
        "coveredAfter": sum(bool(a[y, x]) for x, y in points),
    }
    (ROOT / "annotated-stem.json").write_text(json.dumps(evidence, indent=2), encoding="utf8")
    (ROOT / "mask-encode.json").write_text(json.dumps(performance, indent=2), encoding="utf8")
    (ROOT / "annotations.json").write_text(
        json.dumps(DETAILS, ensure_ascii=False, indent=2), encoding="utf8"
    )
    page += '<h2>Imports réels sur mobile</h2><div class="grid">'
    for file in ["live-ui-0-1440.png", "live-ui-1-390.png"]:
        page += f'<a href="{file}"><img loading="lazy" src="{file}"></a>'
    page += "</div></html>"
    (ROOT / "index.html").write_text(page, encoding="utf8")
    print("Review built; annotated stem:", evidence)


if __name__ == "__main__":
    main()
