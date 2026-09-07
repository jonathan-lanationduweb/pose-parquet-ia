# Contrat fonctionnel entre l'interface publique et le service Python

Ce document dit **qui produit quoi**, et surtout ce qui est déjà vrai
aujourd'hui par rapport à ce qui reste à écrire. Il accompagne
`docs/product-visualizer-ux.md`, qui décrit l'expérience.

Trois marqueurs, utilisés partout :

| marqueur | sens |
| --- | --- |
| **ACTUEL** | existe et fonctionne, vérifié dans le code |
| **FUTUR** | prévu par un contrat déjà écrit, pas encore implémenté |
| **PROPOSITION** | idée de ce document, décidée par personne |

Un champ mal marqué coûte plus cher qu'un champ absent : on construit dessus.

---

## 1. Le partage des rôles

```
        PYTHON                                    JS / WebGL
        ──────                                    ─────────
  comprend la pièce UNE fois              change le parquet à volonté
  ────────────────────────────            ──────────────────────────
  où est le sol                           quelle essence
  quelle perspective                      quelle teinte
  ce qui passe devant                     quel motif
  comment la pièce est éclairée           quelle largeur
  si la photo est exploitable             quelle finition
                                          quels réglages de réalisme
                                          avant/après, comparaison, favoris
```

**La frontière est géométrique.** Python répond à « qu'est-ce que cette photo
montre » ; le moteur répond à « à quoi ça ressemblerait avec ce parquet ». Un
changement de teinte ne change pas ce que la photo montre, donc ne rappelle pas
Python.

---

## 2. Ce que l'interface reçoit — le contrat réel

Deux contrats existent déjà et ne disent pas exactement la même chose. C'est le
point le plus important de ce document.

### Ce que le front attend — **ACTUEL** (côté front)

`pose-parquet.com/docs/future-ai-api-contract.md` décrit
`POST /analyze-room` qui renvoie **directement une scène** :

```json
{
  "schema": "pose-parquet/scene@1",
  "sceneId": "upload-7f3c1a",
  "source": "ai",
  "confidence": 0.87,
  "timings": { "segmentation": 412, "depth": 233, "geometry": 18 },
  "image": { "width": 1600, "height": 1067 },
  "camera": { "horizon": 0.431, "vanishingPoints": […], "fovDeg": 62, … },
  "surfaces": [ … ],
  "floorZones": [ … ],
  "occluders": [ … ],
  "maps": { "floorMask": …, "depth": …, "shading": … },
  "light": { … },
  "warnings": [ … ]
}
```

Le front ne parle **ni d'analyse ni de détection** tant qu'aucun analyseur
`remote` n'est enregistré — parce que ce serait faux. Le point d'extension est
`registerAnalyzer('remote', …)` dans `js/scene/analyzer.js`, **un seul
endroit**.

### Ce que nous produisons — **ACTUEL** (côté Python)

`pose-parquet/analysis@2` **enveloppe** la scène au lieu de l'être :

```json
{
  "schema": "pose-parquet/analysis@2",
  "status": "analysis_incomplete",
  "confidence": null,
  "warnings": [ … ],
  "image": { … },
  "quality": { … },
  "lens": { … },
  "sceneData": null,
  "timings": { … }
}
```

### Les trois écarts à régler, et par qui

| écart | front | nous | qui s'adapte |
| --- | --- | --- | --- |
| **forme** | scène au premier niveau | scène dans `sceneData` | **le front**, dans `analyzer.js` : `(r) => r.sceneData` |
| **URL** | `POST /analyze-room` | `POST /v1/analyze-room` | **le front**, dans l'URL de base |
| **statut** | code HTTP (200/206/422…) | champ `status` | **les deux** : garder les deux, ils ne disent pas la même chose |

**Recommandation — PROPOSITION.** Ne pas aplatir `analysis@2`. L'enveloppe
porte `quality`, `lens` et `timings`, qui n'ont rien à faire dans une scène :
une scène décrit une pièce, pas la netteté d'un JPEG. Le déballage tient en une
ligne côté front, et c'est le bon endroit — c'est déjà là que
`normalizeScene()` travaille.

**Le préfixe `/v1` reste**, délibérément : il permettra de faire vivre deux
contrats en parallèle le jour d'une rupture.

---

## 3. Les quatre statuts, et ce qu'ils déclenchent

`AnalysisStatus` — **ACTUEL**, déjà dans `app/schemas/analysis.py` :

