"""Netteté : trois mesures candidates, et la question qui les précède.

## Le piège que ce module existe pour éviter

Une image **pauvre en détail n'est pas une image floue**. Un mur lisse net et
le même mur passé au flou gaussien contiennent tous deux très peu de haute
fréquence. Toute mesure qui résume l'image par l'énergie de ses dérivées les
confond, et cette confusion n'est pas un seuil à affiner : pour cette mesure,
les deux images sont réellement indiscernables.

La réponse n'est donc pas une mesure plus fine, c'est **une mesure de plus** :
avant de demander « est-ce net ? », il faut demander « y a-t-il de quoi
répondre ? ». D'où deux axes indépendants :

* le **support** (`strong_gradient_ratio`) — y a-t-il des transitions
  franches à mesurer, quelque part ;
* la **netteté** — ce qu'elles valent, quand il y en a.

Sans support, le verdict est `None`, et c'est un résultat, pas un échec.
C'est aussi la seule réponse vraie : personne ne peut dire d'un aplat parfait
s'il est net.

## Les trois candidates, et ce que la mesure a tranché

`laplacian_variance` — candidate A, celle du LOT 0. Variance de la dérivée
seconde : simple, rapide, et **non normalisée**. Son échelle dépend du contenu
autant que de la netteté. Mesurée sur le corpus synthétique, elle échoue sur
les trois cas nets mais pauvres en texture — mur lisse (1,3), détail rare
(22,3), scène architecturale (91,9) tombent tous sous son seuil de 120 alors
qu'aucun n'est flou. Conservée pour pouvoir rejouer le comportement du LOT 0,
pas comme solution.

`reblur_ratio` — candidate B, **retenue**. On refloute l'image et on regarde
quelle part de ses variations locales cela ne change plus : une image déjà
floue ne bouge presque pas. Le résultat est un rapport dans [0, 1], donc sans
échelle à calibrer. D'après Crete et al., *The blur effect: perception and
estimation with a new no-reference perceptual blur metric* (2007).

`edge_width` — candidate C. On cherche les transitions et on mesure leur
**largeur** en pixels : c'est la définition physique du flou, et elle ne
dépend ni du contraste des arêtes ni de leur nombre. Inspirée de Marziliano et
al., *A no-reference perceptual blur metric* (2002).

## Le choix, et pourquoi il a changé deux fois

Il s'est joué sur le corpus, pas sur l'intuition, et il a basculé à chaque
fois qu'un cas manquant y est entré. C'est désagréable à lire et c'est le
fonctionnement normal d'un banc d'essai : une comparaison n'est valable que
sur les cas qu'elle contient.

1. Sur un premier échantillon de quinze cas, B et C se valaient.
2. Le corpus complet a fait gagner C : les images **rééchantillonnées** par
   une distorsion sont réellement adoucies par l'interpolation, et B les
   plaçait à cheval sur sa borne alors que C les laissait toutes à 6,0 px.
3. L'ajout du **bougé aligné sur un axe** a fait gagner B, définitivement.
   La marge de C y devient *négative* : ces images tombent à 8,0 px, dans
   l'intervalle des images nettes, et aucune borne ne peut donc les séparer.

Bilan de bout en bout sur le corpus gradé, faux positifs compris :

| candidate            | FP | FN | remarque                                  |
| -------------------- | -- | -- | ----------------------------------------- |
| `laplacian_variance` | 18 |  2 | confond pauvreté de texture et flou       |
| `edge_width`         |  0 |  2 | rate le bougé aligné sur un axe           |
| `reblur_ratio`       |  0 |  0 | retenue                                   |

B et C ont longtemps été à égalité de nombre d'erreurs ; c'est leur **nature**
qui a tranché. La faiblesse de B est une instabilité sur un motif de traits
fins isolés sur fond uni — le rapport passe de 0,000 à 0,687 par le seul effet
du rééchantillonnage. Une pièce réelle ne ressemble pas à cela. La faiblesse
de C est de déclarer **nette**, avec assurance, une image franchement bougée
horizontalement — ce qu'une photo prise à main levée produit couramment. Entre
une faiblesse qui ne se rencontre que sur un motif de test et une faiblesse
qui se rencontre en vrai, le choix se fait tout seul.

Le premier jet de C prenait la médiane sur *toutes* les transitions
détectées : sur une image bruitée le bruit fournissait des dizaines de
milliers de fausses arêtes très fines, et la médiane déclarait nettes des
images franchement floues. Ne mesurer que les arêtes **fortes** corrige le
défaut. C'est noté ici parce que la version naïve paraît raisonnable.

## Deux bornes, pas un seuil

Chaque candidate a une borne « net » et une borne « flou », et entre les deux
la netteté est déclarée **indéterminée**. Un seuil unique posé au milieu d'une
marge de trois pixels trancherait des cas que la mesure ne sépare pas, avec
l'assurance d'un booléen. Sur ce corpus la bande capture exactement le cas
prévu pour elle : un flou gaussien de sigma 0,8, dont personne ne peut dire
s'il compte comme flou.

## Ce que la mesure ne dit pas

Les bornes sont établies sur le corpus **synthétique** : nets <= 0,3583,
flous >= 0,4778. Elles ne prouvent rien sur des photos réelles — pas de
vignettage, pas de compression agressive, pas de vraie pièce. Elles sont
**révisables et attendues comme révisées** dès qu'un corpus réel existera.

Elles sont posées **sur les bords des groupes mesurés**, pas au milieu de la
marge : tout ce qui tombe entre les deux est déclaré indéterminé plutôt que
tranché. Sur ce corpus, la bande capture les images rééchantillonnées par une
distorsion, qui sont réellement un peu adoucies sans être floues — exactement
ce pour quoi elle existe.

Voir `docs/quality-methodology.md`.
"""

