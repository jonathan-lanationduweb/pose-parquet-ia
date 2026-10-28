# Contact shadow + lighting V4

## IMPLEMENTATION

- Audit de départ : `feature/scene-understanding-v3`, `d129120`, cinq derniers commits inspectés ; modification de logo préexistante conservée.
- Avant : `renderer-gl.js` mélangeait les zones directement sur la photo par alpha ; le fragment métrique générait le matériau et la lumière JS (`shading.js` / worker). `uMask` empaquetait zone R, sol G, objets B.
- Après : même génération des lames et même projection, mais cible de rendu intermédiaire puis passe finale dans `contact-compositor.js` : photo + parquet × lightLayer, contact, masque sol doux, exclusion nette des objets.
- Feather : 25 échantillons, rayon `1.5*2`, `smoothstep(.55,.65,blur)`. Contact : 25 échantillons à 12, `clamp(wide-sharp,0,1)`, `mix(1,.55,contact*.45)`. Aucune constante par scène ; aucune optimisation du noyau.
- Python : Rec.709 BGR ; Gaussian luma 25, masque 15, clamp .4–1.8, mélange neutre hors sol. Statistiques mean/std BGR et Lab collectées. `occluder_mask` conservé, volontairement non utilisé par la formule fournie.
- `SceneData.light.lightLayer` transporte le calque calculé dans les deux passes de l’import FastAPI. Les scènes pré-calculées sans ce champ gardent leur éclairage antérieur et bénéficient du nouveau compositing.
- Les variations spatiales et résidus de l’ancien éclairage ne sont pas appliqués une seconde fois lorsqu’un lightLayer Python existe. Exposition globale, teinte globale bornée et relief du matériau existants restent dans floorRender. Les statistiques Lab préparent l’harmonisation ; aucune recolorisation additionnelle inventée.
- `uPhoto` reçoit la plaque photographique existante (`source` / `masks.compositeSource` lorsque la correction manuelle du foreground l’exige). `uFloorRender` est la cible réelle du renderer ; les masques viennent de `createSceneMasks` ; lightLayer vient de Python.
- Tous les samplers du composite lisent des UV image. Le canevas source est ensuite affiché par l’unique ViewTransform existant ; pas de seconde transformation ni de `gl_FragCoord / viewport` dans le composite. `uTexel` dépend de la résolution réelle des masques rasterisés, pas de la taille CSS.
- Canvas conservé : mêmes 25 positions, mêmes constantes, exclusion et multiplication. Diagnostics DEV pour les sept couches, via le panneau existant.

## MINIMAL REPAIRS TO PROVIDED CODE

1. Python : remettre sur une même expression les affectations coupées après `=` ; aucune formule ni constante remplacée.
2. Adaptation de données : l’entrée du projet est RGB uint8, convertie en BGR contigu ; masques booléens convertis en float32 [0,1] ; contrôle de dimensions/valeurs finies avant OpenCV.
3. Transport : le calque fourni a trois canaux identiques. PNG RG encode lossless un entier gain×10000 ; le décodage restaure le gain float RGB, y compris >1. Lab complet reste côté Python ; ses statistiques de sol voyagent dans SceneData, sans envoyer une seconde photo Lab.
4. GLSL : `#version 300 es`, nom de varying `vUv` adapté au quad image existant ; inversion Y uniquement pour la texture cible FBO, à origine basse ; textures R8 extraites des canaux du masque existant.
5. Intégration : disponibilité alpha du floorRender pour ne pas peindre un produit absent ; exclusion/feather déplacés dans la passe finale pour éviter une double application ; ancien éclairage spatial désactivé seulement quand le lightLayer fourni le remplace.
6. API interne : préparation asynchrone du décodage PNG, sans changer le contrat synchrone des scènes sans calque ; relais du diagnostic dans l’adaptateur DEV ; doublon préexistant de propriété `mid` retiré.

Aucun changement d’algorithme sur les deux blocs, aucun nouveau modèle, solveur, motif ou matériau. `uImageSize` est fourni comme dans la spécification ; le shader fourni ne l’utilise pas directement et GLSL peut optimiser cet uniforme, contrairement à `uTexel` et aux cinq samplers actifs.

## VISUAL

