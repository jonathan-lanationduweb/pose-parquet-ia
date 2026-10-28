# Foreground mask V5

## ROOT CAUSES

Le modèle existant voit la photo fournie 1536×1024 à **512×341**, complétée en tenseur **1×3×352×512**. Les classes ADE20K sont ensuite remontées en nearest-neighbor à 1536×1024 : les marches et petits manques existent déjà dans le masque source. Les 150 classes et les catégories prioritaires, dont radiateur 146, ont été vérifiées dans le modèle installé.

Chaîne conservée : photo originale → réduction/padding → inférence existante → classes source → foreground sémantique + trous du sol → ancien GrabCut → V5 haute résolution → polygones exacts → raster et alpha locale du navigateur → texture occluder V4. Le nettoyage d’aire existant concerne le sol, pas une suppression des petits objets ; les trous sont conservés.

Erreurs observées : B OBJECT_PARTIAL, C THIN_OBJECT_LOST, D EDGE_COARSE, E FALSE_POSITIVE possible aux contacts sombres, F RUG_ERROR. Aucun objet entier manquant n’a une GT exhaustive permettant un score A. Pas de nouveau modèle évalué ou téléchargé.

## OBJECT COVERAGE

V5 est raccordé aux **nouvelles analyses/imports**, en passe qualité. Les photos existantes servent de cas de recompilation et de revue ; les JSON précalculés du catalogue ne sont pas réécrits. Les corps principaux étaient déjà couverts ; les progrès concernent surtout les contacts, les petits manques et les silhouettes. La protection structurelle reste séparée.

Neuf scènes : canapé/console/tapis, table/chaises, lit/plante/coussins, tapis clair, cuisine, bureau chargé, radiateur/meuble, couloir sombre et pièce vide. La photo fournie reste privée ; sa provenance photographique n’est pas certifiée.

## THIN OBJECTS

Ridges fins du prior protégés ; aucun opening/closing global. Les propositions de lignes sont courtes, contrastées, attachées à deux zones existantes et à un seed fin. Pas de suppression des petites composantes uniquement selon leur aire : les modifications doivent garder un ancrage.

Sur **10 pixels centraux de tige vérifiés manuellement** : couverture **0/10 → 10/10**. Ce n’est pas un rappel global de plante. Les tests GT couvrent 1/3/5 px, pieds inclinés et sombre sur sombre. Un câble entièrement absent et sans ancrage fiable peut rester manqué.

## RUGS

Le tapis reste une surface foreground ; le plan continue dessous. Les tests de tapis proche de la couleur du sol conservent le prior ambigu. Les franges des photos progressent localement, sans certification de chaque fibre.

## EDGE REFINEMENT

Responsabilité explicite `ForegroundUnderstanding` : vraie photo uint8 source, références Lab locales multiples, bande bornée 6–18 px selon la résolution, preuve de couleur avant changement, consensus local sur les seules propositions, ancrage topologique et préservation fine. Pas de nouvelle segmentation complète, pas de gros flou du masque.

Les méthodes antérieures restent disponibles. FAST conserve son coarse ; QUALITY affine sans relancer le solveur caméra. Masque logique = polygones binaires ; alpha visuel = raster/refinement photo local existant du navigateur, sans substitution du logique par un flou global.

## FALSE POSITIVES

Pièce vide : **0 pixel logique modifié dans le domaine de sol** ; les tests de sol texturé sans seed restent vides. Les contacts peu contrastés restent conservateurs. Une partie des bandes sombres peut être une ombre photographique difficile à distinguer d’un objet. Le petit capuchon clair sous le pied de chaise existe déjà dans l’original : il n’a pas été effacé arbitrairement.

## MASK MAPPING

Le compositor, CameraModel, FloorPlane, ViewTransform, motifs, matériaux, lighting et shader de contact V4 sont identiques à HEAD V4. Les UV, positions et constantes ne changent pas. Une convention `width-1` d’un ancien outil de revue a été écartée : les masques avant sont rejoués directement depuis les fonctions V4, et le profil de polygones utilise les centres de cellules.

