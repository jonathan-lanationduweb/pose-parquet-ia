"""Passe exploratoire de segmentation du sol — LOT C.0.

    EXPLORATOIRE · RÉFÉRENCES = BROUILLONS IA · PAS DE VÉRITÉ TERRAIN
    OFFICIELLE · AUCUN CHOIX DE MODÈLE

Ce script exécute les candidats sur nos vraies photos, écrit des aperçus à
regarder, et calcule des chiffres qu'il **interdit de lire comme un banc
d'essai**. La raison est écrite au LOT B : les quatre relevés de référence
sont des brouillons produits par une machine, `status = draft`, jamais
approuvés. Comparer un modèle à eux mesure une ressemblance entre deux
prédictions, pas une justesse.

Ce que cette passe peut donc dire : « ce candidat trouve le sol, celui-là
peint le mur, celui-là efface les pieds de chaise ». Ce qu'elle ne peut pas
dire : lequel est le meilleur.

Usage
-----
    python -m scripts.explore_floor                    les 4 scènes pilotes
    python -m scripts.explore_floor --toutes           les 11 photos
    python -m scripts.explore_floor --candidats opencv,upernet
"""

from __future__ import annotations

import argparse
import contextlib
import json
import platform
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.services.floor_geometric import GeometricFloorBaseline
from app.services.floor_segmentation import FloorSegmentationResult, mask_to_png_bytes
from benchmarks.segmentation import MetricConfig, boundary_metrics, load_mask, mask_metrics

#: Les quatre scènes du pilote : ce sont les seules qui ont un relevé, même
#: brouillon, donc les seules où un chiffre est calculable.
PILOTES = ("sejour", "chambre", "couloir", "petite-piece")

SORTIE = Path("review/floor-candidates")


@dataclass(frozen=True, slots=True)
class Candidat:
    cle: str
    fabrique: Any


def candidats_disponibles() -> dict[str, Candidat]:
    """Les candidats de la première vague, et rien d'autre.

    Trois entrées, choisies dans la grille de licences vérifiée. SAM 2.1 n'y
    est pas : obtenir `floorVisible` d'un modèle par invite demande de décider
    QUELLE invite, et cette méthode n'est pas définie — le mettre ici sans
    l'avoir définie donnerait un résultat qu'on ne saurait pas interpréter.
    """
    from app.services.floor_semantic import OneFormerFloor, UperNetFloor

    return {
        "opencv": Candidat("opencv", GeometricFloorBaseline),
        "oneformer": Candidat("oneformer", OneFormerFloor),
        "upernet": Candidat("upernet", UperNetFloor),
    }


def environnement() -> dict[str, object]:
    """La machine, telle qu'elle est. Aucune supposition sur un GPU."""
    infos: dict[str, object] = {
        "platform": platform.platform(),
        "processor": platform.processor(),
        "logical_cores": __import__("os").cpu_count(),
        "disk_free_gib": round(shutil.disk_usage(".").free / 2**30, 1),
    }
    try:
        from app.services.floor_semantic import environnement as env_torch

        infos.update(env_torch())
    except Exception as e:  # noqa: BLE001 — l'absence de torch est une info
        infos["torch"] = f"indisponible ({e.__class__.__name__})"
    return infos


def charger_photo(root: Path, photo_id: str) -> np.ndarray:
    """La photo, dans les mêmes pixels que ceux du relevé."""
    from benchmarks.dataset import load_manifest

    manifest = load_manifest(root)
    entree = next((p for p in manifest.photos if p.id == photo_id), None)
    if entree is None:
        raise SystemExit(f"photo « {photo_id} » absente du manifeste")
    chemin = root / entree.file
    image = cv2.imread(str(chemin))
    if image is None:
        raise SystemExit(f"photo illisible : {chemin}")
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def reference_brouillon(
    root: Path, photo_id: str
) -> tuple[np.ndarray | None, np.ndarray | None, dict[str, Any] | None]:
    """Le brouillon IA et ses zones incertaines. **Pas une vérité terrain.**"""
    chemin = root / "annotations" / f"{photo_id}.AI.json"
    if not chemin.is_file():
        return None, None, None
    brut = json.loads(chemin.read_text(encoding="utf-8"))
    dossier = root / "annotations"
    masque = load_mask(dossier / brut["masks"]["floorVisible"], brut["width"], brut["height"])
    incertain = None
    if brut["masks"].get("uncertain"):
        incertain = load_mask(dossier / brut["masks"]["uncertain"], brut["width"], brut["height"])
    return masque, incertain, brut