| statut | code HTTP suggéré | ce que l'UX fait | `sceneData` |
| --- | --- | --- | --- |
| `success` | 200 | rendu direct, aucun travail demandé | complet |
| `partial` | 206 | rendu direct + réserve non bloquante *si visible* | complet, avec `warnings` |
| `needs_manual_adjustment` | 206 | rendu + invitation à retoucher au pinceau | partiel mais peignable |
| `rejected` | 422 | pas de rendu, raison + conseil + porte de sortie | `null` |
| `analysis_incomplete` | 200 | **état de développement** : ne jamais l'exposer au public | `null` |

`analysis_incomplete` est ce que le service renvoie **aujourd'hui**, parce
qu'aucun étage ne cherche le sol. C'est un statut honnête, et c'est pourquoi
l'interface publique ne doit pas encore proposer l'analyse automatique : le
front doit continuer à se taire tant que `/health` ne déclare pas la capacité.

### La règle de repli, à ne pas perdre

> Aucune panne du service ne doit priver l'utilisateur du Visualiseur.

Le mode manuel est le socle, l'analyse est une accélération. Sur 415, 422, 429
ou 5xx, le front bascule sur la sélection manuelle **sans afficher d'erreur
technique**. C'est le front qui a raison sur ce point, et c'est déjà écrit dans
son contrat.

---

## 4. Bloc par bloc

| bloc | état | qui le produit | ce dont l'UX a besoin |
| --- | --- | --- | --- |
| `schema` | **ACTUEL** | Python | rien à afficher |
| `status` | **ACTUEL** | Python | décide lequel des 4 écrans |
| `confidence` | **ACTUEL** (toujours `null`) | Python | **jamais affiché tel quel** — voir plus bas |
| `warnings` | **ACTUEL** | Python | traduits en phrases, jamais montrés en codes |
| `image` | **ACTUEL** | Python | dimensions, pour le cadrage |
| `quality` | **ACTUEL** | Python | motif d'un `rejected` (flou, sombre, petit) |
| `lens` | **ACTUEL** | Python | avertissement de distorsion, rien de plus |
| `timings` | **ACTUEL** | Python | **jamais affiché** |
| `sceneData.camera` | **FUTUR** (LOT 4) | Python | rien à afficher — nourrit le moteur |
| `sceneData.surfaces` | **FUTUR** (LOT 6) | Python | « une seule pièce » ou « deux espaces » |
| `sceneData.floorZones` | **FUTUR** (LOT 2/6) | Python | le sol peint |
| `sceneData.occluders` | **FUTUR** (LOT 5) | Python | coche « obstacles identifiés » |
| `sceneData.light` | **FUTUR** (LOT 4) | Python | rien — nourrit le moteur |
| `maps.floorMask` | **FUTUR** | Python | alternative pixel-exacte au polygone |
| `maps.depth` | **FUTUR** (LOT 3) | Python | tri des occlusions, contact au sol |
| `maps.shading` | **FUTUR** | Python | évite au front de le recalculer |

### `confidence` — à ne pas afficher

Le champ existe et vaut `null`. Quand il portera un nombre, **il ne devra pas
être montré**. « Confiance : 0,72 » ne dit rien à un particulier et invite à
douter d'un résultat correct. Il sert à **choisir l'écran**, pas à l'illustrer.

La logique de confiance elle-même est le LOT IA 7 : rien ici ne la préempte.

### Les warnings sont des codes, pas des phrases

Notre `Warn` est un vocabulaire fermé de 11 codes — `image_blurry`,
`image_too_dark`, `lens_distortion_suspected`… Le contrat du front dit
« phrases prêtes à afficher ».

**PROPOSITION** : renvoyer les deux, `{code, message}`. Le code reste
mesurable par le banc d'essai — c'est indispensable, la matrice de confusion en
dépend — et le message reste traduisible sans redéployer le front. Renvoyer
seulement des phrases rendrait le banc d'essai aveugle ; renvoyer seulement des
codes obligerait le front à maintenir une table de traduction en double.

---

## 5. Capacités du moteur — le classement qui évite d'inventer

Quatre catégories, jamais mélangées. Vérifié en lisant le front en lecture
seule (`js/scene/material.js`, `product.js`, `texture.js`, `mask.js`,
`compare.js`, `renderer*.js`).

### `EXISTING_RENDERER_CAPABILITY` — le moteur le fait déjà

