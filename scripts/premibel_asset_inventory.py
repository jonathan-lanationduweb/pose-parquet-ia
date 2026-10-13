"""Inventaire des images produit Premibel disponibles localement.

    python -m scripts.premibel_asset_inventory

Pour chaque référence du catalogue, ce que le projet a réellement :

    A  vignette commerciale (≈ 324 px, export de la boutique)
    B  photo d'ambiance (sol en perspective, meubles, lumière de la pièce)
    C  photo produit rapprochée (lames en gros plan)
    D  texture matière exploitable (atlas exact construit et validé)
    E  plusieurs lames / échantillons du même produit
    F  aucun asset exploitable

Une vignette est classée B par défaut ; C seulement si elle figure dans
``GROS_PLANS``, relevé à l'œil le 13 octobre 2026 sur les planches des 382
vignettes. D vient de l'index des matières exactes. Personne ne transforme ici
une vignette en texture : c'est le rôle de ``scripts.import_premibel_material``,
qui valide avant de déclarer « exact ».

Écrit ``review/premibel-materials/inventory.json`` et ``inventory.md``.
"""

from __future__ import annotations

import collections
import json
from pathlib import Path

from PIL import Image

RACINE = Path(__file__).resolve().parents[1]
CATALOGUE = RACINE / "tools/premibel-catalog-data.js"
INDEX = RACINE / "web/data/materials/premibel/index.json"
HEROS = RACINE / "tools/local-demo-assets/premibel"
SORTIE = RACINE / "review/premibel-materials"

#: Vignettes qui montrent les lames de près (classement visuel, 13/10/2026).
GROS_PLANS = {
    "BAMB36103",
    "BAMB36110",
    "BAMB36126L_1",
    "BAMB36127L_1",
    "CHEN36243",
    "CHEN38163",
    "CHENF228",
    "CHENF238",
    "CHENF240",
    "CHENF2678",
    "CHENF2681",
    "F52386574",
    "MERB16001",
    "POINF38000",
    "POINF39030",
}


def main() -> None:
    texte = CATALOGUE.read_text(encoding="utf-8")
    produits = json.loads(texte[texte.index("[") : texte.rindex("]") + 1])
    exacts = {
        pid
        for pid, e in json.loads(INDEX.read_text(encoding="utf-8"))["materials"].items()
        if e.get("materialFidelity") == "exact"
    }
    lignes = []
    compte: collections.Counter[str] = collections.Counter()
    for p in produits:
        types = []
        vignette = p.get("thumbnail") or ""
        fichier = RACINE / "web" / vignette.replace("../web/", "") if vignette else None
        taille = None
        if fichier and fichier.is_file():
            types.append("A")
            taille = Image.open(fichier).size
            types.append("C" if fichier.stem in GROS_PLANS else "B")
        hero = HEROS / f"{p['id']}.jpg"
        if not hero.is_file():
            hero = HEROS / f"{p['id']}.png"
        if hero.is_file() and "B" not in types:
            types.append("B")
        if p["id"] in exacts:
            types.append("D")
        if not types:
            types.append("F")
        for t in types:
            compte[t] += 1
        lignes.append(
            {
                "id": p["id"],
                "types": types,
                "thumbnailSize": taille,
                "largeImage": hero.is_file(),
                "renderable": p.get("renderable") is not False,
            }
        )
    SORTIE.mkdir(parents=True, exist_ok=True)
    resume = {
        "products": len(produits),
        "counts": dict(sorted(compte.items())),
        "plankSamples": 0,
        "note": "E (plusieurs lames ou échantillons) : aucun — l'export ne fournit ni `sample` ni "
        "`plankVariants` ni cartes de matière (0 sur 395).",
    }
    (SORTIE / "inventory.json").write_text(
        json.dumps({"summary": resume, "products": lignes}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    md = [
        "# Inventaire des images produit Premibel",
        "",
        f"{len(produits)} références. Une référence peut cumuler plusieurs types.",
        "",
        "| type | signification | références |",
        "| --- | --- | --- |",
    ]
    sens = {
        "A": "vignette commerciale (≈ 324 px)",
        "B": "photo d'ambiance",
        "C": "photo produit rapprochée",
        "D": "texture matière exploitable (atlas exact validé)",
        "E": "plusieurs lames / échantillons",
        "F": "aucun asset exploitable",
    }
    for t in "ABCDEF":
        md.append(f"| {t} | {sens[t]} | {compte.get(t, 0)} |")
    md += ["", resume["note"]]
    (SORTIE / "inventory.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps(resume, ensure_ascii=False))


if __name__ == "__main__":
    main()
