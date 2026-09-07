# Protocole d'annotation du sol

Ce document définit la vérité terrain du LOT 2 : ce qu'on annote, comment, et
ce qu'on refuse d'annoter. Il s'adresse à qui va tenir la souris.

Le préambule dont il sort n'a mis en place **aucun modèle**. Il a mis en place
la balance : format, contrôles, métriques, banc d'essai vide. Le corpus réel
reste à collecter.

---

## 1. Les trois notions à ne jamais confondre

### Le sol visible — `floor_visible`

Les pixels où l'on **voit** le sol. C'est le seul masque contre lequel une
segmentation sera mesurée, et le seul dont une personne peut décider en
regardant l'image.

| ce qu'on voit | sol visible ? |
| --- | --- |
| parquet, carrelage, béton, lino apparent | **oui** |
| tapis, carpette, paillasson | **non** — ils cachent le sol |
| meuble, canapé, carton posé | **non** |
| pied de chaise, de table, de lit | **non** |
| plinthe | **non** — elle appartient au mur |
| mur, porte, fenêtre, plafond | **non** |
| sol aperçu à travers une porte ouverte | **oui**, si on le voit |
| reflet sur le sol | **oui** — c'est le sol, éclairé autrement |
| ombre portée sur le sol | **oui** — c'est le sol, moins éclairé |

Les deux dernières lignes sont celles qui font hésiter. La règle : on annote la
**surface**, pas son éclairement. Un sol dans l'ombre reste du sol.

### L'étendue géométrique du sol — non annotée

La surface que le sol occupe *vraiment*, y compris sous le canapé et sous le
tapis. C'est ce dont le Visualiseur a besoin pour poser des lames continues, et
**ce n'est pas ce qu'on annote ici.**

Elle ne se voit pas : elle se déduit de la perspective. Elle appartient donc à
un lot qui saura la déduire, pas à un relevé humain qui devrait l'inventer.

Le champ `masks.floorExtent` existe et reste vide. Il est là pour qu'on ne
range pas cette notion dans `floor_visible` par commodité — mesurer un
segmenteur contre une cible que l'image ne contient pas serait l'erreur la plus
coûteuse du projet, et elle serait invisible : les chiffres auraient l'air bons.

### L'incertain — `uncertain`

Les pixels dont une personne honnête dit qu'elle **ne sait pas**. Ils sont
exclus de toutes les métriques.

Raisons prévues (`UncertainReason`) : coin caché, ombre forte, meuble collé au
mur, faible contraste, coupé par le cadre, reflet, flou de bougé, autre.

> **Ne forcez jamais une limite que vous ne voyez pas.** Un trait tiré au
> hasard pour « finir proprement » devient une exigence chiffrée contre
> laquelle un modèle sera jugé. Marquer la zone incertaine est plus utile, plus
> rapide, et plus vrai.

---

## 2. Le contour repéré — `boundary`

Facultatif, et précieux. Ce sont des **polylignes** — un contour mur/sol est un
trait, pas une surface — chacune avec sa nature :

| nature | ce que c'est | ce qu'elle coûte si elle est fausse |
| --- | --- | --- |
| `wall_floor` | la jonction mur/sol | tout le plan de perspective |
| `baseboard` | le bas de plinthe, s'il se distingue | quelques centimètres d'échelle |
| `door_threshold` | seuil de porte : **changement** de sol | la continuité entre pièces |
| `frame_cut` | le sol est coupé par le bord du cadre | rien : la scène n'y a pas de frontière |
| `object_contact` | pied de meuble, bord de tapis | le tri des occlusions |

Distinguer les natures sert une chose précise : pouvoir mesurer plus tard la
qualité **là où elle compte**. Dix pixels d'erreur sur `wall_floor` décalent
tout ce qu'on en déduira ; dix pixels sur `frame_cut` ne coûtent rien.

---

## 3. Conventions techniques

* masques en **PNG 8 bits niveaux de gris**, sans perte. Jamais de JPEG : un
  artefact de compression sur une frontière de masque *est* une frontière
  fausse ;
* **0 = non, 255 = oui.** Rien entre les deux. Le validateur refuse toute autre
  valeur — un pixel à 127 signale une interpolation ou un JPEG ;
