"""La campagne d'annotation pilote : quatre scènes, deux passes chacune.

Quatre scènes, pas onze. Le but n'est pas de couvrir le corpus mais de
**calibrer le protocole** : mesurer combien de temps une annotation coûte, où
une même main se contredit d'une passe à l'autre, et si les règles du §1 se
laissent appliquer sur de vraies photos.

Huit relevés suffisent pour cela, et huit relevés sont faisables. Quarante-quatre
ne le seraient pas, et une campagne qu'on n'achève pas ne mesure rien.

## Pourquoi ces quatre

Le choix vise la **diversité des difficultés réelles**, pas le remplissage des
catégories. Quatre pièces vides bien réparties en `easy`/`medium`/`hard`
n'auraient rien appris.

Chaque scène apporte au moins un cas qu'aucune autre ne porte, et les deux
décisions humaines prises après le rapport du LOT 2A — extérieur exclu,
élément encastré exclu — sont mises à l'épreuve par `chambre`, qui porte les
deux.

## Ce que ce module ne fait pas

Il ne crée aucun masque et ne mesure rien. Il dit **quels relevés sont
attendus** et lesquels manquent, pour qu'une commande puisse répondre « il en
reste trois » sans que personne tienne le compte à la main.
"""

from dataclasses import dataclass
from typing import Any

#: Étiquettes des deux passes indépendantes attendues par scène.
PASSES: tuple[str, ...] = ("A", "B")


@dataclass(frozen=True, slots=True)
class Selection:
    """Une scène retenue, et la raison de l'avoir retenue.

    La raison est stockée, pas seulement documentée : dans six mois, « pourquoi
    celle-là » sera la première question, et une sélection dont on a perdu le
    motif se refait au hasard.
    """

    photo_id: str
    role: str
    #: Ce que cette scène apporte et qu'aucune autre du corpus ne porte.
    rationale: str
    #: Les pièges attendus, dans les mots de l'annotateur.
    watch_for: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "photoId": self.photo_id,
            "role": self.role,
            "rationale": self.rationale,
            "watchFor": list(self.watch_for),
        }


#: Les quatre scènes de la campagne pilote.
#:
#: L'ordre est celui dans lequel les annoter : la plus simple d'abord, pour
#: prendre la main sur l'outil et donner une durée de référence, la plus
#: laborieuse en dernier, quand le geste est acquis.
CAMPAIGN: tuple[Selection, ...] = (
    Selection(
        photo_id="sejour",
        role="easy",
        rationale=(
            "La référence facile — et un piège utile malgré tout : deux pièces "
            "en enfilade sur UN SEUL parquet. L'ouverture n'est pas une "
            "frontière de sol, et un annotateur peut être tenté d'en tracer "
            "une. Seule scène `easy` à porter des reflets francs, ce qui met à "
            "l'épreuve la règle « un reflet est du sol »."
        ),
        watch_for=(
            "ne PAS couper le masque à l'ouverture : le parquet continue",
            "les reflets de fenêtre sur les lames sont du sol",
            "sa durée devient la référence des trois autres",
        ),
    ),
    Selection(
        photo_id="chambre",
        role="medium",
        rationale=(
            "La scène qui met à l'épreuve les DEUX décisions humaines : une "
            "terrasse visible par la porte-fenêtre (désormais exclue) et une "
            "grille de ventilation encastrée dans le parquet (désormais "
            "exclue). Contraste mur/sol très élevé, ce qui isole les deux "
            "règles de toute difficulté de frontière : si un désaccord "
            "apparaît ici, il porte sur la définition, pas sur la main."
        ),
        watch_for=(
            "la terrasse est DEHORS : hors du masque, même de plain-pied",
            "le seuil de la porte-fenêtre est un contour, pas une fin de sol",
            "la grille encastrée est exclue ; le parquet autour reste inclus",
        ),
    ),
    Selection(
        photo_id="couloir",
        role="hard",
        rationale=(
            "Le cas décisif de la frontière mur/sol : bois clair sur bois "
            "clair, sans plinthe ni changement de teinte à droite. Le front y "
            "avait mesuré des résidus de 46 et 61 px en tentant de relever le "
            "pied de mur. C'est ici que le masque `uncertain` doit prouver son "
            "utilité, et ici que la répétabilité sera la plus basse."
        ),
        watch_for=(
            "ne forcez PAS la ligne de pied de mur : déclarez-la incertaine",
            "la zone incertaine doit couvrir toute la largeur du doute",
            "la part incertaine sera élevée : c'est un résultat, pas un échec",
        ),
    ),
    Selection(
        photo_id="petite-piece",
        role="most_ambiguous",
        rationale=(
            "La scène la plus ambiguë du corpus, et de loin : huit pieds "
            "fuselés (bureau et chaise) à contourner, un rideau tombant "
            "jusqu'au sol dont on ne voit pas la fin, un angle de murs masqué "
            "par le bureau, un radiateur avec du sol dessous, et le sol coupé "
            "par le bas du cadre. Le front l'avait classée "
            "« boundary-not-verifiable ». Sa durée est l'information la plus "
            "utile du lot : c'est elle qui dira si trente scènes sont "
            "réalistes."
        ),
        watch_for=(
            "le bas du cadre est un `frame_cut`, pas une frontière de scène",
            "le pied du rideau et l'angle masqué : incertains, pas devinés",
            "le sol sous le radiateur est du sol si on le voit",
        ),
    ),
)


def expected_annotations() -> tuple[tuple[str, str], ...]:
    """Les huit relevés attendus, sous forme (photo, passe)."""
    return tuple((selection.photo_id, label) for selection in CAMPAIGN for label in PASSES)


def progress(present: set[tuple[str, str]]) -> dict[str, Any]:
    """Ce qui est là, ce qui manque, et si l'analyse peut tourner.

    `present` est l'ensemble des couples (photo, passe) trouvés dans le
    corpus. La fonction ne lit rien elle-même : elle compare une attente à un
    constat, et rien d'autre.
    """
    expected = expected_annotations()
    missing = [pair for pair in expected if pair not in present]
    return {
        "scenes": [selection.as_dict() for selection in CAMPAIGN],
        "expected": len(expected),
        "collected": len(expected) - len(missing),
        "missing": [{"photoId": photo, "pass": label} for photo, label in missing],
        "complete": not missing,
    }