def apercu(image_rgb: np.ndarray, masque: np.ndarray, couleur: tuple[int, int, int]) -> np.ndarray:
    """La photo, le masque posé dessus, et son contour en blanc."""
    vue = image_rgb.astype(np.float32).copy()
    zone = masque.astype(bool)
    teinte = np.array(couleur, dtype=np.float32)
    vue[zone] = vue[zone] * 0.55 + teinte * 0.45
    contours, _ = cv2.findContours(masque.astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    cv2.drawContours(vue, contours, -1, (255, 255, 255), 2)
    return vue.clip(0, 255).astype(np.uint8)


def ecrire(chemin: Path, image_rgb: np.ndarray) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(chemin), cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR))


def _arrondi(valeur: float | None) -> float | None:
    """`None` reste `None` : une mesure impossible n'est pas un zéro."""
    return None if valeur is None else round(valeur, 4)


def metriques_exploratoires(
    prediction: np.ndarray, brouillon: np.ndarray, incertain: np.ndarray | None
) -> dict[str, float | None]:
    """Chiffres calculés contre un BROUILLON. Estampillés comme tels partout.

    Les zones incertaines du brouillon sont **exclues**, comme le protocole le
    demande : on ne juge pas un candidat sur des pixels que le relevé lui-même
    déclare indécidables.
    """
    surface = mask_metrics(prediction, brouillon, ignore=incertain)
    sortie: dict[str, float | None] = {
        "iou": _arrondi(surface.iou),
        "dice": _arrondi(surface.dice),
        "precision": _arrondi(surface.precision),
        "recall": _arrondi(surface.recall),
        "ignored_fraction": round(surface.ignored_fraction, 4),
    }
    for fraction in (0.0025, 0.005, 0.01):
        bord = boundary_metrics(
            prediction, brouillon, incertain, MetricConfig(boundary_tolerance_fraction=fraction)
        )
        sortie[f"boundary_f1_{fraction * 100:g}pct"] = _arrondi(bord.f1)
    return sortie


def defauts_par_role(
    prediction: np.ndarray, brut: dict[str, Any], largeur: int, hauteur: int
) -> dict[str, Any]:
    """Débordement par rôle d'exclusion, et préservation des objets fins.

    C'est ce que le LOT B.2 a rendu calculable : chaque exclusion porte son
    rôle, donc on peut dire « ce candidat a peint par-dessus un occulteur »
    plutôt que « il a débordé quelque part ».

    `rug bleed` reste **NON MESURABLE** : le corpus n'a aucun tapis, et il n'y
    a rien à mesurer sur un cas absent.
    """
    par_role: dict[str, dict[str, float]] = {}
    fines_perdues = 0
    fines_total = 0
    for exclusion in brut.get("exclusions", []):
        sommets = np.array(
            [
                [
                    int(round(min(max(p["x"], 0.0), 1.0) * (largeur - 1))),
                    int(round(min(max(p["y"], 0.0), 1.0) * (hauteur - 1))),
                ]
                for p in exclusion["polygon"]
            ],
            dtype=np.int32,
        )
        gabarit = np.zeros((hauteur, largeur), np.uint8)
        cv2.fillPoly(gabarit, [sommets], 1)
        aire = int(gabarit.sum())
        if not aire:
            continue
        deborde = int((prediction & (gabarit > 0)).sum())
        role = exclusion.get("role", "unknown")
        entree = par_role.setdefault(role, {"exclusions": 0, "aire": 0, "deborde": 0})
        entree["exclusions"] += 1
        entree["aire"] += aire
        entree["deborde"] += deborde
        if exclusion.get("thin"):
            fines_total += 1
            # « Perdu » : plus de la moitié de l'objet fin est repeinte.
            if deborde > aire * 0.5:
                fines_perdues += 1

    for entree in par_role.values():
        aire = entree["aire"]
        entree["bleed_ratio"] = round(entree["deborde"] / aire, 4) if aire else 0.0

    return {
        "par_role": par_role,
        "thin_objects": {"total": fines_total, "perdus": fines_perdues},
        "rug_bleed": "NOT MEASURABLE — floor_covering = 0 dans le corpus",
    }


def executer(
    image: np.ndarray, candidat: Candidat
) -> tuple[FloorSegmentationResult | None, str | None]:
    """Exécute un candidat. Un échec est rapporté, jamais bricolé."""
    try:
        moteur = candidat.fabrique()
        return moteur.segment(image), None
    except MemoryError:
        return None, "NOT_RUN_RESOURCE_LIMIT : mémoire insuffisante"
    except ImportError as e:
        return None, f"NOT_RUN_DEPENDENCY : {e}"
    except Exception as e:  # noqa: BLE001 — on veut la cause, pas un masque
        return None, f"FAILED : {e.__class__.__name__} — {e}"


