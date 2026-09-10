# Autonomie du rendu — audit et plan d'extraction

> **ACTIF.** Fait foi sur : ce que le moteur de rendu est réellement, quelle
> est la dépendance d'exécution restante vers `pose-parquet.com`, quel noyau
> minimal l'extraction demande, et dans quel ordre. Audit fait le
> **10 septembre 2026** (LOT UX.2A), en lecture seule des deux dépôts.
>
> **Aucune extraction n'a été faite.** Aucun fichier copié, aucun asset
> déplacé, `ENGINE_URL` inchangé, l'iframe en place, `VisualizerAdapter`
> intact. Ce document est un plan, pas un début de migration.

## 1. Le seul couplage restant

`tools/product-concept.html` charge hors écran
`../../pose-parquet.com/outils/studio.html?perf=1` dans une iframe de même
origine, et pilote le moteur par `window.__studio`. C'est **la seule
dépendance d'exécution** vers le dépôt gelé : vérifié en servant le
visualiseur avec et sans le front à côté (`mode: "live"` contre
`mode: "static"`).

Ce qui n'en est **pas** une, contrairement à ce qu'on pourrait croire :

- les captures de repli et les vignettes produit sont déjà locales, dans
  `tools/local-demo-assets/` (30 fichiers, 4 Mo, hors de Git) ;
- le mini-catalogue des cinq produits est écrit dans le fichier lui-même ;
- aucune requête réseau, aucun asset distant, aucun `localhost` codé en dur.

Note documentaire : l'en-tête du fichier annonce encore les captures dans
`datasets/private-real/_renders/`, alors que le code lit
`local-demo-assets/renderings/`. Dérive à corriger, sans effet fonctionnel.

## 2. Le moteur réel, et sa frontière avec le Studio

Le moteur de rendu **n'est pas** le Studio. Le Studio est une interface de
calibration ; le moteur est un module que l'on instancie.

La preuve n'est pas une opinion : **`js/product/app.js`, le visualiseur
produit du front, importe déjà le moteur directement** — sans iframe, sans
`window.__studio` :

```js
import { analyzeScene, loadSceneIndex, scenesBibliotheque } from '../scene/analyzer.js';
import { loadImage, loadFile } from '../scene/image-loader.js';
import { createSceneRenderer } from '../scene/renderer.js';
import { quandCartesPretes } from '../scene/material.js';
```

Un consommateur du moteur sans le Studio existe donc déjà et fonctionne. La
frontière est nette, et elle passe par `createSceneRenderer()`.

### 2.1 L'API du moteur, telle qu'elle est

```
createSceneRenderer({ prefer })   → { backend, ready, scene, masks, photo, size,
                                       setScene(scene, prepared),
                                       preparer(config), surfacesFor(config),
                                       paint(target, config, perSurface, step),
                                       paintWithCanvas(...), warm(), 
                                       invalidateMasks(), refreshLighting() }
config = { material, pattern, angle, width, scale }
```

Aucun `Premibel`, aucun `Pose Parquet`, aucun identifiant commercial :
`material` est un objet matériau, pas une référence de vente. Le moteur est
déjà agnostique du site — c'est la condition du multi-sites, et elle est
remplie.

### 2.2 Ce que `window.__studio` fait vraiment

Les sept commandes du contrat ne sont pas le moteur : ce sont sept lignes de
`js/studio/app.js` qui écrivent une configuration puis demandent un rendu.

| commande | définie dans | ce qu'elle fait réellement | remplacée localement par |
| --- | --- | --- | --- |
| `openRoom` | `js/studio/app.js` | `analyzeScene` + `loadImage` + `renderer.setScene` | le même enchaînement, sans le Studio |
| `selectMaterial` | `js/studio/app.js` | écrit `config.material` (et le motif par défaut du matériau) | écriture locale de la config |
| `setPattern` | `js/studio/app.js` (une ligne) | `config = {...config, pattern}` puis rendu | idem |
| `setAngle` | `js/studio/app.js` (une ligne) | `config = {...config, angle}` puis rendu | idem |
| `setWidth` | `js/studio/app.js` | borne 0,02–0,5 m, écrit, rend | idem, garde comprise |
| `getCapabilities` | `js/studio/app.js` | déduit des setters présents | déduit des mêmes setters |
| `onRendered` | `js/studio/app.js` | ensemble d'abonnés notifié après `paint()` | un `EventTarget` local, ou le retour de `paint()` |