Contrôles 1440 / 390×844, WebGL DPR2 et Canvas DPR1 ; aller-retour ViewTransform vérifié en DPR1/2. Pixels opaques préservés. La scène vide a 0 changement logique ; quelques pixels d’AA de bord diffèrent entre les sérialisations (écart moyen final 0,028/255, maximum ponctuel 131/255), pas un déplacement global ni un nouvel objet.

## QUALITY GATE

`foregroundQuality` transporte un **indice local non calibré**, plafonné à 0,75, pas un Dice/IoU ni la confiance du sol recyclée. Exemple réel : **0,658** ; résultat APPROXIMATE_RENDER. Les tests prouvent qu’un foreground incertain bloque AUTO_RENDER même si les autres scores sont bons. Les omissions sans seed restent une limite explicite.

## VISUAL BEFORE/AFTER

Revue privée : `review/foreground-mask-v5/index.html`. Pour chaque scène : original, floorMask, masques avant/après, overlays rouges sans parquet, rendus V4 avant/après, crops 2× et captures 390 GL/Canvas. Le mode DEV **« Masque auto rouge · photo seule »** masque entièrement le parquet et montre le logique automatique ; le diagnostic V4 des objets montre le masque raster courant.

Les nombres ci-dessous sont les **pixels occultés dans le domaine utile au sol**, pas des scores de précision. Pas de GT complète sur ces photos ; les appréciations restent visuelles et partielles.

| SCENE | OBJECT TYPE | MASK BEFORE | MASK AFTER | THIN OBJECT | EDGE | FALSE POSITIVE | FINAL RESULT |
| --- | --- | --- | --- | --- | --- | --- | --- |
| bright | cuisine, meubles bas | 18995 | 19524 | petits contacts | ajustements locaux | ambiguïtés conservées | partiel |
| dark | couloir sans objet au sol | 0 | 0 | sans objet | inchangé | aucun nouveau pixel utile | non-régression |
| empty | meuble bas et radiateur | 5351 | 5533 | conservés | ajustements locaux | pas de GT complète | partiel |
| empty-room | pièce vide | 0 | 0 | sans objet | inchangé | aucun nouveau pixel utile | non-régression |
| old-floor | bureau, chaise, câbles | 13422 | 13441 | récupération bornée | ajustements modestes | pas de GT complète | partiel |
| plant | lit, plante, objets | 170706 | 171627 | tige annotée 0/10 → 10/10 | bords du lit et objets affinés | non évalué exhaustivement | progrès |
| rug | tapis clair, plante | 32528 | 32676 | franges partielles | ajustements locaux | bas contraste conservateur | progrès localisés |
| sofa | canapé, console, tapis | 93227 | 94001 | pieds conservés | contacts partiellement affinés | contacts sombres ambigus | progrès localisés |
| thin-legs | table et chaises | 70526 | 70789 | pieds conservés / ajustés | ajustements locaux | capuchon clair présent sur photo | progrès localisés |

## PERFORMANCE

Photo fournie 1536×1024 ; première exécution / médiane chaude / p95 chaud / max chaud en ms. Quatre échantillons chauds : percentiles indicatifs. Revue des neuf scènes : 5 raffinements chacune à partir des labels en cache, **sans prétendre mesurer l’inférence**.

| Étape | Premier / médiane / p95 / max, ms |
| --- | --- |
| V5 total | 2766.2 / 2748.2 / 2826.9 / 2836.8 |
| Préservation fine | 120.1 / 124.9 / 127.4 / 127.4 |
| Bords / couleurs | 1392.4 / 1356.3 / 1362.6 / 1362.8 |
| Recherche de lignes fines | 1175.1 / 1202.1 / 1264.5 / 1271.0 |
| Polygones + JSON | 185.1 / 157.7 / 202.7 / 209.7 |
| JSON SceneData | 10.5 / 8.0 / 8.7 / 8.7 |
| Raster / alpha navigateur | 521.6 / 418.4 / 507.5 / 520.8 |

