# Journal des défauts visuels et de leurs diagnostics

Ne marquer RESOLVED qu'après confirmation, correction locale, régression et revue.
Un PASS porte sur le périmètre indiqué, jamais sur tout le réalisme de la scène.

## CASE #001 — largeur par défaut erronée dans le diagnostic

- Date : 26 octobre 2026.
- Scène : fixture synthétique 100×100, plan fixe 4×4 m.
- Produit : lame déclarée 0,19×1,80 m, largeur non forcée.
- Symptôme : D4 MODERATE, center ; le diagnostic annonçait 0,15 m.
- CONFIRMED CORRECT : D1 PASS — buffers de masque inchangés ; D3 PASS —
  données de plan/projection inchangées. Aucune validation d'échelle absolue.
- Test avant correction : reviewGeometry avec material.boardWidth=0.19,
  config.width absent. Sortie observée 0.15 au lieu de 0.19.
- Cause confirmée : constante de repli 0.15 au lieu du profil réel du matériau.
- Correction : web/scene/geometry-review.js lit patternProfile ; longueur exposée.
  Aucun changement au renderer, aux textures ou à la caméra pour ce correctif.
- Régression : tools/defect-report.check.mjs ; défaut 190 mm, échelle ×2,
  override 90 mm, longueur 1,80 m, scène et masques inchangés.
- Résultat visuel : better pour les données du diagnostic ; rendu parquet same.
- Statut : RESOLVED (diagnostic uniquement).

## CASE #002 — diagnostic périmé lors du retour à un rendu en cache

- Date : 26 octobre 2026.
- Scène : chambre ; produits BTRPF39009 et CHENF36014.
- Symptômes : D4 MODERATE et D5 MODERATE, center, dans les overlays.
- Séquence confirmée : A (90 mm, 17°) → B (150 mm, 90°) → A depuis le cache.
  A était affiché, mais snapshot et comparaison unlit utilisaient B.
- Preuve avant : hit=true, expectedWidth=0.09, width=0.15, angle=90,
  dernier uniforme du diagnostic sans lumière=0.15.
- CONFIRMED CORRECT : D3 PASS — calibration de la chambre préservée ;
  la correction ne change pas la géométrie ni la logique du cache.
- Cause : lire config du dernier passage GPU au lieu du profil/angle associés
  au frame actuellement affiché par l'adaptateur.
- Correction : diagnosticSnapshot et diagnosticUnlitFrame reçoivent activeProfile
  et activeAngle. La configuration normale du moteur reste inchangée.
- Régression : tools/diagnostic-state.check.mjs. Après : width=0.09,
  angle=17, uniforme=0.09, cache toujours utilisé.
- Résultat visuel : better pour overlays/unlit ; rendu principal same.
- Statut : RESOLVED (instrumentation introduite et corrigée avant livraison).

## CASE #003 — contours irréguliers dans la photo privée, diagnostic ouvert

- Date : 26 octobre 2026.
- Scène : photo privée du salon avec tapis.
- Symptôme : D8 MODERATE ; rectangle normalisé x=0,35–0,60, y=0,42–0,49 autour du bas du meuble TV.
- Statut : OBSERVED, non résolu par cette mission.
- CONFIRMED CORRECT : aucun PASS visuel global ; ne pas inventer de cause.
- Prochain test : pack original/render/masks en résolution source, distinguer
  contour source incomplet et filtrage du compositing. Rapport localisé fourni
  dans review/defects/case-004-private ; cause non encore confirmée.
- Aucun correctif de segmentation, caméra ou lumière appliqué à partir de ce
  seul constat. Les nouvelles captures sont privées, dans review/defects/.

## CASE #004 — ancien overlay visible après import d'une nouvelle photo

- Date : 26 octobre 2026.
- Scènes : pièce de démonstration puis nouvelle photo ; aucune analyse réelle
  dans le test (réponse 503 simulée).
- Symptôme : D1 BLOCKING dans l'outil de diagnostic, toute l'image :
  masque de la scène précédente affiché/exporté sur une nouvelle photo.