Autrement dit : **le pont ne transporte rien que le moteur ne sache faire
directement.** Il existe uniquement parce que le moteur est dans l'autre
dépôt.

## 3. Le noyau minimal

Fermeture transitive des imports, à partir de `createSceneRenderer`.

| classement | fichier | lignes | rôle |
| --- | --- | --- | --- |
| `CORE_RENDERER` | `js/scene/renderer.js` | 240 | orchestration, éclairement, `paint` |
| `CORE_RENDERER` | `js/scene/renderer-gl.js` | 480 | moteur WebGL2, shaders **en ligne** |
| `CORE_RENDERER` | `js/scene/renderer-canvas.js` | 321 | moteur logiciel de repli et de référence |
| `CORE_RENDERER` | `js/scene/mask.js` | 312 | masques de zones, trous, occulteurs |
| `CORE_RENDERER` | `js/scene/shading.js` | 266 | cartes d'éclairement et de reflets |
| `CORE_RENDERER` | `js/scene/geometry.js` | 99 | repère de zone, jacobien, lumière de tuile |
| `CORE_RENDERER` | `js/scene/perspective.js` | 101 | homographie 4 points et son inverse |
| `REQUIRED_MATERIAL` | `js/scene/material.js` | 376 | cartes d'un matériau, cache de 12 entrées, worker |
| `REQUIRED_MATERIAL` | `js/scene/texture.js` | 835 | tuile de bois **dessinée**, profils de motif |
| `REQUIRED_MATERIAL` | `js/scene/relief.js` | 41 | relief et rugosité dérivés de l'albédo |
| `REQUIRED_MATERIAL` | `js/scene/texture-worker.js` | 47 | même travail, hors du fil principal |
| `REQUIRED_SCENE` | `js/scene/schema.js` | 297 | `pose-parquet/scene@1`, normalisation |
| `REQUIRED_SCENE` | `js/scene/analyzer.js` | 226 | index des scènes, chargement, `analyzeScene` |
| `REQUIRED_SCENE` | `js/scene/image-loader.js` | 67 | décodage, EXIF, préparation du canevas |
| utilitaire | `js/utils/dom.js` | 59 | `seeded` seulement — 3 lignes utiles sur 59 |
| utilitaire | `js/utils/perf.js` | 132 | mesures, inertes sans `?perf=1` |

**15 fichiers, ≈ 3 900 lignes, 154 Ko de source.** Rien d'autre n'est
nécessaire au rendu.

### 3.1 Ce qui reste dehors

| classement | fichiers | pourquoi |
| --- | --- | --- |
| `EDITOR_ONLY` | `js/scene/editor.js`, `js/scene/export.js`, `js/studio/app.js` (1 485 l.), `js/studio/compare.js`, `js/studio/help.js`, `js/studio/main.js` | calibration, édition de zones, export d'images, interface du Studio |
| `SITE_ONLY` | `js/main.js`, `js/components/*` (12 fichiers), `js/animations/reveal.js`, `js/forms/*`, `js/utils/icons.js`, `js/utils/motion.js`, `js/scene/preview.js`, `js/tools/*` | navigation, accordéons, carrousels, formulaires, aperçus de pages |
| `DEV_ONLY` | `js/utils/perf.js` (conservé, inerte par défaut) | mesure |
| `UNUSED_BY_PRODUCT` | `js/studio/catalog.js`, `js/scene/product.js` (586 l.) | **le pont commercial** : c'est là que vivent les références Premibel et leur mappage vers un matériau. À NE PAS extraire — `product-concept.html` a déjà son propre catalogue |

Le Studio complet représente à lui seul plus de lignes que tout le noyau.
Ne pas l'embarquer n'est pas une économie de place, c'est une économie de
surface : un outil de calibration dans un produit finit par être ouvert par
un client.

