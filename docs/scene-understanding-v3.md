# Scene Understanding V3

V3 extends the real imported-photo analysis path. It does not replace the renderer,
copy Roomvo, use a depth model, transmit photos to an external AI service or enable walls.
Roomvo is a visual benchmark only. The existing catalogue camera calibrations are preserved.

## CURRENT PIPELINE — audit

Before V3, `pipeline._segmentation_experimentale` ran the installed semantic model,
`floor_scene` refined visible floor, estimated several camera candidates, serialized
visible components and added semantic foreground/openings. Fine foreground authoring
existed in `photo_mask_refiner`, but was only used by the offline catalogue compiler.
A furniture silhouette therefore constrained both floor support and compositing.

The installed OneFormer ADE20K model already supplies floor, furniture, rug, plant,
chair, bed, cushion, pouf and structural classes. `foreground.OBJECT_CLASSES` is the
explicit lookup. Openings of unknown role are conservative exclusions. No additional
model has been selected or downloaded. Missing semantic parts remain a real limitation;
refinement cannot reconstruct an entirely absent object reliably.

## ROOM LAYOUT

`room_layout.estimate_room_layout` extracts structural floor/wall adjacency, line
segments on that boundary, an observed floor envelope and recovered support behind
semantic foreground. Unknown wall/recess pixels are not extrapolated as new visible floor.
The envelope is a support domain, not measured room dimensions. Its confidence is an
evidence ratio, not a calibrated probability. Horizon, measured vanishing directions and
the existing camera candidate list are attached by `floor_scene` after camera solving.

## FOREGROUND / THIN OBJECTS

Logical foreground is separate from physical support. Original-resolution photo-guided,
per-component GrabCut refines uncertain silhouettes. Hard interior seeds and thin local
ridges retain supports; the object's own convex envelope permits recovering a false
concavity inside a cushion. RGB still distinguishes such a concavity from real floor
between chair legs. A single optimization round replaces three rounds after
checking both opposite cases. Structural exclusions remain separate fixture masks.

Trace: original upright RGB → model working resolution (landscape 352×512 or square
512×512 with the installed OpenVINO profile) → nearest-neighbour semantic labels at
original resolution → floor morphology → independent semantic foreground/ridges →
original-RGB refinement → normalized exact pixel-cell polygons → browser mask raster →
local edge alpha → GPU mask texture. A thin part absent from the low-resolution model
can still be missed; no claim of arbitrary thin-object recovery is made.

The browser prepares up to 1600×1200 pixels on desktop and 1100×825 on small screens.
Normalized geometry is shared; subpixel branches at those resolutions are a practical
limit. Existing GL/Canvas/DPR and one-pixel-support checks protect this path.

## CAMERA / FLOOR PLANE

Existing multi-candidate CameraSolver and metric FloorPlane are reused. The camera mask
recovers semantic foreground support rather than tracing furniture as room walls.
Quality Pass receives the Fast Pass `PerspectiveEstimate`; it cannot independently move
the camera or plane. Actual camera/plane equality is tested, not inferred from similar images.

A reproduced rejection (`camera-plane-disagreement`) exposed an old fallback defect:
a single off-axis rail VP was combined with a horizontal reference axis as if those
axes were orthogonal. The fallback now uses a camera-horizontal reference basis. The
measured rail VP remains diagnostic evidence; floor yaw is uncertain. A reliable measured
orthogonal VP pair continues to use its existing reference plane. Pattern shaders and
physical dimensions are unchanged.

## QUALITY GATE

`scene_quality.scene_quality_gate` returns AUTO_RENDER, APPROXIMATE_RENDER,
MANUAL_REQUIRED or FAILED_GRACEFULLY, with the eight requested quality fields.
Unknown foreground/illumination confidence stays null. It never becomes a floor score.
S1 FAIL, S2 FAIL or S4 BLOCKING override high numeric scores. Non-finite geometry fails
gracefully. Invalid projections or genuinely insufficient measured scores require manual
correction. Missing confidence prevents AUTO_RENDER. Empty/no-floor outputs also carry
an explicit manual decision. Legacy lowercase API status names remain compatible.

