"""Assemblage de la SceneData — le dernier étage, et il n'existe pas encore.

Ce module est délibérément court, et il ne fabrique **rien**. Sa raison d'être
au LOT 0 est de tenir le seul endroit du projet où une scène pourra naître,
pour qu'on n'en trouve jamais une deuxième ailleurs.

## Pourquoi il ne renvoie rien

Une `SceneData` exige au minimum une zone de sol, donc un quadrilatère de
perspective et un contour. Ces deux valeurs viennent de la segmentation
(LOT 2) et de la géométrie (LOT 4). Tant qu'elles n'existent pas, il n'y a que
deux façons d'en produire une :

* deviner un quadrilatère plausible — c'est exactement ce que fait déjà le
  front dans son analyseur `manual`, et le refaire côté serveur ne rendrait
  service à personne tout en portant l'étiquette `source: "ai"`, qui autorise
  l'interface à parler de « détection » ;
* renvoyer une scène vide — que `normalizeScene()` refuse, et à juste titre.

La bonne réponse est donc `None`, accompagnée d'un `status` qui le dit. Le
front retombe sur la sélection manuelle, qui reste le socle du Visualiseur :
« aucune panne du service ne doit priver l'utilisateur du Visualiseur ».

## Ce qu'il fera, au LOT 6

Recevoir un masque de sol, un jeu de plans, des occulteurs et une caméra, et
les composer en `SceneData` — en propageant les confiances de chaque étage
vers `confidence`, zone par zone. La validation Pydantic de `SceneData` est,
elle, déjà en place et testée contre les scènes réelles du front : c'est ce
qui garantit qu'aucun champ n'aura été inventé le jour où cette fonction
produira quelque chose.
"""

from app.core.warnings import Warn
from app.schemas.scene_data import SceneData

#: Étages dont dépend la construction d'une scène, et qui manquent tous.
#: Écrit ici plutôt que dans un commentaire : le test de non-régression du
#: LOT 6 lira cette liste pour vérifier qu'elle s'est bien vidée.
MISSING_STAGES: tuple[str, ...] = ("segmentation", "depth", "perspective", "occlusion")


def build_scene_data() -> SceneData | None:
    """Compose une `SceneData`. Renvoie `None` tant que les étages manquent.

    La signature restera celle-ci une fois les étages présents : ce sont ses
    paramètres qui apparaîtront, pas son type de retour qui changera — un
    étage peut toujours échouer, et `None` restera une réponse valide.
    """
    return None


def missing_stage_warnings() -> list[Warn]:
    """Dit que des étages n'ont pas tourné, plutôt que de laisser croire à un silence.

    « Rien à signaler » et « je n'ai pas regardé » ne sont pas la même chose,
    et une liste d'avertissements vide voudrait dire la première.
    """
    return [Warn.STAGE_NOT_IMPLEMENTED] if MISSING_STAGES else []