from dataclasses import dataclass

import cv2
import numpy as np

from app.core.config import BlurMethod, get_settings

#: Magnitude de gradient, en unités de luma (0 → 1) après lissage 3×3,
#: au-delà de laquelle un pixel compte comme « transition franche ».
#:
#: Mesurée : un dégradé lisse de bout en bout d'image ne dépasse jamais 0,013 ;
#: une arête franche atteint 1,7 ; la même arête floutée à sigma 6 tient encore
#: 0,17. Le bruit de capteur, lui, est ramené sous 0,04 par le lissage
#: préalable. 0,08 laisse donc de la marge des deux côtés.
_STRONG_GRADIENT = 0.08

#: Une ligne sur N est examinée pour la largeur d'arête. Le flou est une
#: propriété locale continue : mesurer toutes les lignes coûte quatre fois plus
#: pour un résultat identique à la première décimale.
_EDGE_ROW_STEP = 4

#: Largeur au-delà de laquelle on cesse de suivre une transition. Sans borne,
#: un dégradé très doux serait lu comme une unique arête large de 800 px.
_EDGE_MAX_WIDTH = 60

#: Fraction du gradient maximal (percentile 99,9) au-dessus de laquelle une
#: transition est jugée « forte » pour la candidate C.
#:
#: Ce seuil est **relatif au contenu de l'image**, et c'est la faiblesse
#: connue de la candidate retenue : sur une scène dont l'arête la plus franche
#: est peu contrastée, il descend avec elle. Le plancher absolu
#: `_STRONG_GRADIENT` borne le risque, et le support est mesuré séparément —
#: mais la dépendance reste, et elle est à surveiller sur photos réelles.
_EDGE_STRONG_FRACTION = 0.25

#: Taille du noyau de reflou de la candidate B. 9 est la valeur d'origine.
_REBLUR_KERNEL = 9


@dataclass(frozen=True, slots=True)
class BlurReading:
    """Toutes les mesures de netteté d'une image, quelle que soit la candidate.

    Les trois sont calculées ensemble : elles partagent le prétraitement,
    aucune ne coûte cher, et un rapport de benchmark qui les porte toutes
    permet de rejouer un choix de méthode sans réanalyser le corpus.
    """

    #: Candidate A. Plus haut = plus de détail net (échelle 0 → 255).
    laplacian_variance: float
    #: Candidate B. 0 = net, 1 = flou. `None` si l'image n'a aucune variation.
    reblur_ratio: float | None
    #: Candidate C. Largeur médiane des transitions fortes, en pixels à la
    #: résolution de travail. `None` si aucune n'est mesurable.
    edge_width_px: float | None
    #: La même, ramenée à `blur_working_side`, pour lecture. La mesure brute
    #: reste publiée à côté.
    #:
    #: Elle ne suffit pas à rendre le verdict portable : la largeur d'arête a
    #: un plancher d'environ trois pixels, imposé par le noyau de dérivation.
    #: Sur une image plus petite que la taille de travail, multiplier ce
    #: plancher rend n'importe quelle image floue — une vignette nette de
    #: 320 px atteignait ainsi 12,8 px normalisés. D'où le domaine de validité
    #: appliqué dans `classify`.
    edge_width_normalized: float | None
    #: Nombre de transitions fortes mesurées, pour lire `edge_width_px`.
    edge_count: int
    #: **Support.** Part des pixels portant une transition franche. C'est lui
    #: qui décide si une conclusion est possible, avant toute netteté.
    strong_gradient_ratio: float
    working_side: int