## 4. `SceneData` réellement consommé par le moteur

Relevé par lecture des champs lus dans `renderer.js`, `renderer-gl.js`,
`renderer-canvas.js`, `mask.js`, `shading.js`, `geometry.js`.

| champ | obligatoire | unité / repère | rôle | repli |
| --- | --- | --- | --- | --- |
| `floorZones[].plane.quad` | **oui** | 4 points normalisés, ordre fond-G, fond-D, proche-D, proche-G | l'homographie ; **peut sortir du cadre** | aucun — lève |
| `floorZones[].plane.meters.{width,depth}` | non | mètres | échelle réelle du sol | 4,2 × 4 m |
| `floorZones[].plane.origin.{u,v}` | non | mètres de sol | décale la trame, aligne les lames d'une zone à l'autre | 0, 0 |
| `floorZones[].plane.rotationDeg` | non | degrés | orientation propre au plan | 0 |
| `floorZones[].mask.polygon` | non | normalisé | surface réellement peinte | le `quad` |
| `floorZones[].mask.holes[]` | non | normalisé | ce qui perce la zone | vide |
| `floorZones[].surfaceId` | non | — | **clé de continuité** : même surface, même bois | `'sol'` |
| `floorZones[].id`, `.order` | non | — | identité, ordre de peinture | dérivés de l'index |
| `surfaces[]` | non | — | déduites des zones si absentes | déduites |
| `occluders[].polygon` | non | normalisé | pixels d'origine restitués | vide |
| `occluders[].{depth,castsShadow,feather}` | non | — | ombre de contact, adoucissement | 0,5 / vrai / 0,0015 |
| `light.{kind,strength,blurRadius,ambient,tint,contact}` | non | fractions | éclairement relu dans la photo | `photo-luma`, 1, 0,035, 0,22, 0,5, 0,35 |
| `image.{width,height}` | oui de fait | pixels | dimension du rendu | 0 |

### 4.1 Écart avec la cible Python — à connaître avant le LOT F

Le moteur **ne lit ni `camera`, ni `depth`, ni `confidence`, ni `warnings`.**
Ces champs existent dans `pose-parquet/scene@1` et sont normalisés, mais
aucune ligne du rendu ne les consulte.

Or [AI-ARCHITECTURE-V2.md](AI-ARCHITECTURE-V2.md) prévoit de produire la
caméra, la profondeur et la confiance par composant. Ce n'est pas une
contradiction — ces sorties servent à d'autres choses (tri des occlusions,
échelle de lame, écran de statut) — mais il faut le dire clairement :

> **produire `camera` et `depth` ne changera rien au rendu tant que le moteur
> ne les lit pas.** Les faire consommer est un travail de moteur, à décider au
> LOT E ou F, et il n'est pas dans ce plan.

Ce que Python doit produire pour que le rendu fonctionne se réduit donc à :
**un `plane.quad` par zone, un `mask.polygon`, des `occluders`, un
`surfaceId`.** C'est exactement ce que la vérité terrain du LOT B annote — à
un détail près, et il est de taille : `floorExtent` (le sol **sous** les
meubles) n'est ni annoté ni produit, et le `quad` d'un plan doit pouvoir
sortir du cadre. Le moteur, lui, l'accepte déjà.

## 5. Le pipeline, aujourd'hui et demain

Aujourd'hui, fichier par fichier :

```
tools/product-concept.html
  applyFloor()                        L2200
  → adapter.applyProfile(profil, angle)          L1727  (file d'attente, cache 8)
    → getRenderStateKey(profil, angle)           L1536  api1|scene|famille|motif|largeur|angle
    → iframe #engine  ../../pose-parquet.com/outils/studio.html?perf=1
      → js/studio/main.js → js/studio/app.js
        → window.__studio.{openRoom,selectMaterial,setPattern,setWidth,setAngle}
          → js/scene/analyzer.js  analyzeScene()
          → js/scene/image-loader.js  loadImage()
          → js/scene/renderer.js  setScene() puis paint()
            → material.js → texture.js (+ worker) → relief.js
            → mask.js, shading.js, geometry.js → perspective.js
            → renderer-gl.js  (WebGL2)  ou  renderer-canvas.js
      → studio.canvas  (preserveDrawingBuffer)
  → cachePut(key, copie)                         L1551
  → paintLayer('after', canvas)  drawImage       L1780
```

