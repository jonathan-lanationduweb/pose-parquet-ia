"""Constitue le corpus pilote dans `private-real/`, provenance à l'appui.

Les onze scènes viennent du dépôt du front, **lu en lecture seule**. Elles y
sont créditées nommément — auteur, identifiant Pexels, URL — dans
`assets/images/CREDITS.md`, ce qui satisfait l'exigence de provenance
documentée. Ce script recopie cette provenance plutôt que de l'inventer.

## Pourquoi `private-real/` et pas `public/`

Ce n'est pas une limite de la licence. La licence Pexels autoriserait
probablement la redistribution — elle interdit de reverser les photos sur une
plateforme de banque d'images, pas de constituer un corpus d'évaluation.

C'est une **décision humaine prise au préambule** : pas de corpus Pexels
redistribué dans ce dépôt. `redistributable: false` enregistre donc notre
choix, et non une contrainte du titulaire. La note de provenance le dit, pour
qu'un lecteur futur ne prenne pas l'un pour l'autre.

## Ce que ce script ne fait pas

Il ne crée **aucune annotation**. Le sol se relève à la main : c'est l'objet du
LOT 2A, et c'est un travail humain que rien ici ne peut remplacer. Voir
`docs/pilot-runbook.md`.

Les difficultés et les traits ci-dessous viennent de deux sources : les
jugements que le front a lui-même consignés scène par scène
(`data/scenes/index.json`), et l'observation des photos. Ils sont **révisables**
— la première annotation dira si une scène rangée en `medium` coûte en réalité
autant qu'une `hard`.

Usage
-----
    python -m scripts.collect_pilot
    python -m scripts.collect_pilot --front C:/chemin/vers/pose-parquet.com
"""

import argparse
import shutil
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from benchmarks.dataset import Difficulty, Provenance, SceneTrait, Usage, sha256_of
from scripts.add_photo import add

T = SceneTrait

#: Chemin par défaut du dépôt du front, lu en LECTURE SEULE.
DEFAULT_FRONT = Path(r"C:\Users\jonat\Desktop\pose-parquet.com")

#: Nom exact de la licence, tel que le front la documente.
LICENSE = "Pexels License"

#: Date à laquelle la provenance a été relevée dans le CREDITS.md du front.
VERIFIED_ON = date(2026, 9, 7)


@dataclass(frozen=True, slots=True)
class Pick:
    """Une scène du pilote, et pourquoi elle y est."""

    photo_id: str
    source_file: str
    author: str
    pexels_id: str
    difficulty: Difficulty
    traits: tuple[SceneTrait, ...]
    #: Ce que cette scène doit éprouver. C'est le champ qui justifie sa
    #: présence : une photo qui n'éprouve rien qu'une autre n'éprouve déjà ne
    #: fait que rallonger le temps d'annotation.
    note: str


