"""Images de base du corpus : les scènes saines dont on dérive tout le reste.

`patterns.py` fournit des primitives (aplats, damiers, barres). Ce module
fournit les **bases** du corpus du LOT 1 : des images nettes, bien exposées,
auxquelles `transforms.py` applique ensuite une dégradation connue.

Chacune isole une propriété, et le nom dit laquelle. Elles ne cherchent pas à
ressembler à une photographie — elles cherchent à rendre une question
décidable.

La question centrale du lot est celle-ci : **une image pauvre en détail n'est
pas une image floue.** Trois bases y répondent ensemble, et aucune seule ne
suffit :

* `textured` — nette et riche. Une mesure de netteté doit y répondre fort ;
* `smooth_wall` — nette et *vide*. Aucune haute fréquence à mesurer, alors que
  rien n'est flou. Toute mesure fondée sur une dérivée y répond aussi bas que
  sur une image franchement floue, et c'est exactement le piège ;
* `sparse_detail` — nette, presque vide, mais avec quelques arêtes franches.
  C'est le cas réaliste d'un mur blanc avec un chambranle, et le seul où l'on
  peut à la fois constater le manque de texture *et* conclure sur la netteté.

Pour la distorsion, la distinction qui compte n'est pas « y a-t-il des
droites » mais **combien, et longues** :

* `architectural` — peu d'arêtes, très longues, irrégulièrement placées ;
* `patterns.checkerboard` — beaucoup d'arêtes, toutes courtes et régulières ;
* `curved_objects` — des courbes véritables, que la scène contient vraiment.

Tout est déterministe : chaque fonction bruitée prend une graine explicite.
"""

from typing import cast

import cv2
import numpy as np

#: Format de travail par défaut du corpus. 1600 × 1067 est le format des
#: scènes calibrées du front, ce qui rend les ordres de grandeur en pixels
#: directement comparables aux relevés existants.
CORPUS_SIZE = (1600, 1067)

#: Tons de référence. Assez éloignés des bornes pour qu'aucune base saine ne
#: déclenche d'avertissement d'exposition — une base qui en déclencherait
#: brouillerait la lecture de la transformation qu'on lui applique ensuite.
_WALL = 150
_INK = 60


def _blank(size: tuple[int, int], value: int) -> np.ndarray:
    width, height = size
    return np.full((height, width, 3), value, dtype=np.uint8)


def textured(size: tuple[int, int] = CORPUS_SIZE, seed: int = 11) -> np.ndarray:
    """Nette et riche en détail, à plusieurs échelles.

    Un empilement de rectangles à bords francs plutôt qu'un bruit blanc : le
    bruit blanc est « net » au sens de la dérivée mais ne ressemble à aucune
    photographie, et surtout il ne se dégrade pas comme une vraie image sous
    un flou modéré. Les rectangles donnent un spectre large avec de vraies
    arêtes, ce qui est la propriété qu'on veut mesurer.
    """
    width, height = size
    rng = np.random.default_rng(seed)
    canvas = _blank(size, _WALL)

    for scale, count in ((0.22, 40), (0.09, 120), (0.035, 300)):
        box_w = max(2, int(width * scale))
        box_h = max(2, int(height * scale))
        for _ in range(count):
            x = int(rng.integers(0, max(1, width - box_w)))
            y = int(rng.integers(0, max(1, height - box_h)))
            tone = int(rng.integers(45, 215))
            canvas[y : y + box_h, x : x + box_w] = tone

    # Quelques traits fins : ce sont eux qui disparaissent en premier sous un
    # flou léger, et donc eux qui rendent les faibles sigmas mesurables.
    for _ in range(60):
        y = int(rng.integers(0, height))
        canvas[y : y + 1, :] = int(rng.integers(30, 225))
    return canvas


def smooth_wall(size: tuple[int, int] = CORPUS_SIZE) -> np.ndarray:
    """Parfaitement nette et **sans aucun détail** : un dégradé lisse.

    Rien n'est flou ici. Aucun pixel n'a été moyenné avec son voisin. Et
    pourtant la variance du Laplacien y est quasi nulle, comme sur une image
    franchement floutée. C'est le contre-exemple qui interdit de traduire
    « peu de haute fréquence » par « floue ».
    """
    width, height = size
    ys, xs = np.mgrid[0:height, 0:width].astype(np.float32)
    ramp = 120.0 + 55.0 * (xs / max(width - 1, 1)) - 25.0 * (ys / max(height - 1, 1))
    return np.repeat(np.clip(ramp, 0, 255).astype(np.uint8)[:, :, None], 3, axis=2)


