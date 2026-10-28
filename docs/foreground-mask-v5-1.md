# Foreground V5.1 — bilan technique et produit

## Verdict

`FOREGROUND_V5_1_NEEDS_WORK`.

Les optimisations sont utiles et conservent les résultats V5. **Les objectifs produit ne sont pas atteints** : aucun gain visuel supplémentaire n'est livré sur les objets absents des seeds, et les temps first/final ne baissent pas de façon convaincante dans la comparaison contrôlée. La branche est un lot d'optimisation et d'audit, pas une déclaration de problème résolu.

## Périmètre

Base `d87781f`, branche `feature/foreground-mask-v5-1`. ForegroundUnderstanding V5, préservation fine, tapis, diagnostic, correction manuelle et Fast/Quality conservés. CameraModel, FloorPlane, projection, motifs, matériaux, éclairage V4 et contact compositor V4 inchangés. Modification locale du logo exclue du lot. Aucun nouveau modèle, export, poids ou téléchargement.

## Information perdue

OneFormer ADE20K Swin Tiny local, OpenVINO GPU, postprocess CPU f32 existant. Exemple 1536×1024 : resize INTER_AREA 512×341, padding répliqué 352×512, prédiction, suppression du padding, labels remontés par voisin le plus proche. Une ligne source de 1–3 px représente seulement 0,33–1 px à l'entrée. L'upsampling ne recrée pas les détails effacés. Le padding ne déforme pas le ratio et n'est pas la source d'un décalage d'UV.

