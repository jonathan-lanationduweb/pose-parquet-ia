# Campagne pilote d'annotation — LOT IA 2A

**Quatre scènes, deux passes chacune, huit relevés.** Tout le reste est prêt :
les photos, l'outil, les contrôles, les métriques et la commande d'analyse.

> **Statut du lot**
>
> | | |
> | --- | --- |
> | Infrastructure LOT IA 2A | **VALIDÉE** |
> | Expérience LOT IA 2A | **EN ATTENTE DES ANNOTATIONS HUMAINES** |
> | LOT IA 2B | **non autorisé** avant analyse des premières annotations |
>
> Aucun modèle n'est installé, et aucun ne le sera avant d'avoir lu ce que la
> campagne dira du protocole.

> **Pourquoi ces relevés ne peuvent pas être faits à votre place.** Le LOT 2A
> mesure la difficulté d'annotation, le temps qu'elle prend, les hésitations
> humaines et l'écart entre deux passes. Ces quatre grandeurs sont des mesures
> *d'un humain qui annote*. Les produire moi-même fabriquerait précisément la
> donnée que ce lot existe pour observer, et une seconde passe faite par moi
> serait un annotateur simulé.

---

## 1. Les quatre scènes, et pourquoi celles-là

Le choix vise la **diversité des difficultés réelles**, pas le remplissage des
catégories : quatre pièces vides bien réparties en `easy`/`medium`/`hard`
n'auraient rien appris. Chacune apporte au moins un cas qu'aucune autre ne
porte — un test le vérifie.

| ordre | scène | rôle | ce qu'elle seule apporte |
| --- | --- | --- | --- |
| 1 | `sejour` | `easy` | deux pièces en enfilade sur **un seul** parquet, et des reflets francs |
| 2 | `chambre` | `medium` | une **terrasse** vue par la porte-fenêtre, et une **grille encastrée** |
| 3 | `couloir` | `hard` | bois clair sur bois clair, **sans plinthe** : où finit le mur ? |
| 4 | `petite-piece` | la plus ambiguë | huit pieds fins, rideau au sol, angle masqué, sol coupé par le cadre |

**Annotez-les dans cet ordre.** `sejour` sert à prendre la main et donne la
durée de référence ; `petite-piece` vient en dernier, quand le geste est acquis
— et sa durée est l'information la plus utile du lot, celle qui dira si trente
scènes sont réalistes.

### Ce que chaque scène met à l'épreuve

**`sejour`** — l'ouverture entre les deux pièces **n'est pas** une frontière de
sol : le parquet continue, le masque continue. Les reflets de fenêtre sur les
lames sont du sol.

**`chambre`** — la scène qui teste les deux décisions récentes :

* la **terrasse est dehors** → hors du masque, *même de plain-pied et dans le
  prolongement exact du parquet* ;
* le **seuil de la porte-fenêtre** reçoit un contour, il n'est pas une fin de
  sol par épuisement ;
* la **grille de ventilation** encastrée est exclue ; le parquet autour reste
  inclus.

Son contraste mur/sol est très élevé, ce qui isole ces règles de toute
difficulté de frontière : un désaccord ici portera sur la **définition**, pas
sur la main.

**`couloir`** — ne forcez **pas** la ligne de pied de mur à droite. Déclarez-la
incertaine, et faites la zone assez large (voir §5). Une part incertaine élevée
est un **résultat**, pas un échec.

**`petite-piece`** — le bas du cadre est un `frame_cut`. Le pied du rideau et
l'angle masqué par le bureau sont incertains, pas devinés. Le sol sous le
radiateur est du sol si on le voit.

---

## 2. Passe A — la procédure

### 1 · Ouvrir l'outil

**Double-cliquez sur `tools/annotate.html`.** Aucun serveur n'est nécessaire :
l'outil est un fichier unique, sans dépendance et sans requête réseau ; il lit
l'image que vous lui donnez et n'envoie rien.

Si votre navigateur refuse d'ouvrir un fichier local, et **seulement** dans ce
cas, servez le dossier depuis `C:\Users\jonat\Desktop\pose-parquet-ai` :