Revue privée locale : `review/contact-shadow-lighting-v4/index.html`.
Huit scènes, huit couches, avant/après desktop et 390. Images examinées : objets opaques conservés, léger contact autour des objets, lumière réellement appliquée ; pas de retour visible des joints/grains fins dans les cartes observées.
Les erreurs de masque héritées (contact sous canapé/meuble, petit reste clair sous un pied, partie de tige) restent possibles : cette mission n’autorise pas à changer la segmentation. Une zone de masque erronée ne peut pas être réparée par ces deux formules.
Les captures `live-ui-*` proviennent des vrais imports API ; les sous-dossiers de cas montrent le renderer et ses couches. Les captures `ui.png` de ces fixtures seules montrent l’état de la page, pas un parcours d’import.

## PERFORMANCE

Médianes en ms ; 8 scènes × 10 frames chaudes par viewport/version. Temps frame = appel réel, copie Canvas et attente GPU (`gl.finish`), **pas un temps CPU pur**. GPU mesuré par `EXT_disjoint_timer_query_webgl2`, sans disjoint accepté. Coût GPU de la passe finale : 8×5 mesures. Chrome sur ce PC ; aucune mesure de GPU physique de téléphone.

| Viewport | Frame avant | GPU total avant | Frame après | GPU total après | GPU composite seul après |
| --- | --- | --- | --- | --- | --- |
| 1440 | 12.75 | 3.26 | 14.05 | 7.60 | 3.99 |
| 390 | 8.35 | 2.69 | 11.25 | 5.74 | 3.15 |

Les premières séries sans timer GPU restent archivées ; cette table utilise les séries instrumentées comparables. Le coût supplémentaire est explicite. Pas de pré-calcul des noyaux à ce stade.
Canvas : médiane ~793 ms desktop, ~804 ms à 390, 8×3 frames. Fallback fonctionnel mais lent ; ne pas le présenter comme un chemin interactif à 60 Hz.

## MOBILE

390×844, DPR2, émulation Chrome. Deux imports réels après préchauffage du modèle : desktop premier/final 5.692/9.654 s, mobile 2.985/5.665 s ; un POST chacun, changements de produit sans nouvelle analyse, aucun débordement horizontal. Ce ne sont pas des percentiles ni des temps garantis.

## REGRESSIONS

Caméra, FloorPlane, ViewTransform et motifs inchangés. Rotation et changement de produit conservent les mêmes plans. Alignement testé en redimensionnement 1440→390→1440, DPR1/2, WebGL/Canvas. Les retouches manuelles restent prioritaires sur une réponse qualité tardive.

## TESTS

- Python complet : **531 passed**, deux avertissements de dépendances.
- Ruff et Mypy application : passent.
- `test_lighting_layers_v4.py` : 8 tests, référence numérique, noir/sombre/clair, petit masque, dimensions, gains, absence de NaN, joints fins et transport.
- Contrat HTTP fast/quality : lightLayer présent sur les deux passes, une seule inférence, géométrie conservée.
- `compositing-alignment-v4.check.mjs` : **57 600 canaux comparés**, écart maximal **0.501/255**, feather/contact et orientation FBO vérifiés sur le vrai shader.
- `contact-shadow-lighting-v4.check.mjs` : huit scènes desktop/390, WebGL et Canvas ; pixels objets opaques inchangés ; éclairage différent de la version sans lumière sur les huit scènes.
- Occlusions/pieds fins, DPR et resize : passe ; fast/quality WebGL : passe ; moteur/motifs/lumière existants : passe ; projection : voir log privé.

## FILES

Python : `app/services/lighting_layers.py`, raccord `floor_scene.py`, `app/schemas/scene_data.py`, tests V4 et contrat HTTP.
Web : `contact-compositor.js`, `renderer-gl.js`, `renderer-canvas.js`, `renderer.js`, `schema.js`, adaptateur local et panneau DEV ; une seule ligne de relais DEV dans le HTML.
Revue : scripts/outils V4, rapport ; aucune photo ajoutée à Git.

## GIT

Branche `feature/contact-shadow-lighting-v4`. Commits locaux logiques ; publication de cette branche seulement après validation. Aucun merge/rebase de main, aucun force push. Modification du logo antérieure conservée séparément.

## VERDICT

`CONTACT_SHADOW_LIGHTING_V4_READY_FOR_HUMAN_REVIEW` pour l’intégration des mécanismes fournis.
Limites : masques hérités imparfaits, fallback Canvas lent, téléphone physique non mesuré ; aucune garantie globale de photoréalisme.
