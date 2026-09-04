# SceneData : le contrat actuel, et ce que Python en fournira

Ce document sépare deux choses qu'il serait coûteux de confondre :

* le **SceneData actuel**, celui que le Visualiseur consomme aujourd'hui, tel
  qu'il est réellement écrit dans `pose-parquet.com/js/scene/schema.js` et
  dans les douze scènes de `pose-parquet.com/data/scenes/*.json` ;
* le **SceneData futur fourni par Python**, c'est-à-dire le sous-ensemble que
  ce service saura remplir, lot par lot.

Le front a été inspecté **en lecture seule**. Aucun fichier du dépôt
`pose-parquet.com` n'a été modifié, et **le contrat du front ne doit pas
l'être** : c'est à Python de s'y conformer, pas l'inverse.

---

## 1. SceneData actuel

Version : `pose-parquet/scene@1`. Le front refuse une **majeure** inconnue
plutôt que de peindre n'importe quoi.

### Deux règles qui gouvernent tout

**Toutes les coordonnées sont normalisées** (0 → 1 sur l'image analysée),
jamais en pixels. Le front retaille librement la photo sans invalider la
scène.

**Les valeurs légèrement hors [0, 1] sont permises et utiles.** Un plan de sol
se prolonge très souvent au-delà du cadre — la scène `salon` du front a un
quadrilatère qui va de `x = -0.02` à `x = 1.02`. Aucun champ de coordonnée
n'est donc borné dans notre modèle Pydantic : les borner casserait des scènes
valides.

### Structure

| bloc         | rôle                                                             |
| ------------ | ---------------------------------------------------------------- |
| `schema`     | version, `pose-parquet/scene@1`                                  |
| `id`, `label`| identité de la scène                                             |
| `source`     | `manual` \| `precalibrated` \| `ai`                              |
| `confidence` | 0 → 1, ou `null`                                                 |
| `image`      | dimensions **de l'image analysée**, `alt`, `credit`              |
| `camera`     | `horizon`, `vanishingPoints`, `fovDeg`, `tiltDeg`, `heightM`     |
| `surfaces`   | les sols distincts ; deux zones de même `surfaceId` = même parquet |
| `planes`     | plans nommés, référençables — voir ci-dessous                    |
| `floorZones` | une zone = **un plan de perspective** + **un masque**            |
| `occluders`  | ce qui doit rester **devant** le parquet                         |
| `depth`      | `plane` (calculée) ou `image` (carte)                            |
| `light`      | report de l'éclairement de la photo                              |
| `warnings`   | codes remontés à l'utilisateur                                   |

### Les trois subtilités qui comptent

**Un plan n'est pas un contour.** `plane.quad` définit l'homographie qui envoie
le carré unité sur le sol : il donne la fuite et l'échelle, et peut déborder
largement de ce qui est visible. `mask.polygon` est la surface réellement
peinte, aussi découpée qu'il faut, avec ses `holes`. C'est cette séparation
qui permet de traiter proprement une pièce vue à travers une ouverture.

**`planeRef` est la clé de la continuité.** Onze des douze scènes du front
déclarent leur plan une fois dans `planes` et le référencent depuis la zone.
Deux pièces en enfilade sur la même dalle sont **un seul plan de sol** vu à
travers une ouverture : le déclarer une fois garantit une continuité exacte,
là où deux plans calibrés séparément laissent un décalage au raccord. Notre
modèle accepte les deux formes et résout la référence à la validation — et
lève sur une référence morte, comme le front.

**Un occulteur n'est pas un trou de masque.** Il vaut pour toutes les zones et
survit à une correction du contour : le rendu y restaure les pixels d'origine,
donc un canapé n'est jamais repeint, quelle que soit la zone sur laquelle il
se trouve.

### Les valeurs de `light` ne sont pas décoratives

`blurRadius: 0.035`, `ambient: 0.22`, `tint: 0.5`, `contact: 0.35`. Ces
nombres viennent du front et y sont commentés un par un. En diverger
produirait un rendu différent de celui des pièces calibrées **pour la même
photo** — un test verrouille donc ces défauts.

Pour mémoire, ce que chacun évite : `blurRadius` sépare l'éclairement du
détail, sans quoi les lames de l'ancien sol réapparaissent en fantôme sous le
nouveau parquet ; `ambient` empêche un parquet foncé de s'effondrer vers le
noir dans une zone peu éclairée — on ne lirait plus un sol sombre mais un
trou.

### Ce que le front met dans les scènes et que nous ignorons

Les scènes calibrées portent des champs de travail : `note`, `status`,
`geometryStatus`, `visualStatus`, `visualReason`, `visualNote`. Ils ne
concernent pas le rendu — ils tracent la revue humaine. Notre modèle les
ignore (`extra="ignore"`), ce qui est indispensable pour valider les scènes
réelles, notre seule vérité terrain géométrique.

Un test les valide toutes les douze quand le dépôt du front est présent, et
s'ignore sinon (`POSE_PARQUET_FRONT` pour le désigner ailleurs). C'est le seul
test qui prouve que ce schéma n'a rien inventé.

---

## 2. SceneData futur fourni par Python

Le front a déjà spécifié la réponse attendue dans
`pose-parquet.com/docs/future-ai-api-contract.md`. Ce qui suit dit **quand**
Python saura remplir quoi.

| champ                     | lot     | état                                            |
| ------------------------- | ------- | ----------------------------------------------- |
| `schema`, `id`, `source`  | LOT 6   | trivial, mais sans le reste il n'y a pas de scène |
| `image.width/height`      | ✅ LOT 0 | déjà mesuré, après redressement EXIF            |
| `warnings`                | ✅ LOT 0 | codes déjà émis, voir `app/core/warnings.py`    |
| `floorZones[].mask`       | LOT 2   | segmentation du sol                             |
| `depth`                   | LOT 3   | carte relative ; l'échelle métrique reste à caler |
| `camera.horizon`          | LOT 4   | le seul champ caméra dont le front a besoin     |
| `camera.vanishingPoints`  | LOT 4   | sans réseau de neurones, depuis le contour du sol |
| `floorZones[].plane`      | LOT 4   | quadrilatère et échelle                         |
| `surfaces`, `planeRef`    | LOT 4   | continuité entre zones                          |
| `occluders`               | LOT 5   | meubles, tapis, radiateurs, lignes de contact   |
| `confidence`              | LOT 7   | agrégée depuis les confiances de chaque étage   |
| `light`                   | —       | défauts du front conservés ; `sun` reste ouvert |

Aujourd'hui, `POST /v1/analyze-room` renvoie donc **`sceneData: null`** et
`status: "analysis_incomplete"`.

### Pourquoi ne pas renvoyer une scène approximative dès maintenant

Une `SceneData` exige au minimum une zone de sol, donc un quadrilatère et un
contour. Sans segmentation ni géométrie, il n'y a que deux façons d'en
produire une :

* **deviner un quadrilatère plausible** — c'est exactement ce que fait déjà
  l'analyseur `manual` du front. Le refaire côté serveur ne rendrait service à
  personne, tout en portant l'étiquette `source: "ai"` qui autorise
  l'interface à parler de « détection » ;
* **renvoyer une scène vide** — que `normalizeScene()` refuse, à juste titre.

`null` est donc la bonne réponse, et le front retombe sur la sélection
manuelle. C'est conforme à sa règle de conception : « aucune panne du service
ne doit priver l'utilisateur du Visualiseur ».

### Ce qui manque au contrat actuel, et qu'il faudra y ajouter

**Un bloc `lens`.** `SceneData` décrit une caméra sténopé : un horizon, une
focale, des points de fuite, et rien de plus. Il n'y a **aucun coefficient de
distorsion**, et toutes les mesures de calibrage supposent que les droites du
monde sont droites dans l'image. Le jour où une correction existera, la scène
devra porter les coefficients, le centre optique, et la provenance de ces
valeurs — mesurée, lue, ou supposée. Voir `docs/lens-distortion.md`.

**Les `maps`.** Le contrat du front prévoit `floorMask`, `depth` et `shading`
en PNG base64, plus petites que l'image. Elles ne sont pas modélisées ici :
les modéliser avant de savoir quel modèle les produit reviendrait à figer un
format d'échange autour d'un choix qui n'est pas fait.

### Un écart d'URL à ne pas oublier

Le contrat du front écrit `POST /analyze-room`. Ce service expose
`POST /v1/analyze-room`. Le préfixe de version est délibéré — il permettra de
faire vivre deux contrats en parallèle le jour d'une rupture. Côté front, cela
se règle dans l'URL de base de l'analyseur `remote`, en un seul endroit
(`js/scene/analyzer.js`), et rien d'autre ne bouge.

---

## 3. Le branchement, le jour venu

Un seul point d'accroche existe déjà côté front, et il n'a pas besoin d'être
modifié pour être utilisé :

```js
// js/scene/analyzer.js
registerAnalyzer('remote', async ({ file }) => {
  const body = new FormData();
  body.append('image', file);
  const response = await fetch(`${API}/v1/analyze-room`, { method: 'POST', body });
  return normalizeScene((await response.json()).sceneData);
});
```

Ce qui **ne change pas** quand le service arrive : le schéma `SceneData`, le
moteur de rendu, les masques, les matériaux, la comparaison, l'export, et
l'écran de correction — qui reste utile, et devient facultatif.

Une seule étape disparaît du parcours : placer les points à la main.

---

## Sources inspectées, en lecture seule

* `pose-parquet.com/js/scene/schema.js` — le schéma normatif
* `pose-parquet.com/js/scene/analyzer.js` — le point de branchement
* `pose-parquet.com/data/scenes/*.json` — douze scènes calibrées
* `pose-parquet.com/data/scenes/index.json` — statuts et raisons d'échec
* `pose-parquet.com/docs/future-ai-api-contract.md` — la réponse attendue
* `pose-parquet.com/docs/future-python-architecture.md` — le pipeline visé
* `pose-parquet.com/docs/photo-lens-distortion.md` — la distorsion