```bash
.venv/Scripts/python.exe -m http.server 8000
```

puis ouvrez `http://localhost:8000/tools/annotate.html`. Arrêtez-le avec
`Ctrl+C` quand vous avez fini.

### 2 · La première image

`datasets/private-real/sejour.jpg` — la plus simple, et sa durée sert de
référence aux trois autres.

Remplissez les deux champs sous la zone de dépôt :

| champ | valeur |
| --- | --- |
| Scène | `sejour` |
| Session | `A` |

**Le champ « Session » n'est pas décoratif** : il nomme le fichier exporté.
Sans lui, la passe B se téléchargerait sous le même nom que la A et
l'écraserait à l'import — sans aucune erreur, et avec une paire devenue
impossible à mesurer.

Raccourci : l'outil accepte aussi `annotate.html?scene=sejour&pass=A`, qui
préremplit les deux champs.

### 3 · Tracer

| geste | effet |
| --- | --- |
| clic | pose un sommet |
| <kbd>Entrée</kbd> ou double-clic | ferme la forme |
| <kbd>Échap</kbd> | abandonne la forme en cours |
| glisser un sommet | le déplace — inutile de tout refaire |
| double-clic sur un segment | insère un sommet |
| <kbd>Suppr</kbd> sur un sommet sélectionné | le retire |
| <kbd>Ctrl+Z</kbd> / <kbd>Ctrl+Maj+Z</kbd> | annuler / rétablir |
| molette | zoom |
| <kbd>Espace</kbd> + glisser | déplace l'image |

Trois outils dans la barre du bas : **Sol**, **Exclure**, **Incertain**. Les
contours typés sont facultatifs, derrière le bouton « … ».

### 4 · Vérifier, puis enregistrer

**Vérifier le tracé** ouvre une revue : chaque couche se masque pour
l'inspecter, avec le compte des zones. Puis **Valider et enregistrer**. Le
navigateur télécharge `sejour.A.draw.json`. Importez-le :

```bash
.venv/Scripts/python.exe -m scripts.import_annotation --draw ~/Downloads/sejour.A.draw.json --annotator jonathan --independent --status reviewed --overlay controle-sejour-A.jpg
```

L'étiquette de passe et la durée sont **reprises du tracé** : rien à retaper.
Les masques PNG et le JSON d'annotation atterrissent dans
`datasets/annotations/`.

> `--independent` déclare que cette passe a été dessinée **sans regarder
> l'autre passe**. Cela ne parle pas de relecture. L'outil ne peut pas le
> vérifier : ne posez le drapeau que si c'est vrai.
>
> `--status reviewed` dit « terminée, et son auteur l'a relue ». Elle
> **n'entre pas** au banc d'essai officiel, et c'est voulu : personne d'autre
> ne l'a vue.
>
> `--overlay` écrit l'aperçu de contrôle. Regardez-le avant de vous déclarer
> satisfait : c'est là que se voient un morceau de mur happé, une bande de sol
> oubliée le long d'une plinthe, un tapis resté dedans, un pied de chaise
> effacé.

### Les quatre états, et lequel choisir

Ne pas les confondre est la seule chose qui donne du poids à `approved`.

| état | statut | bloc `review` | entre au banc d'essai officiel ? |
| --- | --- | --- | --- |
| annotation **terminée** | `draft` | interdit | non |
| annotation **relue par son auteur** | `reviewed` | son auteur, nommé | **non** |
| annotation **revue par un tiers** | `reviewed` | l'autre personne, nommée | non, pas encore |
| annotation **approuvée pour la mesure** | `approved` | un relecteur nommé | **oui** |

**Une personne seule s'arrête à `reviewed`.** C'est l'état honnête d'un relevé
fini, relu par son auteur, et que personne d'autre n'a vu.

`approved` reste techniquement atteignable par l'auteur seul — le schéma
l'autorise, et il l'inscrit alors comme son propre relecteur. Mais ce n'est
**pas** une revue indépendante, et le contrôle le dit maintenant à voix haute :
un avertissement `self_approved` apparaît, et le bilan compte séparément
`selfApproved` et `independentlyReviewed`. Approuver son propre relevé est
donc une décision consciente et tracée, jamais un effet de bord d'une commande
copiée.