def sparse_detail(size: tuple[int, int] = CORPUS_SIZE) -> np.ndarray:
    """Nette, pauvre en texture, mais avec quelques arêtes franches.

    Le mur blanc avec un chambranle et une plinthe : c'est le cas réaliste, et
    le seul où une mesure honnête peut à la fois dire « il n'y a presque rien
    à voir » et « ce qu'il y a à voir est net ».
    """
    canvas = smooth_wall(size)
    width, height = size
    # Un chambranle, une plinthe, une arête de mur. Trois arêtes, franches.
    canvas[:, int(width * 0.31) : int(width * 0.315)] = _INK
    canvas[int(height * 0.86) : int(height * 0.87), :] = _INK + 20
    canvas[:, int(width * 0.74) : int(width * 0.743)] = _INK + 35
    return canvas


def architectural(size: tuple[int, int] = CORPUS_SIZE, seed: int = 5) -> np.ndarray:
    """Peu d'arêtes, très longues, irrégulièrement placées.

    C'est la base des essais de distorsion. Les positions sont irrégulières
    exprès : une grille régulière serait un motif répétitif, et les deux ne
    posent pas le même problème au détecteur (voir l'en-tête du module).

    Le fond porte une texture douce, sans arête, pour que le détecteur ait à
    choisir les bonnes colonnes plutôt qu'à se poser sur un aplat parfait.
    """
    width, height = size
    canvas = smooth_wall(size)
    rng = np.random.default_rng(seed)

    # Texture basse fréquence : elle ne crée aucune arête franche mais empêche
    # le fond d'être un aplat, ce qui serait irréaliste et trop facile.
    blotches = rng.normal(0.0, 9.0, (height // 32 + 1, width // 32 + 1)).astype(np.float32)
    smooth = np.asarray(
        cv2.resize(blotches, (width, height), interpolation=cv2.INTER_CUBIC), dtype=np.float32
    )
    canvas = np.clip(canvas.astype(np.float32) + smooth[:, :, None], 0, 255).astype(np.uint8)

    for fraction in (0.085, 0.235, 0.395, 0.615, 0.775, 0.925):
        x = int(width * fraction)
        canvas[:, x : x + 4] = _INK
    for fraction in (0.14, 0.47, 0.82):
        y = int(height * fraction)
        canvas[y : y + 4, :] = _INK + 25
    return cast(np.ndarray, canvas)


def line_field(
    size: tuple[int, int] = CORPUS_SIZE,
    columns: tuple[float, ...] = (0.1, 0.28, 0.72, 0.9),
    span: float = 1.0,
    gaps: int = 0,
) -> np.ndarray:
    """Champ de lignes verticales de longueur et de continuité choisies.

    `span` est la fraction de la hauteur couverte, `gaps` le nombre
    d'interruptions. Les trois cas que le lot doit couvrir se demandent ici :

    * lignes longues — `span=1.0, gaps=0` ;
    * lignes courtes — `span=0.15` : la flèche y est noyée dans le bruit,
      puisqu'elle croît comme le carré de la longueur ;
    * lignes interrompues — `gaps=3` : un chambranle coupé par un meuble.
      Un traqueur doit s'y arrêter, pas sauter le trou en inventant la suite.
    """
    width, height = size
    canvas = _blank(size, _WALL)
    drawn = int(height * min(max(span, 0.0), 1.0))
    top = (height - drawn) // 2

    blanked: list[tuple[int, int]] = []
    if gaps > 0 and drawn > 0:
        step = drawn // (gaps + 1)
        hole = max(4, step // 4)
        blanked = [(top + step * (i + 1) - hole // 2, hole) for i in range(gaps)]

    for fraction in columns:
        x = int(width * fraction)
        canvas[top : top + drawn, x : x + 4] = _INK
        for start, hole in blanked:
            canvas[start : start + hole, x : x + 4] = _WALL
    return canvas


def curved_objects(size: tuple[int, int] = CORPUS_SIZE) -> np.ndarray:
    """Des courbes que la scène contient **vraiment** : arches, cercles.

    Aucune distorsion n'est appliquée. Un détecteur qui mesure de la courbure
    sans vérifier sa cohérence radiale déclarera pourtant l'objectif fautif —
    c'est le faux positif le plus intéressant du corpus, parce qu'il ne se
    corrige pas en durcissant un seuil.
    """
    width, height = size
    canvas = _blank(size, _WALL)
    for cx_fraction, radius_fraction in ((0.2, 0.34), (0.52, 0.26), (0.84, 0.36)):
        center = (int(width * cx_fraction), int(height * 0.5))
        cv2.circle(canvas, center, int(height * radius_fraction), (_INK, _INK, _INK), 5)
    # Deux arches, pour que la courbure ne soit pas seulement circulaire.
    for cx_fraction in (0.35, 0.68):
        center = (int(width * cx_fraction), int(height * 0.92))
        cv2.ellipse(
            canvas, center, (int(width * 0.13), int(height * 0.5)), 0, 180, 360, (80, 80, 80), 5
        )
    return canvas
