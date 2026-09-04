"""Génère un petit corpus synthétique, et son manifeste.

Ces images ne remplacent pas des photos de pièces : aucune ne contient de
sol, de mur ni de meuble. Elles servent à autre chose, et c'est précisément
leur intérêt — **leurs propriétés sont connues exactement**. Une droite est
droite au pixel près, une image noire est noire, une image floue l'est d'un
rayon choisi. Un banc d'essai a besoin de ce genre de repère avant de
s'attaquer à des photos réelles dont personne ne connaît la vérité.

Le corpus de vraies photos, lui, vit dans `datasets/{easy,medium,hard,rejected}`
et suit les règles de `datasets/README.md`.

Usage
-----
    python -m scripts.make_fixtures
    python -m scripts.make_fixtures --out datasets/synthetic
"""

import argparse
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

from app.core.warnings import Warn
from benchmarks.dataset import DATASET_SCHEMA
from tests import factories

#: Chaque entrée : identifiant, fabricant d'image, format, difficulté visée,
#: et les avertissements qu'on **attend** de l'analyse. Cette dernière colonne
#: est la seule qui compte : c'est elle qui transforme une image en test.
#: `rejected` ne veut pas dire « mauvaise photo » mais « photo dont on attend
#: qu'elle soit **refusée** ». Aujourd'hui un seul avertissement est bloquant,
#: `image_too_small` : c'est donc la seule fixture de ce bac. Les autres cas
#: extrêmes vivent en `hard`, où ils documentent ce que le service voit sans
#: préjuger de ce qu'il devrait en faire.
FIXTURES: tuple[tuple[str, Callable[[], np.ndarray | bytes], str, str, list[Warn]], ...] = (
    (
        "synth-sharp-midtone",
        factories.mid_tone_checkerboard,
        "JPEG",
        "easy",
        [],
    ),
    (
        "synth-blurry",
        lambda: factories.checkerboard(blur=8, low=70, high=190),
        "JPEG",
        "medium",
        [Warn.IMAGE_BLURRY],
    ),
    # Une image uniforme n'a aucun détail : la variance du Laplacien y vaut
    # zéro et le service la classe « pas nette ». Ce n'est pas un défaut de la
    # mesure, c'est sa limite, et elle est déclarée ici plutôt que passée sous
    # silence. Ces deux images sont rangées en `hard` et non en `rejected` :
    # aujourd'hui le service les analyse au lieu de les refuser. Faut-il en
    # faire un refus ? C'est une décision du LOT 1, à prendre sur le corpus.
    (
        "synth-black",
        lambda: factories.flat(2),
        "PNG",
        "hard",
        [Warn.IMAGE_TOO_DARK, Warn.IMAGE_LOW_CONTRAST, Warn.IMAGE_BLURRY],
    ),
    (
        "synth-white",
        lambda: factories.flat(254),
        "PNG",
        "hard",
        [Warn.IMAGE_OVEREXPOSED, Warn.IMAGE_LOW_CONTRAST, Warn.IMAGE_BLURRY],
    ),
    (
        "synth-too-small",
        lambda: factories.mid_tone_checkerboard(size=(320, 240)),
        "JPEG",
        "rejected",
        [Warn.IMAGE_TOO_SMALL],
    ),
    (
        "synth-straight-edges",
        lambda: factories.straight_bars(size=(1600, 1000)),
        "PNG",
        "easy",
        [],
    ),
    (
        "synth-bowed-edges",
        lambda: factories.bowed_bars(size=(1600, 1000), amplitude=18.0),
        "PNG",
        "hard",
        [Warn.LENS_DISTORTION_SUSPECTED],
    ),
    (
        "synth-panorama",
        lambda: factories.mid_tone_checkerboard(size=(2000, 400)),
        "JPEG",
        "hard",
        [Warn.IMAGE_EXTREME_ASPECT_RATIO],
    ),
    (
        "synth-exif-portrait",
        factories.portrait_with_exif_rotation,
        "JPEG",
        "medium",
        [],
    ),
)

_EXTENSIONS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}


def generate(out_dir: Path) -> Path:
    """Écrit les images et le manifeste. Renvoie le chemin du manifeste."""
    out_dir.mkdir(parents=True, exist_ok=True)
    photos: list[dict[str, Any]] = []

    for photo_id, make, image_format, difficulty, expected in FIXTURES:
        produced = make()
        # Certaines fixtures sont déjà encodées : l'orientation EXIF ne peut
        # pas se transporter dans un tableau NumPy.
        data = produced if isinstance(produced, bytes) else factories.encode(produced, image_format)
        filename = f"{photo_id}.{_EXTENSIONS[image_format]}"
        (out_dir / filename).write_bytes(data)
        photos.append(
            {
                "id": photo_id,
                "file": filename,
                "difficulty": difficulty,
                "source": "généré par scripts/make_fixtures.py",
                "license": "aucune (image synthétique, sans auteur)",
                "expectedIssues": [w.value for w in expected],
                # Aucune vérité terrain : ces images n'ont pas de sol. La
                # renseigner « pour faire complet » serait exactement la
                # fausse donnée que ce projet refuse.
                "groundTruth": {"available": False},
            }
        )

    manifest = {
        "schema": DATASET_SCHEMA,
        "note": (
            "Corpus SYNTHÉTIQUE, régénérable par scripts/make_fixtures.py. Aucune de "
            "ces images ne contient de pièce : elles éprouvent les mesures techniques "
            "sur des cas dont les propriétés sont connues exactement. Ne pas les "
            "confondre avec le corpus de photos réelles — voir datasets/README.md."
        ),
        "photos": photos,
    }
    path = out_dir / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", type=Path, default=Path("datasets/synthetic"))
    args = parser.parse_args(argv)

    path = generate(args.out)
    print(f"{len(FIXTURES)} fixtures écrites dans {args.out}")
    print(f"Manifeste : {path}")
    print(f"Benchmark : python -m benchmarks.run_benchmark --dataset {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