Ce que l'auto-relecture attrape quand même : un masque oublié, un trou mal
fermé, un contour tracé dans la mauvaise catégorie. Ce qu'elle n'attrape pas :
une mauvaise **lecture** de la scène, puisque c'est la même lecture qui relit.
Une erreur d'interprétation cohérente avec elle-même y survit intacte.

C'est la raison pour laquelle les deux passes indépendantes existent : elles
mesurent ce que l'auto-relecture est structurellement incapable de voir. Si
une seconde personne est disponible, ne serait-ce que pour relire deux scènes,
cela vaut mieux que quatre auto-relectures.

### Relire un relevé produit par la machine, et le promouvoir

Les quatre relevés du pilote portent `annotator = claude-ai`, `passLabel = AI`
et `status = draft`. Les relire ne demande **ni** de redessiner, **ni** d'ouvrir
un JSON.

**1. Dessiner les planches**, puis les regarder :

```bash
.venv/Scripts/python.exe -m scripts.review_board
```

Deux images dans `review/pilot-AI/` — ignoré par Git, comme les photos :
`PILOT-REVIEW.jpg` (les quatre scènes, photo, relevé, zone la plus dure) et
`PILOT-REVIEW-CROPS.jpg` (les douze zones critiques, photo et relevé côte à
côte). Les cadrages sont **dérivés de la géométrie du relevé** : ils suivent le
tracé si le tracé change, au lieu de montrer un ancien endroit.

Huit contrôles passent avant que la planche existe — dimensions, disjonction
du sol et de l'incertain, cohérence des exclusions avec le masque final, rôles
conservés, empreintes des masques inchangées, statut, annotateur, nom de passe.
**Si l'un échoue, aucune planche n'est dessinée** : une image qui ne montre pas
les octets mesurés ne peut pas être approuvée.

**2. Promouvoir**, une scène à la fois, après avoir regardé :

```bash
.venv/Scripts/python.exe -m scripts.review_annotation --photo sejour --pass-label AI --reviewer jonathan --status approved --note "revue visuelle : conforme"
```

Ce script ne touche **que** le statut et le bloc de revue. L'auteur du tracé,
sa date, sa révision, sa passe, ses géométries et ses masques restent
exactement en place — il n'existe aucune option pour réécrire `annotator`.
C'est la différence avec une réimportation, qui refait tout et daterait le
relevé du jour de la revue.

Comme `annotator` vaut `claude-ai` et `reviewer` votre nom, les deux diffèrent :
c'est une **revue indépendante** au sens du bilan de corpus, et non une
auto-relecture. Ce que la revue ne fabrique pas, en revanche, c'est une paire
humaine A/B : la répétabilité reste un autre protocole, et le corpus n'en a
aucune.

Si une zone ne convient pas, ne promouvez pas : dites laquelle. Le tracé sera
corrigé, sa `revision` incrémentée, et la planche redessinée.

### 5 · Passer à la suivante

Rechargez la page (ou **Tout effacer**), puis reprenez au point 2 avec
`chambre`, `couloir`, `petite-piece` — même procédure, passe `A` à chaque fois.

Vérifiez l'avancement quand vous voulez :

```bash
.venv/Scripts/python.exe -m benchmarks.run_pilot
```

Il annonce `4/8 relevé(s)` et liste nommément ce qui manque.

### 6 · Les passes B, plus tard

**Attendez au moins un jour.** Une seconde passe faite dans la demi-heure
mesure votre mémoire à court terme, pas votre protocole.

Même procédure, avec `B` dans le champ Passe :

```bash
.venv/Scripts/python.exe -m scripts.import_annotation --draw ~/Downloads/sejour.B.draw.json --annotator jonathan --independent --status approved --reviewer jonathan
```

Gardez le **même nom d'annotateur** si c'est bien vous. Le nom de la mesure en
dépend, et il n'est pas cosmétique :

