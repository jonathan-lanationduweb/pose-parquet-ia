"""Segmentation du sol — interface commune, et l'adaptation qui compte.

**EXPLORATOIRE. AUCUNE VÉRITÉ TERRAIN OFFICIELLE. AUCUN CHOIX DE MODÈLE.**

Ce module donne une forme commune à des candidats qui ne se ressemblent pas :
une base géométrique sans apprentissage, et des modèles sémantiques entraînés
sur ADE20K. Trois candidats, pas trente : il n'y a donc ni registre de
greffons, ni fabrique, ni découverte dynamique — une fonction et un
`Protocol` suffisent, et une usine à plugins pour trois entrées serait du
décor.

## Le point qui décide de tout : `floor` n'est pas `floorVisible`

ADE20K a une classe `floor;flooring` (indice 3 en base zéro, 4 en base un) et
une classe `rug;carpet;carpeting` (28 / 29). Un modèle qui les prédit ne
répond pas pour autant à notre question. Notre `floorVisible`
(`docs/annotation-protocol.md`) est **plus strict** :

* il exclut les tapis — que la classe `rug` permet justement de retirer ;
* il exclut ce qui **repose** sur le sol : meubles, pieds, cartons. ADE20K a
  des classes pour beaucoup d'entre eux, mais elles décrivent l'objet, pas le
  fait qu'il masque le sol ;
* il exclut la surface **extérieure** vue par une ouverture — ADE20K la nomme
  `earth`, `grass`, `sidewalk`, `road`… sans dire qu'elle est dehors ;
* il exclut les éléments techniques encastrés, qu'aucune classe ne distingue ;
* et il **inclut** les ombres et les reflets francs, qu'un modèle a tendance à
  perdre.

L'adaptation appliquée ici est donc **volontairement minimale et générale** :

    floorVisible ≈ (classe floor)  −  (classes de revêtement posé)

et rien d'autre. Pas de règle par scène, pas de seuil ajusté à la main sur une
image, aucune information venue des relevés. Ce qui manque à cette règle est
précisément ce que le LOT D doit apporter — et le mesurer honnêtement suppose
de ne pas le compenser ici en cachette.

## Ce que ce module ne fait pas

Il ne choisit pas, il ne classe pas, il ne note pas. Il exécute et il rend un
masque, une frontière et des durées. Le jugement appartient à l'œil humain sur
les aperçus, et aux métriques une fois qu'une vérité terrain approuvée
existera — c'est-à-dire pas aujourd'hui.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import cv2
import numpy as np

#: Indices ADE20K (base zéro, ordre de `objectInfo150.csv`) dont nous avons
#: besoin. Relevés sur la liste officielle, pas devinés :
#: `wall` 0, `floor;flooring` 3, `rug;carpet;carpeting` 28.
ADE20K_FLOOR = 3
ADE20K_RUG = 28
ADE20K_WALL = 0

#: Ce qu'on retire du sol prédit : un revêtement posé n'est pas du sol
#: remplaçable. C'est la seule soustraction faite, et elle est générale.
ADE20K_FLOOR_COVERINGS = (ADE20K_RUG,)


@dataclass(frozen=True, slots=True)
class FloorSegmentationResult:
    """Ce qu'un candidat rend, quel qu'il soit.

    `mask` est booléen, à la résolution de l'image d'entrée. `probability`
    n'existe que si le candidat en produit une — une base géométrique n'en a
    aucune, et lui en inventer une serait mentir sur sa nature.
    """

    candidate: str
    mask: np.ndarray
    probability: np.ndarray | None = None
    #: Frontière du masque, en coordonnées normalisées : c'est là que se juge
    #: la limite sol/mur, et elle ne demande aucun modèle de plus.
    boundary: list[list[tuple[float, float]]] = field(default_factory=list)
    #: `model_load`, `inference`, `post`, `total` — en ms. Une clé absente
    #: signifie « étage non exécuté », jamais « instantané ».
    timings: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def coverage(self) -> float:
        """Part de l'image jugée « sol visible »."""
        return float(self.mask.mean()) if self.mask.size else 0.0


class FloorSegmenter(Protocol):
    """Un candidat. Une méthode, et un nom pour le reconnaître."""

    name: str

    def segment(self, image_rgb: np.ndarray) -> FloorSegmentationResult: ...


def semantic_to_floor_visible(
    labels: np.ndarray,
    *,
    floor_id: int = ADE20K_FLOOR,
    covering_ids: tuple[int, ...] = ADE20K_FLOOR_COVERINGS,
) -> np.ndarray:
    """Carte de classes ADE20K → masque de sol visible.

    Deux lignes, et c'est délibéré : toute règle supplémentaire serait une
    correction que le modèle n'a pas faite, et la lui créditer rendrait la
    comparaison fausse.
    """
    floor: np.ndarray = labels == floor_id
    for covering in covering_ids:
        floor &= labels != covering
    return floor


def clean_mask(mask: np.ndarray, *, min_area_ratio: float = 0.002) -> np.ndarray:
    """Retire les miettes, garde les trous.

    Les composantes minuscules sont du bruit de prédiction. Les **trous**, en
    revanche, ne sont pas comblés : un trou est peut-être un pied de chaise, et
    le boucher effacerait exactement ce que la préservation des objets fins
    doit mesurer.
    """
    binaire = mask.astype(np.uint8)
    nb, etiquettes, stats, _ = cv2.connectedComponentsWithStats(binaire, connectivity=8)
    if nb <= 1:
        return mask
    seuil = mask.size * min_area_ratio
    garde = np.zeros_like(mask)
    for i in range(1, nb):
        if stats[i, cv2.CC_STAT_AREA] >= seuil:
            garde |= etiquettes == i
    return garde


def mask_boundary(
    mask: np.ndarray, *, epsilon_ratio: float = 0.0015
) -> list[list[tuple[float, float]]]:
    """Contour du masque, en coordonnées normalisées.

    Sert à regarder la limite sol/mur de près — l'endroit où trois pixels de
    trop se voient immédiatement sur une plinthe blanche. Aucun modèle
    supplémentaire n'est nécessaire pour l'obtenir : elle se dérive de la
    prédiction elle-même.
    """
    hauteur, largeur = mask.shape[:2]
    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    sorties: list[list[tuple[float, float]]] = []
    for contour in contours:
        if cv2.contourArea(contour) < mask.size * 0.001:
            continue
        approx = cv2.approxPolyDP(contour, epsilon_ratio * max(largeur, hauteur), True)
        sorties.append(
            [(float(p[0][0]) / (largeur - 1), float(p[0][1]) / (hauteur - 1)) for p in approx]
        )
    return sorties


def mask_to_png_bytes(mask: np.ndarray) -> bytes:
    """Masque binaire → PNG.

    Format retenu pour cette passe, et la raison est la simplicité : un PNG
    binaire se relit avec n'importe quoi, se compare octet à octet, s'ouvre
    dans une visionneuse, et pèse quelques kilo-octets sur un masque de sol.
    Un tableau JSON de pixels serait illisible et énorme ; un codage par plages
    ou un polygone seraient plus compacts mais demanderaient un décodeur de
    plus, à écrire et à éprouver, pour un gain qui ne se voit pas à cette
    échelle. Le polygone existe déjà par ailleurs, sous le nom `boundary`.
    """
    ok, tampon = cv2.imencode(".png", (mask.astype(np.uint8) * 255))
    if not ok:
        raise RuntimeError("encodage PNG du masque impossible")
    return bytes(tampon.tobytes())
