# Obstacle occlusion V3 — 27 octobre 2026

Verdict : **OBSTACLE_OCCLUSION_V3_READY_FOR_HUMAN_REVIEW**.
Plusieurs scènes progressent visiblement. Ce verdict autorise la revue humaine,
pas une déclaration de perfection sur toute photo importée.

## Causes confirmées

- D2-A : 1 omission de pipeline : plusieurs classes ADE20K déjà calculées
  (coussin, pouf, carton, pot, etc.) ne rejoignaient pas la protection.
  Correction de la table des classes, sans nouveau modèle.
- D2-B : 0 défaut confirmé de mapping/compositing dans les cas testés.
- D2-C : contours source trop grossiers observés dans 4 scènes de contrôle
  (piano/tapis, lit, console, photo privée). Affinage local ajouté ;
  le cas privé sous la console reste partiellement ouvert.
- D2-D : pieds absents des anciens masques dans 2 scènes de catalogue
  (canapé et salle à manger). Les sorties du modèle déjà installé récupèrent
  les supports ; seules les données d'occlusion de ces scènes sont actualisées.
- D2-E : 0 erreur de convention alpha confirmée. Ne pas confondre un bord
  source irrégulier ou une ombre avec une erreur alpha.

Ces comptes distinguent une omission générale et des manifestations visuelles ;
ils ne sont pas une estimation statistique de précision.

## Ce qui change

Le front affine uniquement une bande de 2 pixels source autour des masques,
avec des exemples de couleur fiables cherchés dans un rayon de 4 pixels.
Pas de dilation globale, de flou large ou de recalage du sol. Les branches
fines du masque initial restent protégées. Le calcul intervient à la préparation
du masque, puis son résultat est réutilisé pour les matériaux et les retouches.

Les scènes sans furniture/rug/mask-opening contournent cet affinage.
La décision backend expose une qualité d'occlusion non calibrée, sans inventer
un score. Avec une occupation significative et une décision auparavant AUTO,
elle préfère approximate_render. Le seuil d'occupation de 5 % est une règle de
prudence, pas une confiance statistique.

La commande générique scripts/refresh_scene_occlusion.py consomme des classes
déjà produites. Elle ne lance pas d'IA, reste idempotente, conserve les
protections existantes et vérifie camera/planes/floorZones/light à l'identique.
Aucun branchement par nom de pièce dans le moteur.

## Matrice visuelle

Les packs privés sont dans review/occlusion-obstacles/index.html.
Chaque cas contient original, avant, après, masques, grille, caméra, crops et
métadonnées. Même caméra, plan, produit, motif et angle pour chaque A/B.

| Scène / objet | Avant | Après | D2 | D8 | Résultat |
|---|---|---|---|---|---|
| Chambre dégagée | Référence | Identique pixel par pixel | PASS témoin | Identique | Non-régression |
| Salon / canapé | Pied recouvert | Support retrouvé | Amélioré | Petits bords résiduels | Revue humaine |
| Salle à manger / table | Supports arrière recouverts | Supports conservés | Amélioré | Bords fins visibles | Revue humaine |
| Salle à manger / chaise | Pieds manquants | Pieds visibles conservés | Amélioré | Résidu mineur | Revue humaine |
| Pied fin synthétique | Masque connu | Même protection | PASS technique | Alpha partiel vérifié | WebGL + Canvas |
| Piano / tapis | Contour grossier | Contact affiné, intérieur protégé | PASS sur le tapis inspecté | Amélioré | Revue humaine |
| Grande pièce / console | Bord pixelisé | Bord local affiné | Supports protégés | Résidu mineur | Revue humaine |
| Chambre / lit | Bord inférieur irrégulier | Contact plus propre | Lit protégé | Amélioré | Revue humaine |
| Terrasse | Référence | Identique pixel par pixel | PASS témoin | Identique | Non-régression |
| Photo privée / console | Bord irrégulier | Gain local limité | Gros objets préservés | Reste à corriger | Retouche locale utile |

La régression sur les vraies scènes vérifie **260 pixels opaques retrouvés**
du pied du canapé et **1 527 + 1 883 pixels** de supports de chaises.
Erreur RGB maximale face à la photo originale : **0** sur ces sondes.
Ces nombres concernent les crops examinés, pas une mesure de justesse globale.

## Invariants et masques

- D3 / D6 : caméras, plans, matrices, horizon et fuites identiques dans les packs.
- D4 : dimensions physiques configurées identiques. L'échelle absolue reste
  fondée sur une hauteur de caméra supposée, sans mesure de la pièce.
- Motifs : aucune modification de leurs modules ou de leurs cellules.
- La lumière n'a pas été réécrite. La préparation existante reste dépendante du
  masque : modifier les pixels considérés comme sol peut changer ses statistiques.
  Le nombre de pixels différents d'un rendu n'est donc pas une mesure d'IoU.
