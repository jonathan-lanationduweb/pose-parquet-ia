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

Les quatre derniers membres — `config`, `renderer`, `catalog`, `setContext` —
ne sont **pas** dans le contrat. Ils servent à lire un état depuis la console
pendant une mesure ; ils n'ont ni version ni garantie, et le pont n'y touche
pas. Une garde automatique le vérifie : voir §12.

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
| clef | `getRenderStateKey()` — voir plus bas |
| contenu | un canevas, copie du rendu du moteur |
| borne | **8 entrées** |
| éviction | la moins récemment utilisée (un `Map` relu est réinséré) |
| coût mémoire | hauteur × largeur × 4 octets par entrée : 3,2 Mo en 1100 × 734, 6,8 Mo en 1600 × 1067 — soit **26 à 55 Mo** pour huit entrées |
| invalidation | par la clef ; vidé à l'import d'une photo, et à chaque (re)connexion du moteur |

### La clef décrit un état de rendu, pas une référence

```
api1|sejour|chene-naturel|lames|0.1900|0
 │     │        │           │      │    └─ angle, en degrés
 │     │        │           │      └────── largeur en mètres, ou `auto`
 │     │        │           └───────────── motif
 │     │        └───────────────────────── famille de texture
 │     └────────────────────────────────── scène ouverte dans le moteur
 └──────────────────────────────────────── version du contrat
```

La première version utilisait `scène│référence│orientation`. Ça marchait — par
accident : chaque référence pilote aujourd'hui son motif, sa largeur et sa
matière, donc la référence *résumait* l'état. Le jour où le profil d'une
référence change sans que la référence change — une largeur corrigée sur la
fiche Premibel, une famille de texture réaffectée — ce cache aurait rendu
l'ancienne image, et **rien ne l'aurait dit**. La clef énumère donc
maintenant ce qu'on envoie vraiment au moteur.

La référence produit reste une métadonnée : deux références de même profil
donnent le même rendu, et ce serait deux entrées pour une seule image.

Ce qui n'y figure pas, et pourquoi :

| exclu | raison |
| --- | --- |
| `lengthM` | le profil le porte, l'adaptateur ne l'envoie pas — aucun pixel n'en dépend. À ajouter le jour où une commande l'accepte. |
| `scale` | aucune commande, capacité `false`. |
| l'empreinte du bundle | le cache vit en mémoire et meurt avec la page : un autre bundle implique un autre chargement, donc un cache vide. Rien à mettre dans la clef. |

La clef est calculée **dans l'adaptateur**, à partir du profil qu'il va
envoyer — jamais fournie par l'appelant. Un appelant qui se tromperait de clef
ne peut donc pas nous faire servir la mauvaise image.

Pourquoi huit entrées : l'utilisateur ne fait pas d'aller-retour entre douze
produits, il en compare deux ou trois ; au-delà le gain se dilue et la
mémoire, non. Vérifié : 15 états distincts demandés, cache plafonné à 8,
mémoire stable à 93–94 Mo du début à la fin.

Pourquoi les vidages explicites : ce sont les seuls cas où **les pixels
changeraient sans que la clef bouge**. Une photo importée n'appartient plus
aux scènes de démonstration ; une capture retenue pendant le repli statique ne
vaut plus rien dès que le moteur répond ; et un moteur qui vient de se
recharger n'a plus rien d'ouvert.

### Un refus du moteur arrête tout

`setWidth` renvoie `false` pour une valeur hors du plausible, et **n'écrit
rien**. Le pont vérifie ce retour avant de s'abonner et avant d'envoyer la
moindre autre commande : continuer reviendrait à rendre l'ancienne largeur puis
à la retenir sous une clef qui en annonce une autre — le cache mentirait, et
pour toute la session.

Vérifié en Chrome : `NaN`, `0`, `-1`, `5`, `Infinity`, `'0.19'` sont tous
refusés, `config.width` reste à sa valeur, et un profil à 9 m fait renvoyer
`null` à `applyProfile` avec la raison `largeur refusee par le moteur : 9`.
Le cache ne bouge pas.

