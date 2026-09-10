"""Planche de revue visuelle des relevés — LOT B.4.

Le problème que cet outil résout n'est pas technique, il est humain : juger
quatre relevés demandait d'ouvrir une vingtaine de fichiers, de retrouver quel
aperçu correspondait à quelle scène, et de zoomer à la main sur les zones
difficiles. Personne ne fait ça deux fois, et une revue qu'on ne fait pas est
une revue qu'on remplace par une approbation de confiance.

Cet outil produit donc **une planche d'ensemble et une planche de détail**, et
rien d'autre. Le relecteur regarde, puis répond scène par scène : d'accord, ou
à reprendre.

Trois refus délibérés :

* il ne modifie **aucune** annotation, aucun masque, aucune photo. Il lit ;
* il **refuse de dessiner** une planche dont les masques ne correspondent plus
  à leur empreinte enregistrée. Approuver une image qui ne montre pas les
  octets mesurés serait pire que ne pas approuver ;
* il ne décide rien. Il n'écrit aucun statut : la promotion est un autre
  geste, fait par une personne, avec `scripts/review_annotation.py`.

Les zones critiques ne sont pas des rectangles saisis à la main : chacune est
**dérivée de la géométrie du relevé** — une exclusion, une zone incertaine, un
segment de contour. Un cadrage recopié à la main se décalerait au premier
changement de tracé, et montrerait le mauvais endroit sans le dire.

Usage
-----
    python -m scripts.review_board
    python -m scripts.review_board --pass-label AI --out review/pilot-AI
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.schemas.annotation import FloorAnnotation
from app.services.image_loader import load_image
from benchmarks.annotations import ANNOTATIONS_DIR
from benchmarks.dataset import load_manifest
from scripts.import_annotation import render_overlay

#: Ordre imposé des scènes du pilote. Il suit celui du carnet de campagne, pour
#: qu'une planche et un rapport se lisent dans le même ordre.
SCENES = ("sejour", "chambre", "couloir", "petite-piece")

Selector = tuple[Literal["exclusion", "uncertain", "boundary"], str, str]


@dataclass(frozen=True, slots=True)
class Zone:
    """Une zone critique : un libellé humain, et un sélecteur géométrique."""

    label: str
    #: ("exclusion" | "uncertain" | "boundary", clé, mode) où la clé est un
    #: rôle, un motif ou une nature de contour. Le mode choisit parmi les
    #: géométries qui portent cette clé : `first`, `union`, `thin` (les
    #: exclusions assez minces pour qu'une erreur de contour les avale), ou
    #: `idx:1,2` pour désigner des géométries précises par leur rang.
    #: **Aucune coordonnée** : elles viennent toutes du relevé, et un tracé
    #: modifié déplace le cadrage avec lui.
    selector: Selector


#: Les zones que le relecteur doit voir de près, scène par scène. Ce sont
#: exactement celles où un relevé automatique peut se tromper sans que ça
#: saute aux yeux sur la vue d'ensemble.
ZONES: dict[str, tuple[Zone, ...]] = {
    "sejour": (
        Zone("Grille de ventilation encastree", ("exclusion", "structural", "first")),
        Zone("Enfilade : jonction de la piece du fond", ("boundary", "wall_floor", "idx:1,2")),
        Zone("Reflet au bas de la porte", ("uncertain", "reflection", "first")),
    ),
    "chambre": (
        Zone("Grille de convecteur", ("exclusion", "structural", "first")),
        Zone("Boitier indecidable", ("exclusion", "unknown", "first")),
        Zone("Seuil de terrasse", ("boundary", "door_threshold", "first")),
    ),
    "couloir": (
        Zone("Limite a faible contraste", ("uncertain", "low_contrast", "first")),
        Zone("Seuil de porte", ("boundary", "door_threshold", "first")),
    ),
    "petite-piece": (
        Zone("Pieds fins de chaise", ("exclusion", "occluder", "thin")),
        Zone("Jonction derriere le bureau", ("boundary", "wall_floor", "idx:1")),
        Zone("Coin en ombre forte", ("uncertain", "strong_shadow", "first")),
        Zone("Disques de contact et reflets", ("uncertain", "reflection", "union")),
    ),
}

#: La zone montrée sur la planche d'ensemble, une par scène : la plus difficile.
PRINCIPALE: dict[str, str] = {
    "sejour": "Grille de ventilation encastree",
    "chambre": "Grille de convecteur",
    "couloir": "Limite a faible contraste",
    "petite-piece": "Pieds fins de chaise",
}

ENCRE = (28, 26, 24)
ENCRE_PALE = (110, 105, 100)
FOND = (250, 249, 247)
ROUGE = (208, 62, 48)
VERT = (40, 150, 80)


def _police(taille: int, gras: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Une police lisible, ou celle par défaut si le système n'en a pas."""
    for nom in ("segoeuib.ttf", "arialbd.ttf") if gras else ("segoeui.ttf", "arial.ttf"):
        chemin = Path("C:/Windows/Fonts") / nom
        if chemin.is_file():
            return ImageFont.truetype(str(chemin), taille)
    return ImageFont.load_default(taille)