- CONFIRMED CORRECT : D3 PASS — aucune calibration modifiée par la correction ;
  rendu principal préservé. Ce PASS ne juge pas les fuites de la nouvelle photo.
- Preuve avant : engineScene=piece-claire, currentScene=uploaded,
  refused=false, hidden=false.
- Cause : snapshot autorisé dès que le renderer avait une scène prête, sans
  vérifier qu'elle correspondait à la photo courante ; overlay non masqué en erreur.
- Correction : garde de scène courante et d'état de la photo ; effacement de
  l'overlay en attente/erreur. Aucun changement au pipeline d'analyse.
- Régression : tools/diagnostic-source-state.check.mjs ; import réel d'une autre
  image locale, export refusé et overlay masqué jusqu'à la bonne scène.
- Résultat visuel : better, plus d'ancien masque sur la nouvelle photo.
- Statut : RESOLVED (instrumentation avant livraison).
## CASE #005 — D2-A, classes de premier plan déjà disponibles mais ignorées

- Date : 27 octobre 2026.
- Cause confirmée : OBJECT_CLASSES omettait notamment cushion/pillow, ottoman,
  box, pot et vase présents dans la configuration ADE20K locale et les sorties
  enregistrées. Leur protection dépendait parfois de trous fortuits du sol.
- Correction : réutiliser ces classes dans foreground.py, sans nouveau modèle.
- Régression : test_existing_ade20k_floor_objects_do_not_depend_on_enclosed_holes,
  test_ground_classes_never_become_objects, test_resized_labels_keep_rug_and_thin_objects.
- La qualité d'occlusion reste non calibrée ; floor_scene.py expose cette limite
  et préfère approximate_render pour une occupation significative.
- Statut : RESOLVED pour la sélection des classes, pas une garantie de segmentation.

## CASE #006 — D2-D, supports absents des masques de catalogue

- Date : 27 octobre 2026.
- Observation : DEBUG MASKS laisse verts les supports arrière des chaises et
  une partie du pied du canapé. D3/D4/D6 configurés conservés.
- Cause confirmée : anciens polygones incomplets ; les classes issues du modèle
  déjà installé contiennent les supports. Aucun défaut de projection nécessaire.
- Correction : actualisation additive des occluders par une commande générique,
  idempotente, sans modifier camera/planes/floorZones/light. Deux scènes revues.
- Régression : obstacle-scene.check.mjs : 260 + 1527 + 1883 pixels opaques
  nouvellement protégés, erreur RGB face à la photo = 0.
- Résultat visuel : better sur canapé et table/chaises ; petits contacts restent
  candidats à la revue. Pas de modèle ajouté ou téléchargé.
- Statut : RESOLVED pour les supports contrôlés.

## CASE #007 — D2-C / D8, contours de contact approximatifs

- Date : 27 octobre 2026.
- Observation : marches et petites fuites sur les contours du lit, du tapis
  et des consoles. La grille ne justifie aucun changement de perspective.
- Correction bornée : photo-guided foreground matte, bande 2 px source,
  graines fiables cherchées sur 4 px, conservation des branches fines.
  Pas de dilation, flou global ou recalcul du plan. Masque raffiné mis en cache.
- Régression : obstacle-occlusion.check.mjs, 12 configurations WebGL/Canvas,
  DPR/resize, correction manuelle et A/B/A. Pièce dégagée/terrasse identiques
  pixel par pixel dans les packs de revue.
- Alpha audité : straight alpha, même formule CPU/GPU ; aucun D2-B/D2-E confirmé.
- Résultat : better sur les bords contrôlés ; CASE #003 sous la console de
  la photo privée reste PARTIAL/OPEN. Ne pas le présenter comme totalement corrigé.
- Dossier de preuves privé : review/occlusion-obstacles/.

## CASE #008 — S3/S4/S8, D1/D2/D8 : perte des cellules lors de la sérialisation

- Date : 27 octobre 2026.
- Observation : dégradation récurrente des bords dans les masques avant matière
  ou éclairage. Grilles S1/S2 conservées.
