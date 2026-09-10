"""Contrôle le corpus : manifeste, images, provenance, masques, statuts.

À lancer avant tout banc d'essai, et après chaque annotation. Sort en code 1
dès qu'une erreur est trouvée, pour pouvoir être branché sur un contrôle
automatique.

Ce qui est vérifié, et pourquoi chacun mérite d'être bloquant :

* **une image référencée qui n'existe pas** — un rapport la sauterait
  silencieusement et la moyenne porterait sur un corpus différent de celui
  qu'on croit ;
* **un hash qui ne correspond plus** — l'image a changé sous l'annotation. Le
  masque décrit alors une autre photo ;
* **des dimensions de masque différentes de l'image** — rien n'est
  redimensionné, donc rien n'est comparable ;
* **des valeurs autres que 0 et 255** — signature d'une interpolation ou d'un
  JPEG, donc de frontières fausses ;
* **une licence non renseignée** — une licence absente ne doit jamais devenir
  une licence supposée ;
* **un statut approuvé sans relecture nommée** — refusé par le schéma
  lui-même, avant d'arriver ici ;
* **une zone incertaine qui avale l'image** — il ne resterait pas assez à
  mesurer.

Usage
-----
    python -m scripts.validate_dataset
    python -m scripts.validate_dataset --dataset datasets --json
"""

import argparse
import json
import sys
from pathlib import Path

from benchmarks.annotations import corpus_report, load_corpus
from benchmarks.dataset import golden_coverage, load_manifest, sha256_of


def _check_manifest_files(root: Path) -> list[str]:
    """Contrôles portant sur le manifeste seul, annotations mises à part.

    Une photo peut être enregistrée sans être encore annotée : c'est l'état
    normal d'un corpus en cours de constitution, et il faut pouvoir vérifier sa
    provenance avant d'investir du temps à l'annoter.
    """
    problems: list[str] = []
    manifest = load_manifest(root)

    seen: dict[str, str] = {}
    for photo in manifest.photos:
        path = root / photo.file
        if not path.is_file():
            problems.append(f"{photo.id} : fichier absent ({photo.file})")
            continue

        digest = sha256_of(path)
        if photo.provenance.sha256 and photo.provenance.sha256 != digest:
            problems.append(f"{photo.id} : sha256 du manifeste ne correspond plus au fichier")
        if digest in seen and seen[digest] != photo.id:
            problems.append(
                f"{photo.id} : octets identiques à {seen[digest]} — doublon dans le corpus"
            )
        seen[digest] = photo.id

        if photo.provenance.redistributable and photo.file.startswith("private-real/"):
            problems.append(
                f"{photo.id} : déclarée redistribuable mais rangée dans private-real/ — "
                "déplacez-la dans public/ ou corrigez la provenance"
            )
        if not photo.provenance.redistributable and photo.file.startswith("public/"):
            problems.append(
                f"{photo.id} : rangée dans public/ mais non redistribuable — "
                "public/ est versionné, donc redistribué de fait"
            )
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    parser.add_argument("--dataset", type=Path, default=Path("datasets"))
    parser.add_argument(
        "--json", action="store_true", help="rapport machine sur la sortie standard"
    )
    args = parser.parse_args(argv)

    try:
        manifest_problems = _check_manifest_files(args.dataset)
        scenes = load_corpus(args.dataset)
    except (FileNotFoundError, KeyError, ValueError) as failure:
        print(f"Erreur : {failure}", file=sys.stderr)
        return 1

    manifest = load_manifest(args.dataset)
    report = corpus_report(scenes)
    report["manifestProblems"] = manifest_problems
    report["goldenCoverage"] = golden_coverage(manifest)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        photos = len(manifest.photos)
        print(f"Manifeste : {photos} photo(s), {len(manifest_problems)} problème(s)")
        for problem in manifest_problems:
            print(f"  ERREUR  {problem}")
        print(
            f"Annotations : {report['scenes']} scène(s), {report['usable']} exploitable(s) "
            f"au banc d'essai officiel"
        )
        print(f"  statuts : {report['byStatus']}")
        for issue in report["issues"]:
            level = "ERREUR " if issue["level"] == "error" else "avertis."
            print(f"  {level} [{issue['code']}] {issue['message']}")

        roles = report["exclusionsByRole"]
        print(f"Exclusions : {sum(roles.values())}, dont {report['thinExclusions']} fine(s)")
        for role, compte in roles.items():
            if compte or role in {"occluder", "floor_covering", "structural", "unknown"}:
                print(f"  {role:<16} {compte}{'' if compte else '  — aucune'}")
        if not roles.get("floor_covering"):
            print(
                "  avertis. aucun revetement de sol annote : le corpus n'a pas de "
                "tapis, donc le debordement sur tapis reste NON MESURABLE"
            )

        golden = report["goldenCoverage"]
        print(f"Jeu visuel de référence : {golden['scenes']} scène(s)")
        for case, ids in golden["byCase"].items():
            marque = " ".join(ids) if ids else "— NON COUVERT"
            print(f"  {case:<20} {marque}")
        if golden["scenes"] and not golden["majorityIsHard"]:
            print(
                "  avertis. la majorité du jeu de référence est facile : "
                "il ne prouvera pas grand-chose"
            )
        if not photos:
            print(
                "\nLe corpus réel est vide. Le format, les contrôles et le banc d'essai "
                "sont en place ; les photos restent à collecter.\n"
                "Voir datasets/README.md et docs/annotation-protocol.md."
            )

    failed = bool(manifest_problems) or report["withErrors"] > 0
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
