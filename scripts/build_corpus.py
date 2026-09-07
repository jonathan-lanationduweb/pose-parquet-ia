"""Écrit le corpus synthétique sur le disque, avec son manifeste.

Le banc d'essai n'en a pas besoin : il construit les images en mémoire depuis
`corpus/catalogue.py`, ce qui évite d'entretenir des octets sur le disque en
plus du code qui les produit. Cet outil sert à autre chose — **regarder les
images**.

C'est moins accessoire qu'il n'y paraît. Le front a perdu du temps sur un
diagnostic de distorsion dont tous les chiffres semblaient bons et dont le
tracé, une fois dessiné sur la photo, partait visiblement en biais. Un corpus
qu'on ne peut pas ouvrir est un corpus qu'on croit sur parole.

Le dossier produit est régénérable et n'est pas versionné.

Usage
-----
    python -m scripts.build_corpus
    python -m scripts.build_corpus --out datasets/synthetic
"""

import argparse
import json
from pathlib import Path
from typing import Any

from corpus import patterns
from corpus.catalogue import CATALOGUE, SEED, Entry
from corpus.transforms import DISTORTION_MODEL

_EXTENSIONS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp", "JPEG-EXIF6": "jpg"}


def _encode(entry: Entry) -> bytes:
    image = entry.build()
    if entry.image_format == "JPEG-EXIF6":
        return patterns.encode_with_exif_orientation(image, 6)
    return patterns.encode(image, entry.image_format)


def generate(out_dir: Path) -> Path:
    """Écrit les images et le manifeste. Renvoie le chemin du manifeste."""
    out_dir.mkdir(parents=True, exist_ok=True)
    photos: list[dict[str, Any]] = []

    for entry in CATALOGUE:
        filename = f"{entry.id}.{_EXTENSIONS[entry.image_format]}"
        (out_dir / filename).write_bytes(_encode(entry))
        photos.append(
            {
                "id": entry.id,
                "file": filename,
                "difficulty": entry.difficulty,
                "source": "généré par scripts/build_corpus.py",
                "license": "aucune (image synthétique, sans auteur)",
                "expectedIssues": [warning.value for warning in entry.expected],
                "graded": entry.graded,
                # La vérité terrain est ce qu'on a **imposé** à l'image, jamais
                # une estimation. Ces images n'ont pas de sol : le bloc
                # `groundTruth` du format dataset reste donc vide, et le
                # remplir « pour faire complet » serait exactement la fausse
                # donnée que ce projet refuse.
                "groundTruth": {
                    "available": False,
                    "lens": (
                        {"k1": entry.truth["k1"], "provenance": "imposée par le générateur"}
                        if "k1" in entry.truth
                        else None
                    ),
                },
                "notes": entry.note or None,
            }
        )

    manifest = {
        "schema": "pose-parquet-ai/dataset@1",
        "note": (
            f"Corpus SYNTHÉTIQUE, régénérable par scripts/build_corpus.py (graine {SEED}). "
            "Aucune de ces images ne contient de pièce : elles éprouvent les mesures "
            "techniques sur des cas dont les propriétés sont connues exactement. Ne pas "
            "les confondre avec le corpus de photos réelles — voir datasets/README.md. "
            f"Modèle de distorsion : {DISTORTION_MODEL}."
        ),
        "photos": photos,
    }
    path = out_dir / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    parser.add_argument("--out", type=Path, default=Path("datasets/synthetic"))
    args = parser.parse_args(argv)

    path = generate(args.out)
    print(f"{len(CATALOGUE)} images écrites dans {args.out}")
    print(f"Manifeste : {path}")
    print("Le banc d'essai n'en a pas besoin : python -m benchmarks.run_benchmark")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