| qui a fait les deux passes | nom de la mesure |
| --- | --- |
| la **même** personne | `intra_annotator_repeatability` |
| deux personnes **réellement différentes** | `inter_annotator_agreement` |

Le module le déduit des champs `annotator` et refuse de choisir à votre place.
La répétabilité mesure la stabilité d'**une main** : c'est une **borne
optimiste**, parce que personne ne reproduit ses propres hésitations aussi mal
que celles d'un autre. L'accord, lui, mesure ce que le **protocole** transmet
d'une tête à une autre — et c'est lui qui plafonne ce qu'on pourra exiger d'un
modèle.

Mettre deux noms différents pour deux passes que vous avez faites toutes les
deux gonflerait donc précisément le chiffre qui servira de plafond. Le pilote
mesurera une **répétabilité**, et le rapport l'écrira ainsi.

### 7 · Ce qui est chronométré tout seul

| donnée | comment |
| --- | --- |
| durée du premier tracé | **automatique** — l'outil compte, et se met en pause après 60 s sans geste |
| durée de relecture | `--review-seconds 90`, si vous la mesurez |
| durée des corrections | `--corrections-seconds 45`, si vous en faites |
| nombre de reprises | `--corrections 3`, si vous les comptez |

Seule la première est automatique, et c'est la plus fastidieuse à tenir à la
main. Les trois autres sont facultatives : une durée absente vaut mieux qu'une
durée inventée.

L'outil ne mesure rien d'autre. Pas de trace de gestes, pas d'envoi.

### 8 · Ce qu'il ne faut surtout pas regarder avant la passe B

C'est la condition qui décide si la mesure vaut quelque chose. Avant de refaire
une scène, **n'ouvrez pas** :

* `datasets/annotations/<scène>.A.json` ;
* `datasets/annotations/masks/<scène>.A.*.png` ;
* les images de comparaison de `benchmarks/out/pilot/` ;
* le rapport `pilot.json`, dont la partie « désaccord » vous dirait où vous
  avez hésité ;
* vos propres notes de la passe A.

Et **ne rechargez pas** le tracé A dans l'outil : le bouton « Recharger un
tracé » sert à reprendre un travail interrompu, pas à refaire une passe.

Si vous regardez malgré tout, ce n'est pas grave — mais **importez la passe
sans `--independent`**. Le rapport marquera la paire, et un chiffre
honnêtement diminué vaut mieux qu'un chiffre faux.

---

## 3. Analyser les huit relevés

Une seule commande, quand les huit sont là :

```bash
.venv/Scripts/python.exe -m benchmarks.run_pilot --render
```

Elle écrit `benchmarks/out/pilot/pilot.json` et une image de comparaison par
scène. Elle produit, **par scène** : IoU, Dice, précision, rappel,
`BF@0.25%`, `BF@0.5%`, `BF@1%`, la part incertaine de chaque passe, la
localisation du désaccord et ses principaux foyers, la durée de chaque passe.
Et **au global** : moyenne, médiane, minimum, maximum, et la répétabilité par
difficulté.

Légende des images de comparaison :

| couleur | sens |
| --- | --- |
| vert | les deux passes sont d'accord : c'est du sol |
| bleu | seule la passe A l'a compté |
| rouge | seule la passe B l'a compté |
| jaune | déclaré indécidable par au moins l'une des deux — exclu des scores |

Les chiffres à regarder, dans cet ordre :

1. **le temps**, par difficulté. C'est lui qui décide de la taille du corpus ;
2. **l'IoU minimum** entre passes. C'est le plafond réaliste, pas la moyenne ;
3. **la F-mesure de contour selon la tolérance.** Les trois valeurs sont
   publiées et **aucune n'est un objectif** : si le score bouge beaucoup de
   0,25 % à 1 %, le choix de tolérance compte plus que le choix de modèle, et
   il faudra le trancher avant tout banc d'essai ;
4. **la répartition du désaccord** — jonction, cadre, ou surface entière. Un
   désaccord de surface porte sur la **définition** du sol visible, donc sur le
   protocole ; un désaccord de jonction porte sur la main.