Demain, proposition — **aucune iframe, aucun second moteur** :

```
tools/product-concept.html
  applyFloor()                       inchangé
  → LocalRendererAdapter.applyProfile(profil, angle)
    → même clef de cache, même file d'attente, même cache de 8 captures
    → web/renderer/  (le MÊME moteur, importé en module)
      createSceneRenderer() · setScene() · paint(target, config)
    → notifie « rendu fini » (retour de paint, ou évènement local)
  → paintLayer('after', canvas)      inchangé
```

L'adaptateur garde sa forme actuelle : c'est tout l'intérêt d'en avoir un.
Le contrat interne `applyProfile(profil, angle) → canvas` ne change pas, donc
le viewport, l'avant/après et la comparaison ne changent pas non plus.

## 6. Assets, et ce qu'ils coûtent

Découverte qui simplifie beaucoup l'extraction : **il n'y a aucune texture de
bois à copier.** Les tuiles sont **dessinées** par `texture.js` — veinage,
nœuds, fentes, contraste, largeur, finition — à partir d'une description
JSON. Pas d'albédo photographique, pas de carte de normales, pas de
rugosité, pas de LUT, pas de bruit stocké. Les shaders sont en ligne dans
`renderer-gl.js`.

| asset | chemin source | réellement utilisé | taille | provenance | couplage à un site |
| --- | --- | --- | --- | --- | --- |
| définitions de parquets | `data/parquets.json` | **oui** | 18 Ko | données du projet | aucun |
| familles de rendu | `data/render-families.json` | **oui** | 8,6 Ko | données du projet | aucun |
| scènes calibrées | `data/scenes/*.json` (17) | **5 sur 17** pour les pièces du visualiseur | 160 Ko au total | calibrées à la main | aucun |
| index des scènes | `data/scenes/index.json` | oui | — | — | aucun |
| photos de pièces | `assets/images/room-*.jpg` (140 fichiers, 4 tailles) | **5 en 1600 px** = 724 Ko | 12 Mo au total | Pexels, usage commercial autorisé, attribution non obligatoire, créditée dans `assets/images/CREDITS.md` | aucun |
| captures de repli | `tools/local-demo-assets/renderings/` | oui | déjà local | dérivées des photos ci-dessus | **déjà dans ce dépôt** |
| vignettes produit | `tools/local-demo-assets/premibel/` | oui | déjà local | Premibel | déjà local |

**Ce qu'il faudrait apporter : 4 fichiers de données (≈ 190 Ko) et 5 photos
(≈ 724 Ko).** Rien d'autre. Aucune texture, aucun shader, aucun binaire de
modèle.

## 7. Changer de produit sans refaire l'analyse — oui

L'architecture le permet déjà, et c'est structurel : `setScene()` et `paint()`
sont deux appels séparés. La scène — masques, éclairement, homographies —
est installée une fois ; changer de matériau, de motif, de largeur ou d'angle
ne rappelle que `paint()`.

C'est exactement le fonctionnement visé : Python analyse **une fois**, le
navigateur rejoue autant de produits qu'on veut. Aucune ligne à changer pour
cela.

## 8. Performance : où passe le temps, mesuré

Mesures faites le 10 septembre 2026, WebGL2, scène `sejour` en 1600 × 1067,
`onRendered` comme signal de fin.

| étape | coût mesuré | ce qui le cause |
| --- | --- | --- |
| ouverture de page + moteur joignable | ~6,5 s au premier rendu, côté visualiseur | chargement de l'iframe, du bundle, de la scène, de la photo, puis première texture |
| `openRoom` seul, moteur déjà chargé | **1,88 s** | scène + photo + masques + cartes d'éclairement |
| matériau **froid**, motif à chevrons | **17,2 s** | tuile procédurale 1280 px + pyramide de mips + relief |
| matériau déjà vu, **nouveau motif** | **2,9 s** | la clef de cache inclut le motif : nouvelle tuile |
| changement d'angle, texture inchangée | **1,2 – 2,1 s** | repeinture plein cadre, pas de texture |
| changement de largeur | **1,4 – 3,0 s** | nouvelle tuile si la largeur change le profil |
| capture du canevas (`drawImage`) | **< 1 ms** | même origine, aucun encodage |
| clef déjà en cache, côté visualiseur | **0 ms** | copie retenue, aucun rendu |

