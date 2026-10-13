"""Planches de revue des matières Premibel exactes.

    python -m scripts.premibel_material_review

Assemble, sous ``review/premibel-materials/`` (non versionné) :

* ``01-product-source.jpg``        vignette, photo source annotée, atlas ;
* ``02-representative-vs-exact.jpg`` même pièce : ancienne matière, nouvelle ;
* ``03/04/05-room-exact-N.jpg``    les matières exactes dans trois pièces ;
* ``REVIEW-PREMIBEL-MATERIALS.jpg`` la planche de synthèse.

Lit les sorties de ``scripts.import_premibel_material`` (planches
d'extraction) et de ``tools/premibel-materials.capture.mjs`` (rendus).
"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RACINE = Path(__file__).resolve().parents[1]
REVUE = RACINE / "review/premibel-materials"
RENDUS = REVUE / "renders"
SOURCES = RACINE / "web/data/materials/premibel-sources.json"
INDEX = RACINE / "web/data/materials/premibel/index.json"


def police(taille: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    for nom in ("segoeui.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(nom, taille)
        except OSError:
            continue
    return ImageFont.load_default()


def vignette(pid: str, source: str) -> Path | None:
    for c in (
        RACINE / f"tools/local-demo-assets/premibel/thumb.{pid}.jpg",
        RACINE / f"web/assets/products/premibel/{pid}.webp",
        RACINE / source,
    ):
        if c.is_file():
            return c
    return None


def ajuste(img: Image.Image, largeur: int, hauteur: int) -> Image.Image:
    img = img.convert("RGB")
    img.thumbnail((largeur, hauteur))
    fond = Image.new("RGB", (largeur, hauteur), "white")
    fond.paste(img, ((largeur - img.width) // 2, (hauteur - img.height) // 2))
    return fond


def recadre_sol(img: Image.Image) -> Image.Image:
    """Le bas de l'image, là où le parquet se lit le mieux."""
    w, h = img.size
    return img.crop((int(w * 0.04), int(h * 0.55), int(w * 0.96), h))


def grille(
    titre: str,
    lignes: list[tuple[str, list[tuple[str, Image.Image | None]]]],
    cell: tuple[int, int],
) -> Image.Image:
    cw, ch = cell
    ncol = max(len(c) for _, c in lignes)
    marge, entete, legende = 16, 56, 24
    larg = 190 + ncol * (cw + marge) + marge
    haut = entete + len(lignes) * (ch + legende + marge) + marge
    planche = Image.new("RGB", (larg, haut), "white")
    d = ImageDraw.Draw(planche)
    d.text((marge, 14), titre, fill="black", font=police(24))
    y = entete
    for etiquette, cellules in lignes:
        d.text((marge, y + legende + ch // 2 - 10), etiquette, fill="black", font=police(17))
        x = 190
        for nom, im in cellules:
            d.text((x, y), nom, fill=(60, 60, 60), font=police(15))
            if im is not None:
                planche.paste(ajuste(im, cw, ch), (x, y + legende))
            else:
                d.rectangle((x, y + legende, x + cw, y + legende + ch), outline=(200, 200, 200))
                d.text((x + 10, y + legende + 10), "—", fill=(150, 150, 150), font=police(15))
            x += cw + marge
        y += ch + legende + marge
    return planche


def ouvrir(p: Path) -> Image.Image | None:
    return Image.open(p) if p.is_file() else None


def main() -> None:
    sources = {p["id"]: p for p in json.loads(SOURCES.read_text(encoding="utf-8"))["products"]}
    index = json.loads(INDEX.read_text(encoding="utf-8"))["materials"]
    exacts = [pid for pid, e in index.items() if e.get("materialFidelity") == "exact"]
    refuses = [
        (pid, e.get("rejected", []))
        for pid, e in index.items()
        if e.get("materialFidelity") != "exact"
    ]

    lignes = []
    for pid in exacts:
        s = sources[pid]
        v = vignette(pid, s["source"])
        lignes.append(
            (
                pid,
                [
                    ("vignette catalogue", ouvrir(v) if v else None),
                    ("photo source", ouvrir(RACINE / s["source"])),
                    (
                        "extraction (zones, lames, atlas)",
                        ouvrir(REVUE / "extraction" / f"{pid}.jpg"),
                    ),
                ],
            )
        )
    for pid, _ in refuses:
        s = sources.get(pid)
        if s:
            lignes.append(
                (
                    f"{pid} (refusé)",
                    [
                        ("vignette catalogue", ouvrir(RACINE / s["source"])),
                        ("extraction", ouvrir(REVUE / "extraction" / f"{pid}.jpg")),
                    ],
                )
            )
    grille("Sources des matières exactes — et des refus", lignes, (380, 300)).save(
        REVUE / "01-product-source.jpg", quality=86
    )

    lignes = []
    for pid in exacts:
        rep = ouvrir(RENDUS / f"piece-claire-{pid}-representative.jpg")
        ex = ouvrir(RENDUS / f"piece-claire-{pid}-exact.jpg")
        v = vignette(pid, sources[pid]["source"])
        lignes.append(
            (
                pid,
                [
                    ("vignette Premibel", ouvrir(v) if v else None),
                    ("ancienne : représentative", recadre_sol(rep) if rep else None),
                    ("nouvelle : exacte", recadre_sol(ex) if ex else None),
                ],
            )
        )
    grille(
        "Représentative contre exacte — grande pièce claire, même cadrage", lignes, (520, 300)
    ).save(REVUE / "02-representative-vs-exact.jpg", quality=86)

    for n, (piece, nom) in enumerate(
        (
            ("chambre", "chambre bleue"),
            ("sejour", "séjour"),
            ("couloir-enfilade", "couloir bleu (scène sombre)"),
        ),
        start=3,
    ):
        cellules = [(pid, ouvrir(RENDUS / f"{piece}-{pid}-exact.jpg")) for pid in exacts]
        lignes = (
            [(nom, cellules[:2]), ("", cellules[2:4])] if len(cellules) > 2 else [(nom, cellules)]
        )
        grille(f"Matières exactes — {nom}", lignes, (640, 427)).save(
            REVUE / f"{n:02d}-room-exact-{n - 2}.jpg", quality=86
        )

    # Synthèse : une ligne par produit, source → représentative → exacte → chambre → séjour.
    lignes = []
    for pid in exacts:
        v = vignette(pid, sources[pid]["source"])
        rep = ouvrir(RENDUS / f"piece-claire-{pid}-representative.jpg")
        lignes.append(
            (
                pid,
                [
                    ("vignette", ouvrir(v) if v else None),
                    ("représentative", recadre_sol(rep) if rep else None),
                    (
                        "exacte",
                        recadre_sol(
                            ouvrir(RENDUS / f"piece-claire-{pid}-exact.jpg")
                            or Image.new("RGB", (8, 8))
                        ),
                    ),
                    ("chambre bleue", ouvrir(RENDUS / f"chambre-{pid}-exact.jpg")),
                    ("couloir sombre", ouvrir(RENDUS / f"couloir-enfilade-{pid}-exact.jpg")),
                ],
            )
        )
    titre = f"Matières Premibel exactes : {len(exacts)} produits — refusés : " + ", ".join(
        p for p, _ in refuses
    )
    grille(titre, lignes, (330, 220)).save(REVUE / "REVIEW-PREMIBEL-MATERIALS.jpg", quality=86)
    print("planches écrites :", ", ".join(sorted(p.name for p in REVUE.glob("*.jpg"))))


if __name__ == "__main__":
    main()
