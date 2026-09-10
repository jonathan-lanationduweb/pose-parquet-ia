"""Transforme un tracé d'annotation en masques PNG et en fichier d'annotation.

L'outil de tracé (`tools/annotate.html`) produit des **polygones normalisés**.
Ce script les rastérise aux dimensions exactes de l'image telle que le
pipeline la charge, calcule les empreintes, et écrit l'annotation.

Le partage des rôles est délibéré : le navigateur dessine, Python possède le
format. Un tracé n'est donc jamais qu'une entrée intermédiaire, et n'importe
quel autre outil peut produire le même JSON sans que le corpus dépende du
nôtre.

## Le contrôle qui justifie ce script

Un navigateur applique l'orientation EXIF pour afficher une photo ; notre
pipeline l'applique aussi, mais rien ne garantit qu'ils obtiennent le même
cadre. Un tracé fait sur une image affichée en portrait et rastérisé sur une
image décodée en paysage donnerait un masque **silencieusement faux** : bonnes
dimensions nulle part, mais aucune erreur levée.

Ce script recharge donc l'image avec `image_loader.load_image` — le même code
que le service — et **refuse** le tracé si les dimensions ne correspondent pas.
C'est le seul endroit où cette vérification peut avoir lieu, et c'est ce qui
rend l'annotation rattachable aux pixels que le modèle verra.

Usage
-----
    python -m scripts.import_annotation --draw room-001.draw.json --annotator jonathan
    python -m scripts.import_annotation --draw r.draw.json --annotator jo --status reviewed \\
        --reviewer alex
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.schemas.annotation import (
    AnnotationStatus,
    AnnotationTiming,
    BoundaryKind,
    BoundarySegment,
    FloorAnnotation,
    MaskFiles,
    Point,
    Review,
    UncertainReason,
    UncertainZone,
)
from app.services.image_loader import load_image
from benchmarks.annotations import ANNOTATIONS_DIR
from benchmarks.dataset import load_manifest, sha256_of
from benchmarks.segmentation import save_mask

#: Format attendu en entrée, produit par `tools/annotate.html`.
DRAW_SCHEMA = "pose-parquet-ai/floor-draw@1"


class ImportError_(Exception):
    """Le tracé n'est pas exploitable. Le dire, jamais le rattraper."""


def _polygon_to_pixels(points: list[dict[str, float]], width: int, height: int) -> np.ndarray:
    """Polygone normalisé → sommets en pixels entiers.

    Les coordonnées sont bornées au cadre : un annotateur qui déborde
    légèrement en tirant un point hors de l'image exprime « jusqu'au bord »,
    et non une erreur à refuser.
    """
    coordinates = [
        (
            int(round(min(max(point["x"], 0.0), 1.0) * (width - 1))),
            int(round(min(max(point["y"], 0.0), 1.0) * (height - 1))),
        )
        for point in points
    ]
    return np.array([coordinates], dtype=np.int32)  # (1, N, 2), la forme attendue par cv2


def rasterize(
    polygons: list[list[dict[str, float]]],
    holes: list[list[dict[str, float]]],
    width: int,
    height: int,
) -> np.ndarray:
    """Rastérise une union de polygones, moins une union de trous.

    Les trous portent une notion précise : ce qui **cache** le sol sans être
    du mur — un tapis, un pied de meuble, une caisse posée. Le sol visible est
    donc la surface tracée moins ce qui la recouvre, et jamais l'inverse.
    """
    canvas = np.zeros((height, width), dtype=np.uint8)
    for polygon in polygons:
        cv2.fillPoly(canvas, [_polygon_to_pixels(polygon, width, height)[0]], color=1)
    for hole in holes:
        cv2.fillPoly(canvas, [_polygon_to_pixels(hole, width, height)[0]], color=0)
    return canvas.astype(bool)