Deux conclusions qui pèsent sur la suite :

1. **L'iframe ne coûte presque rien.** La capture est sous la milliseconde.
   Supprimer le pont rendra le visualiseur autonome ; **cela ne le rendra pas
   rapide.**
2. **Le coût est dans la fabrication des tuiles**, et accessoirement dans la
   repeinture plein cadre. Le cache de matériaux plafonne à 12 entrées, celui
   des captures à 8. Rendre un changement de produit « quasi immédiat »
   demande de préchauffer les tuiles des produits visibles au catalogue, et
   éventuellement de peindre à résolution réduite pendant le geste. **C'est un
   lot de performance distinct, à ne pas mélanger avec l'extraction.**

## 9. Rectiligne, multi-vues, 360, 3D

Réponse honnête, tirée du modèle géométrique et non d'un espoir.

Le moteur repose sur **une homographie 4 points** (`perspective.js`,
`squareToQuad`) : il envoie le carré unité sur un quadrilatère de l'image et
parcourt les pixels en remontant aux coordonnées du sol. L'éclairement est
relu dans la photo elle-même. Tout est en espace image, en 2D.

| cible | verdict |
| --- | --- |
| photo rectiligne + plan de sol | **OUI** — c'est exactement son modèle |
| plusieurs points de vue rectilignes | **architecture possible**, sans changer le moteur : chaque vue est une scène, avec son propre `quad`. Ce qui manque est la **cohérence entre vues** — même origine de trame, même échelle — et cela se joue dans `plane.origin` et `plane.meters`, pas dans le rendu. Rien n'est fait, mais rien ne s'y oppose |
| panorama 360 équirectangulaire | **NÉCESSITE UNE ADAPTATION RÉELLE.** Une homographie ne décrit pas une projection équirectangulaire : le sol n'y est pas un quadrilatère, et les droites du sol y sont des courbes. Il faudrait soit rendre par tuiles rectilignes reprojetées, soit remplacer l'étage géométrique. Un moteur photo 2D ne « supporte » pas le 360 parce qu'on lui donne une image 360 |
| navigation 3D véritable | **NON — autre brique.** Il n'y a ni maillage, ni profondeur par pixel, ni caméra 3D. Le champ `depth` existe mais n'est pas lu (§4.1) |

## 10. Structure proposée dans `pose-parquet-ai`

Volontairement plate, et **aucun fichier n'est créé par cet audit** :

```
web/
  renderer/     le noyau §3, tel quel, imports relatifs conservés
  scene/        schema.js, analyzer.js, image-loader.js
  data/         parquets.json, render-families.json, scenes/*.json (5)
  assets/rooms/ les 5 photos en 1600 px
tools/
  product-concept.html   ← toujours l'UNIQUE HTML du visualiseur
```

« Un seul HTML » ne veut pas dire « 3 000 lignes dans un fichier » : la page
pourra charger des modules JS et des feuilles CSS. Ce qui reste interdit,
c'est un **second HTML de visualiseur**.

## 11. Ce que `product-concept.html` contient, et ce qui pourrait sortir

2 987 lignes, réparties ainsi :

| bloc | lignes | part |
| --- | --- | --- |
| en-tête documentaire | 78 | 3 % |
| CSS | 502 | 17 % |
| structure HTML | 316 | 11 % |
| JavaScript | 2 085 | 70 % |

Dans le JavaScript, quatre blocs sortiraient sans changer un comportement :

| bloc | lignes | extraction |
| --- | --- | --- |
| données de démonstration (pièces, 5 produits Premibel, rendus attendus) | ~300 | `web/product/demo-data.js` — c'est de la donnée, pas du code |
| `VisualizerAdapter` + cache + attente de rendu | ~430 | `web/product/renderer-adapter.js` — **le fichier que l'extraction remplace** |
| viewport : pan, zoom, immersif | ~330 | `web/product/viewport.js` |
| CSS | 502 | `web/product/product.css` |