def _working_gray(luma01: np.ndarray, target: int) -> np.ndarray:
    """Luma ramenée au côté long de travail. N'agrandit jamais.

    Agrandir fabriquerait du flou d'interpolation : une photo petite mais nette
    serait déclarée floue.
    """
    height, width = luma01.shape[:2]
    long_side = max(height, width)
    if long_side <= target:
        return luma01
    scale = target / long_side
    size = (max(1, round(width * scale)), max(1, round(height * scale)))
    return cv2.resize(luma01, size, interpolation=cv2.INTER_AREA)


def _gradient_magnitude(gray: np.ndarray) -> np.ndarray:
    """Norme du gradient, après un lissage léger.

    Le lissage n'est pas cosmétique : sans lui, un bruit de capteur d'écart-type
    6/255 produit une réponse de Sobel du même ordre qu'une arête franchement
    floutée. Le support et la netteté deviendraient alors des mesures du bruit.
    """
    smoothed = cv2.GaussianBlur(gray, (3, 3), 0)
    return np.hypot(
        cv2.Sobel(smoothed, cv2.CV_32F, 1, 0, ksize=3),
        cv2.Sobel(smoothed, cv2.CV_32F, 0, 1, ksize=3),
    )


def strong_gradient_ratio(gray: np.ndarray) -> float:
    """Part des pixels portant une transition franche. **Le support.**"""
    return float((_gradient_magnitude(gray) > _STRONG_GRADIENT).mean())


def laplacian_variance(gray: np.ndarray) -> float:
    """Candidate A — variance du Laplacien, sur une luma ramenée en 0 → 255.

    L'échelle 0 → 255 place la mesure dans les ordres de grandeur publiés
    (quelques dizaines à quelques milliers), donc comparables à la littérature
    et aux relevés du LOT 0.
    """
    scaled = (np.clip(gray, 0.0, 1.0) * 255.0).astype(np.uint8)
    return float(cv2.Laplacian(scaled, cv2.CV_64F).var())


def _denoise(gray: np.ndarray) -> np.ndarray:
    """Médian 3×3 avant la candidate B.

    Mesuré : sans ce filtre, une image floutée à sigma 4 puis bruitée à 6/255
    donne 0,475 — donc « nette », alors qu'elle est franchement floue. Le bruit
    fournit de la variation locale que le reflou détruit, et la mesure lit
    cette destruction comme du détail. Avec le filtre, la même image donne
    0,635. Un médian est préféré à un gaussien : il retire le bruit
    impulsionnel sans étaler les arêtes, donc sans fabriquer le flou qu'on
    cherche à mesurer.
    """
    # `rint` et non une troncature : `astype(np.uint8)` tronque, ce qui biaise
    # chaque valeur vers le bas d'un demi-niveau. Sur un aplat dont la luma
    # tombe juste sous un entier, la troncature n'arrondit pas tous les pixels
    # du même côté et fabrique un tramage de ±1/255 — donc des « arêtes » de
    # 4 px de large sur une image parfaitement uniforme.
    as_bytes = np.rint(np.clip(gray, 0.0, 1.0) * 255.0).astype(np.uint8)
    denoised: np.ndarray = np.asarray(cv2.medianBlur(as_bytes, 3), dtype=np.float32)
    return denoised / 255.0


def reblur_ratio(gray: np.ndarray) -> float | None:
    """Candidate B — part de la variation locale que le reflou ne change plus.

    0 : refloutter change tout, l'image était nette.
    1 : refloutter ne change rien, l'image était déjà floue.

    Renvoie `None` quand l'image n'a aucune variation à comparer : le rapport
    y serait 0/0, et le remplacer par une valeur par défaut ferait passer un
    aplat pour parfaitement net.
    """
    kernel = np.ones((1, _REBLUR_KERNEL), dtype=np.float32) / _REBLUR_KERNEL
    scores: list[float] = []

    for axis, blur_kernel in ((1, kernel), (0, kernel.T)):
        blurred = cv2.filter2D(gray, -1, blur_kernel)
        original = np.abs(np.diff(gray, axis=axis))
        reblurred = np.abs(np.diff(blurred, axis=axis))
        total = float(original.sum())
        if total <= 1e-6:
            continue
        # Ce que le reflou a *retiré* de variation. Ce qui reste après
        # soustraction est le détail que l'image tenait encore.
        remaining = float(np.maximum(original - reblurred, 0.0).sum())
        scores.append((total - remaining) / total)

    return max(scores) if scores else None