### Un moteur rechargé est renégocié

L'écouteur `load` de l'iframe reste attaché : le moteur peut être rechargé, et
il faut alors reprendre la négociation au lieu de continuer à parler à un
document mort.

Ce défaut a été trouvé en le testant : avant correction, un rechargement de
l'iframe laissait le pont croire la pièce ouverte. Il ne la réouvrait donc pas,
le moteur restait sur son écran de départ, et **le sol restait sur la capture
de repli indéfiniment** — sans erreur console, sans rien pour l'expliquer.
Une (re)connexion remet maintenant `scene` à `null` et vide le cache.

Après correction : rechargement de l'iframe, puis un clic produit → la pièce
est réouverte, le rendu live revient, et le compteur d'abonnements montre
2 pris / 2 rendus, donc **aucun écouteur fantôme**.

### Préchargement : mesuré, puis écarté

Le front warm-up déjà ses propres tuiles. Un préchargement supplémentaire
piloté depuis le prototype ne pourrait que transformer un **240 ms** en
**20 ms**, pour des références que l'utilisateur a déjà vues une fois — en
occupant le moteur, qui est unique et partagé, au moment où un vrai clic peut
arriver. Le gain est réel mais petit, le risque porte sur le clic qui compte.
**Non fait**, et la mesure est la raison.

---

## 12. Revue visuelle — ce qui a été regardé, et vu

### L'amorce statique ne fait pas voir deux sols

C'était le risque du montage : clic → capture préfabriquée → rendu live →
remplacement. Si les deux images diffèrent, l'utilisateur voit un premier
parquet puis un second.

Mesuré sur trois transitions, écart moyen par canal sur la zone de sol,
échantillons normalisés à la même taille :

| transition | amorce montrée | écart amorce ↔ live | écart produit précédent ↔ live |
| --- | --- | --- | --- |
| Houston → Zeus | oui | **1,9 / 255** | 13,6 |
| Colza → Pivoine | oui | **2,5 / 255** | 38,1 |
| Zeus → Notting Hill | oui | **1,8 / 255** | 10,8 |

Moins de 1 % d'écart, et la luminance moyenne du sol est identique au dixième
(187,3 contre 187,3 ; 149,0 contre 149,0 ; 196,9 contre 196,9). Distribution
de l'écart : 0,80 % des pixels de sol au-dessus de 16/255, 0,05 % au-dessus de
32, **aucun** au-dessus de 64, et aucune ligne où l'écart se concentre — c'est
du bruit de rééchantillonnage sur les joints, pas une zone fausse.

La raison est simple : **les captures préfabriquées SONT des rendus de ce
moteur**. L'option A du plan de secours (« mettre à jour les captures pour
qu'elles correspondent à l'état live ») était déjà satisfaite. Le passage se
lit comme « le parquet s'affine », pas comme « le parquet change deux fois »,
et aucune transition longue n'a été ajoutée pour masquer quoi que ce soit.

### Les cinq produits sont identifiables

Planche de contrôle produite localement, même pièce, même caméra, même zoom
(hors Git) :

| référence | état de rendu | verdict |
| --- | --- | --- |
| Zeus | `chene-sable│point-de-hongrie│0.0920` | point de Hongrie immédiat : pointes en onglet alignées |
| Notting Hill | `chene-craie│baton-rompu│0.0900` | bâton rompu immédiat : bouts d'équerre, décrochement en marche d'escalier |
| Houston | `chene-naturel│lames│0.1900` | lames larges, teinte miel |
| Colza | `chene-sable│lames│0.1500` | lames plus étroites, teinte pâle |
| Pivoine | `chene-rustique│lames│0.1500` | même géométrie que Colza, matière nettement plus foncée et contrastée |

Zeus et Notting Hill se distinguent sans hésitation côte à côte : ce sont deux
motifs différents, pas deux variantes du même.