# --- Lecture, et refus de montrer autre chose que les octets mesurés -------


@dataclass(frozen=True, slots=True)
class Releve:
    scene: str
    annotation: FloorAnnotation
    photo: np.ndarray
    apercu: np.ndarray
    brut: dict[str, Any]
    controles: dict[str, bool]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _lire_gris(path: Path) -> np.ndarray:
    """Lit une image en niveaux de gris, ou refuse.

    `cv2.imread` renvoie `None` sur un fichier absent ou illisible, sans lever :
    un masque manquant produirait sinon une planche muette au lieu d'un refus.
    """
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise FileNotFoundError(f"masque illisible : {path}")
    return image


def _charger(scene: str, root: Path, pass_label: str, out_dir: Path) -> Releve:
    chemin = root / ANNOTATIONS_DIR / f"{scene}.{pass_label}.json"
    brut = json.loads(chemin.read_text(encoding="utf-8"))
    annotation = FloorAnnotation.model_validate(brut)

    manifest = load_manifest(root)
    photo = next(p for p in manifest.photos if p.id == scene)
    # Les mêmes pixels que ceux qu'un modèle verra : même chargeur, même
    # redressement EXIF que l'importeur. Une planche dessinée sur une autre
    # orientation jugerait un décalage qui n'existe pas.
    image = load_image((root / photo.file).read_bytes()).rgb

    dossier = root / ANNOTATIONS_DIR
    sol = _lire_gris(dossier / annotation.masks.floor_visible)
    incertain = (
        None
        if annotation.masks.uncertain is None
        else _lire_gris(dossier / annotation.masks.uncertain)
    )

    controles = _controler(annotation, brut, dossier, image, sol, incertain, pass_label)

    # L'aperçu passe par la fonction de l'importeur : une seule convention de
    # couleurs dans le projet, et elle est déjà écrite.
    apercu_path = out_dir / f"{scene}.{pass_label}.overlay.png"
    zone = None if incertain is None else np.asarray(incertain > 0)
    render_overlay(image, np.asarray(sol > 0), zone, apercu_path)
    relu = cv2.imread(str(apercu_path))
    if relu is None:
        raise FileNotFoundError(f"apercu illisible : {apercu_path}")
    apercu = cv2.cvtColor(relu, cv2.COLOR_BGR2RGB)

    return Releve(scene, annotation, image, apercu, brut, controles)