def _row_edge_widths(magnitude: np.ndarray, threshold: float) -> list[int]:
    """Largeurs des transitions fortes d'une ligne, en pixels.

    Une transition est un maximum local de gradient ; sa largeur est la
    distance entre les deux minima locaux qui l'encadrent. C'est directement
    ce que le flou étale.
    """
    if magnitude.size < 3:
        return []
    interior = magnitude[1:-1]
    peaks = np.flatnonzero(
        (interior > magnitude[:-2]) & (interior >= magnitude[2:]) & (interior >= threshold)
    )

    widths: list[int] = []
    last = magnitude.size - 1
    for peak in peaks + 1:
        left = int(peak)
        while left > 0 and magnitude[left - 1] < magnitude[left] and peak - left < _EDGE_MAX_WIDTH:
            left -= 1
        right = int(peak)
        while (
            right < last
            and magnitude[right + 1] < magnitude[right]
            and right - peak < _EDGE_MAX_WIDTH
        ):
            right += 1
        if right - left + 1 < _EDGE_MAX_WIDTH:
            widths.append(right - left + 1)
    return widths


def _widths_along(magnitude: np.ndarray) -> list[int]:
    """Largeurs de toutes les transitions les plus franches, ligne par ligne.

    Le seuil est **purement relatif** au gradient le plus fort de cette
    direction, sans plancher absolu. Un plancher absolu paraît prudent et
    produit ici l'inverse de ce qu'on veut : quand une direction est
    franchement floue, ses transitions descendent sous le plancher, la liste
    revient vide, et le maximum entre directions retombe silencieusement sur la
    direction restée nette. Un bougé horizontal de 21 px était ainsi déclaré
    net. Une direction sans transition mesurable est une **preuve de flou**,
    pas une absence de preuve.

    Le plancher absolu reste à sa place : dans `strong_gradient_ratio`, qui
    décide s'il y a du support **avant** qu'on lise une largeur.
    """
    threshold = float(np.percentile(magnitude, 99.9)) * _EDGE_STRONG_FRACTION
    if threshold <= 1e-6:
        # Aucun gradient nulle part : un seuil relatif valant zéro ferait de
        # chaque pixel un maximum local, et un aplat parfait recevrait une
        # largeur d'arête. Il n'a pas d'arête, il n'a rien.
        return []
    widths: list[int] = []
    for index in range(0, magnitude.shape[0], _EDGE_ROW_STEP):
        widths.extend(_row_edge_widths(magnitude[index], threshold))
    return widths


def edge_width(gray: np.ndarray) -> tuple[float | None, int]:
    """Candidate C — largeur médiane des transitions **fortes**, et leur nombre.

    Mesurée dans les **deux directions**, et c'est la plus floue qui compte.

    Un flou de bougé est anisotrope : il étale le long du mouvement et laisse
    l'axe perpendiculaire presque intact. Ne dériver que selon x mesurait donc
    une direction au hasard — un bougé à 30° ressortait net à une résolution et
    flou à une autre, selon la direction où tombaient les arêtes les plus
    contrastées. Retenir le maximum répond à la vraie question : « reste-t-il
    une direction dans laquelle on ne lit plus le détail ? »

    :returns: largeur médiane en pixels et nombre de transitions retenues.
        `None` quand l'image n'en contient aucune : c'est le cas du mur lisse,
        et le seul verdict honnête y est « je ne sais pas ».

    La médiane, pas la moyenne : quelques transitions très larges — un dégradé
    doux qui traîne — tireraient une moyenne vers le flou alors que l'essentiel
    des arêtes est franc.

    Le médian préalable n'est pas décoratif. Le bruit fabrique des transitions
    d'un ou deux pixels de large, donc très « nettes », et en nombre elles
    tirent la médiane vers le bas : une image floue et bruitée passait pour
    nette. Mesuré à 1600 px, un flou de sigma 3 bruité à 12/255 remonte de
    11 px à 13 px avec le filtre. Un médian plutôt qu'un gaussien : il retire
    le bruit sans étaler les arêtes, donc sans fabriquer le flou qu'on mesure.
    """
    smoothed = cv2.GaussianBlur(_denoise(gray), (3, 3), 0)

    # Selon x sur l'image, puis selon x sur la transposée : deux fois le même
    # code, deux directions. Transposer est exact et n'introduit aucune
    # courbure ni aucun flou.
    horizontal = _widths_along(np.abs(cv2.Sobel(smoothed, cv2.CV_32F, 1, 0, ksize=3)))
    vertical = _widths_along(
        np.abs(cv2.Sobel(np.ascontiguousarray(smoothed.T), cv2.CV_32F, 1, 0, ksize=3))
    )

    medians = [float(np.median(w)) for w in (horizontal, vertical) if w]
    if not medians:
        return None, 0
    return max(medians), len(horizontal) + len(vertical)