**Colza et Pivoine** ont la même géométrie — mêmes lames de 150 mm — et ne se
distinguent que par la matière. Elles se distinguent facilement, parce que les
deux familles de texture de démonstration sont éloignées. Mais c'est une
distinction de **teinte de démonstration**, pas de matière Premibel : rien
ici ne prétend que le rendu de Pivoine est fidèle à Pivoine. Voir §7 et §8 —
`tone`, `grain` et `finish` restent `approximate`.

### Largeur de lame : 190 contre 150

À 250 %, cadré sur le sol, Houston montre des lames visiblement plus larges
que Colza : environ 6 lames là où Colza en montre 9 sur la même portion de
sol, soit un rapport d'environ 1,4 pour un rapport attendu de 1,27. La
différence se voit sans lire la fiche.

Deux mesures automatiques ont été tentées puis **écartées** : le comptage de
minima locaux et la fréquence spatiale dominante donnent des résultats
incohérents sur une photo en perspective, où le pas apparent varie avec la
profondeur et où le veinage produit des creux aussi marqués que les joints.
Plutôt que de publier un chiffre qui ne tient pas, la vérification a été faite
là où elle est exacte : à la source.

Même pièce, même caméra, même matière, même motif, seule `setWidth` change —
90, 130, 190, 300 mm — et la progression est franche et monotone. Un piège au
passage : Pivoine paraît d'abord avoir des lames plus étroites que Colza alors
qu'elles font la même largeur. Ce sont ses veines, pas ses joints.

### Comparaison A/B : raccord exact

Zeus contre Notting Hill, écart entre les deux couches par bande horizontale :

| bande | écart moyen | écart max |
| --- | --- | --- |
| 0–17 % (plafond) | **0** | **0** |
| 17–33 % (murs) | **0** | **0** |
| 33–50 % (murs, embrasure) | **0** | **0** |
| 50–67 % | 4,0 | 61 |
| 67–83 % | 14,1 | 65 |
| 83–100 % | 17,2 | 80 |

Les deux versions sont **identiques au pixel** partout sauf sur le sol. Aucun
décalage de cadrage, aucun meuble déplacé, aucune différence d'échelle de la
photo. Les trois couches — photo, version A, version B — occupent exactement
la même boîte (141,54 · 999 × 666), au dixième de pixel.

### Avant / après

À 240 %, original contre Houston : `#photo` et `#after` occupent la même boîte
(−138,8 · −674,0 · 2397,6 × 1598,4), au dixième de pixel. Seul le sol change.

L'original et le rendu ne sont pas identiques au bit près hors du sol — le
moteur redessine toute la photo, donc le plafond et les murs passent par son
encodage : écart moyen 1,3 à 4,2 sur 255 selon la bande. C'est de l'ordre du
demi-pour-cent, invisible à l'œil, et sans effet sur la comparaison A/B, où
l'écart hors sol est exactement nul puisque les deux côtés sortent du même
moteur.

### Viewport

`z`, `x` et `y` sont restés identiques pendant toute la série des cinq
produits, à 100 % comme à 250 %, ainsi qu'à l'ouverture d'une comparaison et
d'un avant/après. Aucun recentrage automatique entre deux produits.

### Clics rapides, et vingt clics

| épreuve | résultat |
| --- | --- |
| sens de pose 0 → 90 → 45 très vite | converge sur 45°, en live, bouton 45 actif |
| Houston → Zeus → Colza très vite | converge sur Colza, en live |
| 20 changements enchaînés à 60 ms | dernier produit affiché, en live, convergence 2 183 ms |

Sur les vingt changements : aucun état bloqué, aucun repli resté affiché,
**13 abonnements pris et 13 rendus** — zéro écouteur accumulé — cache plafonné
à 5 (le nombre d'états distincts demandés), et aucune erreur console.

### Mémoire

15 états distincts demandés (5 produits × 3 orientations) contre un cache
borné à 8 :

| | |
| --- | --- |
| cache maximum observé | **8** |
| mémoire au départ | 93 Mo |
| mémoire à la fin | 94 Mo |
| retour à un produit récent | 22 ms, retenu |

La borne tient et l'éviction libère : pas de croissance sur quinze états, donc
pas de fuite grossière.
