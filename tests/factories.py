"""Fixtures d'images, générées plutôt que téléchargées.

Aucun binaire n'est versionné pour faire passer les tests. Ces images sont
fabriquées, donc reproductibles, minuscules, et surtout **connues** : quand un
test affirme qu'une image est floue, elle l'est par construction, pas parce
que quelqu'un l'a trouvée floue un jour.

Le corpus de photos réelles est une autre affaire, et il a son propre dossier
et ses propres règles : voir `datasets/README.md`.
"""

from io import BytesIO

import numpy as np
from PIL import Image

#: Taille par défaut, au-dessus de `PPAI_MIN_LONG_SIDE` pour que les fixtures
#: ne déclenchent pas `image_too_small` sans le vouloir.
DEFAULT_SIZE = (960, 720)


def encode(array: np.ndarray, image_format: str = "JPEG", **save: object) -> bytes:
    """Encode un tableau H × W × 3 uint8 dans le format demandé."""
    buffer = BytesIO()
    Image.fromarray(array, mode="RGB").save(buffer, format=image_format, **save)
    return buffer.getvalue()


def flat(value: int, size: tuple[int, int] = DEFAULT_SIZE) -> np.ndarray:
    """Image uniforme. Nette au sens du Laplacien (aucune transition) mais plate."""
    width, height = size
    return np.full((height, width, 3), value, dtype=np.uint8)


def noise(size: tuple[int, int] = DEFAULT_SIZE, seed: int = 7) -> np.ndarray:
    """Bruit blanc : le cas extrême de variance du Laplacien élevée."""
    width, height = size
    rng = np.random.default_rng(seed)
    return rng.integers(0, 256, (height, width, 3), dtype=np.uint8)


def checkerboard(
    size: tuple[int, int] = DEFAULT_SIZE,
    square: int = 24,
    blur: int = 0,
    low: int = 0,
    high: int = 255,
) -> np.ndarray:
    """Damier, éventuellement flouté, aux deux tons choisis.

    `blur` en pixels donne une image franchement floue à contenu identique :
    c'est la paire qu'il faut pour tester une mesure de netteté, puisque seule
    la netteté change entre les deux.

    `low` et `high` comptent plus qu'il n'y paraît. Le damier noir et blanc
    par défaut est **la moitié noire et la moitié brûlée** : il déclenche à
    juste titre `image_too_dark` et `image_overexposed`. Pour éprouver le cas
    « rien à signaler », il faut des tons intermédiaires — voir
    `mid_tone_checkerboard()`.
    """
    from PIL import ImageFilter

    width, height = size
    ys, xs = np.mgrid[0:height, 0:width]
    cells = (xs // square + ys // square) % 2
    pattern = np.where(cells == 1, high, low).astype(np.uint8)
    array = np.repeat(pattern[:, :, None], 3, axis=2)
    if blur <= 0:
        return array
    blurred = Image.fromarray(array, mode="RGB").filter(ImageFilter.GaussianBlur(blur))
    return np.asarray(blurred, dtype=np.uint8)


def mid_tone_checkerboard(size: tuple[int, int] = DEFAULT_SIZE) -> np.ndarray:
    """Damier net, bien exposé, franchement contrasté : le cas sans reproche.

    C'est la fixture de référence pour vérifier qu'une photo correcte ne
    déclenche **aucun** avertissement — un test qu'un damier noir et blanc ne
    peut pas rendre, puisqu'il est à moitié brûlé.
    """
    return checkerboard(size=size, low=70, high=190)


#: Tons des fixtures d'objectif. Mi-tons volontairement : un fond à 235
#: déclencherait `image_overexposed` et brouillerait une fixture qui ne doit
#: éprouver qu'une chose — la courbure des arêtes.
_BAR_BACKGROUND = 190
_BAR_INK = 55


def straight_bars(
    size: tuple[int, int] = DEFAULT_SIZE, columns: tuple[float, ...] = (0.1, 0.25, 0.75, 0.9)
) -> np.ndarray:
    """Barres verticales parfaitement droites, sur fond clair.

    Vérité terrain de l'analyse d'objectif : des droites droites doivent
    donner une flèche quasi nulle. Les colonnes sont placées loin du centre,
    là où la mesure a un sens.
    """
    width, height = size
    array = np.full((height, width, 3), _BAR_BACKGROUND, dtype=np.uint8)
    for fraction in columns:
        x = int(width * fraction)
        array[:, max(0, x - 3) : x + 3] = _BAR_INK
    return array


def bowed_bars(
    size: tuple[int, int] = DEFAULT_SIZE,
    columns: tuple[float, ...] = (0.1, 0.25, 0.75, 0.9),
    amplitude: float = 14.0,
) -> np.ndarray:
    """Les mêmes barres, courbées en arc — signature d'une distorsion.

    Le décalage suit une parabole en fonction de la ligne, et croît avec
    l'éloignement du centre de l'image : c'est le comportement d'une
    distorsion radiale, pas un simple cisaillement.
    """
    width, height = size
    array = np.full((height, width, 3), _BAR_BACKGROUND, dtype=np.uint8)
    center_x = (width - 1) / 2.0
    for fraction in columns:
        x0 = width * fraction
        radial = abs(x0 - center_x) / center_x
        for y in range(height):
            t = (y - (height - 1) / 2.0) / ((height - 1) / 2.0)
            x = int(round(x0 + amplitude * radial * (t * t - 1.0 / 3.0)))
            array[y, max(0, x - 3) : x + 3] = _BAR_INK
    return array


def portrait_with_exif_rotation() -> bytes:
    """JPEG **paysage** portant une orientation EXIF 6 (rotation de 90°).

    L'orientation 6 veut dire « l'appareil était tourné » : un lecteur qui la
    respecte doit afficher l'image en portrait. C'est le cas qui casse tout en
    silence — sans redressement, on cherche l'horizon dans une pièce couchée.
    """
    array = checkerboard(size=(960, 720), square=30)
    image = Image.fromarray(array, mode="RGB")
    exif = image.getexif()
    exif[0x0112] = 6
    buffer = BytesIO()
    image.save(buffer, format="JPEG", exif=exif, quality=92)
    return buffer.getvalue()