Photo-quality rejection occurs before segmentation. Imported uncertain scenes retain
plain French messages and the existing Ajuster action. Adding/removing/undoing/finishing
manual edits does not call inference again.

## ILLUMINATION / CONTACT SHADOWS

The existing `shading.js` is the IlluminationEstimator: mask-weighted, downsampled,
low-frequency luminance gain; bounded light tint; filtered light residuals. Dark residuals
remain distinct `shadow` maps with morphological rejection of narrow old joints/wood grain.
No raw per-pixel old-floor RGB is multiplied into the new material.

V3 corrects synthetic contact darkening: a mask edge alone no longer creates a black
outline. Boundary contact modulation requires an observed luminance deficit in the photo.
The independent observed shadow residual is retained. Synthetic checks cover uniform
illumination, a real dark patch, old tile joints, large sunlight and grain suppression.
Wide old-material variation can still be confused with illumination; no reflectance
separation ground truth or ray tracing is claimed.

## COMPOSITOR

Original photo → metric new material × scene illumination × observed contact maps →
foreground visibility. Binary foreground is authoritative; the browser uses a separate
local photo-guided alpha near mixed edges. Convention: straight RGB/alpha, GL context
`premultipliedAlpha:false`, SRC_ALPHA / ONE_MINUS_SRC_ALPHA, same interpolation in Canvas.
The existing inverse-composited backing plate removes old-floor colour already mixed into
edge pixels, so foreground alpha is not applied twice. Lighting always samples the original
source, never that corrected plate. Opaque foreground pixels keep their original colour.

DEV controls now include lighting OFF, neutral floor and foreground OFF. The latter
changes only a diagnostic draw uniform/config; it does not edit masks or production shaders.

## FAST PASS / QUALITY PASS

The visualizer opts in using `X-Scene-Passes: fast-quality`. One segmentation produces
Fast SceneData with coarse foreground/layout and the existing camera. A bounded background
worker refines masks from the same in-memory arrays without invoking `segment()` again.
The JSON response contains an opaque quality capability. GET reads pending/ready/failed;
DELETE releases it. At most two jobs, one quality worker, logical expiry 180 seconds.
Completed jobs retain JSON only. No photo is saved by the service. This expiry applies
to internal refinement results, not the user's simulator/QR link.

The browser polls through `room-analysis-client`, applies the same projection and uses
its existing 180 ms transition. Current product choice is retained. A new photo or manual
edit increments the generation and supersedes late quality results. Network failure keeps
the first usable result. Product switches use prepared browser scene/material caches only.
Capacity saturation explicitly reports unavailable refinement rather than claiming quality.

The refinement registry is in-process. Multi-worker deployment needs sticky routing or a
project-controlled shared job service; this mission does not build cloud infrastructure.

## VISUAL MATRIX / PERFORMANCE / MOBILE

Generated private artifacts: `review/scene-understanding-v3/index.html`, per-scene reports,
original/masks/layout/grid/neutral/illumination/contact/unlit/final images and crops.
`matrix.json` records five compilation runs per scene from cached semantic labels, explicitly
NOT model inference or end-to-end latency. `live-benchmark.json` records actual API imports
with inference, first/final browser render, stage timings and product switching, five runs
per representative case, including 390×844. First process run and subsequent warm median,
p95 and max are kept separately. Model cold load/warmup timings come from the running
model's measured `modelWarmupMs`; they are not replaced with a warm inference time.

The earlier unoptimized live run is kept as `live-benchmark-before-optimization.json`.
Do not compare compilation-only times with live upload-to-render measurements. Targets
2–4 seconds and <100–150 ms are goals, not a guarantee. New material preparation is distinct
from switching to a previously prepared material.

## REGRESSIONS / TESTS

