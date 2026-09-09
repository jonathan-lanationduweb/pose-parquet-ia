# Brancher le catalogue sur le vrai moteur de rendu

Le prototype ne dessine pas de parquet, et ne doit jamais s'y remettre. Mais
il ne doit pas non plus se contenter d'images figées : **cliquer un produit
doit changer le sol pour de vrai.** Ce document dit comment, et ce qui manque
encore.

---

## 1. La chaîne

```
catalogue Premibel
      ↓          PREMIBEL_DEMO_PRODUCTS[].renderProfile
VisualizerAdapter
      ↓          window.__studio du front
vrai moteur JS/WebGL
      ↓          drawImage, même origine
couches du viewport
```

L'interface ne connaît pas le moteur. Elle dit « applique ce produit » ;
l'adaptateur traduit, attend, recopie. Le jour où le moteur change d'API,
seul l'adaptateur bouge.

---

## 2. Le contrat de pilotage, version 1

Le front expose `window.__studio`, activé par `?perf=1` (voir
`js/utils/perf.js`). Il reste **derrière ce drapeau** : c'est un point
d'accroche d'instrumentation, pas une API publique du site. Une décision
humaine a autorisé une modification **minimale** du front pour en faire un
contrat propre — rien de plus.

| membre | ce qu'il fait | ajouté par ce lot |
| --- | --- | --- |
| `apiVersion` | `1` — la version que l'appelant doit savoir conduire | ✔ |
| `openRoom(id)` | charge une scène du front | |
| `selectMaterial(familyId)` | change la famille de texture | |
| `setPattern(id)` | `lames`, `point-de-hongrie`, `baton-rompu` | |
| `setAngle(deg)` | tourne le motif dans le plan du sol | |
| `setWidth(metres)` | largeur de lame ; `null` rend la main au motif | ✔ |
| `getCapabilities()` | ce qui est réellement pilotable | ✔ |
| `onRendered(cb)` | prévient quand un rendu a abouti ; rend son désabonnement | ✔ |
| `canvas` | le canevas du rendu | |
| `renderer` | l'objet moteur (`backend`, `ready`) | |
| `catalog`, `config`, `setContext` | lecture, diagnostic | |

Ce qui a été **délibérément écarté** :

- **`setScale`.** Le moteur honore `config.scale`, mais le prototype ne s'en
  sert pas. Un setter dont personne n'appelle est une promesse à maintenir
  sans contrepartie. `getCapabilities()` répond donc `scale: false`, et le
  jour où le besoin existe, ajouter la commande suffira à faire passer la
  capacité à `true` — elle est déduite, pas écrite à la main.
- **Toute sortie du drapeau `?perf=1`.** Aucune page publique du front ne
  dépend de `__studio` (vérifié par `_generator/check-studio-api.js`).

`setWidth` valide avant d'écrire : hors de `[0,02 m ; 0,5 m]`, ou non fini,
elle renvoie `false` **et ne touche à rien**. Une largeur aberrante qui
passerait quand même casserait le rendu sans que l'appelant l'apprenne.

`onRendered` est le membre le plus utile des quatre, et il n'était pas
demandé. Sans lui, celui qui pilote le moteur de l'extérieur n'a qu'une
solution : sonder le canevas jusqu'à ce qu'il cesse de changer. Voir §10 —
c'est ce sondage qui produisait le chiffre de « 1,25 s » du lot précédent.

Ce que le moteur honore vraiment, côté rendu, indépendamment de ce que
`__studio` expose :

| paramètre | où c'est lu | effet |
| --- | --- | --- |
| `config.pattern` | `patternProfile()`, `js/scene/texture.js` | géométrie du motif |
| `config.width` (m) | idem — court-circuite la largeur par défaut du motif | largeur de lame réelle |
| `config.angle` (deg) | `renderer-gl.js` ligne ~448 | sens de pose |
| `config.scale` | `renderer-gl.js` (`uTileMeters`) | échelle du motif |
| `materialId` | `createMaterial()`, `data/parquets.json` | teinte, veinage, nœuds, finition |