def _controler(
    annotation: FloorAnnotation,
    brut: dict[str, Any],
    dossier: Path,
    image: np.ndarray,
    sol: np.ndarray,
    incertain: np.ndarray | None,
    pass_label: str,
) -> dict[str, bool]:
    """Les sept contrôles qui doivent passer avant qu'un humain regarde.

    Aucun n'est un jugement sur le tracé : ce sont des conditions pour que la
    planche montre bien ce qu'elle prétend montrer.
    """
    hauteur, largeur = image.shape[:2]
    chevauchement = 0 if incertain is None else int(((sol > 0) & (incertain > 0)).sum())

    # Les exclusions doivent être absentes du masque final : c'est leur raison
    # d'être. On les rastérise depuis leurs propres polygones et on vérifie que
    # le sol relevé ne les recouvre pas.
    trous_coherents = True
    for exclusion in annotation.exclusions:
        gabarit = np.zeros((hauteur, largeur), np.uint8)
        sommets = np.array(
            [
                [
                    int(round(min(max(p.x, 0.0), 1.0) * (largeur - 1))),
                    int(round(min(max(p.y, 0.0), 1.0) * (hauteur - 1))),
                ]
                for p in exclusion.polygon
            ],
            dtype=np.int32,
        )
        cv2.fillPoly(gabarit, [sommets], 1)
        # Une érosion de 2 px écarte le seul désaccord attendu : le pixel de
        # bord, où rastérisation du trou et rastérisation du sol se disputent
        # la frontière. Au-delà, c'est une vraie incohérence.
        coeur = cv2.erode(gabarit, np.ones((5, 5), np.uint8))
        if coeur.any() and (sol > 0)[coeur > 0].any():
            trous_coherents = False

    empreintes = annotation.mask_sha256 or {}
    inchange = _sha256(dossier / annotation.masks.floor_visible) == empreintes.get("floorVisible")
    if annotation.masks.uncertain is not None:
        inchange = inchange and _sha256(dossier / annotation.masks.uncertain) == empreintes.get(
            "uncertain"
        )

    return {
        "A. masques aux dimensions du releve": sol.shape == (annotation.height, annotation.width)
        and (incertain is None or incertain.shape == (annotation.height, annotation.width))
        and (annotation.height, annotation.width) == (hauteur, largeur),
        "B. sol et incertain disjoints": chevauchement == 0,
        "C. exclusions absentes du masque final": trous_coherents,
        "D. roles d exclusion conserves": all("role" in e for e in brut.get("exclusions", [])),
        "E. masques identiques a leur empreinte": inchange,
        "F. statut draft": annotation.status.value == "draft",
        "G. annotateur claude-ai": annotation.annotator == "claude-ai",
        "H. passe non renommee": annotation.pass_label == pass_label,
    }


# --- Cadrages dérivés du relevé -------------------------------------------


def _polygones(releve: Releve, selector: Selector) -> list[list[tuple[float, float]]]:
    genre, cle, mode = selector
    trouves: list[list[tuple[float, float]]] = []
    if genre == "exclusion":
        trouves = [
            [(p.x, p.y) for p in e.polygon]
            for e in releve.annotation.exclusions
            if e.role.value == cle and (mode != "thin" or e.thin)
        ]
    elif genre == "uncertain":
        trouves = [
            [(p.x, p.y) for p in z.polygon]
            for z in releve.annotation.uncertain_zones
            if z.reason.value == cle
        ]
    else:
        trouves = [
            [(p.x, p.y) for p in s.points]
            for s in releve.annotation.boundary
            if s.kind.value == cle
        ]
    if not trouves:
        return []
    if mode.startswith("idx:"):
        rangs = [int(r) for r in mode[4:].split(",")]
        return [trouves[r] for r in rangs if r < len(trouves)]
    if mode in {"union", "thin"}:
        return trouves
    return [trouves[0]]


def _cadre(
    polygones: list[list[tuple[float, float]]], largeur: int, hauteur: int, marge: float = 0.35
) -> tuple[int, int, int, int] | None:
    """Boîte carrée autour d'une géométrie, élargie puis ramenée dans l'image.

    Carrée, parce qu'une vignette étirée fausse le jugement d'un pied fin :
    l'œil compare des épaisseurs, et une anisotropie les déforme.
    """
    if not polygones:
        return None
    xs = [p[0] * (largeur - 1) for poly in polygones for p in poly]
    ys = [p[1] * (hauteur - 1) for poly in polygones for p in poly]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    cote = max(x1 - x0, y1 - y0, 90.0) * (1 + 2 * marge)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    cote = min(cote, float(min(largeur, hauteur)))
    gx = int(round(min(max(cx - cote / 2, 0), largeur - cote)))
    gy = int(round(min(max(cy - cote / 2, 0), hauteur - cote)))
    return gx, gy, int(round(cote)), int(round(cote))