def render_overlay(
    image_rgb: np.ndarray,
    floor: np.ndarray,
    uncertain: np.ndarray | None,
    out_path: Path,
) -> None:
    """Écrit l'aperçu de contrôle : la photo, et le relevé posé par-dessus.

    C'est le seul moyen de voir ce qu'on a réellement tracé. Les quatre fautes
    que cet aperçu attrape, et qu'un JSON ne montre pas : un morceau de mur
    happé, une bande de sol oubliée le long d'une plinthe, un tapis resté
    dedans, un pied de chaise effacé.

    La photo n'est jamais modifiée : l'aperçu est une image de plus, écrite là
    où on la demande, et elle n'entre ni au manifeste ni à Git.
    """
    apercu = image_rgb.astype(np.float32).copy()
    # Vert sur le sol relevé, ambre sur l'incertain : deux teintes qui ne se
    # confondent avec aucun sol réel, donc lisibles sur n'importe quelle photo.
    vert = np.array([40, 190, 90], dtype=np.float32)
    sol = floor.astype(bool)
    apercu[sol] = apercu[sol] * 0.55 + vert * 0.45
    if uncertain is not None:
        zone = uncertain.astype(bool)
        ambre = np.array([245, 175, 40], dtype=np.float32)
        apercu[zone] = apercu[zone] * 0.55 + ambre * 0.45

    # Le contour du relevé, en trait plein : c'est lui qu'on vient juger.
    contours, _ = cv2.findContours(floor.astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    cv2.drawContours(apercu, contours, -1, (255, 255, 255), 2)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    rendu = apercu.clip(0, 255).astype(np.uint8)
    cv2.imwrite(str(out_path), cv2.cvtColor(rendu, cv2.COLOR_RGB2BGR))


def _load_draw(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != DRAW_SCHEMA:
        raise ImportError_(f"{path.name} : schéma « {data.get('schema')} », attendu {DRAW_SCHEMA}")
    for required in ("photoId", "width", "height", "floorPolygons"):
        if required not in data:
            raise ImportError_(f"{path.name} : champ « {required} » manquant")
    if not data["floorPolygons"]:
        raise ImportError_(
            f"{path.name} : aucun polygone de sol. Si la scène n'a pas de sol visible, "
            "rangez-la en difficulté « rejected » et écrivez-le dans les notes."
        )
    return data


def build(
    draw_path: Path,
    root: Path,
    annotator: str,
    status: AnnotationStatus,
    reviewer: str | None,
    notes: str | None,
    pass_label: str | None = None,
    independent: bool = False,
    timing: AnnotationTiming | None = None,
    overlay: Path | None = None,
) -> Path:
    """Écrit les masques et l'annotation. Renvoie le chemin de l'annotation.

    Une seconde passe sur la même photo s'écrit sous un nom distinct
    (`photo.B.json`) et ne remplace donc pas la première : c'est ce qui rend la
    comparaison possible. Sans `pass_label`, une réimportation écrase, ce qui
    est le comportement voulu pour une correction.
    """
    draw = _load_draw(draw_path)
    photo_id = str(draw["photoId"])

    manifest = load_manifest(root)
    photo = next((entry for entry in manifest.photos if entry.id == photo_id), None)
    if photo is None:
        raise ImportError_(
            f"photo « {photo_id} » absente de {root / 'manifest.json'} — "
            "enregistrez-la d'abord (scripts/add_photo.py) pour qu'elle ait une provenance"
        )

    image_path = root / photo.file
    if not image_path.is_file():
        raise ImportError_(f"image absente : {image_path}")

    # LE contrôle : les mêmes pixels que ceux que le modèle verra.
    loaded = load_image(image_path.read_bytes())
    if (loaded.width, loaded.height) != (int(draw["width"]), int(draw["height"])):
        raise ImportError_(
            f"{draw_path.name} : le tracé annonce {draw['width']}×{draw['height']}, "
            f"or le pipeline charge l'image en {loaded.width}×{loaded.height}"
            + (
                " — une orientation EXIF a été appliquée d'un côté seulement. "
                "Rouvrez la photo dans l'outil de tracé et refaites le relevé."
                if loaded.exif_orientation_applied
                else " — le tracé ne correspond pas à cette image."
            )
        )

    width, height = loaded.width, loaded.height
    masks_dir = root / ANNOTATIONS_DIR / "masks"

    # Le temps chronométré par l'outil, s'il n'a pas été fourni autrement. Ici
    # et non dans la CLI : un appelant qui passe par `build` doit obtenir le
    # même comportement, sans quoi la métrique de temps se perd en silence.
    if timing is None and draw.get("drawSeconds") is not None:
        timing = AnnotationTiming(first_pass_seconds=float(draw["drawSeconds"]))

    # L'étiquette de passe saisie dans l'outil, à défaut de --pass-label. Sans
    # cette reprise, importer une passe B en oubliant le drapeau écraserait la
    # passe A : aucune erreur levée, un relevé perdu, et une paire devenue
    # impossible à mesurer.
    if pass_label is None and draw.get("passLabel"):
        pass_label = str(draw["passLabel"]).strip() or None

    floor = rasterize(draw["floorPolygons"], draw.get("floorHoles", []), width, height)
    suffix = f".{pass_label}" if pass_label else ""
    floor_name = f"{photo_id}{suffix}.floor-visible.png"
    save_mask(floor, masks_dir / floor_name)

    zones = draw.get("uncertainZones", [])
    uncertain_name: str | None = None
    if zones:
        uncertain = rasterize([zone["polygon"] for zone in zones], [], width, height)
        uncertain_name = f"{photo_id}{suffix}.uncertain.png"
        save_mask(uncertain, masks_dir / uncertain_name)

    if overlay is not None:
        zone = None
        if zones:
            zone = rasterize([z["polygon"] for z in zones], [], width, height)
        render_overlay(loaded.rgb, floor, zone, overlay)

    annotation = FloorAnnotation(
        photo_id=photo_id,
        width=width,
        height=height,
        masks=MaskFiles(
            floor_visible=f"masks/{floor_name}",
            uncertain=None if uncertain_name is None else f"masks/{uncertain_name}",
        ),
        boundary=[
            BoundarySegment(
                kind=BoundaryKind(segment["kind"]),
                points=[Point(x=p["x"], y=p["y"]) for p in segment["points"]],
                note=segment.get("note"),
            )
            for segment in draw.get("boundary", [])
        ],
        uncertain_zones=[
            UncertainZone(
                reason=UncertainReason(zone["reason"]),
                polygon=[Point(x=p["x"], y=p["y"]) for p in zone["polygon"]],
                note=zone.get("note"),
            )
            for zone in zones
        ],
        annotator=annotator,
        annotated_on=date.today(),
        pass_label=pass_label,
        independent_pass=independent,
        timing=timing,
        status=status,
        # Sans relecteur nommé, c'est l'annotateur qui est inscrit : une
        # **auto-relecture**, et le rapport la lira comme telle puisque les deux
        # noms coïncident. Le repli va dans le sens conservateur — il ne peut
        # que sous-estimer la relecture, jamais la surestimer — mais il reste un
        # repli : nommer explicitement un relecteur est toujours préférable.
        review=(
            None
            if status is AnnotationStatus.DRAFT
            else Review(reviewer=reviewer or annotator, reviewed_on=date.today())
        ),
        mask_sha256={
            "floorVisible": sha256_of(masks_dir / floor_name),
            **({"uncertain": sha256_of(masks_dir / uncertain_name)} if uncertain_name else {}),
        },
        notes=notes or draw.get("notes"),
    )

    out_path = root / ANNOTATIONS_DIR / f"{photo_id}{suffix}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(
            annotation.model_dump(by_alias=True, mode="json", exclude_none=False),
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    parser.add_argument("--draw", type=Path, required=True, help="fichier .draw.json")
    parser.add_argument("--dataset", type=Path, default=Path("datasets"))
    parser.add_argument("--annotator", required=True, help="qui a dessiné")
    parser.add_argument(
        "--status",
        choices=[status.value for status in AnnotationStatus],
        default=AnnotationStatus.DRAFT.value,
        help="draft par défaut ; seules les approved entrent au banc d'essai",
    )
    parser.add_argument(
        "--reviewer",
        help="qui a relu. Omis sur un statut non-draft, l'annotateur est "
        "inscrit : l'annotation devient une AUTO-RELECTURE, pas une revue "
        "indépendante. Nommez un relecteur distinct dès qu'il en existe un.",
    )
    parser.add_argument("--notes")
    parser.add_argument(
        "--pass-label",
        help="« A », « B »… pour une photo annotée plusieurs fois. "
        "Sans lui, une réimportation écrase l'annotation existante.",
    )
    parser.add_argument(
        "--independent",
        action="store_true",
        help="déclare que cette passe a été faite SANS regarder les autres. "
        "L'outil ne peut pas le vérifier : c'est une déclaration, et le nom de "
        "la mesure d'accord en dépend.",
    )
    parser.add_argument(
        "--seconds",
        type=float,
        help="durée du premier tracé, en secondes. Par défaut, celle que "
        "l'outil a chronométrée (champ drawSeconds du tracé).",
    )
    parser.add_argument("--corrections-seconds", type=float, default=0.0)
    parser.add_argument("--review-seconds", type=float, default=0.0)
    parser.add_argument("--corrections", type=int, help="nombre de reprises, s'il se compte")
    parser.add_argument(
        "--overlay",
        type=Path,
        help=(
            "écrit un aperçu de contrôle — la photo avec le relevé par-dessus. "
            "À regarder avant d'approuver. N'entre ni au manifeste, ni à Git."
        ),
    )
    args = parser.parse_args(argv)

    # `--seconds` l'emporte ; sinon `build` reprendra ce que l'outil a
    # chronométré. Les durées de correction et de revue, elles, ne peuvent
    # venir que d'ici : l'outil ne les voit pas.
    timing = (
        None
        if args.seconds is None
        else AnnotationTiming(
            first_pass_seconds=args.seconds,
            corrections_seconds=args.corrections_seconds,
            review_seconds=args.review_seconds,
            correction_count=args.corrections,
        )
    )

    try:
        path = build(
            args.draw,
            args.dataset,
            args.annotator,
            AnnotationStatus(args.status),
            args.reviewer,
            args.notes,
            pass_label=args.pass_label,
            independent=args.independent,
            timing=timing,
            overlay=args.overlay,
        )
    except (ImportError_, FileNotFoundError, ValueError) as failure:
        print(f"Erreur : {failure}", file=sys.stderr)
        return 2

    print(f"Annotation écrite : {path}")
    if args.overlay:
        print(f"Aperçu de contrôle : {args.overlay} — regardez-le avant d'approuver")
    print("Contrôlez-la : python -m scripts.validate_dataset")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
