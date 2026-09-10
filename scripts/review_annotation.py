"""Promotion de statut d'un relevé déjà importé — LOT B.4.

Le manque que ce script comble : la seule façon d'écrire un statut était de
**réimporter** le tracé (`scripts/import_annotation.py`). Réimporter refait
tout — il rastérise les masques, et il réécrit `annotatedOn` avec la date du
jour. Une promotion faite ainsi déplacerait la date du relevé vers la date de
la revue, et un relevé du 10 septembre relu le 15 se présenterait comme
dessiné le 15. C'est une falsification de traçabilité, petite et durable.

Ce script fait donc l'inverse : il ne touche **que** le statut et le bloc de
revue. L'auteur du tracé, sa date, sa révision, sa passe, ses géométries et
ses masques sont laissés exactement en place. Il n'y a aucun cas où promouvoir
doit changer qui a dessiné.

Deux refus, tous deux volontaires :

* si un masque ne correspond plus à son empreinte enregistrée, la promotion
  est refusée. Approuver un relevé dont les octets ont bougé depuis la mesure
  reviendrait à approuver quelque chose qu'on n'a pas regardé ;
* un tracé produit par une machine reste attribué à la machine. Il n'existe
  aucune option pour réécrire `annotator` : un relevé relu par une personne
  devient un relevé **relu** par elle, jamais un relevé **dessiné** par elle.

Usage
-----
    python -m scripts.review_annotation --photo sejour --pass-label AI \\
        --reviewer jonathan --status approved --note "revue visuelle : conforme"
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path

from app.schemas.annotation import AnnotationStatus, FloorAnnotation
from benchmarks.annotations import ANNOTATIONS_DIR


class ReviewError(Exception):
    """La promotion est refusée. Le dire, jamais la rattraper."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def promote(
    path: Path,
    reviewer: str,
    status: AnnotationStatus,
    note: str | None = None,
    corrected: bool = False,
    today: date | None = None,
) -> dict[str, object]:
    """Écrit le statut et la revue, et rien d'autre.

    :returns: ce qui a changé, champ par champ — de quoi vérifier d'un coup
        d'œil que la géométrie n'a pas bougé.
    :raises ReviewError: statut refusé, ou masques désynchronisés.
    """
    if status is AnnotationStatus.DRAFT:
        raise ReviewError(
            "rétrograder vers « draft » n'est pas une promotion : reprenez le tracé "
            "et réimportez-le, ce qui incrémentera la révision"
        )

    brut = json.loads(path.read_text(encoding="utf-8"))
    annotation = FloorAnnotation.model_validate(brut)

    # Les octets, avant tout le reste. Un masque modifié après l'import doit
    # faire échouer la promotion, pas la traverser en silence.
    dossier = path.parent
    empreintes = annotation.mask_sha256 or {}
    a_verifier = [("floorVisible", annotation.masks.floor_visible)]
    if annotation.masks.uncertain is not None:
        a_verifier.append(("uncertain", annotation.masks.uncertain))
    for cle, relatif in a_verifier:
        reel = _sha256(dossier / relatif)
        if empreintes.get(cle) != reel:
            raise ReviewError(
                f"le masque « {relatif} » ne correspond plus à son empreinte : "
                f"{empreintes.get(cle)} attendu, {reel} sur le disque. "
                "Réimportez le tracé en incrémentant --revision avant toute revue."
            )

    avant = {"status": brut["status"], "review": brut.get("review")}
    brut["status"] = status.value
    brut["review"] = {
        "reviewer": reviewer,
        "reviewedOn": (today or date.today()).isoformat(),
        "corrected": corrected,
        "note": note,
    }
    # Revalidé avant écriture : le schéma refuse un statut relu sans bloc de
    # revue nommé et daté, et c'est lui qui a le dernier mot.
    FloorAnnotation.model_validate(brut)
    path.write_text(json.dumps(brut, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "photo": annotation.photo_id,
        "annotateur (inchange)": annotation.annotator,
        "date du trace (inchangee)": annotation.annotated_on.isoformat(),
        "revision (inchangee)": annotation.revision,
        "passe (inchangee)": annotation.pass_label,
        "statut": f"{avant['status']} -> {status.value}",
        "relecteur": reviewer,
        "revue independante": annotation.annotator != reviewer,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Promouvoir le statut d'un relevé importé")
    parser.add_argument("--dataset", type=Path, default=Path("datasets"))
    parser.add_argument("--photo", required=True, help="identifiant de la photo, ex. sejour")
    parser.add_argument("--pass-label", default=None, help="suffixe de passe, ex. AI, A, B")
    parser.add_argument("--reviewer", required=True, help="qui a relu — jamais qui a dessiné")
    parser.add_argument(
        "--status",
        required=True,
        choices=[AnnotationStatus.REVIEWED.value, AnnotationStatus.APPROVED.value],
        help="reviewed : constaté. approved : engagé comme référence au banc d'essai",
    )
    parser.add_argument("--note", help="verdict écrit du relecteur")
    parser.add_argument(
        "--corrected",
        action="store_true",
        help="le relecteur a modifié le masque, pas seulement donné un avis",
    )
    args = parser.parse_args(argv)

    suffixe = f".{args.pass_label}" if args.pass_label else ""
    chemin = args.dataset / ANNOTATIONS_DIR / f"{args.photo}{suffixe}.json"
    if not chemin.is_file():
        print(f"relevé absent : {chemin}")
        return 1

    try:
        bilan = promote(
            chemin,
            args.reviewer,
            AnnotationStatus(args.status),
            note=args.note,
            corrected=args.corrected,
        )
    except ReviewError as refus:
        print(f"promotion refusée — {refus}")
        return 1

    for cle, valeur in bilan.items():
        print(f"  {cle:<28} {valeur}")
    if not bilan["revue independante"]:
        print(
            "\n  avertis. relecteur et annotateur portent le même nom : c'est une "
            "AUTO-RELECTURE, et le bilan de corpus la comptera comme telle."
        )
    print(f"\nÉcrit : {chemin}")
    print("Contrôlez : python -m scripts.validate_dataset")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