* dimensions **exactement** celles de l'image telle que le pipeline la charge,
  c'est-à-dire **après redressement EXIF** (`image_loader.load_image`) ;
* géométrie complémentaire en coordonnées **normalisées** 0 → 1, comme
  `SceneData`. Elle survit à un changement de résolution, là où un masque
  raster n'y survit pas ;
* **aucun redimensionnement automatique.** Des dimensions qui ne correspondent
  plus sont une erreur à corriger, pas une interpolation à appliquer.

### L'orientation EXIF, et pourquoi elle est dangereuse

Un navigateur redresse une photo pour l'afficher ; notre pipeline la redresse
aussi. Rien ne garantit qu'ils obtiennent le même cadre. Un tracé fait sur une
image affichée en portrait et rastérisé sur la même image décodée en paysage
donnerait un masque **silencieusement faux** : aucune erreur levée, des
frontières partout à côté.

`scripts/import_annotation.py` recharge donc l'image avec le code du service et
**refuse** le tracé si les dimensions diffèrent. C'est le seul endroit où ce
défaut peut encore être arrêté.

---

## 4. La chaîne, du début à la fin

```bash
# 1. Enregistrer la photo et sa provenance. Le hash est calculé, pas saisi.
python -m scripts.add_photo \
    --file private-real/salon.jpg --id salon-01 --difficulty medium \
    --source "photo personnelle" --license "propriétaire" \
    --verified-on 2026-09-07 --traits furnished,rug,existing_parquet

# 2. Tracer. Ouvrir tools/annotate.html dans un navigateur, charger la photo,
#    dessiner, télécharger le .draw.json. Rien ne quitte la machine.

# 3. Rastériser et écrire l'annotation.
python -m scripts.import_annotation --draw salon-01.draw.json --annotator jonathan

# 4. Contrôler.
python -m scripts.validate_dataset

# 5. Mesurer, quand des candidats existeront.
python -m benchmarks.run_segmentation
```

### L'outil de tracé

`tools/annotate.html` : un fichier, aucune dépendance, aucune étape de
construction. Il ne fait qu'une chose — produire des polygones normalisés — et
Python possède le format.

Ce partage est délibéré : le tracé n'est qu'une **entrée intermédiaire**, et
n'importe quel autre outil peut produire le même JSON. Si l'annotation à la
main devient trop lente sur trente scènes, on peut passer à un outil externe
(Labelme, CVAT, Label Studio) et écrire un convertisseur de vingt lignes vers
`floor-draw@1`, sans rien changer au corpus déjà annoté ni aux métriques. Rien
dans le format ne dépend de l'outil.

`tests/fixtures/tool-output.draw.json` est la sortie **réelle** de l'outil, et
un test vérifie que l'import l'accepte telle quelle. C'est le contrat entre les
deux moitiés du dispositif.

---

## 5. `draft` → `reviewed` → `approved`

| statut | ce qu'il dit | entre au banc d'essai officiel |
| --- | --- | --- |
| `draft` | tracé, pas relu | **non** |
| `reviewed` | relu par une personne nommée | **non** |
| `approved` | relu, et engagé comme référence | **oui** |

Le schéma refuse un statut `reviewed` ou `approved` sans bloc `review` nommé et
daté. Sans ce refus, le champ ne serait qu'une déclaration d'intention : on
pourrait approuver sans que personne n'ait regardé, et le banc d'essai
mesurerait contre un brouillon en croyant mesurer contre une référence.

`reviewed` et `approved` sont distincts exprès. Relire, c'est constater l'état ;
approuver, c'est engager la mesure. La même personne peut faire les deux, mais
pas sans le dire.

Un masque modifié après coup est détecté par son hash : le validateur signale
l'écart et demande d'incrémenter `revision`. Un résultat de banc d'essai reste
ainsi rattachable aux octets exacts sur lesquels il a été calculé.

---

## 6. Double annotation : comment la mesurer, le jour venu

Le dispositif multi-annotateur **n'est pas construit** : à zéro photo, il n'y
aurait rien à comparer. Voici comment il se branchera, pour que rien dans le
format n'ait à changer.