---

## 3. Le point sale a disparu

Le lot précédent écrivait `studio.config.width = …` faute de setter, puis
déclenchait un rendu par un appel public. Ça marchait, et c'était fragile :
`config` est un objet vif exposé par un getter, et toucher à l'état interne
d'un autre programme marche jusqu'au jour où ça ne marche plus, sans rien
dire.

**Après ce lot : zéro mutation de `studio.config` depuis pose-parquet-ai.**
Le fichier ne mentionne même plus `studio.config` en lecture, et un test le
refuse (`aucune mutation de la configuration du moteur`).

Le sondage du canevas a disparu du même coup : plus de `settle()`, plus de
« deux relevés identiques », plus de boucle à 90 ms.

### Négociation, et échec rapide

`connect()` refuse vite et pour une raison précise. Vérifié en Chrome contre
cinq faux moteurs :

| ce qu'annonce le moteur | verdict | raison affichée en `?dev=1` |
| --- | --- | --- |
| pas de `__studio` | `static` | `point d accroche __studio absent — le moteur est-il servi avec ?perf=1 ?` |
| aucune `apiVersion` | `static` | `contrat v0 (aucune version annoncee), ce pont conduit la v1` |
| `apiVersion: 99` | `static` | `contrat v99, ce pont conduit la v1` |
| `setWidth` absent | `static` | `commandes manquantes : setWidth` |
| canevas 0 × 0 | `static` | `le canevas du moteur est absent ou vide` |
| toutes capacités à `false` | `static` | `le moteur n annonce aucune capacite pilotable` |

Le repli est **muet dans l'interface** — les captures préfabriquées reprennent
la main — et **explicite en `?dev=1`**. Une dégradation silencieuse est
acceptable ; une dégradation inexplicable est un piège posé à son successeur.

---

## 4. Comment on parle au moteur sans le modifier

Le vrai Visualiseur est chargé **hors écran, dans une iframe, sur la même
origine**. Même origine, donc : `iframe.contentWindow.__studio` est joignable,
et son canevas est lisible par `drawImage`.

C'est ce qui a décidé du choix parmi les trois options envisagées :

| option | verdict |
| --- | --- |
| iframe même origine + `window.__studio` | **retenue.** Rien à ajouter au front, rien à dupliquer, canevas lisible. |
| harnais dédié + `postMessage` | écartée : il faudrait **ajouter une page au front**, ce qui est interdit ici. |
| import des modules ES du front depuis notre origine | écartée : import cross-origin sans CORS, et il faudrait recâbler tout le studio — donc dupliquer. |

La même origine se règle au service : un serveur enraciné sur le dossier qui
contient les deux dépôts.

```
http://localhost:8796/pose-parquet-ai/tools/product-concept.html
http://localhost:8796/pose-parquet.com/outils/studio.html?perf=1
```

Le chemin du moteur est réglable par `?engine=…`. Servi autrement, l'iframe
n'est pas joignable et l'adaptateur passe en `static` — sans rien casser.

### Un piège de cache, à connaître avant de perdre une heure

Le studio ne charge pas `js/studio/app.js` : il charge
`assets/dist/<empreinte>/js/studio/main.js`, une copie produite par
`node _generator/build.js` et dont le nom porte l'empreinte du contenu.
Modifier la source **sans reconstruire** ne change donc rien à ce que le
navigateur exécute — la page servie continue d'importer l'ancien arbre, en
silence. Et même après reconstruction, `outils/studio.html` peut rester en
cache navigateur avec l'ancienne empreinte : c'est exactement ce qui donne un
`apiVersion` absent alors que le fichier sur le disque l'expose.

Deux gardes existent contre ça : `_generator/check-studio-api.js` refuse une
copie publiée qui ne correspond pas à la source, et le pont dit en `?dev=1`
quelle version il a trouvée. En développement, un paramètre quelconque
ajouté à l'URL du moteur (`?engine=…&cb=2`) suffit à contourner le cache.

---

## 5. Les capacités décident de l'interface