def _vignette(image: np.ndarray, cadre: tuple[int, int, int, int], cote: int) -> Image.Image:
    x, y, w, h = cadre
    decoupe = image[y : y + h, x : x + w]
    return Image.fromarray(decoupe).resize((cote, cote), Image.Resampling.LANCZOS)


def _marquer_exclusions(releve: Releve) -> np.ndarray:
    """L'aperçu, plus le contour des exclusions en rouge.

    Sur l'aperçu seul, une exclusion est un **trou** : elle se voit comme une
    absence de vert, ce qui la rend indiscernable d'un oubli. Le contour rouge
    dit « ceci a été retiré exprès », et c'est justement ce que le relecteur
    doit juger.
    """
    copie = releve.apercu.copy()
    hauteur, largeur = copie.shape[:2]
    for exclusion in releve.annotation.exclusions:
        sommets = np.array(
            [
                [
                    int(round(min(max(p.x, 0.0), 1.0) * (largeur - 1))),
                    int(round(min(max(p.y, 0.0), 1.0) * (hauteur - 1))),
                ]
                for p in exclusion.polygon
            ],
            dtype=np.int32,
        )
        cv2.polylines(copie, [sommets], True, ROUGE, 2, cv2.LINE_AA)
    return copie


# --- Les deux planches -----------------------------------------------------


def _texte(
    dessin: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    texte: str,
    taille: int = 15,
    gras: bool = False,
    couleur: tuple[int, int, int] = ENCRE,
) -> None:
    dessin.text(xy, texte, font=_police(taille, gras), fill=couleur)


def _planche_ensemble(releves: list[Releve], chemin: Path) -> None:
    """Quatre lignes, une par scène : la photo, le relevé, la zone la plus dure."""
    marge, gouttiere, hauteur_ligne = 28, 16, 300
    largeur_vue = int(hauteur_ligne * 1.5)
    largeur = marge * 2 + 190 + largeur_vue * 2 + hauteur_ligne + gouttiere * 3
    entete = 118
    hauteur = entete + len(releves) * (hauteur_ligne + 42) + marge

    planche = Image.new("RGB", (largeur, hauteur), FOND)
    dessin = ImageDraw.Draw(planche)

    _texte(dessin, (marge, marge - 6), "REVUE DES RELEVES PILOTE", 30, True)
    _texte(
        dessin,
        (marge, marge + 32),
        "Quatre traces generes par IA, en attente d une revue humaine."
        " Repondre par scene : d accord, ou a reprendre.",
        15,
        couleur=ENCRE_PALE,
    )
    legende = [
        ("vert", (40, 190, 90), "sol visible releve"),
        ("ambre", (245, 175, 40), "incertain, exclu des mesures"),
        ("rouge", ROUGE, "exclusion : retire volontairement"),
        ("blanc", (255, 255, 255), "contour du releve"),
    ]
    x = marge
    for _, couleur, libelle in legende:
        dessin.rectangle([x, marge + 62, x + 26, marge + 78], fill=couleur, outline=ENCRE_PALE)
        _texte(dessin, (x + 33, marge + 61), libelle, 14, couleur=ENCRE_PALE)
        x += 40 + int(dessin.textlength(libelle, font=_police(14)))

    y = entete
    for releve in releves:
        souci = [nom for nom, ok in releve.controles.items() if not ok]
        _texte(dessin, (marge, y + 4), releve.scene.upper(), 22, True)
        annotation = releve.annotation
        identite = f"{annotation.width}x{annotation.height}\nrevision {annotation.revision}"
        _texte(dessin, (marge, y + 34), identite, 13, couleur=ENCRE_PALE)
        _texte(
            dessin,
            (marge, y + 78),
            "controles : OK" if not souci else f"controles : {len(souci)} ECHEC",
            14,
            True,
            VERT if not souci else ROUGE,
        )

        x = marge + 190
        for image, titre in (
            (releve.photo, "photo d origine"),
            (_marquer_exclusions(releve), "releve pose dessus"),
        ):
            vue = Image.fromarray(image).resize(
                (largeur_vue, hauteur_ligne), Image.Resampling.LANCZOS
            )
            planche.paste(vue, (x, y))
            _texte(dessin, (x, y + hauteur_ligne + 6), titre, 14, couleur=ENCRE_PALE)
            x += largeur_vue + gouttiere

        etiquette = PRINCIPALE[releve.scene]
        zone = next(z for z in ZONES[releve.scene] if z.label == etiquette)
        cadre = _cadre(
            _polygones(releve, zone.selector), releve.annotation.width, releve.annotation.height
        )
        if cadre is not None:
            planche.paste(_vignette(_marquer_exclusions(releve), cadre, hauteur_ligne), (x, y))
            _texte(
                dessin, (x, y + hauteur_ligne + 6), f"zoom : {etiquette}", 14, couleur=ENCRE_PALE
            )
        y += hauteur_ligne + 42

    chemin.parent.mkdir(parents=True, exist_ok=True)
    planche.save(chemin, quality=92)


