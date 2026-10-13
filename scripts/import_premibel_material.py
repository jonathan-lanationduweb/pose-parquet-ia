"""Construit des matières EXACTES à partir des photos produit Premibel.

    python -m scripts.import_premibel_material            # tous les produits
    python -m scripts.import_premibel_material CHENF228   # un seul

Entrée : ``web/data/materials/premibel-sources.json`` — pour chaque produit,
la photo et des zones de sol annotées (quadrilatères le long des lames).

Pour chaque zone :

1. **redressement** par homographie. Le rapport longueur / largeur réel de la
   zone se déduit de la caméra : la focale est résolue par l'orthogonalité des
   deux directions du rectangle quand la perspective le permet, sinon supposée
   (champ horizontal de 60°, une photo de téléphone ou d'appareil courant) —
   et l'hypothèse est écrite dans les métadonnées ;
2. **joints** : les joints longs sont cherchés dans le profil de luminance de
   l'image redressée (minima près des positions attendues), les joints de
   bout dans le profil transversal. Une lame n'est jamais coupée à cheval
   sur un joint : on ne garde que l'intérieur des lames, marges retirées ;
3. **lumière** : la photo porte l'éclairage de sa pièce. Le gradient basse
   fréquence est retiré (division par un flou large), la couleur moyenne de
   la zone est conservée — c'est elle, la teinte du produit ;
4. **atlas** : chaque morceau de lame devient une rangée d'un atlas, à
   0,6 px/mm (plus du double de la tuile du moteur, 0,27 px/mm).

Validation : une matière n'est déclarée ``exact`` que si la photo est assez
fine (≥ 0,3 px/mm dans le bois), si au moins quatre morceaux de lames
distincts en sortent, et s'ils totalisent au moins 1,5 m de bois et une longueur de lame. Sinon le
produit garde sa matière représentative, et la raison est écrite.

Sorties :

* ``web/data/materials/premibel/<id>.json`` — la définition de matière
  (versionnée : métadonnées et couleurs moyennes, aucun pixel) ;
* ``web/data/materials/premibel/index.json`` — le statut de chaque produit ;
* ``web/assets/products/premibel/materials/<id>.atlas.webp`` — l'atlas,
  **non versionné**, comme les photos dont il dérive ;
* ``review/premibel-materials/extraction/<id>.jpg`` — la planche de contrôle.

Rien n'est téléchargé : seules les images déjà présentes localement servent.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np

RACINE = Path(__file__).resolve().parents[1]
SOURCES = RACINE / "web/data/materials/premibel-sources.json"
FAMILLES = RACINE / "web/data/parquets.json"
SORTIE_DEF = RACINE / "web/data/materials/premibel"
SORTIE_ATLAS = RACINE / "web/assets/products/premibel/materials"
SORTIE_REVUE = RACINE / "review/premibel-materials/extraction"

#: Résolution de l'atlas. La tuile du moteur vaut 1280 px pour 4,80 m, soit
#: 0,267 px/mm : 0,6 laisse plus du double, pour les rotations et le zoom.
PPM_ATLAS = 0.6
#: En dessous, la photo est moins fine que la tuile : la matière serait floue.
PPM_SOURCE_MIN = 0.3
MORCEAUX_MIN = 4
#: Assez de bois réel pour que la répétition ne se voie pas : au moins 1,5 m
#: au total, et au moins une longueur de lame (mesuré le 13/10/2026 : avec
#: 0,96 m de bois pour des lames de 1,21 m, le même nœud revenait partout).
BOIS_MIN_M = 1.5
#: Une « lame entière » annotée doit retrouver, redressée, l'aspect réel de
#: la lame à ±45 % près ; sinon l'annotation (ou la perspective) est fausse.
TOLERANCE_ASPECT = 0.45
#: Marge retirée de chaque côté d'une lame : le chanfrein et le joint ne
#: doivent pas entrer dans la matière (le moteur dessine les siens).
MARGE = 0.08
#: Champ horizontal supposé quand la focale ne se déduit pas de la zone.
CHAMP_SUPPOSE_DEG = 60.0


@dataclass
class Morceau:
    """Un morceau de lame redressé, prêt pour l'atlas."""

    image: np.ndarray  # BGR, longueur le long de x
    ppm_source: float
    longueur_mm: float
    zone: int


