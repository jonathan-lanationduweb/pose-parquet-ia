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

## 2. L'API réelle du moteur

Le front expose un point d'accroche `window.__studio`, activé par `?perf=1`
(voir `js/utils/perf.js` — « `?perf=1` dans l'URL […] active les mesures »).
Il est décrit là-bas comme un outil de mesure, pas comme une API publique :
c'est une réserve, pas un détail.

Ce qu'il porte, vérifié en le lisant et en l'appelant :

| membre | ce qu'il fait | utilisé ici |
| --- | --- | --- |
| `openRoom(id)` | charge une scène du front | oui |
| `selectMaterial(familyId)` | change la famille de texture | oui |
| `setPattern(id)` | `lames`, `point-de-hongrie`, `baton-rompu` | oui |
| `setAngle(deg)` | tourne le motif dans le plan du sol | oui |
| `canvas` | le canevas du rendu | oui, en lecture |
| `renderer` | l'objet moteur (`backend`, `ready`) | diagnostic |
| `catalog` | le catalogue du front | non |
| `config` | l'état courant — **objet vif, pas une copie** | oui, voir §3 |
| `setContext` | contexte éditorial | non |

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

## 3. Le seul point sale, et ce qu'il faudrait pour l'effacer

**La largeur de lame n'a pas de setter.** Le moteur l'honore pourtant :
`config.width` en mètres court-circuite la largeur propre au motif. L'adaptateur
écrit donc `studio.config.width` puis déclenche un rendu par un appel public
(`setPattern`). C'est le seul endroit où l'on touche à l'état interne du front.

Cela marche, mais c'est fragile : `config` est un objet vif exposé par un
getter, et rien ne garantit qu'il le reste.

**API minimale qui rendrait l'intégration propre** — à décider, pas à faire
unilatéralement :

```js
// js/studio/app.js, dans le bloc `if (perfActif) { window.__studio = { … } }`
setWidth: (metres) => { interaction('largeur'); config = { ...config, width: metres }; demandeRendu(true); },
setScale: (k)      => { interaction('echelle'); config = { ...config, scale: k };      demandeRendu(true); },
getCapabilities: () => ({ pattern: true, width: true, orientation: true, scale: true,
                          finish: false, grain: false, joints: false }),
```

Trois lignes, dans un bloc déjà réservé aux outils. **Le front n'a pas été
modifié** : cette passe est en lecture seule, et la décision revient à
l'humain.

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

---

## 5. Les capacités décident de l'interface

L'adaptateur ne **déclare** pas une capacité : il regarde si le moteur la
porte.

```js
{
  pattern:     typeof studio.setPattern === 'function',
  width:       studio.config && 'width' in studio.config,
  orientation: typeof studio.setAngle === 'function',
  finish: false,   // cuite dans la famille de texture
  grain:  false,
  joints: false,
}
```

Mesuré en direct : `pattern ✓ · width ✓ · orientation ✓ · finish ✗ · grain ✗ ·
joints ✗`.

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
| moteur | celui du front, piloté par `__studio` | le même, appelé par une API stable |
| largeur | `config.width` écrit à la main | `setWidth()` |
| matière | famille de démonstration | assets Premibel par référence |
| exactitude | géométrie exacte, matière approchée | exacte partout, ou dite |
| scènes | cinq scènes du front | scènes + photo du visiteur analysée par Python |
| détection | aucune | LOT IA, non commencé |
| captures | amorce et filet | inutiles |

---

## 10. Latence mesurée

Sur cette machine, séjour, moteur WebGL2, mesure de bout en bout du clic à la
couche redessinée :

| référence | ms |
| --- | --- |
| Zeus (point de Hongrie 92) | 562 |
| Colza (lames 150) | 963 |
| Houston (lames 190) | 1 444 |
| Pivoine (lames 150) | 1 576 |
| Notting Hill (bâton rompu 90) | 1 709 |

**Moyenne ≈ 1,25 s, et non moins de 500 ms.** Le retour *immédiat* — carte
sélectionnée, « Application… », sol d'amorce — est bien sous les 100 ms, mais
le rendu vrai prend entre une demi-seconde et près de deux secondes. C'est
au-dessus de la cible, et il ne faut pas le maquiller : l'essentiel du temps
part dans la fabrication de la tuile de texture, qui se refait à chaque
changement de largeur ou de motif.

Piste, non faite ici : un cache de tuiles par (famille, motif, largeur) côté
moteur — la clé existe déjà (`material.js`, fonction `key`).
