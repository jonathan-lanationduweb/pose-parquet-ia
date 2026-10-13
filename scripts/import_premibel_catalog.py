"""Import an authorized Premibel export and local thumbnails; never scrape or copy a renderer."""

import argparse
import json
import re
import shutil
from pathlib import Path


def millimeters(value: object) -> float | None:
    if not isinstance(value, str) or "mm" not in value.lower():
        return None
    nums = [float(n.replace(",", ".")) for n in re.findall(r"[0-9]+(?:[.,][0-9]+)?", value)]
    return sum(nums) / len(nums) if nums else None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--asset-root", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.source.read_text(encoding="utf-8"))
    families = {
        p["id"]
        for p in json.loads(Path("web/data/parquets.json").read_text(encoding="utf-8"))["parquets"]
    }
    rows = []
    target = Path("web/assets/products/premibel")
    target.mkdir(parents=True, exist_ok=True)
    for p in data["produits"]:
        if not p.get("active"):
            continue
        width = millimeters(p["dimensions"].get("widthMm"))
        length = millimeters(p["dimensions"].get("lengthMm"))
        family = p.get("visualFamily")
        pattern = p.get("defaultPattern")
        renderable = bool(
            width
            and length
            and family in families
            and pattern in ("lames", "point-de-hongrie", "baton-rompu")
        )
        thumb = None
        if p.get("thumbnail"):
            source = args.asset_root / p["thumbnail"]
            if source.is_file():
                shutil.copyfile(source, target / source.name)
                thumb = "../web/assets/products/premibel/" + source.name
        finish = {"Verni": "verni", "Huilé": "huile", "Brut": "brut"}.get(p.get("finish"), "brut")
        tone = {
            "fonce": "fonce",
            "brun": "fonce",
            "cuivre": "chaud",
            "blanc": "clair",
            "brut": "naturel",
        }.get(p.get("tone"), p.get("tone") or "naturel")
        if tone not in ("clair", "naturel", "chaud", "fonce"):
            tone = "naturel"
        row = {
            "id": p["sku"],
            "ref": p["sku"],
            "reference": p["sku"],
            "source": "premibel",
            "name": p["name"],
            "category": p.get("type"),
            "pattern": pattern,
            "compatiblePatterns": p.get("compatiblePatterns", []),
            "widthMm": width,
            "lengthMm": length,
            "dimensionsSource": p["dimensions"],
            "finish": finish,
            "tone": tone,
            "collection": p.get("range"),
            "species": p.get("species"),
            "type": p.get("type"),
            "aspect": p.get("treatment") or "",
            "catalogThumbnail": thumb,
            "thumbnail": thumb,
            "productUrl": p.get("productUrl"),
            "heroImage": thumb,
            "renderable": renderable,
            "materialFidelity": "representative" if renderable else "unavailable",
            "visualAccuracy": "approximate" if renderable else "unavailable",
            "materialAsset": None,
            "renderMaterial": {"kind": "procedural", "family": family} if renderable else None,
            "checkedAt": data.get("generatedAt"),
            "rightsStatus": ("authorized local export; thumbnail reuse for local review; "
                            "distribution rights not established"),
        }
        if renderable:
            assert width is not None and length is not None
            row["renderProfile"] = {
                "materialFamily": family,
                "pattern": pattern,
                "widthM": width / 1000,
                "lengthM": length / 1000,
                "orientationDeg": 0,
            }
            row["renderAccuracy"] = {
                "pattern": "exact",
                "width": "exact",
                "orientation": "exact",
                "tone": "approximate",
                "grain": "approximate",
                "finish": "approximate",
            }
        rows.append(row)
    result = {
        "source": data.get("endpoint"),
        "sourceGeneratedAt": data.get("generatedAt"),
        "products": rows,
    }
    Path("web/data/catalog.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # Classic data script keeps the existing single entry and offline serving contract.
    Path("tools/premibel-catalog-data.js").write_text(
        "window.PP_PREMIBEL_CATALOG=" + json.dumps(rows, ensure_ascii=False) + ";\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "products": len(rows),
                "representative": sum(r["renderable"] for r in rows),
                "unavailable": sum(not r["renderable"] for r in rows),
                "thumbnails": sum(bool(r["thumbnail"]) for r in rows),
                "exact": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