#: Onze scènes, choisies pour ce qu'elles éprouvent et non pour faire nombre.
#:
#: Le déséquilibre — trois faciles, deux moyennes, cinq difficiles — n'est pas
#: recherché : les photos disponibles sont soit des intérieurs vides mis en
#: scène (donc faciles), soit des cas de frontière franchement durs. Il y a
#: peu d'entre-deux, et **presque aucun mobilier** : le front a choisi ses
#: photos pour leurs sols DÉGAGÉS, ce qui est l'inverse de ce qu'un banc
#: d'essai de segmentation demande. Voir le rapport du lot.
PILOT: tuple[Pick, ...] = (
    Pick(
        "bureau-vide",
        "room-bureau-vide.jpg",
        "Curtis Adams",
        "7028110",
        Difficulty.EASY,
        (T.EMPTY_ROOM, T.EXISTING_PARQUET, T.DOORS, T.EASY_PERSPECTIVE),
        "Référence facile : pièce vide, plinthes blanches franches, vue d'angle. "
        "Une embrasure en bas à gauche montre un sol plus sombre au-delà.",
    ),
    Pick(
        "entree-cadree",
        "room-entree-cadree.jpg",
        "Gustavo Galeano Maz",
        "7865621",
        Difficulty.EASY,
        (T.EMPTY_ROOM, T.EXISTING_PARQUET, T.TILES, T.DOORS, T.CROPPED, T.EASY_PERSPECTIVE),
        "SEUIL DE PORTE net : le parquet cède la place à un sol clair de couloir. "
        "Changement de sol, pas fin de sol. Cadrage serré, centre optique "
        "possiblement décentré — le LOT 1 a mesuré 43 % d'erreur de k1 sur ce "
        "cas de figure, en synthétique seulement.",
    ),
    Pick(
        "sejour",
        "room-sejour.jpg",
        "Curtis Adams",
        "3935327",
        Difficulty.EASY,
        (
            T.EMPTY_ROOM,
            T.EXISTING_PARQUET,
            T.REFLECTIVE_FLOOR,
            T.DOORS,
            T.LARGE_ROOM,
            T.EASY_PERSPECTIVE,
        ),
        "Deux pièces en enfilade sur UN SEUL parquet : l'ouverture n'est pas une "
        "frontière de sol, et un annotateur peut être tenté d'en tracer une. "
        "Reflets francs de fenêtre sur les lames.",
    ),
    Pick(
        "chambre",
        "room-chambre.jpg",
        "Max Vakhtbovych",
        "7587859",
        Difficulty.MEDIUM,
        (
            T.EMPTY_ROOM,
            T.EXISTING_PARQUET,
            T.DOORS,
            T.EXTERIOR_VISIBLE,
            T.LARGE_ROOM,
            T.EASY_PERSPECTIVE,
        ),
        "LA QUESTION QUE LE PROTOCOLE NE TRANCHE PAS : une terrasse extérieure "
        "est visible par la porte-fenêtre. Est-elle « du sol » ? Porte aussi une "
        "grille de ventilation encastrée dans le parquet. Contraste mur/sol très "
        "élevé (murs bleu foncé), ce qui en fait un témoin utile.",
    ),
    Pick(
        "piece-claire",
        "room-piece-claire.jpg",
        "Max Vakhtbovych",
        "8146330",
        Difficulty.MEDIUM,
        (
            T.FURNISHED,
            T.RADIATOR,
            T.DOORS,
            T.EXISTING_PARQUET,
            T.EASY_PERSPECTIVE,
        ),
        "Meuble bas sur pieds courts et radiateur, tous deux avec du sol visible "
        "dessous. Tache de soleil dure au pied de la baie. Aucune plinthe : le "
        "mur gris rencontre directement le sol clair.",
    ),
    Pick(
        "appartement-ancien",
        "room-appartement-ancien.jpg",
        "Curtis Adams",
        "8583672",
        Difficulty.HARD,
        (
            T.FURNISHED,
            T.THIN_FURNITURE_LEGS,
            T.EXISTING_PARQUET,
            T.CORRIDOR,
            T.DOORS,
            T.HARD_PERSPECTIVE,
        ),
        "PIEDS FINS : une console cabriole et un porte-manteau à colonnettes, "
        "huit pieds à contourner. Couloir profond, sols visibles par plusieurs "
        "embrasures successives. Le front y avait laissé une bande du même sol "
        "hors de son masque.",
    ),
    Pick(
        "salon",
        "room-salon.jpg",
        "Curtis Adams",
        "7027842",
        Difficulty.HARD,
        (
            T.EMPTY_ROOM,
            T.EXISTING_PARQUET,
            T.DARK_FLOOR,
            T.REFLECTIVE_FLOOR,
            T.DOORS,
            T.LARGE_ROOM,
        ),
        "Parquet foncé très réfléchissant : reflets de fenêtre assez francs pour "
        "qu'on soit tenté de les exclure. Quatre zones de sol par trois "
        "ouvertures. Une bouche de soufflage encastrée dans le sol.",
    ),
    Pick(
        "couloir",
        "room-couloir.jpg",
        "Max Vakhtbovych",
        "7587374",
        Difficulty.HARD,
        (
            T.EMPTY_ROOM,
            T.CORRIDOR,
            T.EXISTING_PARQUET,
            T.LOW_WALL_FLOOR_CONTRAST,
            T.DOORS,
        ),
        "LE CAS DÉCISIF. Bois clair sur bois clair : à droite, le mur crème "
        "rejoint le sol sans plinthe ni marche de teinte. Le front a mesuré des "
        "résidus de 46 et 61 px en tentant d'y relever le pied de mur. C'est ici "
        "que le masque `uncertain` doit prouver son utilité.",
    ),
    Pick(
        "petite-piece",
        "room-petite-piece.jpg",
        "Image Hunter",
        "26747989",
        Difficulty.HARD,
        (
            T.FURNISHED,
            T.THIN_FURNITURE_LEGS,
            T.RADIATOR,
            T.EXISTING_PARQUET,
            T.SMALL_ROOM,
            T.HIDDEN_CORNERS,
        ),
        "La plus laborieuse : bureau et chaise à pieds fuselés (huit pieds), "
        "rideau tombant jusqu'au sol dont on ne voit pas la fin, angle de murs "
        "masqué par le bureau, sol coupé par le bas du cadre. Front : "
        "« boundary-not-verifiable ».",
    ),
    Pick(
        "piece-arcades",
        "room-piece-arcades.jpg",
        "Daniel Tanque",
        "13702811",
        Difficulty.HARD,
        (
            T.EMPTY_ROOM,
            T.EXISTING_PARQUET,
            T.CURVED_ARCHITECTURE,
            T.LARGE_ROOM,
            T.DOORS,
            T.LOW_WALL_FLOOR_CONTRAST,
        ),
        "COURBES ARCHITECTURALES RÉELLES : deux arcades maçonnées, dont une "
        "alcôve avec son propre sol visible. Le LOT 1 n'avait éprouvé ce cas "
        "qu'en synthétique. Embrasure sombre au fond où le sol n'est PAS "
        "visible — bonne occasion de ne pas l'inventer.",
    ),
    Pick(
        "contraste",
        "room-contraste.jpg",
        "sanket mahind",
        "18707513",
        Difficulty.REJECTED,
        (T.NOT_A_ROOM, T.EMPTY_ROOM, T.DARK_FLOOR, T.EXISTING_PARQUET),
        "Rangée en `rejected` parce que ce n'est pas une pièce : un mur, un rai "
        "de soleil, une lisière de sol. À noter : son sol est parfaitement "
        "annotable. `rejected` veut dire « on n'attend pas de SceneData "
        "exploitable », pas « le sol est indéchiffrable ».",
    ),
)