| réglage | où c'est, dans le front |
| --- | --- |
| **motif** : `lames`, `point-de-hongrie`, `baton-rompu` | `product.js` → `KNOWN_PATTERNS` ; `texture.js` → `drawChevron` |
| **largeur de lame** | `material.js` → `width: entry.boardWidth` ; config `{ width }` |
| **longueur de lame** | `plankLength` dans la clé de cache texture |
| **orientation / angle** | config du renderer `{ material, pattern, angle, width, scale }` |
| **échelle** | même config, `scale` |
| **rugosité** (mat → verni) | `material.js` → `FINISHES` : `brut .95` → `vernis .34` |
| **clearcoat / brillance** | même table, `0.0` → `0.38` ; déclenche `buildGlossMap` |
| **relief / chanfrein** | `bevel`, `relief`, carte `normal` |
| **variation entre lames** | `variation: entry.texture.spread / 30` |
| **joints** | carte `normal` : « chanfreins, veines creusées, joints » |
| **rendu par surface** | `perSurface: Map(surfaceId → config)` — deux parquets dans une photo |
| **pinceau add/remove** | `mask.js` → `beginStroke(zoneId, mode, radius, point)` |
| **avant/après** | présent dans le studio |
| **comparaison 2 et 3** | `compare.js`, modes `slider` et `grid` |
| **deux moteurs** | WebGL et logiciel, avec repli automatique |

**C'est beaucoup plus que je ne l'attendais**, et cela change la spécification :
la personnalisation « avancée » du §5 de l'UX n'est pas à construire, elle est
à **exposer**. Les curseurs orientation / variation / joints / brillance
correspondent tous à des paramètres réels.

### `PRODUCT_CATALOG_PROPERTY` — porté par la référence vendue

`product.js` modélise déjà : `woodSpecies`, `range`, `tone`, `finish`,
`parquetType`, `dimensions {widthMm, lengthMm, thicknessMm}`,
`compatiblePatterns`, `patternProfiles`, avec des bornes de validation
(`widthMm` 40–1200, `lengthMm` 200–3000).

**Conséquences pour l'UX** :

- l'essence, la teinte et la finition proposées viennent du catalogue, **pas
  d'une liste inventée** ;
- un motif absent de `compatiblePatterns` ne doit pas être offert ;
- la largeur se choisit en crans **réels**, pas en curseur libre ;
- toutes les finitions ne sont pas disponibles pour toutes les références — le
  panneau doit s'adapter à la sélection.

Le prototype utilise des données **DEMO** clairement isolées. Il ne touche pas
au catalogue Premibel.

### `PROPOSED_RENDERER_CAPABILITY` — n'existe pas, à décider

| proposition | pourquoi ce serait utile | coût |
| --- | --- | --- |
| **contraste du veinage** séparé de la variation | deux curseurs pour deux effets aujourd'hui confondus | nouvelle carte, ou post-traitement de l'albédo |
| **teinte continue** (glissement colorimétrique) | essayer une teinte hors catalogue | s'oppose au catalogue : à écarter |
| **plinthes / seuils** rendus | un parquet qui s'arrête net au mur se voit | géométrie supplémentaire |
| **ombre de contact renforcée** | ancrer les meubles | `light.contact` existe déjà — peut-être suffisant |

Aucune n'est nécessaire au produit décrit. Les citer sert à ne pas les
confondre avec l'existant.

### `UX_ONLY_DEMO` — vit dans le prototype, jamais ailleurs

- les six noms d'ambiances (« Clair et lumineux »…) ;
- les essences et teintes citées en exemple ;
- les trois moments d'analyse (« Le sol · La perspective · Les obstacles ») ;
- les quatre états d'analyse simulés par un sélecteur ;
- l'aperçu de sol du prototype, qui est un motif SVG et **pas** un rendu.

---

## 6. Ce qui n'appartient pas à `SceneData`

`SceneData` décrit **ce que la photo montre**. Une seule scène supporte cent
parquets ; y ranger le choix de l'utilisateur obligerait à revalider une scène
à chaque pastille de teinte.

**PROPOSITION** — un état séparé, côté client uniquement :

```
visualizerState = {
  active:  { materialId, pattern, widthMm, finish, angleDeg, variation, joints, gloss },
  slots:   [ { id, label, config, thumbnail } ],     // comparaison
  favourites: [ { id, label, config, savedAt } ],    // favoris
  beforeAfter: { mode: 'hold' | 'slider' | 'toggle', position: 0.5 },
  adjustments: { strokes: [ … ] },                   // retouches au pinceau
}
```

Rien de cela ne remonte à Python, et rien de cela ne modifie `SceneData`.

