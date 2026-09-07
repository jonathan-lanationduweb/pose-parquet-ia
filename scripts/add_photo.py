"""Enregistre une photo au manifeste, avec sa provenance et son empreinte.

Passer par ce script plutôt que d'éditer le JSON à la main a une raison
précise : **la provenance devient obligatoire de fait**. Les arguments
`--source`, `--license` et `--verified-on` sont requis, il n'y a pas de valeur
par défaut permissive, et le hash est calculé plutôt que saisi. Une photo
enregistrée ici a donc toujours de quoi être citée.

`--redistributable` est un drapeau qu'il faut poser explicitement, et le script
refuse de le poser sur une image rangée dans `private-real/`. C'est le
garde-fou qui empêche qu'une photo non redistribuable finisse versionnée par
inadvertance — le cas exact que la décision conservatrice du projet vise à
éviter.

Usage
-----
    python -m scripts.add_photo --file private-real/salon.jpg --id salon-01 \\
        --difficulty medium --source "photo personnelle" --license "propriétaire" \\
        --verified-on 2026-09-07 --traits furnished,rug,existing_parquet

    python -m scripts.add_photo --file public/mur.png --id mur-01 --difficulty easy \\
        --source "auteur, https://…" --license CC0 --verified-on 2026-09-07 \\
        --redistributable
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from benchmarks.dataset import (
    Difficulty,
    Photo,
    Provenance,
    SceneTrait,
    Usage,
    load_manifest,
    sha256_of,
)


def add(
    root: Path,
    photo_id: str,
    relative_file: str,
    difficulty: Difficulty,
    provenance: Provenance,
    traits: list[SceneTrait],
    notes: str | None,
) -> None:
    """Ajoute ou remplace une entrée, et réécrit le manifeste trié."""
    manifest = load_manifest(root)
    entry = Photo(
        id=photo_id,
        file=relative_file,
        difficulty=difficulty,
        provenance=provenance,
        traits=traits,
        notes=notes,
    )
    kept = [photo for photo in manifest.photos if photo.id != photo_id]
    manifest.photos = sorted([*kept, entry], key=lambda photo: photo.id)

    (root / "manifest.json").write_text(
        json.dumps(
            manifest.model_dump(by_alias=True, mode="json", exclude_none=True),
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    parser.add_argument("--dataset", type=Path, default=Path("datasets"))
    parser.add_argument("--file", required=True, help="chemin relatif au dossier du corpus")
    parser.add_argument(
        "--id", required=True, help="identifiant stable ; le renommer perd l'historique"
    )
    parser.add_argument(
        "--difficulty", required=True, choices=[value.value for value in Difficulty]
    )
    parser.add_argument("--source", required=True, help="d'où vient la photo")
    parser.add_argument("--source-url")
    parser.add_argument("--author")
    parser.add_argument(
        "--license",
        required=True,
        help="nom exact de la licence ; « inconnue » est acceptable, l'inventer non",
    )
    parser.add_argument(
        "--verified-on",
        required=True,
        help="date à laquelle une personne a REGARDÉ les conditions (AAAA-MM-JJ)",
    )
    parser.add_argument(
        "--redistributable",
        action="store_true",
        help="à poser seulement après vérification ; interdit sous private-real/",
    )
    parser.add_argument(
        "--traits", default="", help="valeurs de SceneTrait, séparées par des virgules"
    )
    parser.add_argument("--notes")
    args = parser.parse_args(argv)

    path = args.dataset / args.file
    if not path.is_file():
        print(f"Erreur : image absente ({path})", file=sys.stderr)
        return 2

    if args.redistributable and args.file.startswith("private-real/"):
        print(
            "Erreur : --redistributable sur une image de private-real/. "
            "Ce dossier est hors de Git parce que son contenu ne se partage pas ; "
            "si la licence l'autorise, déplacez le fichier dans public/.",
            file=sys.stderr,
        )
        return 2
    if not args.redistributable and args.file.startswith("public/"):
        print(
            "Erreur : public/ est versionné, donc redistribué de fait. "
            "Rangez une image non redistribuable dans private-real/.",
            file=sys.stderr,
        )
        return 2

    try:
        traits = [SceneTrait(name.strip()) for name in args.traits.split(",") if name.strip()]
        provenance = Provenance(
            source=args.source,
            source_url=args.source_url,
            author=args.author,
            license=args.license,
            verified_on=date.fromisoformat(args.verified_on),
            redistributable=args.redistributable,
            usage=Usage.REDISTRIBUTABLE if args.redistributable else Usage.LOCAL_EVALUATION_ONLY,
            sha256=sha256_of(path),
        )
        add(
            args.dataset,
            args.id,
            args.file,
            Difficulty(args.difficulty),
            provenance,
            traits,
            args.notes,
        )
    except ValueError as failure:
        print(f"Erreur : {failure}", file=sys.stderr)
        return 2

    print(f"{args.id} enregistrée dans {args.dataset / 'manifest.json'}")
    print("Contrôlez : python -m scripts.validate_dataset")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