def measure(luma01: np.ndarray) -> BlurReading:
    """Calcule le support et les trois candidates sur la même image de travail."""
    target = get_settings().blur_working_side
    gray = _working_gray(luma01, target)
    working_side = int(max(gray.shape[:2]))
    ratio = reblur_ratio(_denoise(gray))
    width, count = edge_width(gray)
    return BlurReading(
        laplacian_variance=round(laplacian_variance(gray), 3),
        reblur_ratio=None if ratio is None else round(ratio, 5),
        edge_width_px=None if width is None else round(width, 3),
        edge_width_normalized=(
            None if width is None else round(width * target / max(working_side, 1), 3)
        ),
        edge_count=count,
        strong_gradient_ratio=round(strong_gradient_ratio(gray), 6),
        working_side=int(max(gray.shape[:2])),
    )


def _band_verdict(value: float, sharp_max: float, blurry_min: float) -> bool | None:
    """Applique deux bornes plutôt qu'un seuil.

    Entre les deux, on ne conclut pas. Un seuil unique posé au milieu d'une
    marge étroite tranche des cas que la mesure ne sépare pas, et le fait avec
    l'assurance d'un booléen — c'est la pire façon de se tromper. La bande dit
    « la mesure est là où les deux groupes se touchent », ce qui est vrai.
    """
    if value <= sharp_max:
        return True
    if value >= blurry_min:
        return False
    return None


def classify(reading: BlurReading) -> tuple[bool | None, bool]:
    """Traduit une lecture en verdict, selon la méthode configurée.

    :returns: `(sharp, low_texture)`. `sharp` vaut `None` dans **deux** cas
        bien distincts, et aucun des deux ne veut dire « floue » :

        * le support est insuffisant — un aplat parfait n'a pas de netteté ;
        * la mesure tombe dans la bande où les deux groupes se touchent.

    Séparé de la mesure exprès : changer de méthode ou de bornes ne touche pas
    au code qui mesure, et un benchmark peut rejouer d'autres réglages sur des
    mesures déjà enregistrées.
    """
    settings = get_settings()
    low_texture = reading.strong_gradient_ratio < settings.blur_min_strong_gradient_ratio

    # Domaine de validité. Les bornes sont mesurées sur des images ramenées à
    # `blur_working_side` ; en dessous, l'image n'est pas réduite et la mesure
    # n'est plus sur la même échelle. On ne l'extrapole pas.
    #
    # C'est une lacune fonctionnelle assumée, pas une élégance : les photos
    # entre `min_long_side` (640 px) et la taille de travail (1024 px) ne
    # reçoivent donc **aucun** verdict de netteté. La refermer demande soit un
    # étalonnage par résolution, soit de relever la taille minimale acceptée —
    # les deux appellent un corpus réel, donc un lot ultérieur.
    if reading.working_side < settings.blur_working_side:
        return None, low_texture

    if settings.blur_method is BlurMethod.LAPLACIAN_VARIANCE:
        # Candidate A ne sait dire ni « je ne sais pas » ni « c'est à la
        # limite » : un seuil, un booléen. C'est précisément ce qu'on lui
        # reproche, et le reproduire ici est ce qui rend la comparaison
        # honnête plutôt que flatteuse pour la méthode retenue.
        return reading.laplacian_variance >= settings.blur_sharp_min, low_texture

    if low_texture:
        return None, True

    if settings.blur_method is BlurMethod.REBLUR_RATIO:
        if reading.reblur_ratio is None:
            return None, True
        return (
            _band_verdict(
                reading.reblur_ratio,
                settings.blur_reblur_sharp_max,
                settings.blur_reblur_blurry_min,
            ),
            low_texture,
        )

    if reading.edge_width_normalized is None:
        return None, True
    return (
        _band_verdict(
            reading.edge_width_normalized,
            settings.blur_edge_width_sharp_max,
            settings.blur_edge_width_blurry_min,
        ),
        low_texture,
    )