def _planche_zones(releves: list[Releve], chemin: Path) -> None:
    """Les zones critiques, chacune en photo d'origine et en relevé, cote à cote."""
    cote, marge, gouttiere = 300, 28, 14
    par_ligne = 3
    lignes: list[tuple[str, str, Zone, Releve]] = [
        (r.scene, z.label, z, r) for r in releves for z in ZONES[r.scene]
    ]
    n_lignes = (len(lignes) + par_ligne - 1) // par_ligne
    bloc = cote * 2 + 8
    largeur = marge * 2 + par_ligne * bloc + (par_ligne - 1) * gouttiere
    entete = 96
    hauteur = entete + n_lignes * (cote + 58) + marge

    planche = Image.new("RGB", (largeur, hauteur), FOND)
    dessin = ImageDraw.Draw(planche)
    _texte(dessin, (marge, marge - 6), "ZONES CRITIQUES", 30, True)
    _texte(
        dessin,
        (marge, marge + 32),
        "A gauche la photo, a droite le meme cadrage avec le releve."
        " Cadrages derives de la geometrie du trace, jamais saisis.",
        15,
        couleur=ENCRE_PALE,
    )

    for index, (scene, label, zone, releve) in enumerate(lignes):
        colonne, ligne = index % par_ligne, index // par_ligne
        x = marge + colonne * (bloc + gouttiere)
        y = entete + ligne * (cote + 58)
        cadre = _cadre(
            _polygones(releve, zone.selector), releve.annotation.width, releve.annotation.height
        )
        _texte(dessin, (x, y), f"{scene.upper()} — {label}", 15, True)
        if cadre is None:
            _texte(dessin, (x, y + 26), "zone absente du releve", 14, couleur=ROUGE)
            continue
        planche.paste(_vignette(releve.photo, cadre, cote), (x, y + 24))
        planche.paste(_vignette(_marquer_exclusions(releve), cadre, cote), (x + cote + 8, y + 24))

    chemin.parent.mkdir(parents=True, exist_ok=True)
    planche.save(chemin, quality=92)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Planches de revue visuelle des relevés")
    parser.add_argument("--dataset", type=Path, default=Path("datasets"))
    parser.add_argument("--pass-label", default="AI", help="passe à relire (AI, A, B...)")
    parser.add_argument("--out", type=Path, default=Path("review/pilot-AI"))
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    releves = [_charger(scene, args.dataset, args.pass_label, args.out) for scene in SCENES]

    echecs = 0
    for releve in releves:
        print(f"== {releve.scene}")
        for nom, ok in releve.controles.items():
            print(f"   {'ok  ' if ok else 'ECHEC'} {nom}")
            echecs += 0 if ok else 1

    if echecs:
        print(
            f"\n{echecs} controle(s) en echec : la planche n'est pas dessinee.\n"
            "Une planche qui ne montre pas les octets mesures ne peut pas etre approuvee."
        )
        return 1

    ensemble = args.out / "PILOT-REVIEW.jpg"
    zones = args.out / "PILOT-REVIEW-CROPS.jpg"
    _planche_ensemble(releves, ensemble)
    _planche_zones(releves, zones)
    print(f"\nPlanche d ensemble : {ensemble}")
    print(f"Zones critiques    : {zones}")
    print(f"Apercus par scene  : {args.out}/<scene>.{args.pass_label}.overlay.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