- Cause démontrée : contours OpenCV aux centres des pixels utilisés comme
  sommets de surfaces Canvas ; couverture partielle perdue après normalisation.
- Test avant : contour-roundtrip.check.mjs échoue : rectangle 66 pixels,
  trou 165, diagonale 76, bord image 39 ; pied fin également non exact.
- Correction : primitive commune mask_contours.cell_polygons, bords exacts
  des cellules ; foreground.polygons et floor_scene.mask_zones la réutilisent.
  Aucun changement de caméra ni de plan, pas de dilation ou exception par photo.
- Tests après : 0 erreur sur rectangle, pied d'un pixel, trou, diagonale,
  bord et masque aléatoire ; tests topologiques incluant îlot imbriqué.
- Revue : 11 scènes rejouées après cette seule correction, avant correction alpha.
  Gain local de couverture aux contacts, pas de résolution de tout contour source.
- Statut : RESOLVED pour la sérialisation.

## CASE #009 — S4/S8, D8 : alpha des pixels mixtes supprimé

- Date : 27 octobre 2026.
- Cause démontrée : refineOcclusion utilisait fg < bg ? 255 : 0 ;
  la couverture photo partielle devenait une découpe binaire.
- Test avant : attendu 64 / 191, obtenu 0 / 255.
- Correction : alpha estimé entre graines couleur fiables, garde de contraste
  et de résidu ; zones ambiguës conservent le prior, branches fines préservées.
- Test après : 63 / 191, prior immuable et déterministe, pas de flou global.
- Revue : contacts de chaise/canapé plus graduels ; les bosses grossières sous
  le meuble TV privé demeurent PARTIAL. Pas d'unmixing complet du foreground.
- Régression : 12 configurations WebGL/Canvas DPR1/2 resize, masques/scènes A/B/A,
  Retirer/Terminé sans réanalyse ; caméra/motifs inchangés.
- Statut : RESOLVED pour la quantification, segmentation source encore ouverte.

## Revue produit S1–S8 associée

- docs/visual-quality-spec.md ; rapports privés review/visual-quality-s1-s8/.
- 11 scènes, original/avant/final, grilles, masques, neutre, sans lumière,
  cellules, crops near/mid/far/objets/frontière ; captures 1440 et 390.
- S6 NOT_EVALUABLE faute de référence fabricant. S7 reste PARTIAL.
- Couloir FAILED : original conservé, aucune fausse frame présentée.
- Notes assistant /5 et test qualitatif ne remplacent pas la validation humaine.
- Aucune image privée versionnée, aucun nouveau modèle/recherche depth, aucun push.

## CASE #010 — Huit captures utilisateur : annotations du catalogue incomplètes

- Reproduction : cuisine-ilot, cuisine-blanche, terrasse-mer, couloir-enfilade,
  premibel-entree, salle-a-manger-meublee, bureau-meuble, premibel-chambre.
- Cause : zones de sol trop courtes, exclusions de mobilier contenant du sol,
  jonctions mur/fenêtre grossières. Le moteur respecte ces mauvaises annotations.
- Correction : annotations en pixels de la photo originale dans
  web/data/scene-mask-reviews.json ; application par un outil commun hors ligne.
  Aucun coefficient par scène dans le renderer, aucune modification de caméra,
  plan, dimensions produit, shader, matériau ou algorithme lumineux.
- Le tapis sous le bureau et la grille de cuisine sont présents dans les
  originaux : les préserver. Ne pas les traiter comme de l’ancien parquet.
- L’outil échantillonne les centres des pixels. cv2.fillPoly sur les contours
  des cellules aurait déplacé les autres limites d’un pixel ; ce chemin rejeté
  n’est pas utilisé. Les fragments détachés de moins de neuf pixels ne deviennent
  pas des zones de sol supplémentaires soumises à la validation de géométrie.
- UI : le résumé produit et le catalogue utilisent le motif du profil de rendu
  quand le champ commercial manque, puis un libellé de repli. Plus de undefined.