Personne ne **déclare** une capacité. Le moteur la déduit de ses propres
commandes, le pont retient celles qu'il sait utiliser :

```js
// côté front : ajouter un setter rend la capacité vraie, en oublier un la
// laisse fausse. Aucune liste à tenir à jour.
getCapabilities: () => ({
  pattern:     typeof api.setPattern === 'function',
  width:       typeof api.setWidth === 'function',
  orientation: typeof api.setAngle === 'function',
  scale:       typeof api.setScale === 'function',   // false : pas de setter
  finish: false, grain: false, joints: false,        // cuites dans la texture
})
```

Mesuré en direct, moteur v1 : `pattern ✓ · width ✓ · orientation ✓ ·
scale ✗ · finish ✗ · grain ✗ · joints ✗`.

**Un contrôle visible doit avoir un effet visible.** Conséquence directe :

- le sens de pose est un vrai contrôle, et il tourne réellement le sol ;
- la finition, le veinage et les joints **n'ont plus de contrôle du tout**.
  Ils appartiennent à la famille de texture, le moteur ne les règle pas. Une
  phrase le dit dans le panneau, à la place des curseurs.

Les quatre curseurs décoratifs des versions précédentes (veinage, contraste,
joints, variation) ont donc disparu, et un test refuse tout `type="range"`
dans le fichier.

---

## 6. Priorité des sources, et amorce

```
capture préfabriquée   dessinée TOUT DE SUITE, pour que la pièce ne soit jamais nue
        ↓
rendu du moteur        remplace la capture dès qu'il est prêt
```

La capture n'est plus le mécanisme principal : elle est l'**amorce** et le
**filet**. Quand le moteur répond, c'est lui qu'on voit. `?dev=1` affiche
lequel des deux est à l'écran, et en combien de temps.

Sans moteur joignable, l'interface fonctionne silencieusement sur les
captures. C'est une dégradation, pas une panne, et elle n'est annoncée qu'en
mode développement.

---

## 7. Exactitude, attribut par attribut

Un seul mot pour tout un produit cachait l'essentiel : la géométrie est juste,
la matière ne l'est pas. D'où `renderAccuracy` :

```js
renderAccuracy: {
  pattern:     'exact',        // les trois motifs du moteur sont ceux des produits
  width:       'exact',        // 92 mm font 92 mm, calculés dans le plan du sol
  orientation: 'exact',        // config.angle
  tone:        'approximate',  // famille de texture de démonstration
  grain:       'approximate',
  finish:      'approximate',
}
```

Pour les cinq références : **géométrie exacte, matière approchée.** Rien
n'autorise encore à dire « voici exactement ce produit chez vous », et
l'interface parle d'aperçu.

---

## 8. Ce qu'il manque pour un rendu fidèle au produit

Le pilote du front l'annonce déjà : `visual.albedo`, `visual.normal`,
`visual.roughness` sont `null` pour ses 14 références. Le moteur n'a **aucune
texture Premibel**.

Pour chaque référence, il faudrait :

| asset | pourquoi |
| --- | --- |
| couleur de base (albédo) | la teinte réelle, pas une famille voisine |
| carte de normales | le brossé, le chanfrein, le relief du veinage |
| carte de rugosité | mat, satiné, verni — la réponse à la lumière |
| dimensions physiques | largeur, longueur, épaisseur (déjà relevées) |
| pas de répétition réel | pour ne pas voir la tuile se répéter |
| variation entre lames | nœuds, aubier, écarts de teinte |
| finition | le vernis exact, six couches dans le cas de Zeus |
| photo calibrée | pour vérifier le rendu contre le produit |

**Ces assets n'existent pas. Ils ne sont pas inventés ici.**

### Cible du pipeline

```
référence Premibel
      ↓
paquet d'assets visuels        POINF36005/albedo.webp
      ↓                                   normal.webp
profil de rendu                           roughness.webp
      ↓                                   metadata.json
Visualiseur
```

Rien de tout cela n'est créé maintenant.

---