---

## 4. Ce qu'il faut noter en annotant

Le format prévoit un champ `notes` par annotation — dans l'outil, « Ajouter
une note » sur l'écran de vérification. Utilisez-le pour ce que les masques ne diront pas :

* un endroit où vous avez hésité **sans** le marquer incertain, et pourquoi ;
* une catégorie du protocole qui ne collait pas ;
* un geste que l'outil rend pénible ;
* une raison d'incertitude qui manque à la liste.

Ces notes sont la matière première de la calibration de `floor-annotation@1`.

Les règles et les cas déjà tranchés sont dans `docs/annotation-protocol.md` :
la **définition officielle** de `floor_visible` au §1, et ce que les vraies
photos ont appris au §11. Lisez le §1 avant de commencer.

---

## 5. La règle de tracé qui coûte le plus cher si on l'ignore

Une zone `uncertain` doit couvrir **toute la région dont la frontière est
ambiguë**, et non une ligne symbolique en son centre.

La raison est mesurée : une frontière de masque est épaisse de plusieurs
pixels. Une zone tracée au ras du doute laisse évaluer exactement ce que vous
avez déclaré indécidable — sur le cas observé pendant le lot, la précision de
contour tombait à **0,929** au lieu de **1,0000**, sans que le masque ait
changé : seule la déclaration d'incertitude était trop étroite.

Une zone honnêtement large ne cache rien : les pixels exclus sont comptés et
publiés (`ignoredFraction`). Voir `docs/annotation-protocol.md`, §11.5.

---

## 6. Ce qui manque au corpus, et que vous seul pouvez fournir

Les onze photos viennent du dépôt du front, qui les avait choisies pour leurs
**sols dégagés** — l'inverse de ce qu'un banc d'essai de segmentation demande.

| manque | état actuel | pourquoi c'est prioritaire |
| --- | --- | --- |
| **tapis** | **aucun** | c'est le cas d'école du sol *caché* : il teste la définition même de `floor_visible` |
| **mobilier** | 3 scènes sur 11 | huit scènes sont des pièces vides |

Le futur corpus devra notamment ajouter :

* un **tapis**, ou plusieurs ;
* un canapé ou un fauteuil **avec pieds** ;
* une table et des chaises à **pieds fins** ;
* du mobilier **au contact des murs** ;
* un **radiateur** ;
* un **faible contraste** mur/sol ;
* un sol **sombre ou réfléchissant**.

Le pilote en couvre déjà quelques-uns — pieds fins, radiateur, faible
contraste, sol réfléchissant — mais un seul exemplaire chacun, et jamais avec
un tapis.

**Rien ne sera téléchargé pour combler ces cases.** Aucune recherche
automatique d'images, aucune source externe : une photo dont la provenance
n'est pas certaine ne peut pas servir de référence commune. Une seule photo de
votre salon avec un tapis apporterait plus au corpus que trois pièces vides
supplémentaires :

```bash
.venv/Scripts/python.exe -m scripts.add_photo --file private-real/salon-tapis.jpg --id salon-tapis --difficulty medium --source "photo personnelle" --license "propriétaire" --verified-on 2026-09-07 --traits furnished,rug,existing_parquet
```

---

## 7. Confidentialité — ce que `private-real/` est, et n'est pas

`private-real/` est un **corpus privé de développement contrôlé** : des images
choisies une par une, provenance vérifiée, inscrites au manifeste à la main.
Il est hors de Git ; le dépôt n'en garde que la description.

Une photo envoyée un jour par un visiteur de pose-parquet.com **n'y entre
jamais automatiquement**. Elle reste temporaire, hors de Git, hors du dataset,
hors du banc d'essai permanent, et hors des journaux — ni image, ni base64, ni
chemin. **Les masques dérivés sont temporaires par défaut** au même titre : un
masque de sol décrit la géométrie d'une habitation.

Aucun développement WordPress ni cloud n'est engagé. Voir
`docs/annotation-protocol.md`, §10.