- ViewTransform : aller-retour maximal 1,14e-13 pixel sur les sondes, < 0,5 px.
- Les caches de démonstration utilisent id + SceneData JSON et l'objet photo
  préparé ; masques, dimensions et révision font partie de cette identité.
  Retirer invalide la préparation. A -> B -> A est testé.
- Alpha straight : shader RGB non prémultiplié, alpha =
  floorCoverage * (1 - occlusion), SRC_ALPHA / ONE_MINUS_SRC_ALPHA.
  Canvas utilise la même interpolation sur la photo opaque. Pas de seconde
  restauration rectangulaire ni de feather global.
- Un pixel antialiasé n'est pas traité comme opaque dans les tests ; les supports
  de plusieurs pixels sont vérifiés strictement. Aucune promesse sur un objet
  absent des classes et sans contour exploitable.

Résolutions : original -> entrée réduite du backend sémantique configuré
(profils OpenVINO locaux 352x512 / 512x512 disponibles) -> classes remontées à
la résolution originale -> affinage backend -> polygones normalisés ->
raster au format réellement rendu -> affinage local -> texture GPU identique.
Les imports et petits écrans peuvent être réduits à 1100x825 ; le chemin
desktop est borné à 1600x1200. Les masques sont rerastérisés aux mêmes dimensions,
sans dépendre du DPR écran.

## Performances

Chrome local, 12 mesures après chauffe par scène. Valeurs médiane / p95 / max,
en ms. Le dernier passage est enregistré dans browser-performance.json.
Le p95 vaut le maximum pour cet échantillon court ; ce n'est pas un SLO.

| Scène | Coarse/raster | Affinage front | Upload GPU synchronisé | Rendu complet + copie |
|---|---|---|---|---|
| Canapé 800x600 | 6,7 / 10,3 / 10,3 | 11,1 / 36,9 / 36,9 | 1,5 / 1,8 / 1,8 | 2,0 / 5,3 / 5,3 |
| Lit 900x1029 | 13,7 / 19,7 / 19,7 | 14,2 / 17,7 / 17,7 | 2,6 / 3,4 / 3,4 | 3,2 / 5,2 / 5,2 |
| Console 1600x1067 | 18,7 / 22,3 / 22,3 | 12,9 / 16,7 / 16,7 | 4,8 / 5,4 / 5,4 | 5,1 / 9,1 / 9,1 |
| Dégagée 1600x1067 | 69,3 / 83,3 / 83,3 | 0 / 0 / 0 | 17,9 / 23,7 / 23,7 | 19,0 / 26,4 / 26,4 |
| Terrasse 1125x750 | 12,7 / 28,1 / 28,1 | 0 / 0 / 0 | 3,8 / 10,1 / 10,1 | 4,4 / 10,6 / 10,6 |

Le dernier poste inclut le rendu complet de diagnostic sans éclairage et sa
copie, pas seulement le temps d'une instruction de sampling GPU.
La machine reste partagée : des passages précédents étaient plus lents.
L'affinage n'est pas répété à chaque changement de parquet.

Rejeu backend privé (photo salon 1536x1024, 12 mesures) :
coarse 71,5 / 116,0 / 126,1 ms ; affinage 239,0 / 327,5 / 334,2 ms ;
polygones 134,0 / 183,8 / 211,6 ms.
Sans objet, l'affinage backend était 2,8 / 6,1 / 7,4 ms.
Mesures hors inférence, dans backend-replay.json.
Le test ponctuel du modèle local a coûté 132,2 s au premier chargement,
puis 1,55 s pour la seconde scène. Aucun modèle téléchargé ou ajouté.
Ces coûts de préparation ne sont pas facturés à chaque matériau.

## Tests

- 38 tests pytest : foreground, floor_scene, boundary_refiner, obstacle_refresh.
- obstacle-occlusion.check.mjs : 12 configurations WebGL/Canvas, DPR1/2,
  1440 -> 390 -> 1440, pieds fins et alpha partiel, Retirer, A -> B -> A,
  zéro nouvelle analyse.
- obstacle-scene.check.mjs : 3 crops réels, pixels retrouvés et conservés,
  caméra / planes / floorZones / light inchangés.
- camera-gpu.check.mjs : 660 sondes, erreur source-masque max 0,000085 px.
- metric-cells-gpu.check.mjs : 4600 sondes CPU/GPU, motifs/joints/AA.
- metric-mobile.check.mjs : Retirer, Annuler, Terminé, pincement, catalogue,
  changement de produit ; une seule analyse simulée.
- git diff --check : PASS.

Les captures restent privées et ignorées par Git.
Git : feature/obstacle-occlusion-v3 ; baseline antérieure conservée séparément
dans 64fefbb ; correction du pipeline dans 906fa47. Aucun merge/rebase/force push.