@dataclass
class Rapport:
    """Ce que l'extraction a mesuré, pour la validation et la revue."""

    id: str
    morceaux: list[Morceau] = field(default_factory=list)
    focales: list[str] = field(default_factory=list)
    joints: list[list[float]] = field(default_factory=list)
    raisons: list[str] = field(default_factory=list)
    redresses: list[np.ndarray] = field(default_factory=list)
    quads: list[np.ndarray] = field(default_factory=list)
    ecartes: int = 0
    longueur_lame_m: float = 0.0


def homographie_carre(quad: np.ndarray) -> np.ndarray:
    """Homographie du carré unité (u le long, v en travers) vers le quadrilatère."""
    carre = np.array([[0, 0], [0, 1], [1, 1], [1, 0]], dtype=np.float64)
    return cv2.getPerspectiveTransform(carre.astype(np.float32), quad.astype(np.float32)).astype(
        np.float64
    )


def rapport_aspect(quad_px: np.ndarray, largeur: int, hauteur: int) -> tuple[float, str]:
    """Longueur / largeur réelles de la zone, et l'origine de la focale.

    Avec K = [f 0 cx; 0 f cy; 0 0 1], les colonnes h1, h2 de l'homographie sont
    proportionnelles à K·r1 et K·r2 (r1 ⟂ r2, |r1| = |r2|). L'orthogonalité
    donne f² ; le rapport des normes de K⁻¹h1 et K⁻¹h2 donne l'aspect.
    """
    h = homographie_carre(quad_px)
    cx, cy = largeur / 2.0, hauteur / 2.0
    h1, h2 = h[:, 0], h[:, 1]
    a = np.array([h1[0] - cx * h1[2], h1[1] - cy * h1[2], h1[2]])
    b = np.array([h2[0] - cx * h2[2], h2[1] - cy * h2[2], h2[2]])
    origine = "supposee"
    f = largeur / (2.0 * math.tan(math.radians(CHAMP_SUPPOSE_DEG) / 2.0))
    if abs(a[2] * b[2]) > 1e-12:
        f2 = -(a[0] * b[0] + a[1] * b[1]) / (a[2] * b[2])
        if f2 > 0 and 0.4 * largeur < math.sqrt(f2) < 3.0 * largeur:
            f = math.sqrt(f2)
            origine = "resolue"
    k_inv = np.diag([1.0 / f, 1.0 / f, 1.0])
    r1 = k_inv @ a
    r2 = k_inv @ b
    return float(np.linalg.norm(r1) / np.linalg.norm(r2)), f"{origine}:{f:.0f}px"