Segmentation réelle, 5 imports : première inférence **1332,7 ms**, médiane chaude **308,2 ms**, p95 **316,3 ms**, max **316,6 ms**. Démarrage modèle observé séparément : chargement **82,4 s**, préchauffage **16,1 s**, total **98,5 s**. Même checkpoint local OpenVINO GPU ; aucun téléchargement.

Upload R8 occluder : premier appel CPU observé 0,3 ms ; deux appels suivants, médiane 0,7 ms, p95 0,88 ms, max 0,9 ms (n=2, indicatif) sur le cas desktop ; ces mesures sont des soumissions CPU, pas une durée GPU isolée. JSON et raster/alpha sont mesurés séparément. Ne pas additionner les sous-étapes au parent `highResolutionForeground` qui les englobe.

Imports isolés, modèle prêt, pages neuves : premier rendu première exécution **11,198 s**, puis médiane **8,797 s**, p95 **9,627 s**, max **9,747 s**. Qualité finale : première **23,536 s**, puis médiane **21,261 s**, p95 **21,867 s**, max **21,898 s**. Ce délai reste élevé.

La série concurrente aux tests/captures est archivée séparément. Une hausse de volume de transport a été envisagée puis rejetée : réponses fast ~1,65 Mo en V4 et V5. Des étapes inchangées sont aussi plus lentes que les mesures V4 historiques ; celles-ci ne sont pas un contrôle simultané. Le coût propre V5 est mesuré ci-dessus ; aucune régression totale n’est masquée ou attribuée abusivement au seul masque.

## MOBILE

390×844, Chrome émulé DPR2, pas un téléphone physique. Cinq imports réels au total, un POST chacun, mêmes caméra/plans entre fast et quality ; changer de produit ne relance pas l’IA. Les masques source 1536×1024 sont rasterisés à 1100×733 sur ce viewport et restent dans les mêmes UV normalisés.

## REGRESSIONS

A→B→A : SHA-256 du masque de A identique au retour, B distinct. La retouche manuelle garde la priorité via la génération/annulation existante. Géométrie, rotation et produit vérifiés ; champs camera/planes/floorZones/light avant/après identiques sur la revue. Les composants V4 protégés ont un diff nul.

## TESTS

**546 pytest passent**, deux avertissements de dépendances. **37 tests ciblés finaux passent**, dont contrat HTTP foregroundQuality et une seule inférence. Ruff et Mypy app passent. Quinze tests V5 à GT synthétique connue : objets grands/fins, couleurs sombres/claires, vrais espaces entre pieds, tapis proche du sol, masque vide, dimensions et NaN.

Navigateur : neuf scènes, source→GL/Canvas, pixels opaques, 1440/390, rotation/produit, overlays sans parquet et stale-mask. Encodage/décodage répété ; mesures et logs privés conservés. Aucun score IoU/Dice global n’est inventé pour les photos.

## FILES

`app/services/foreground_understanding.py`, raccord ciblé `floor_scene.py` ; tests V5 et contrat HTTP ; `web/product/foreground-review.js`, relais DEV local/HTML et bouton diagnostic ; outils de revue/capture/performance V5 ; ce rapport. Aucun fichier de modèle, shader V4, CameraModel ou matériau modifié.

## GIT

Branche `feature/foreground-mask-v5`, commits logiques puis push après validation uniquement. Aucun merge/rebase de main ou force push. Le changement de logo préexistant reste conservé hors des commits V5. Images, labels et réponses privées restent ignorés, hors Git et hors dossiers publics.

## LIMITATIONS

Contacts sombres, franges très proches du sol, objets totalement absents des seeds et parties hors domaine utile peuvent rester imparfaits. Les bords supérieurs hors sol restent surtout sémantiques. Pas de GT exhaustive, de mesure 4K ou de téléphone physique. Les JSON précalculés du catalogue gardent leurs masques actuels. Les délais de qualité restent à améliorer.

## VERDICT

`FOREGROUND_MASK_V5_READY_FOR_HUMAN_REVIEW` : progrès localisés sur plusieurs scènes et sur le segment fin annoté, avec revue rouge et limites visibles. Ce verdict ne certifie pas que tous les objets sont désormais parfaits.