## 9. Prototype et produit final

| | prototype | produit final visé |
| --- | --- | --- |
| moteur | celui du front, piloté par `__studio` v1 | le même, dans le même bundle |
| largeur | `setWidth()` | idem |
| attente | `onRendered()` | idem |
| transport | iframe même origine, `?perf=1` | même bundle, ou API de communication |
| matière | famille de démonstration | assets Premibel par référence |
| exactitude | géométrie exacte, matière approchée | exacte partout, ou dite |
| scènes | cinq scènes du front | scènes + photo du visiteur analysée par Python |
| détection | aucune | LOT IA, non commencé |
| captures | amorce et filet | inutiles |

### Ce que la même origine ne règle pas

L'iframe même origine est un montage de démonstration, et il faut le dire :

- elle exige que les deux dépôts soient servis **sous la même origine**, ce
  qui est vrai sur ce poste et faux en production ;
- elle dépend de `?perf=1`, c'est-à-dire d'un drapeau d'instrumentation ;
- elle charge **tout le studio** — interface comprise — pour n'en utiliser que
  le moteur.

Une intégration finale suppose l'un des deux : le visualiseur et l'analyse
**dans le même bundle**, ou une véritable API de communication (`postMessage`
avec un contrat versionné, sur une page du front dédiée à ça). Les deux
sortent du cadre autorisé ici.

---

## 10. Latence : d'où venait le 1,25 s

Le lot précédent annonçait une moyenne de 1,25 s. Ce chiffre était **en
grande partie le mien** :

- le sondage du canevas attendait un changement, puis deux relevés
  identiques, à 90 ms d'intervalle : **270 ms de retard pur** ajoutés à
  chaque mesure ;
- il n'y avait ni échauffement séparé, ni distinction froid/chaud ;
- et une partie des relevés a été prise **onglet caché**. Sans l'onglet au
  premier plan, `requestAnimationFrame` ne se déclenche pas et la chaîne de
  rendu du front s'étire : le même changement passe de 230 ms à plus de 3 s.
  Toutes les mesures ci-dessous portent `document.hidden === false`, vérifié
  à chaque relevé ; celles prises masquées ont été **jetées**, pas moyennées.

### Par type de changement

Moteur piloté directement, séjour, WebGL2, **12 itérations** après **3
échauffements comptés à part**, mesure du premier appel de commande au signal
`onRendered` :

| changement | médiane | min | p90 |
| --- | --- | --- | --- |
| matière seule | **228 ms** | 213 | 229 |
| motif | **232 ms** | 216 | 235 |
| orientation | **230 ms** | 216 | 234 |
| largeur, tuile déjà vue | **251 ms** | 233 | 252 |
| largeur, tuile jamais vue | **534 ms** | 533 | 550 |
| produit complet, à froid | **834 ms** | 233 | 1 650 |

### Où passe le temps

Les compteurs internes du front (`window.__perfRapport()`) donnent la
réponse, et elle est contre-intuitive :

| segment | médiane |
| --- | --- |
| `paint.webgl.q1` — le dessin lui-même | 5 à 18 ms |
| tâches longues du fil principal | **0** |
| `texture.tuile` sur le fil principal | **0** |

La fabrication de la tuile n'apparaît pas dans les compteurs du fil
principal parce qu'elle se fait **dans un worker** (`texture-worker.js`) :
`paint()` sort tôt sur `renderer.enAttente` et `quandCartesPretes()`
replanifie. Conséquence importante : **l'interface ne bloque jamais**. La
latence est une attente, pas un gel — un curseur qui tourne, pas une page
figée. Le reste se répartit entre le regroupement de 70 ms de `demandeRendu`
et l'aller-retour avec le worker.

### De bout en bout, dans le prototype

Séjour, zoom 250 %, onglet visible, chaîne complète du clic à la couche
redessinée :

