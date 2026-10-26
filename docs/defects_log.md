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