La revue privée compare sur chaque scène photo source, photo réduite/remontée (illustration de la perte d'échantillonnage), labels sémantiques d'objets, masque final V5 et masque V5.1. Elle ne présente pas la photo réduite comme une nouvelle inférence. Les labels V5 sont les sorties source archivées, déjà upsamplées. Les objets partiellement semés relèvent du raffinement V5 ; un objet entièrement absent exige une autre observation, pas une fermeture morphologique.

## Source complémentaire : A puis B puis C

A. Essai réel de reshape du graphe installé en 768×768 : rejet de validation `VariadicSplit`, longueur 5376 contre 12096. Le graphe exporté est statique. Augmenter `PPAI_INFERENCE_LONG_SIDE` ne l'augmente pas : `canonical_side=512` prend priorité. Aucune inference 768 n'est revendiquée et aucun graphe non validé n'a été exporté.

B. Deux recadrages chevauchants, chacun 65 % de la largeur source, limités au domaine de sol + contexte supérieur de 6 % de la hauteur. Même checkpoint et même entrée 512 ; marge de bord des crops exclue. C. Un crop couvrant la bande sol/contact avec contexte objet. Cinq exécutions par mode et par scène, métadonnées et boîtes exactes conservées dans `seeds.json`. Propositions cumulées avec les seeds existants pour observer les ajouts, jamais injectées dans la géométrie.

Les tuiles récupèrent des parties d'objets mais ajoutent 87005 pixels de faux tapis sur une scène parquet. La passe contact propose une partie du coussin sombre mais classe aussi une zone de sol entre les chaises comme objet. Le bénéfice ne justifie donc pas une activation automatique. Les timings exploratoires des crops ont croisé en partie le benchmark CPU initial ; ils sont fournis comme coûts observés et non comme test isolé causal. Les mesures paired finales et UI ci-dessous ont été exécutées séparément.

D. Aucun autre modèle évalué. Le rapport séparé ne démontre pas encore plusieurs catégories d'objets critiques totalement sans seed pour lesquelles les crops seraient insuffisants. Les conditions de téléchargement/évaluation d'un autre modèle ne sont donc pas réunies. Prochaine décision fondée sur des annotations d'objets réellement absents, plutôt qu'un score de couleur artificiellement augmenté.

## Optimisations effectivement intégrées

- Couleurs des seeds : conserver une table + carte d'indices et ne lire les couleurs qu'aux pixels de la bande utile. Supprime deux gros tableaux float RGB denses, sans changer les distances ou choix de couleurs.
- Recherche de lignes : prédicat longueur / largeur / endpoints vectorisé avant allocation des échantillons ; le contrôle exact V5 reste ensuite appliqué. Réutilisation de la distance au prior déjà calculée.
- Navigateur : prédicat intérieur du masque calculé une seule fois dans un buffer Uint8 par matte, au lieu de quatre consultations répétées pour chacun des 81 voisins de chaque pixel de bord. Même seuil, même ordre de candidats, même alpha et mêmes échantillons de fond. Aucun coefficient de compositing changé.
- Calculs dépendants uniquement de photo/masque ; aucun cache global d'image privée. Les labels existants restent capturés par la tâche qualité, la correction manuelle conserve sa priorité. Changer de parquet n'effectue aucun POST d'analyse supplémentaire.

Pas de thread pool ajouté : edge/color et lignes partagent désormais la distance au prior, et les gains séquentiels sont mesurés. La comparaison d'un parallélisme dédié n'a pas été faite ; aucun gain de parallélisme n'est revendiqué. Les calculs de couleur et distance restent à résolution source ; seul le choix des pixels examinés et des lignes candidates est borné. Pas de recadrage brutal susceptible de déplacer les frontières ou perdre les seeds proches.

## Tableau obligatoire — neuf scènes

| SCENE | MASK V5 | MASK V5.1 | THIN OBJECTS | MISSING SEEDS | FALSE POSITIVES | QUALITY TIME V5 → V5.1, ms | FINAL RESULT |
|---|---|---|---|---|---|---|---|
| bright | Référence d87781f | Identique bit à bit | Inchangés | Voir rapport séparé | 0 nouveau vs V5 | 397.2 → 293.9 | Meubles bas : contours imparfaits, aucune nouvelle récupération certifiée. |
| dark | Référence d87781f | Identique bit à bit | Inchangés | Voir rapport séparé | 0 nouveau vs V5 | 127.6 → 84.7 | Couloir sombre : absence de nouvel objet, non-régression. |
| empty | Référence d87781f | Identique bit à bit | Inchangés | Voir rapport séparé | 0 nouveau vs V5 | 840.9 → 715.4 | Meuble / radiateur : contacts ambigus conservés. |
| empty-room | Référence d87781f | Identique bit à bit | Inchangés | Voir rapport séparé | 0 nouveau vs V5 | 965.4 → 693.3 | Pièce vide : 0 nouveau pixel de foreground utile. |
| old-floor | Référence d87781f | Identique bit à bit | Inchangés | Voir rapport séparé | 0 nouveau vs V5 | 419.4 → 308.6 | Câbles sous bureau : région encore incomplète, source complémentaire non validée. |
| plant | Référence d87781f | Identique bit à bit | Inchangés | Voir rapport séparé | 0 nouveau vs V5 | 797.5 → 721.1 | Tige annotée 10/10 conservée ; coussin partiel dans le coarse. |
| rug | Référence d87781f | Identique bit à bit | Inchangés | Voir rapport séparé | 0 nouveau vs V5 | 489.9 → 409.0 | Tapis conservé ; tiling rejeté car il invente un tapis sur le parquet. |
| sofa | Référence d87781f | Identique bit à bit | Inchangés | Voir rapport séparé | 0 nouveau vs V5 | 1085.5 → 800.7 | Canapé / tapis conservés ; bande sombre sous meuble ambiguë. |
| thin-legs | Référence d87781f | Identique bit à bit | Inchangés | Voir rapport séparé | 0 nouveau vs V5 | 536.7 → 449.3 | Pieds conservés ; passe contact rejetée sur le sol entre les chaises. |

Qualité time = raffinement ForegroundUnderstanding, labels/prior identiques en cache, cinq échantillons chauds par version. Ce n'est pas le temps de l'ensemble du Quality Pass.

## Performance isolée du raffinement

Même processus, OpenCV 2 threads, six exécutions par scène/version en ordre alterné. Premier échantillon / médiane chaude / p95 chaud, ms, exemple canapé 1536×1024 :

| Étape | V5 | V5.1 |
|---|---|---|
| Total foreground | 1220,1 / 1085,5 / 1137,1 | 1038,9 / 800,7 / 828,8 |
| Préservation fine | 92,3 / 63,9 / 66,0 | 117,9 / 82,8 / 93,5 |
| Edge/color | 610,0 / 543,3 / 588,1 | 617,4 / 418,5 / 442,1 |
| Thin-line | 465,4 / 449,1 / 461,3 | 266,0 / 260,7 / 288,3 |

Gain médian du total environ 26 %. La préservation fine n'est pas accélérée et sa variance n'est pas masquée. L'ancien chiffre V5 ~2,75 s provenait d'une autre série ; on ne l'utilise pas comme contrôle pour annoncer un gain de 70 %.

Polygones foreground + JSON V5.1 (fixtures conservées), premier / médiane / p95 : 490.9 / 431.3 / 511.7 ms. JSON SceneData seul : 5.0 / 6.4 / 6.9 ms. Raster + alpha navigateur, original 1536×1024 : 336.3 / 272.0 / 329.7 ms. N=5 ou 6, p95 indicatif. Le test Node compare également 16 cas alpha à V5, six fois chacun : alpha, backgrounds, nombres de pixels changés et de bords identiques.

## First render / final quality : comparaison réelle

Cinq imports par version, pages neuves, [1440,390,1440,390,390], DPR2 ; modèles déjà préchauffés, aucune suite de tests parallèle. V5 Python encore chargé + module alpha V5 figé ; puis redémarrage local et V5.1. Les mesures historiques V5 à 8,8 / 21,3 s ne sont pas un contrôle simultané : les étapes inchangées ont aussi varié.

| Étape, ms | V5 premier / warm médiane / warm p95 | V5.1 premier / warm médiane / warm p95 |
|---|---|---|
| Inférence | 6611,4 / 627,4 / 662,1 | 2697,4 / 658,7 / 1134,7 |
| First render complet | 18337 / 6355 / 7305,5 | 14247 / 6749 / 7500 |
| Final quality complet | 26342 / 13183 / 14202,7 | 27989 / 13204,5 / 14463,1 |
| highResolutionForeground complet, incluant graph-cut et contours | 6971,8 / 5354,7 / 5452 | 8300,2 / 4860 / 5454,4 |
| SceneData, incluant éclairage V4 | 679,1 / 879,6 / 944,3 | 1729,9 / 892,3 / 947,5 |

Le premier rendu ne s'améliore pas (médiane +6 %), la qualité finale est pratiquement inchangée. Un gain de sous-étape n'est pas présenté comme un gain utilisateur. Le graph-cut antérieur et d'autres étages restent coûteux ; aucune modification de lumière ou de géométrie n'a été faite pour contourner le périmètre.

**Cold** : redémarrage réel observé, chargement 56753,1 ms + première inférence de préchauffage 21151,5 ms = 77904,6 ms. Le premier import du tableau survient ensuite, modèle prêt ; ce n'est pas un chargement cold complet. Pas de cold boot système/driver vierge, ni de p95 de cold boot. Chaque étape possède son premier échantillon et ses mesures chaudes dans les JSON privés ; on ne fabrique pas de cold-inference par addition de benchmarks incompatibles.

## Qualité, sécurité des masques et mobile

Égalité exacte des masques V5/V5.1 sur les neuf scènes : conserve les dix centres de tige déjà récupérés, pieds, tapis, canapé, et aucun nouveau faux pixel utile sur pièce vide. Ce n'est pas une preuve de masque parfait ni une GT exhaustive. `foregroundQuality` reste inchangé, exemple 0,658, inférieur au seuil AUTO ; `confidenceCalibrated=false`. La nouvelle propriété de provenance `implementationVersion=5.1` permet de vérifier le code actif.

WebGL2 et Canvas réels, neuf scènes, 1440 et 390×844, DPR2 en GL et DPR1 en repli Canvas. Pas de débordement horizontal ; coordonnées source conservées ; camera/planes/floorZones/light identiques avant/après. A→B→A retrouve le SHA256 de A, distinct de B. Cinq imports V5.1 réels : un POST chacun, même caméra/plans entre Fast et Quality, changement de produit sans nouvelle analyse. Téléphone physique non mesuré.

## Validation et Git

**546 tests pytest passent**, deux avertissements de dépendances, 209,46 s. Ruff et Mypy app passent. Contrôle final sur neuf masques à partir du code V5.1 actif : identité exacte avec V5 et tige annotée 10/10 conservée ; les 16 cas alpha × six exécutions passent également. Revue GL/Canvas et tests d’import terminés sans erreur. Revue `review/foreground-mask-v5-1/index.html`, logs et données privées ignorés par Git et non servis par HTTP. Outils d'audit publiables sans photos, labels ou réponses API.

Commits logiques sur `feature/foreground-mask-v5-1`, push seulement après succès des tests. Aucun merge/rebase main, force push ou modification distante du logo.

## Limites / travail restant

Les JSON précalculés du catalogue ne sont pas réécrits. Aucune promesse de correction visuelle de toutes les pièces. Les contacts sombres, franges et objets absents des seeds restent à documenter par annotations, et les propositions sémantiques locales nécessitent une validation avant intégration. Targets <1 s foreground : atteinte sur cette série isolée, pas garantie en charge réelle. Targets <4 s first et <6 s final : **non atteintes**. La condition « plusieurs scènes complexes progressent visuellement » n'est pas satisfaite, d'où le verdict NEEDS_WORK.