Tests cover support under objects, unknown structural recesses, original-resolution thin
legs, false object concavities versus real gaps, stable camera/plane between passes,
blocking evidence, unknown confidence, queue bounds, real HTTP progressive contract,
quality/manual/product races, no reanalysis, observed shadows, old-joint suppression and
GL/Canvas compositing. Catalogue calibration JSON is not rewritten by V3.

The old `product-concept.check.js` reports 13 failures against both the untouched 8e03fea
HTML and V3 (capture-fallback assumptions). Logs preserve that comparison; these are not
reported as passing. Real browser product/import/edit checks are the regression evidence.

## FILES / GIT / LIMITATIONS / VERDICT

Branch: `feature/scene-understanding-v3`. Local commits only. No push, main merge or rebase.
Photos, review images, cached labels and private API responses remain ignored and uncommitted.

Limits: single-photo metric scale is assumed; semantic omissions remain possible; indoor
ADE20K floor inference fails on the terrace example; very dark input can lack usable floor;
foreground and illumination confidences are uncalibrated. Those cases require correction
or stay approximate. S6 finish/reflections and universal photorealism are not certified.

Final measured results and human-review verdict are recorded below after validation.


An enlarged hard-core erosion radius was evaluated on all 13 cases and rejected:
it recovered some old-floor halo but damaged cabinet contact silhouettes. The safe
six-pixel core plus independent thin ridges remains. Failed experiment artifacts stay
in ignored `review/scene-understanding-v3-core-candidate`, not production catalogue data.
Remaining D2 issues include a missing part of a plant stem, residual coarse furniture
contact masks and chair-foot fringes. These are not certified as solved by the V3 gate.

## Rapport final de validation

Périmètre livré : analyse automatique des **photos importées**. Les masques pré-calculés des pièces de démonstration ne sont pas réécrits dans ce lot ; leurs défauts de détourage peuvent donc rester visibles.

Revue locale : `review/scene-understanding-v3/index.html`.
Les images et la photo fournie restent privées, hors Git et hors dossiers servis publiquement.
La provenance photographique de la photo fournie n'est pas certifiée.

| Domaine | Résultat |
| --- | --- |
| CURRENT PIPELINE | Une inférence sémantique existante, puis compilation physique et visibilité séparées. |
| ROOM LAYOUT | Frontière structurale, directions de plinthes, enveloppe et support récupéré sous les objets. |
| FOREGROUND | Raffinement générique raccordé aux imports ; concavité fausse du coussin récupérée, halos réduits. |
| THIN OBJECTS | Tests dédiés de supports fins conservés ; une partie de tige reste manquante sur la chambre. |
| CAMERA / FLOOR PLANE | Identiques entre les passes sur 11 scènes compilables ; repli hors axe corrigé ; 2 cas sans plan. |
| QUALITY GATE | Quatre décisions, huit champs ; aucune certitude inventée pour les objets, l'échelle ou la lumière. |
| ILLUMINATION | Estimation basse fréquence conservée, profilée et recalculée avec le masque qualité. |
| CONTACT SHADOWS | Les contours sombres exigent un déficit observé ; anciens joints rejetés dans les tests dédiés. |
| FAST PASS | Premier vrai rendu, sans image de remplacement ; la photo apparaît avant l'analyse. |
| QUALITY PASS | Même caméra, transition courte ; produit conservé ; retouche manuelle prioritaire ; refus final retire le sol provisoire. |
| VISUAL MATRIX S1–S8 | 13 scènes, diagnostics et crops ; appréciations PARTIAL / NOT_EVALUABLE, aucun label de réalisme garanti. |
| PERFORMANCE | 20 imports réels, 5 par cas ; première exécution, médiane/p95/max à chaud et étapes détaillées conservés. |
| MOBILE | Flux complet en Chrome émulé 390×844, y compris correction et changement de produit ; pas de mesure sur téléphone physique. |
| REGRESSIONS | Calibrations du catalogue préservées ; refus des anciens plans invalides explicitement testés. |
| TESTS | 523 pytest passent ; tests navigateur/GL/Canvas, alpha, joint/ombre, flux et projection ; détails ci-dessous. |
| FILES | Services layout/gate/jobs ; pipeline/import ; compositing et diagnostics ; outils de revue et tests. |
| GIT | Branche locale `feature/scene-understanding-v3`, aucun push, merge ou rebase de main. |
| LIMITATIONS | Contours de contact encore partiels, échelle supposée, terrasse et photo sombre non reconnues, confiance objets non calibrée, délais variables. |
| VERDICT | SCENE_UNDERSTANDING_V3_READY_FOR_HUMAN_REVIEW — progrès visibles sur plusieurs scènes complexes, sans certification Roomvo-level. |