def collect(front: Path, root: Path) -> tuple[int, list[str]]:
    """Copie les photos et les enregistre. Renvoie le compte et les problèmes."""
    source_dir = front / "assets" / "images"
    if not source_dir.is_dir():
        raise FileNotFoundError(f"dossier d'images du front introuvable : {source_dir}")

    target_dir = root / "private-real"
    target_dir.mkdir(parents=True, exist_ok=True)

    problems: list[str] = []
    collected = 0
    for pick in PILOT:
        source = source_dir / pick.source_file
        if not source.is_file():
            problems.append(f"{pick.photo_id} : absente du front ({pick.source_file})")
            continue

        target = target_dir / f"{pick.photo_id}.jpg"
        # Copie seule : le front n'est jamais écrit, jamais déplacé.
        shutil.copyfile(source, target)

        add(
            root,
            pick.photo_id,
            f"private-real/{pick.photo_id}.jpg",
            pick.difficulty,
            Provenance(
                source=f"pose-parquet.com, assets/images/{pick.source_file} — Pexels",
                source_url=f"https://www.pexels.com/photo/{pick.pexels_id}/",
                author=pick.author,
                license=LICENSE,
                verified_on=VERIFIED_ON,
                # Notre décision, PAS une contrainte de la licence. La note le dit.
                redistributable=False,
                usage=Usage.LOCAL_EVALUATION_ONLY,
                sha256=sha256_of(target),
                note=(
                    "Provenance recopiée de assets/images/CREDITS.md du front. "
                    "redistributable=false enregistre la décision humaine du "
                    "préambule LOT 2 (pas de corpus Pexels redistribué dans ce "
                    "dépôt), et non une limite de la Pexels License."
                ),
            ),
            list(pick.traits),
            pick.note,
        )
        collected += 1
    return collected, problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    parser.add_argument("--front", type=Path, default=DEFAULT_FRONT, help="dépôt du front, lu seul")
    parser.add_argument("--dataset", type=Path, default=Path("datasets"))
    args = parser.parse_args(argv)

    try:
        collected, problems = collect(args.front, args.dataset)
    except FileNotFoundError as missing:
        print(f"Erreur : {missing}", file=sys.stderr)
        return 2

    for problem in problems:
        print(f"  ! {problem}", file=sys.stderr)
    print(f"{collected} photo(s) dans {args.dataset / 'private-real'} (hors Git)")

    counts: dict[str, int] = {}
    for pick in PILOT:
        counts[pick.difficulty.value] = counts.get(pick.difficulty.value, 0) + 1
    print(f"répartition : {counts}")
    print("\nAucune annotation créée : le relevé du sol est un travail humain.")
    print("Marche à suivre : docs/pilot-runbook.md")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