def main(argv: list[str] | None = None) -> int:
    # La console Windows est en cp1252 : sans cela, un tiret cadratin arrete
    # le script au milieu d'une mesure de quarante secondes.
    for flux in (sys.stdout, sys.stderr):
        with contextlib.suppress(Exception):
            flux.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Passe exploratoire de segmentation du sol")
    parser.add_argument("--dataset", type=Path, default=Path("datasets"))
    parser.add_argument("--out", type=Path, default=SORTIE)
    parser.add_argument("--candidats", default="opencv,oneformer,upernet")
    parser.add_argument("--toutes", action="store_true", help="les 11 photos, non les 4 pilotes")
    parser.add_argument("--photos", default=None, help="liste explicite, séparée par des virgules")
    args = parser.parse_args(argv)

    disponibles = candidats_disponibles()
    choisis = [c.strip() for c in args.candidats.split(",") if c.strip()]
    inconnus = [c for c in choisis if c not in disponibles]
    if inconnus:
        raise SystemExit(f"candidat(s) inconnu(s) : {', '.join(inconnus)}")

    if args.photos:
        photos = [p.strip() for p in args.photos.split(",") if p.strip()]
    elif args.toutes:
        from benchmarks.dataset import load_manifest

        photos = [p.id for p in load_manifest(args.dataset).photos]
    else:
        photos = list(PILOTES)

    print("=" * 74)
    print("EXPLORATOIRE - REFERENCES = BROUILLONS IA — PAS DE VERITE TERRAIN")
    print("           AUCUN CHOIX DE MODELE N'EST FAIT ICI")
    print("=" * 74)
    env = environnement()
    for cle, valeur in env.items():
        print(f"  {cle:<16} {valeur}")
    print()

    rapport: dict[str, Any] = {
        "avertissement": (
            "EXPLORATORY — AI DRAFT REFERENCES — NOT OFFICIAL GT — NOT MODEL SELECTION"
        ),
        "environnement": env,
        "scenes": {},
    }

    for photo_id in photos:
        image = charger_photo(args.dataset, photo_id)
        hauteur, largeur = image.shape[:2]
        brouillon, incertain, brut = reference_brouillon(args.dataset, photo_id)
        dossier = args.out / photo_id
        ecrire(dossier / "00-original.jpg", image)
        if brouillon is not None:
            ecrire(dossier / "01-brouillon-IA.jpg", apercu(image, brouillon, (40, 190, 90)))

        print(
            f"── {photo_id}  {largeur}x{hauteur}"
            f"{'  (brouillon IA disponible)' if brouillon is not None else '  (aucun relevé)'}"
        )
        entree: dict[str, Any] = {
            "resolution": f"{largeur}x{hauteur}",
            "reference": "brouillon IA (draft)" if brouillon is not None else None,
            "candidats": {},
        }

        for cle in choisis:
            t0 = time.perf_counter()
            resultat, souci = executer(image, disponibles[cle])
            if resultat is None:
                print(f"   {cle:<12} {souci}")
                entree["candidats"][cle] = {"statut": souci}
                continue

            ecrire(dossier / f"10-{cle}-overlay.jpg", apercu(image, resultat.mask, (60, 130, 230)))
            (dossier / f"11-{cle}-mask.png").write_bytes(mask_to_png_bytes(resultat.mask))

            ligne: dict[str, Any] = {
                "statut": "ok",
                "couverture": round(resultat.coverage, 4),
                "timings_ms": resultat.timings,
                "metadata": resultat.metadata,
                "wall_ms": round((time.perf_counter() - t0) * 1000, 1),
            }
            if brouillon is not None and brut is not None:
                ligne["exploratoire_vs_brouillon"] = metriques_exploratoires(
                    resultat.mask, brouillon, incertain
                )
                ligne["defauts_par_role"] = defauts_par_role(resultat.mask, brut, largeur, hauteur)
                m = ligne["exploratoire_vs_brouillon"]

                def dit(v: float | None) -> str:
                    return "  n/a" if v is None else f"{v:.3f}"

                print(
                    f"   {cle:<12} couverture {resultat.coverage * 100:5.1f} %"
                    f"  IoU {dit(m['iou'])}  Dice {dit(m['dice'])}"
                    f"  contour 0,5 pc {dit(m['boundary_f1_0.5pct'])}"
                    f"  {resultat.timings.get('inference', 0) / 1000:.1f} s"
                )
            else:
                print(
                    f"   {cle:<12} couverture {resultat.coverage * 100:5.1f} %"
                    f"  (aucun releve : inspection visuelle seulement)"
                    f"  {resultat.timings.get('inference', 0) / 1000:.1f} s"
                )
            entree["candidats"][cle] = ligne

        rapport["scenes"][photo_id] = entree

    chemin = args.out / "rapport-exploratoire.json"
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(rapport, indent=2, ensure_ascii=False), encoding="utf-8")
    print()
    print(f"Apercus et rapport : {args.out}")
    print("Rappel : ces chiffres comparent une prediction a un BROUILLON.")
    print("         Ils ne designent aucun gagnant, et nautorisent pas le LOT C.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