### Mesures finales sur le PC local

Modèle à froid : chargement **55,8 s**, premières inférences/préchauffage **18,3 s**, total **74,1 s**.
Le premier import utile après cette préparation a encore pris **17,4 s** sur le cas initial.
Ces coûts restent affichés ; ils ne sont pas remplacés par les temps à chaud.

| Cas / viewport | Premier rendu chaud médiane / p95 / max, s | Final chaud médiane / p95 / max, s | Produit préparé médiane / p95 / max, ms |
| --- | --- | --- | --- |
| cuisine-ilot · 1440×900 | 3.58 / 4.91 / 5.11 | 5.61 / 6.92 / 7.09 | 84.00 / 404.10 / 983.00 |
| owner-photo · 390×844 | 3.75 / 3.78 / 3.79 | 7.86 / 8.42 / 8.50 | 63.00 / 100.60 / 165.00 |
| owner-photo · 1440×900 | 5.59 / 7.06 / 7.15 | 10.86 / 13.23 / 13.60 | 100.00 / 140.80 / 166.00 |
| piece-claire · 1440×900 | 3.90 / 4.09 / 4.12 | 5.62 / 7.41 / 7.72 | 67.00 / 83.00 / 83.00 |

Les objectifs 2–4 s et <100–150 ms ne sont donc **pas tenus partout**, notamment au p95.
Une nouvelle matière demande aussi sa préparation : elle ne fait pas partie des temps « déjà préparé ».
Chaque import a déclenché un seul POST d'analyse ; les cinq changements de produit suivants n'en ont déclenché aucun.

Les étapes détaillées sont dans `performance.json` / `live-benchmark.json`.
Les durées backend `segmentation` et `occlusion` englobent des sous-étapes : **ne pas les additionner**.
Le foreground et le floor proviennent de la même inférence, pas de deux modèles exécutés séparément.
Les médianes par nom du navigateur sont identifiées comme telles, pas présentées comme échantillons bruts de chaque frame.
`lighting-stage-benchmark.json` mesure séparément illumination et résidus/contact, 5 fois par cas sur les vrais pixels/masques préparés ; ce n'est pas une latence upload→image.

### Vérifications

- `pytest -o addopts='' -q` : **523 passed**, deux avertissements de dépendances.
- Ruff application + ajouts V3 : passe.
- Mypy application : passe ; outils V3 vérifiés avec `--follow-imports=silent`.
- Flux fast/quality : caméra stable, choix produit conservé, correction prioritaire, refus final sans parquet périmé, en WebGL **et** Canvas.
- Profil réel : 20 imports ; profil couches lumière : 20 mesures isolées ; compilation : 5 passages par scène à partir des labels en cache.
- Projection, frontières, occlusions, DPR/redimensionnement, matériaux, alpha/matting, lumière et suppressions d'anciens joints : rapports locaux conservés.
- Les fixtures historiques de caméra ont été rendues cohérentes avec leur quad ; un plan invalide reste refusé, jamais rendu pour satisfaire le test.
- `product-concept.check.js` : **13 échecs hérités identiques à 8e03fea**, vérifiés sur le HTML de départ. Cette vieille batterie de captures n'est pas présentée comme réussie.

Le verdict autorise une **revue humaine**, pas une mise en production avec garantie de photoréalisme.
Les défauts restants sont visibles dans les comparaisons et ne sont pas masqués par un PASS automatique.