Le but n'est pas de départager deux personnes. C'est d'**identifier les images
où même l'humain n'est pas certain** — parce qu'un modèle qui échoue là où deux
annotateurs se contredisent n'échoue pas, il constate.

### Le mécanisme

Une seconde annotation de la même photo se range à côté de la première, sous un
identifiant de fichier distinct (`salon-01.b.json`), avec son propre
`annotator`. Rien à changer : `photo_id` les rattache toutes les deux à la même
image.

### Les trois mesures à calculer

1. **IoU inter-annotateur** — `mask_metrics(a.floor_visible, b.floor_visible)`
   avec pour `ignore` l'**union** des deux masques d'incertitude. Le code
   existe déjà et ne fait pas de différence entre comparer un modèle à un
   humain et deux humains entre eux ;
2. **désaccord de contour** — `boundary_metrics` entre les deux, à la même
   tolérance que le banc d'essai. C'est la mesure la plus parlante : deux
   personnes s'accordent presque toujours sur la surface et se séparent sur la
   jonction mur/sol ;
3. **carte de désaccord** — le ou-exclusif des deux masques. À regarder, pas à
   moyenner : elle montre *où* le doute se concentre.

### Ce qu'on en fera

Un IoU inter-annotateur devient le **plafond** de ce qu'on peut exiger d'un
modèle sur cette photo. Exiger 0,95 là où deux personnes ne s'accordent qu'à
0,88 n'est pas de l'exigence, c'est une erreur de lecture.

Priorité pour les doubles annotations : les scènes `hard`, et celles portant
`low_wall_floor_contrast`, `hidden_corners` ou `reflective_floor`. Ce sont
celles où le désaccord est probable, donc celles où il est informatif.

---

## 7. Ce que le banc d'essai sépare

Trois choses qu'une moyenne d'IoU mélange :

* **la performance du candidat** — ses métriques, par image et agrégées ;
* **la difficulté de l'image** — agrégats par difficulté et **par trait**, pour
  répondre à « échoue-t-il sur les tapis, ou sur les sols sombres ? » ;
* **la fiabilité de la référence** — part de pixels incertains, statut,
  révision, et demain le désaccord inter-annotateur.

Un IoU de 0,80 sur une scène dont 30 % est déclarée indécidable ne dit pas la
même chose que 0,80 sur une scène nette. `ignoredFraction` est publiée avec
chaque résultat pour que la différence se voie.

Les scènes rangées en `rejected` sont **exclues des agrégats** : on n'attend pas
qu'elles soient segmentables, et les compter tirerait une moyenne vers le bas
sans rien apprendre.

---

## 8. Les métriques, et ce qu'elles ne disent pas

| métrique | répond à |
| --- | --- |
| IoU, Dice | quelle part du sol est trouvée |
| précision | ce qui est annoncé sol l'est-il |
| rappel | ce qui est sol est-il annoncé |
| F-mesure de contour | la frontière est-elle au bon endroit |

**La métrique de contour est celle qui compte pour ce projet.** Mesuré sur un
cas d'école : un masque décalé de 30 px garde un IoU de **0,67** — qu'on
lirait comme « à peu près juste » — et sa F-mesure de contour tombe à
**0,002**. C'est la frontière qui fixera le plan de perspective, donc toutes
les lames posées.

La tolérance est exprimée en **fraction de la diagonale** (0,5 % par défaut,
soit ~10 px sur 1600 × 1067), pour qu'une même erreur visuelle donne le même
score à toute résolution.

Deux comportements à connaître :

* une métrique **indéfinie** (`null`) n'est pas un zéro. Sur une scène sans sol
  visible, une prédiction vide n'est pas une segmentation parfaite : c'est une
  mesure impossible, et publier 1,0 gonflerait la moyenne du corpus à chaque
  scène sans sol ;
* le **bord du cadre** est écarté du calcul de contour. Quand le sol est coupé
  par le bas de l'image, le masque y a un bord mais la scène non ; le compter
  gonflerait la F-mesure sans rien mesurer. Conséquence : un masque couvrant
  toute l'image n'a plus aucun contour évaluable, et sa précision devient
  indéfinie plutôt que parfaite.