- Validation : points photo inspectés (sol, pieds, plinthes, tapis), invariants
  caméra/plans/lumière, rejeu stable des annotations ; huit scènes dans le vrai
  moteur à 1440 et 390 px ; avant/après/neutre/grille dans review/defects/.
- Comparaison privée et rapports S1–S8 : review/eight-scene-review/index.html,
  générés par tools/build-reviewed-scenes.mjs. Aucune photo versionnée.
- Limites : halos et petits fragments près des supports, franges, lit et pouf
  restent PARTIAL. Pas de certification globale du photoréalisme, pas de gain
  automatique sur les photos importées. Terrasse : libellé corrigé uniquement.
- Trello : « Corriger les découpes des pièces du catalogue » ;
  « Préserver pieds, tapis et plinthes » ; « Corriger le libellé terrasse » ;
  « Vérifier les 8 scènes sur mobile ». Contours fins encore à reprendre.

## CASE #011 — Rejet utilisateur de CASE #010 : corrections trop ponctuelles

- L’utilisateur constate encore le défaut dans toutes les pièces. Le serveur
  renvoie bien les fichiers locaux modifiés avec Cache-Control no-store ;
  l’inspection des onglets ne justifie pas d’attribuer le retour au seul cache.
- Cause commune confirmée : silhouettes déjà soustraites de floorZones puis
  répétées dans occluders. Affiner le deuxième masque ne peut pas récupérer
  les pixels dont le premier masque interdit déjà la pose.
- Compilation catalogue : reconstituer le support derrière le foreground dans
  l’enveloppe du plan existant ; une zone géométrique par plan, avec les découpes
  précises dans le matte. Ne pas valider chaque îlot de quelques pixels comme
  s’il constituait une nouvelle pièce. Caméra, plans, dimensions et lumière
  déclarée restent identiques.
- Affinage commun hors ligne, objet par objet : un GMM global apprend le brun
  des meubles et conserve ensuite du sol brun autour du pouf clair. Le traitement
  local conserve des graines fiables et les supports fins. Les grilles fixes
  restent protégées. Aucun traitement dans le chemin du changement de produit.
- Six scènes meublées ont reçu les masques relus. Le couloir et la terrasse
  n’ont aucun objet à affiner et leurs masques ne sont pas modifiés par ce lot.
- Les labels manquants ont été produits avec le OneFormer/OpenVINO déjà installé,
  en mode hors ligne, une seule session de chargement ; pas de nouveau modèle,
  pas de téléchargement, pas de recherche depth, pas de nouvelle caméra.
- Deuxième cause commune : une photo C contient déjà aF+(1-a)Bancien. L’utiliser
  comme couleur foreground puis appliquer a à nouveau conserve de l’ancien bois.
  La plaque de compositing utilise P=(C-tBancien)/(1-t), t étant la couverture
  réellement remplacée. Uniquement les bords à estimation fiable sont corrigés ;
  pixels opaques, photo originale, entrée lumière et retouches explicites restent
  préservés. WebGL et Canvas utilisent cette même plaque, calculée avec les masques
  et réutilisée entre les produits ; aucune nouvelle branche du shader.
- Tests : inverse blend connu (a=.25/.5/.75, couverture .5/1), source immuable,
  alpha mixte, suppression/annulation/validation mobile sans réanalyse, 12 cas
  WebGL/Canvas DPR1/2, supports réels préservés, huit pièces à 1440/390, huit tests
  Python ciblés. Captures : review/defects/common-after-*.
- Revue dans l’interface normale et onglet DEV existant rechargé sur la salle
  à manger. Comparatif depuis CASE #010 : review/common-foreground-review/.
- Limite visuelle explicite : des contours grossiers demeurent sous le lit,
  autour du pouf et de certains petits objets. Une réussite de test n’est pas
  une validation globale S1–S8. Le résultat global reste NEEDS_WORK.
- Trello : « Affiner les contours des objets » ; « Supprimer les halos d’ancien
  parquet » ; « Vérifier ordinateur et mobile ». Ne pas cocher « rendu final validé ».