| moment | mesuré |
| --- | --- |
| ouverture d'une pièce | 2 898 – 2 951 ms |
| **première apparition** d'une référence | 241 – 1 541 ms (médiane 561) |
| référence **déjà vue**, capture retenue | **20 – 44 ms** |
| comparaison A/B, à froid | 481 ms |
| comparaison A/B, tout en cache | **21 ms** |
| sens de pose, tuile déjà vue | 227 – 242 ms |
| sens de pose, capture retenue | 20 – 53 ms |

Détail des cinq références, page fraîchement chargée :

| référence | première apparition |
| --- | --- |
| Zeus (point de Hongrie 92) | 20 ms — déjà appliquée à l'ouverture |
| Pivoine (lames 150) | 241 ms |
| Colza (lames 150) | 561 ms |
| Houston (lames 190) | 941 ms |
| Notting Hill (bâton rompu 90) | 1 541 ms |

### Face aux cibles

| cible | résultat |
| --- | --- |
| retour immédiat < 100 ms | **tenue** — carte sélectionnée et sol d'amorce sans attendre le moteur |
| rendu chaud < 400 ms | **tenue largement** — 20 à 44 ms |
| rendu froid < 700 ms | **tenue en médiane (561 ms), pas au pire cas** |

Deux références sur cinq dépassent la cible à froid : Houston à 941 ms et
Notting Hill à 1 541 ms. C'est écrit ici parce que c'est vrai. Le pire cas
est la première apparition d'un motif que le moteur n'a jamais construit, et
il tient dans l'attente d'un worker — pas dans un gel de l'interface.

---

## 11. Deux caches, et pourquoi il en faut deux

**Le front a déjà le sien**, et le lot précédent se trompait en le disant
absent. `js/scene/material.js` :

```js
const MAX_CACHE = 12;
const key = (material, config) =>
  `${material.id}|${config.pattern}|${config.width || 'auto'}|${config.plankLength || 'auto'}`;
```

Douze entrées, éviction de la plus anciennement insérée, plus
`warmMaterial()` qui précharge pendant les périodes d'inactivité et
`enCache()` pour que l'interface sache si un clic va coûter cher. **Rien à
ajouter là.** C'est ce cache qui explique qu'une même référence coûte
941 ms la première fois et 241 ms la deuxième.

**Ce qu'il ne fait pas :** même tuile en cache, le moteur *repeint la scène
entière* et nous *recopions le canevas*. D'où le second cache, côté
pose-parquet-ai — celui des **résultats** :

| | |
| --- | --- |
| clef | `scène│référence│orientation` |
| contenu | un canevas, copie du rendu du moteur |
| borne | **8 entrées** |
| éviction | la moins récemment utilisée (un `Map` relu est réinséré) |
| coût mémoire | hauteur × largeur × 4 octets par entrée : 3,2 Mo en 1100 × 734, 6,8 Mo en 1600 × 1067 — soit **26 à 55 Mo** pour huit entrées |
| invalidation | par la clef ; vidé à l'import d'une photo et quand le moteur devient joignable après coup |

Pourquoi ces trois termes dans la clef, et pas plus : ce sont exactement les
trois choses qui changent les pixels. Le motif et la largeur sont déterminés
par la référence, les remettre dans la clef n'ajouterait rien. Pourquoi huit :
l'utilisateur ne fait pas d'aller-retour entre douze produits, il en compare
deux ou trois ; au-delà le gain se dilue et la mémoire, non.

Pourquoi deux vidages explicites : ce sont les deux seuls cas où **les pixels
changeraient sans que la clef bouge**. Une photo importée n'appartient plus
aux scènes de démonstration ; et une capture retenue pendant le repli
statique ne vaut plus rien dès que le moteur répond.

### Préchargement : mesuré, puis écarté

Le front warm-up déjà ses propres tuiles. Un préchargement supplémentaire
piloté depuis le prototype ne pourrait que transformer un **240 ms** en
**20 ms**, pour des références que l'utilisateur a déjà vues une fois — en
occupant le moteur, qui est unique et partagé, au moment où un vrai clic peut
arriver. Le gain est réel mais petit, le risque porte sur le clic qui compte.
**Non fait**, et la mesure est la raison.