**Aucun seuil de réussite n'est fixé.** L'objectif hérité du front — IoU > 0,92
contre le masque humain — a été écrit avant toute donnée. Il reste la cible,
mais rien dans ce préambule ne le valide : il n'y a pas encore une seule photo
réelle annotée.

---

## 9. Provenance, licence, confidentialité

Trois régimes, et la distinction est juridique avant d'être technique.

| dossier | contenu | dans Git |
| --- | --- | --- |
| `public/` | licence autorisant la redistribution | **oui** |
| `private-real/` | tout le reste | **non** |
| `synthetic/` | généré par `scripts/build_corpus.py` | non, régénérable |
| `annotations/` | masques et JSON | **oui**, voir plus bas |

Le manifeste référence une image privée par **chemin et par hash** sans que ses
octets entrent dans le dépôt.

Deux garde-fous automatiques : `add_photo.py` refuse `--redistributable` sur un
fichier de `private-real/`, et `validate_dataset.py` refuse une image non
redistribuable rangée dans `public/` — puisque `public/` est versionné, donc
redistribué de fait.

**Une licence absente ne doit jamais devenir une licence supposée.**
`license` est obligatoire et « inconnue » est une réponse acceptable ;
`redistributable` reste alors faux, et le validateur refuse la combinaison
inverse.

`verified_on` est la date à laquelle une personne a *regardé* les conditions,
pas celle du téléchargement. Sans elle, une licence recopiée il y a deux ans se
lit comme une licence vérifiée aujourd'hui.

### Les annotations sont versionnées, y compris pour les images privées

Un masque binaire est notre travail et ne contient aucun pixel de la photo :
c'est une forme, pas une image. Les versionner préserve le seul actif coûteux
du lot — des heures de relevé humain — et permet de les relire, les comparer et
les corriger dans l'historique.

C'est un choix, et il se renverse d'une ligne dans `.gitignore`
(`datasets/annotations/masks/`) si l'on préfère considérer une silhouette
précise comme un dérivé de l'œuvre. Signalé ici pour que la décision soit
consciente plutôt que subie.

### Les photos Pexels du front

**Décision humaine déjà prise : elles ne constituent pas un corpus
redistribué dans ce dépôt.** Aucune n'a été copiée, l'API Pexels n'est pas
utilisée, et rien n'est présenté comme redistribuable.

Elles peuvent servir de **tests privés locaux** si leur provenance est
documentée entrée par entrée : `private-real/`, licence nommée,
`redistributable: false`, `usage: local_evaluation_only`.

Deux scènes du front méritent d'y passer en priorité, pour ce qu'elles
éprouvent :

* **`entree-cadree`** — recadrage, donc centre optique probablement décentré.
  Le LOT 1 a mesuré 43 % d'erreur d'intensité de distorsion sur ce cas de
  figure, et cette scène permettrait de le vérifier sur une vraie photo ;
* **`piece-arcades`** — courbes architecturales réelles. Le LOT 1 a construit
  ce cas synthétiquement (`curved_objects`) pour vérifier qu'on ne les impute
  pas à l'objectif ; en voici une version photographique.

Leur intérêt est documenté ici. Leur intégration reste une décision, et un
`add_photo.py` par photo.

---

## 10. Ce que ce préambule ne prouve pas

* **aucune photo réelle n'est annotée.** Le format, les contrôles et les
  métriques sont éprouvés sur des images synthétiques et sur un tracé produit
  par l'outil réel. Rien n'est éprouvé sur une vraie pièce ;
* **aucun seuil n'est validé.** Ni la tolérance de contour, ni la cible d'IoU,
  ni la limite de zone incertaine ;
* **le temps d'annotation est inconnu.** Une pièce meublée aux pieds fins peut
  demander bien plus qu'une pièce vide, et c'est cette durée qui décidera si
  trente scènes sont réalistes ou s'il faut un outil externe ;
* **la définition du sol visible n'a pas été éprouvée à deux.** Le tableau du
  §1 paraît clair ; c'est la première paire d'annotations indépendantes qui
  dira s'il l'est.
