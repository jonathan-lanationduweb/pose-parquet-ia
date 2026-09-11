"""Base de comparaison géométrique — sans apprentissage.

**EXPLORATOIRE.** Elle ne sert pas à être belle. Elle sert à répondre à une
seule question, et c'est la question la moins agréable à poser à un modèle :

    un modèle appris apporte-t-il RÉELLEMENT quelque chose ?

Sans elle, tout résultat semble bon : on n'a rien à quoi le comparer. Avec
elle, un modèle qui ne fait pas mieux qu'une heuristique de quinze lignes est
démasqué immédiatement.

## L'heuristique, en une phrase

Le sol d'une photo d'intérieur est **en bas**, il est **grossièrement
homogène**, et il est séparé du mur par une **rupture horizontale**. On
cherche donc, colonne par colonne, la transition la plus franche dans la
moitié basse de l'image, et on garde ce qui est en dessous.

C'est tout. Aucune perspective, aucun objet, aucun tapis, aucun pied de
chaise. On sait d'avance qu'elle échouera sur une pièce meublée : c'est
justement ce qu'on veut pouvoir montrer.

**Pas d'acharnement.** Empiler cinquante heuristiques pour la rendre
compétitive coûterait des jours et fausserait la comparaison — on aurait alors
mis notre intelligence dans la base, pas dans le modèle.
"""

from __future__ import annotations

import time

import cv2
import numpy as np

from app.services.floor_segmentation import (
    FloorSegmentationResult,
    clean_mask,
    mask_boundary,
)


class GeometricFloorBaseline:
    """Sol = ce qui est sous la rupture horizontale la plus franche."""

    name = "opencv-baseline"

    def __init__(self, *, blur: int = 9, search_from: float = 0.35) -> None:
        #: Le flou noie le veinage du parquet, qui sinon crée autant d'arêtes
        #: que la jonction avec le mur.
        self.blur = blur
        #: On ne cherche pas la jonction dans le tiers haut : un tableau ou une
        #: fenêtre y produisent des ruptures plus franches que le sol.
        self.search_from = search_from

    def segment(self, image_rgb: np.ndarray) -> FloorSegmentationResult:
        t0 = time.perf_counter()
        hauteur, largeur = image_rgb.shape[:2]
        gris = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY)
        gris = cv2.GaussianBlur(gris, (self.blur, self.blur), 0)

        # Gradient vertical : une jonction sol/mur est une ligne horizontale,
        # donc une variation forte quand on descend.
        grad = np.abs(cv2.Sobel(gris, cv2.CV_32F, 0, 1, ksize=5))
        depart = int(hauteur * self.search_from)

        # Par colonne, la ligne de rupture la plus forte sous `depart`.
        limites = np.full(largeur, hauteur, dtype=np.int32)
        for x in range(largeur):
            colonne = grad[depart:, x]
            if colonne.size:
                limites[x] = depart + int(np.argmax(colonne))

        # Une jonction est continue : on lisse les limites pour qu'un meuble
        # sombre ne creuse pas un puits d'une colonne de large.
        noyau = max(9, (largeur // 40) | 1)
        lisses = cv2.medianBlur(limites.astype(np.float32).reshape(1, -1), 1).ravel()
        limites = np.convolve(lisses, np.ones(noyau) / noyau, mode="same").astype(np.int32)

        masque = np.zeros((hauteur, largeur), dtype=bool)
        for x in range(largeur):
            masque[limites[x] :, x] = True

        infer_ms = (time.perf_counter() - t0) * 1000
        t1 = time.perf_counter()
        masque = clean_mask(masque)
        bord = mask_boundary(masque)
        post_ms = (time.perf_counter() - t1) * 1000

        return FloorSegmentationResult(
            candidate=self.name,
            mask=masque,
            probability=None,
            boundary=bord,
            timings={
                "model_load": 0.0,
                "inference": round(infer_ms, 1),
                "post": round(post_ms, 1),
                "total": round(infer_ms + post_ms, 1),
            },
            metadata={
                "kind": "geometric",
                "learned": False,
                "inference_resolution": f"{largeur}x{hauteur}",
                "note": (
                    "aucune perspective, aucun objet, aucun tapis : base de "
                    "comparaison, pas candidat produit"
                ),
            },
        )