Soit ~1 560 lignes déplaçables, et une page qui garderait sa structure et son
interface. **À ne pas faire maintenant** : mélanger une modularisation et une
extraction de moteur rendrait toute régression indiagnosticable.

## 12. Stratégie d'extraction, par étapes

Chaque étape est vérifiable seule, et aucune ne casse l'état précédent.

| étape | contenu | vérification |
| --- | --- | --- |
| **E0** | décision humaine : accepter que 15 fichiers du dépôt gelé soient **copiés** (et non liés), avec leur provenance écrite | — |
| **E1** | apporter les données et les 5 photos sous `web/data/` et `web/assets/rooms/` | les 5 scènes se chargent, comparaison octet à octet avec la source |
| **E2** | apporter le noyau §3 sous `web/renderer/` et `web/scene/`, **sans y toucher** | un test qui rend les 5 scènes hors interface et compare les pixels au rendu actuel |
| **E3** | écrire `LocalRendererAdapter` avec le **même** contrat interne que l'actuel | les deux adaptateurs derrière un drapeau : mêmes clefs de cache, mêmes captures |
| **E4** | basculer `ENGINE_URL` → adaptateur local, iframe retirée | le test d'autonomie du §13 |
| **E5** | modulariser la page (§11), une fois l'autonomie acquise | la batterie `product-concept.check.js`, inchangée |

Un point de méthode : **E2 se fait par copie, pas par réécriture.** Le moteur
qui fonctionne est celui-là ; le retoucher pendant qu'on le déplace, c'est
perdre le seul point de comparaison qu'on ait.

## 13. Le test d'autonomie, bloquant

À exécuter à la fin de E4, dans cet ordre :

1. arrêter complètement le service de `pose-parquet.com` ;
2. servir uniquement `pose-parquet-ai` ;
3. ouvrir `tools/product-concept.html` ;
4. choisir une scène ;
5. choisir un parquet ;
6. obtenir un rendu **live** (`mode` ≠ `static`) ;
7. changer l'orientation, et vérifier que les pixels changent ;
8. changer la largeur ;
9. comparer A/B.

Si les neuf points passent : `RUNTIME_EXTERNAL_DEPENDENCY = 0`.

Un neuvième point tacite : le repli statique doit **rester** — c'est ce qui
fait qu'un clone sans photos affiche encore quelque chose d'honnête.

## 14. Risques de régression

| risque | pourquoi il est réel | ce qui le contient |
| --- | --- | --- |
| divergence de pixels après copie | deux moteurs identiques peuvent différer par un chemin de worker, un `import.meta.url`, un flag WebGL | E2 compare les pixels avant/après, scène par scène |
| le worker de texture ne démarre plus | `new Worker(new URL('./texture-worker.js', import.meta.url))` dépend de l'emplacement du module | vérifier `workerIndisponible` après déplacement ; le repli synchrone existe mais coûte cher |
| double source de vérité | le noyau copié divergera de celui du front | l'écrire : après E4, **c'est notre copie qui fait foi**, et le front est gelé de toute façon |
| perte de la référence Canvas | `renderer-canvas.js` est le juge de paix du moteur WebGL | le copier aussi, même s'il ne sert jamais en production |
| régression d'interface pendant l'extraction | mélanger E4 et E5 | ne pas les mélanger |
| licence des photos | Pexels autorise l'usage commercial ; les crédits vivent dans le dépôt gelé | recopier `CREDITS.md` pour les 5 photos retenues |

## 15. Ce que ce document n'autorise pas

- copier quoi que ce soit avant la décision E0 ;
- modifier `pose-parquet.com`, même pour « préparer » l'extraction ;
- écrire un second moteur, un renderer maison, un rendu Python ou un rendu
  CSS — les captures `local-demo-assets/renderings/` restent un **repli**, pas
  une solution ;
- créer un second HTML de visualiseur ;
- traiter l'extraction et la performance dans le même lot.