def affiner_fuite(img: np.ndarray, quad_px: np.ndarray) -> tuple[np.ndarray, str]:
    """Fait passer les côtés « longueur » de la zone par la fuite des lames.

    Une annotation à l'œil se trompe de quelques degrés ; redressée, la lame
    devient oblique et ses joints traversent les morceaux. On mesure donc la
    fuite dans la photo : segments détectés dans la zone, orientés à moins de
    20° des côtés annotés, intersectés aux moindres carrés. Le bord proche
    (début) est gardé ; les deux points du bord lointain glissent sur les
    droites qui rejoignent la fuite. Sans assez de segments, la zone reste
    telle qu'annotée, et c'est écrit.
    """
    gris = np.asarray(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
    masque = np.zeros(gris.shape, np.uint8)
    cv2.fillConvexPoly(masque, quad_px.astype(np.int32), 255)
    lsd = cv2.createLineSegmentDetector()
    segs = lsd.detect(gris)[0]
    if segs is None:
        return quad_px, "annotee"
    d_gauche = quad_px[3] - quad_px[0]
    d_droite = quad_px[2] - quad_px[1]
    axe = d_gauche / np.linalg.norm(d_gauche) + d_droite / np.linalg.norm(d_droite)
    axe /= np.linalg.norm(axe)
    lignes = []
    for x1, y1, x2, y2 in segs.reshape(-1, 4):
        mx, my = int((x1 + x2) / 2), int((y1 + y2) / 2)
        if not (0 <= my < masque.shape[0] and 0 <= mx < masque.shape[1]) or not masque[my, mx]:
            continue
        v = np.array([x2 - x1, y2 - y1])
        n = np.linalg.norm(v)
        if n < 12:
            continue
        if abs(float(v @ axe) / n) < math.cos(math.radians(20)):
            continue
        # droite a·x + b·y = c, pondérée par la longueur
        a, b = -v[1] / n, v[0] / n
        lignes.append((a, b, a * x1 + b * y1, n))
    if len(lignes) < 6:
        return quad_px, "annotee"
    A = np.array([[a, b] for a, b, _, _ in lignes]) * np.array([w for *_, w in lignes])[:, None]
    c = np.array([c for _, _, c, _ in lignes]) * np.array([w for *_, w in lignes])
    fuite, *_ = np.linalg.lstsq(A, c, rcond=None)
    # Fuite derrière la caméra ou absurde : on garde l'annotation.
    if not np.all(np.isfinite(fuite)) or float((fuite - quad_px[0]) @ axe) <= 0:
        return quad_px, "annotee"
    # Lames presque parallèles dans la photo (gros plan vu de dessus) : la
    # fuite part à l'infini et ne dit plus rien de fiable.
    if np.linalg.norm(fuite - np.array(gris.shape[::-1]) / 2) > 8 * max(gris.shape):
        return quad_px, "annotee (lames paralleles)"
    q = quad_px.copy()
    for i_proche, i_loin in ((0, 3), (1, 2)):
        d = fuite - q[i_proche]
        t = float((quad_px[i_loin] - q[i_proche]) @ d) / float(d @ d)
        q[i_loin] = q[i_proche] + max(0.05, min(0.95, t)) * d
    # Garde-fou : une correction qui change l'aire de la zone de plus de 35 %
    # n'est pas une correction, c'est une autre zone. On garde l'annotation.
    def aire(z: np.ndarray) -> float:
        return abs(float(cv2.contourArea(z.astype(np.float32))))
    if not 0.65 < aire(q) / max(1e-6, aire(quad_px)) < 1.35:
        return quad_px, "annotee (fuite mesuree incoherente)"
    return q, f"mesuree:{len(lignes)} segments"


def redresser(img: np.ndarray, quad_px: np.ndarray, aspect: float) -> np.ndarray:
    """La zone, vue de dessus : longueur le long de x, largeur le long de y."""
    travers = max(np.linalg.norm(quad_px[0] - quad_px[1]), np.linalg.norm(quad_px[3] - quad_px[2]))
    largeur_px = max(8, int(round(travers)))
    longueur_px = max(8, int(round(largeur_px * aspect)))
    dest = np.array(
        [[0, 0], [0, largeur_px], [longueur_px, largeur_px], [longueur_px, 0]], dtype=np.float32
    )
    m = cv2.getPerspectiveTransform(quad_px.astype(np.float32), dest)
    return cv2.warpPerspective(
        img, m, (longueur_px, largeur_px), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT
    )


def profil_sombre(gris: np.ndarray, axe: int) -> np.ndarray:
    """Obscurité moyenne le long d'un axe, détendue : les joints en ressortent."""
    p = gris.mean(axis=axe).astype(np.float64)
    fond = cv2.GaussianBlur(
        p.reshape(-1, 1), (1, 0), sigmaX=0, sigmaY=max(3.0, len(p) / 12)
    ).ravel()
    return fond - p  # positif là où c'est plus sombre que l'entour


def joints_longs(gris: np.ndarray, n: int) -> list[int]:
    """Positions (en y) des n-1 joints longs, cherchés près de k/n."""
    h = gris.shape[0]
    p = profil_sombre(gris, 1)
    joints = []
    for k in range(1, n):
        attendu = h * k / n
        lo, hi = int(max(1, attendu - h / (2.5 * n))), int(min(h - 1, attendu + h / (2.5 * n)))
        joints.append(lo + int(np.argmax(p[lo:hi])))
    return joints


def periode_lames(gris: np.ndarray) -> int | None:
    """Largeur de lame (px) estimée par l'autocorrélation du profil transversal."""
    p = profil_sombre(gris, 1)
    p = p - p.mean()
    if not np.any(p):
        return None
    ac = np.correlate(p, p, mode="full")[len(p) - 1 :]
    ac /= ac[0]
    debut = max(6, len(p) // 12)
    if debut >= len(ac) - 2:
        return None
    pic = debut + int(np.argmax(ac[debut : len(p) // 2]))
    return pic if ac[pic] > 0.15 else None


def joints_de_bout(gris_lame: np.ndarray) -> list[int]:
    """Joints de bout (en x) : une ligne sombre nette sur toute la largeur, ou
    un saut de teinte franc — deux lames voisines n'ont pas la même couleur,
    et le joint lui-même peut être invisible à cette résolution."""
    p = profil_sombre(gris_lame, 0)
    seuil = max(6.0, 4.0 * np.median(np.abs(p)))
    candidats = [i for i in range(2, len(p) - 2) if p[i] > seuil and p[i] == p[i - 2 : i + 3].max()]
    col = gris_lame.mean(axis=0).astype(np.float64)
    fen = max(4, gris_lame.shape[0] // 2)
    if len(col) > 2 * fen + 4:
        saut = np.array(
            [
                abs(col[i - fen : i].mean() - col[i : i + fen].mean())
                for i in range(fen, len(col) - fen)
            ]
        )
        seuil_saut = max(14.0, 4.0 * float(np.median(saut)))
        for j in range(1, len(saut) - 1):
            if saut[j] > seuil_saut and saut[j] == saut[max(0, j - fen) : j + fen].max():
                candidats.append(j + fen)
    candidats.sort()
    retenus: list[int] = []
    for c in candidats:
        if not retenus or c - retenus[-1] > gris_lame.shape[0]:
            retenus.append(c)
    return retenus


def joint_interieur(gris_lame: np.ndarray) -> bool:
    """Vrai si un joint long traverse l'intérieur du morceau.

    Un joint mal placé ferait dessiner au moteur un second joint au milieu de
    la lame. Plutôt que de couper le morceau en deux demi-lames (dont on ne
    connaîtrait plus la largeur réelle), on l'écarte.

    Une fissure ou une veine sombre n'est pas un joint : elle ne court pas sur
    toute la longueur. On exige donc une ligne sombre à la MÊME hauteur dans
    au moins quatre tronçons sur cinq.
    """
    h, w = gris_lame.shape
    if h < 10 or w < 40:
        return False
    lo, hi = int(h * 0.2), int(h * 0.8)
    positions = []
    for k in range(5):
        tranche = gris_lame[:, k * w // 5 : (k + 1) * w // 5]
        p = profil_sombre(tranche, 1)
        seuil = max(5.0, 3.5 * float(np.median(np.abs(p))))
        j = lo + int(np.argmax(p[lo:hi]))
        positions.append(j if p[j] > seuil else None)
    vus = [x for x in positions if x is not None]
    if len(vus) < 4:
        return False
    med = float(np.median(vus))
    return sum(1 for x in vus if abs(x - med) <= max(2.0, h * 0.04)) >= 4


def egaliser(morceau: np.ndarray) -> np.ndarray:
    """Retire le gradient de lumière de la pièce, garde la teinte moyenne.

    Sur une bande de lame, l'éclairage de la photo varie surtout le long de
    la lame (vers la fenêtre, vers le fond). On ajuste un polynôme de degré 2
    au profil de luminosité le long de la bande et on le divise : pas de
    biais aux extrémités, là où un flou large se trompe (mesuré : 14 % d'écart
    résiduel entre les deux bouts d'un dégradé synthétique, contre < 2 % ici).
    """
    f = morceau.astype(np.float32)
    lum = cv2.cvtColor(morceau, cv2.COLOR_BGR2GRAY).astype(np.float64) + 1.0
    profil = lum.mean(axis=0)
    x = np.linspace(-1.0, 1.0, profil.size)
    tendance = np.polyval(np.polyfit(x, profil, 2), x) if profil.size >= 8 else profil
    gain = (float(np.median(lum)) / np.maximum(tendance, 1.0)).astype(np.float32)[None, :, None]
    return np.clip(f * gain, 0, 255).astype(np.uint8)


def extraire(produit: dict[str, Any]) -> Rapport:
    """Toutes les zones d'un produit, découpées en morceaux de lames."""
    r = Rapport(produit["id"])
    chemin = RACINE / produit["source"]
    if not chemin.is_file():
        r.raisons.append(f"photo absente : {produit['source']}")
        return r
    img = cv2.imread(str(chemin), cv2.IMREAD_COLOR)
    if img is None:
        r.raisons.append("photo illisible")
        return r
    hauteur, largeur = img.shape[:2]
    largeur_mm = float(produit["widthMm"])
    r.longueur_lame_m = float(produit["lengthMm"]) / 1000
    for iz, zone in enumerate(produit["regions"]):
        quad = np.array(zone["quad"], dtype=np.float64) * [largeur, hauteur]
        # Gros plan vu de dessus : le veinage passerait pour des droites de
        # fuite. La mesure de fuite ne vaut que pour un sol en perspective.
        if zone.get("fuiteAuto", produit["sourceKind"] == "ambiance"):
            quad, origine_fuite = affiner_fuite(img, quad)
        else:
            origine_fuite = "annotee"
        r.quads.append(quad)
        aspect, focale = rapport_aspect(quad, largeur, hauteur)
        r.focales.append(f"{focale} fuite {origine_fuite}")
        # Le bord le plus étroit fixe la finesse réelle : redresser agrandit
        # le fond de la zone, il n'y ajoute aucun détail.
        proche = np.linalg.norm(quad[0] - quad[1])
        loin = np.linalg.norm(quad[3] - quad[2])
        finesse = min(proche, loin) / max(proche, loin)
        if zone.get("wholePlank"):
            attendu = float(produit["lengthMm"]) / largeur_mm
            if abs(aspect / attendu - 1) > TOLERANCE_ASPECT:
                r.ecartes += 1
                r.focales[-1] += (
                    f" lame entiere ecartee (aspect {aspect:.2f} / attendu {attendu:.2f})"
                )
                continue
            # Lame entière : ses dimensions réelles sont connues, elles priment
            # sur l'aspect déduit d'une focale supposée.
            r.focales[-1] += f" aspect mesure {aspect:.2f} -> reel {attendu:.2f}"
            aspect = attendu
        plan = redresser(img, quad, aspect)
        r.redresses.append(plan)
        gris = cv2.cvtColor(plan, cv2.COLOR_BGR2GRAY)
        n = zone.get("planksAcross")
        if not n:
            periode = periode_lames(gris)
            n = max(1, round(gris.shape[0] / periode)) if periode else 1
        bords = [0, *joints_longs(gris, n), gris.shape[0]] if n > 1 else [0, gris.shape[0]]
        r.joints.append([b / gris.shape[0] for b in bords])
        fraction = float(zone.get("widthFraction", 1.0))
        for a, b in zip(bords[:-1], bords[1:], strict=True):
            marge = int(round((b - a) * MARGE))
            lame = plan[a + marge : b - marge]
            if lame.shape[0] < 6:
                continue
            if joint_interieur(cv2.cvtColor(lame, cv2.COLOR_BGR2GRAY)):
                r.ecartes += 1
                continue
            # px par mm dans la photo : la largeur visible de la lame, marges
            # comprises, rapportée à sa largeur réelle.
            ppm = (b - a) / (largeur_mm * fraction) * finesse
            coupes = [0, *joints_de_bout(cv2.cvtColor(lame, cv2.COLOR_BGR2GRAY)), lame.shape[1]]
            for x0, x1 in zip(coupes[:-1], coupes[1:], strict=True):
                x0m, x1m = x0 + 3, x1 - 3
                if x1m - x0m < 8:
                    continue
                piece = lame[:, x0m:x1m]
                longueur_mm = piece.shape[1] / ppm
                if longueur_mm < 100:
                    continue
                r.morceaux.append(Morceau(egaliser(piece), ppm, longueur_mm, iz))
    return r


#: Écart de luminosité gardé entre deux lames : celui d'un vrai lot, pas
#: celui de deux coins de la photo, l'un au soleil, l'autre à l'ombre.
ECART_LAMES = 0.10


def harmoniser(r: Rapport) -> None:
    """Ramène la luminosité de chaque morceau à ±10 % de la médiane du lot.

    Chaque morceau garde sa teinte et son veinage ; seule sa clarté
    d'ensemble, qui dépend surtout de l'endroit de la photo d'où il vient,
    est resserrée.
    """
    if len(r.morceaux) < 2:
        return
    lums = [float(np.median(cv2.cvtColor(m.image, cv2.COLOR_BGR2GRAY))) for m in r.morceaux]
    cible = float(np.median(lums))
    for m, lum in zip(r.morceaux, lums, strict=True):
        voulu = cible * min(1 + ECART_LAMES, max(1 - ECART_LAMES, lum / max(1.0, cible)))
        m.image = np.clip(m.image.astype(np.float32) * (voulu / max(1.0, lum)), 0, 255).astype(
            np.uint8
        )


def valider(r: Rapport) -> list[str]:
    """Les raisons de refuser « exact ». Vide = matière exacte."""
    raisons = list(r.raisons)
    if not r.morceaux:
        return raisons or ["aucun morceau de lame exploitable"]
    ppm = min(m.ppm_source for m in r.morceaux)
    if ppm < PPM_SOURCE_MIN:
        raisons.append(f"photo trop peu fine : {ppm:.2f} px/mm < {PPM_SOURCE_MIN}")
    zones = {(m.zone, round(m.ppm_source, 3)) for m in r.morceaux}
    if len(r.morceaux) < MORCEAUX_MIN:
        raisons.append(f"{len(r.morceaux)} morceau(x) de lame < {MORCEAUX_MIN}")
    bois = sum(m.longueur_mm for m in r.morceaux) / 1000
    if bois < BOIS_MIN_M:
        raisons.append(f"{bois:.2f} m de bois < {BOIS_MIN_M}")
    if r.longueur_lame_m and bois < r.longueur_lame_m:
        raisons.append(f"{bois:.2f} m de bois < une longueur de lame ({r.longueur_lame_m:.2f} m)")
    del zones
    return raisons


def atlas(r: Rapport, largeur_mm: float) -> tuple[np.ndarray, list[dict[str, int]]]:
    """Les morceaux en rangées : une rangée = une lame, largeur réelle à 0,6 px/mm."""
    h = max(4, int(round(largeur_mm * PPM_ATLAS)))
    rangees = []
    rects = []
    for m in r.morceaux:
        longueur = max(8, int(round(m.longueur_mm * PPM_ATLAS)))
        rangees.append(cv2.resize(m.image, (longueur, h), interpolation=cv2.INTER_AREA))
    largeur = max(x.shape[1] for x in rangees)
    sortie = np.zeros((h * len(rangees), largeur, 3), dtype=np.uint8)
    for i, x in enumerate(rangees):
        # Le reste de la rangée est rempli en miroir : le moteur ne lit que
        # `w`, mais une rangée pleine évite tout noir au filtrage.
        reps = math.ceil(largeur / x.shape[1])
        bande = np.concatenate([x if k % 2 == 0 else x[:, ::-1] for k in range(reps)], axis=1)[
            :, :largeur
        ]
        sortie[i * h : (i + 1) * h] = bande
        rects.append({"x": 0, "y": i * h, "w": int(x.shape[1]), "h": h})
    return sortie, rects


def couleurs(atl: np.ndarray) -> dict[str, list[int]]:
    """Base et veinage moyens de l'atlas, en RGB : la teinte du produit."""
    rgb = cv2.cvtColor(atl, cv2.COLOR_BGR2RGB).reshape(-1, 3).astype(np.float64)
    lum = rgb @ [0.2126, 0.7152, 0.0722]
    base = rgb[lum >= np.percentile(lum, 35)].mean(axis=0)
    veine = rgb[lum <= np.percentile(lum, 15)].mean(axis=0)
    return {"base": [int(round(v)) for v in base], "grain": [int(round(v)) for v in veine]}


def definition(
    produit: dict[str, Any],
    famille: dict[str, Any],
    atl: np.ndarray,
    rects: list[dict[str, int]],
    r: Rapport,
) -> dict[str, Any]:
    """La matière : la famille représentative pour le joint, le chanfrein et la
    finition (que la photo ne mesure pas), l'atlas pour le bois lui-même."""
    c = couleurs(atl)
    texture = dict(famille["texture"])
    texture["base"] = c["base"]
    texture["grain"] = c["grain"]
    return {
        "id": f"premibel-{produit['id']}",
        "name": f"Matière exacte {produit['id']}",
        "slug": f"premibel-{produit['id'].lower()}",
        "wood": famille.get("wood", "Chêne"),
        "tone": famille.get("tone"),
        "finish": produit.get("finish", famille.get("finish")),
        "boardWidth": produit["widthMm"] / 1000,
        "boardLength": produit["lengthMm"] / 1000,
        "defaultPattern": produit["pattern"],
        "compatiblePatterns": [produit["pattern"]],
        "texture": texture,
        "atlas": {
            "url": f"assets/products/premibel/materials/{produit['id']}.atlas.webp",
            "ppm": PPM_ATLAS,
            "version": hashlib.sha256(atl.tobytes()).hexdigest()[:16],
            "rows": rects,
        },
        "provenance": {
            "kind": "exact",
            "product": produit["id"],
            "sourceKind": produit["sourceKind"],
            "source": produit["source"],
            "planks": len(r.morceaux),
            "woodMeters": round(sum(m.longueur_mm for m in r.morceaux) / 1000, 2),
            "sourcePxPerMm": round(min(m.ppm_source for m in r.morceaux), 3),
            "focal": r.focales,
            "inherits": famille["id"],
            "inheritedFields": ["joint", "bevel", "sheen", "finish"],
            "limits": (
                "Éclairage de la photo égalisé ; longueur des morceaux déduite de la "
                "perspective. Joint et chanfrein empruntés à la famille représentative."
            ),
        },
    }


def planche(
    produit: dict[str, Any], r: Rapport, atl: np.ndarray | None, statut: str, raisons: list[str]
) -> None:
    """Planche de contrôle : source annotée, zones redressées, atlas."""
    SORTIE_REVUE.mkdir(parents=True, exist_ok=True)
    img = cv2.imread(str(RACINE / produit["source"]), cv2.IMREAD_COLOR)
    if img is None:
        return
    h, w = img.shape[:2]
    for iz, zone in enumerate(produit["regions"]):
        q = (np.array(zone["quad"]) * [w, h]).astype(np.int32)
        cv2.polylines(img, [q], True, (0, 220, 255), 1)
        if iz < len(r.quads):
            cv2.polylines(img, [r.quads[iz].astype(np.int32)], True, (0, 255, 0), 2)
        cv2.putText(
            img,
            str(iz),
            tuple(int(v) for v in q[0]),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 220, 255),
            2,
        )
    hauteur = 360
    blocs = [cv2.resize(img, (int(w * hauteur / h), hauteur))]
    for iz, plan in enumerate(r.redresses):
        p = plan.copy()
        for f in r.joints[iz]:
            y = int(f * (p.shape[0] - 1))
            cv2.line(p, (0, y), (p.shape[1], y), (0, 0, 255), 1)
        e = hauteur / max(p.shape[0], p.shape[1] / 3)
        blocs.append(cv2.resize(p, (max(8, int(p.shape[1] * e)), max(8, int(p.shape[0] * e)))))
    if atl is not None:
        e = min(1.0, 1400 / atl.shape[1])
        blocs.append(
            cv2.resize(atl, (max(8, int(atl.shape[1] * e)), max(8, int(atl.shape[0] * e))))
        )
    largeur = max(b.shape[1] for b in blocs)
    planche_img = np.full((sum(b.shape[0] + 8 for b in blocs) + 40, largeur, 3), 255, np.uint8)
    y = 40
    texte = f"{produit['id']} : {statut}" + (f" - {'; '.join(raisons)}" if raisons else "")
    cv2.putText(planche_img, texte[:140], (8, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
    for b in blocs:
        planche_img[y : y + b.shape[0], : b.shape[1]] = b
        y += b.shape[0] + 8
    cv2.imwrite(
        str(SORTIE_REVUE / f"{produit['id']}.jpg"), planche_img, [cv2.IMWRITE_JPEG_QUALITY, 88]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("ids", nargs="*")
    parser.add_argument("--manifest", type=Path, default=SOURCES)
    args = parser.parse_args()
    sources = json.loads(args.manifest.read_text(encoding="utf-8"))
    familles = {f["id"]: f for f in json.loads(FAMILLES.read_text(encoding="utf-8"))["parquets"]}
    SORTIE_DEF.mkdir(parents=True, exist_ok=True)
    SORTIE_ATLAS.mkdir(parents=True, exist_ok=True)
    chemin_index = SORTIE_DEF / "index.json"
    index = (
        json.loads(chemin_index.read_text(encoding="utf-8"))
        if chemin_index.is_file()
        else {"materials": {}}
    )
    for produit in sources["products"]:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,80}", str(produit.get("id", ""))):
            raise ValueError(
                "Invalid product reference: output paths must remain inside material directories"
            )
        if args.ids and produit["id"] not in args.ids:
            continue
        # La note de revue humaine survit à une nouvelle extraction.
        revue = index["materials"].get(produit["id"], {}).get("review")
        r = extraire(produit)
        harmoniser(r)
        raisons = valider(r)
        atl = None
        if r.morceaux:
            atl, rects = atlas(r, float(produit["widthMm"]))
        if not raisons and atl is not None:
            famille = familles[produit["representativeFamily"]]
            d = definition(produit, famille, atl, rects, r)
            cv2.imwrite(
                str(SORTIE_ATLAS / f"{produit['id']}.atlas.webp"),
                atl,
                [cv2.IMWRITE_WEBP_QUALITY, 92],
            )
            (SORTIE_DEF / f"{produit['id']}.json").write_text(
                json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            index["materials"][produit["id"]] = {
                "materialFidelity": "exact",
                "material": d["id"],
                "definition": f"data/materials/premibel/{produit['id']}.json",
                "pattern": produit["pattern"],
                "widthMm": produit["widthMm"],
                "lengthMm": produit["lengthMm"],
                "planks": d["provenance"]["planks"],
                "sourcePxPerMm": d["provenance"]["sourcePxPerMm"],
            }
            statut = "exact"
        else:
            index["materials"][produit["id"]] = {
                "materialFidelity": "representative",
                "rejected": raisons,
            }
            (SORTIE_DEF / f"{produit['id']}.json").unlink(missing_ok=True)
            statut = "refusé"
        if revue:
            index["materials"][produit["id"]]["review"] = revue
        planche(produit, r, atl, statut, raisons)
        print(
            f"{produit['id']:<12} {statut:<7} morceaux={len(r.morceaux)} "
            f"ppm={min((m.ppm_source for m in r.morceaux), default=0):.2f} "
            f"bois={sum(m.longueur_mm for m in r.morceaux) / 1000:.2f}m "
            f"ecartes={r.ecartes} focale={r.focales} " + ("; ".join(raisons))
        )
    index["schema"] = "pose-parquet/premibel-materials@1"
    index["note"] = (
        "Statut matière des produits passés par scripts/import_premibel_material.py. "
        "Les atlas ne sont pas versionnés : sans eux, le moteur garde la matière "
        "représentative."
    )
    chemin_index.write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