**Un seul point de contact** : `adjustments.strokes` modifie le masque, donc ce
que le moteur peint. Le front porte déjà ces retouches dans `mask.js`, hors de
la scène — c'est le bon endroit, et il n'y a rien à changer.

---

## 7. Les appels réseau, exhaustivement

| moment | appel | pourquoi |
| --- | --- | --- |
| ouverture de la page | `GET /v1/health` | décider si l'analyse automatique est proposée |
| photo envoyée | `POST /v1/analyze-room` | comprendre la pièce |
| photo remplacée | `POST /v1/analyze-room` | c'est une autre pièce |
| photo recadrée | `POST /v1/analyze-room` | la géométrie change |
| changement de teinte | **aucun** | |
| changement de motif | **aucun** | |
| changement de largeur | **aucun** | |
| changement de finition | **aucun** | |
| ambiance appliquée | **aucun** | |
| réglage de réalisme | **aucun** | |
| retouche au pinceau | **aucun** | le masque est client |
| avant/après | **aucun** | |
| comparaison | **aucun** | |
| favori | **aucun** (tant qu'il n'y a pas de compte) | |

**Trois appels au total**, et deux d'entre eux sont le même. Si une évolution
ajoute un appel à cette liste, c'est probablement une erreur d'architecture.

`GET /health` — **ACTUEL** dans notre service, mais il renvoie
`{"status":"ok","service":"pose-parquet-ai"}`. Le front attend
`{ status, models, queue }`. **PROPOSITION** : ajouter un bloc `capabilities`
plutôt que `models` — le front n'a pas besoin de savoir *quel* modèle, mais
*ce que le service sait faire* ce jour-là :

```json
{ "status": "ok", "capabilities": { "floor": false, "depth": false,
  "occlusion": false, "geometry": false }, "queue": 0 }
```

C'est ce qui permettra à l'interface de n'annoncer que ce qui existe — et donc
de ne jamais promettre « obstacles identifiés » sans le LOT 5.

---

## 8. Confidentialité — non négociable

Une photo envoyée par un visiteur, et **tout masque dérivé**, restent
temporaires :

- traités en mémoire, jamais écrits pour être conservés ;
- hors de Git, hors du manifeste, hors du dataset persistant ;
- hors du banc d'essai permanent ;
- hors des journaux — ni image, ni base64, ni chemin.

Le masque compte comme la photo : un masque de sol décrit la **géométrie d'une
habitation** — forme des pièces, emplacement des ouvertures, disposition du
mobilier. Le conserver « parce qu'il ne contient pas l'image » serait une
erreur d'appréciation.

Une photo de visiteur ne peut rejoindre le corpus que par une décision humaine
explicite, avec consentement documenté, et par le même chemin que n'importe
quelle autre image. Voir `docs/annotation-protocol.md` §10.

---

## 9. Ce qui reste à décider par une personne

1. **Aplatir `analysis@2` ou déballer côté front ?** Ma recommandation :
   déballer côté front, une ligne dans `analyzer.js`.
2. **`warnings` : codes, phrases, ou les deux ?** Ma recommandation : les deux.
3. **`/health` : exposer `capabilities` ?** Ma recommandation : oui, et c'est
   ce qui conditionne tout affichage d'analyse automatique.
4. **Génération B des suggestions** — filtrer par luminosité et teinte des
   murs. Faisable sans aucun modèle, et c'est la meilleure évolution
   rapport/effort du produit.
5. **Quand exposer l'analyse automatique au public ?** Pas avant que le LOT 2
   produise un `floorZones` fiable. Un rendu qui déborde du sol coûte plus de
   confiance qu'il n'en gagne.

---

## Sources inspectées, en lecture seule

Dépôt `pose-parquet.com`, aucune écriture, aucune commande Git :

- `docs/future-ai-api-contract.md` — le contrat attendu ;
- `js/scene/analyzer.js` — le point d'extension `registerAnalyzer('remote')` ;
- `js/scene/renderer.js` — la config `{ material, pattern, angle, width, scale }` ;
- `js/scene/material.js` — `FINISHES`, `variation`, `bevel`, `relief` ;
- `js/scene/product.js` — `KNOWN_PATTERNS`, `dimensions`, `compatiblePatterns` ;
- `js/scene/texture.js` — `point-de-hongrie`, `drawChevron` ;
- `js/scene/mask.js` — `beginStroke(zoneId, mode, radius, point)` ;
- `js/scene/editor.js` — « cadre de perspective, contour précis, pinceau » ;
- `js/studio/compare.js` — comparaison 2 et 3.
