# Protocole d'annotation du sol

Ce document définit la vérité terrain du LOT 2 : ce qu'on annote, comment, et
ce qu'on refuse d'annoter. Il s'adresse à qui va tenir la souris.

**Aucun modèle** n'est en place, et ce n'est pas un manque : ce document et le
dispositif qui l'accompagne sont la *balance*. Format, contrôles, métriques,
mesure de l'accord humain, mesure du temps — tout ce contre quoi un modèle sera
un jour pesé.

| | |
| --- | --- |
| Infrastructure LOT IA 2A | **VALIDÉE** |
| Expérience LOT IA 2A | **EN ATTENTE DES ANNOTATIONS HUMAINES** |
| LOT IA 2B | **non autorisé** avant analyse des premières annotations |

Onze photos réelles sont collectées, et une campagne de **quatre scènes × deux
passes** est prête (`docs/pilot-runbook.md`). **Aucune n'est encore annotée** :
c'est le relevé humain qui manque, et lui seul dira si ce protocole tient.

---

## 1. Les trois notions à ne jamais confondre

### Le sol visible — `floor_visible`

> **Définition officielle.** `floor_visible` représente les pixels du **sol
> intérieur réellement visible** appartenant à la surface **candidate au
> remplacement visuel par le parquet**.

Trois mots portent la définition, et chacun exclut quelque chose :

* **intérieur** — une surface extérieure n'en fait pas partie, même vue de
  plain-pied par une baie grande ouverte ;
* **réellement visible** — ce qui est caché est hors du masque, sans
  reconstruction mentale ;
* **candidate au remplacement** — une surface sur laquelle on ne posera jamais
  de parquet n'y est pas, même quand c'est bien du sol.

C'est le seul masque contre lequel une segmentation sera mesurée, et il reste
décidable en regardant l'image : chacune de ces trois conditions se constate,
aucune ne se déduit.

| ce qu'on voit | sol visible ? |
| --- | --- |
| parquet, carrelage, béton, lino apparent | **oui** |
| sol intérieur visible par une porte, une embrasure, une enfilade | **oui** |
| reflet sur le sol | **oui** — c'est le sol, éclairé autrement |
| ombre portée sur le sol | **oui** — c'est le sol, moins éclairé |
| tapis, carpette, paillasson | **non** — ils cachent le sol |
| meuble, canapé, carton posé | **non** |
| pied de chaise, de table, de lit | **non** |
| grille de ventilation, bouche de soufflage encastrée | **non** — voir plus bas |
| trappe technique, regard, plaque encastrée | **non** — voir plus bas |
| terrasse, balcon, jardin, allée, sol extérieur | **non** — voir plus bas |
| plinthe | **non** — elle appartient au mur |
| mur, porte, fenêtre, plafond | **non** |

Reflet et ombre sont les deux lignes qui font hésiter. La règle : on annote la
**surface**, pas son éclairement. Un sol dans l'ombre reste du sol, un sol qui
renvoie une fenêtre reste du sol.

#### La surface extérieure est exclue

**Décision prise.** Une surface extérieure visible par une porte, une baie ou
une porte-fenêtre est **hors de `floor_visible`** : terrasse, balcon, jardin,
allée, et tout sol extérieur aperçu par une ouverture.

**Y compris quand elle est horizontalement continue avec le sol intérieur** —
une terrasse de plain-pied dans le prolongement du parquet reste dehors. La
continuité visuelle n'est pas un argument : c'est justement le piège, et c'est
pourquoi la règle est écrite.

La raison est la finalité : on ne posera pas de parquet sur une terrasse. Un
segmenteur qui la trouve n'a pas trouvé sa cible, et le masquer comme du sol
lui apprendrait à se tromper.

Le **seuil ou l'encadrement** de l'ouverture peut alors recevoir sa propre
polyligne de contour : c'est là que le sol candidat s'arrête, et cette limite
est aussi réelle qu'une jonction mur/sol.

#### Les éléments techniques encastrés sont exclus

**Décision prise.** Une grille de ventilation, une bouche de chauffage, une
trappe technique ou tout autre élément encastré **qui n'est pas destiné à
recevoir du parquet** est hors de `floor_visible`.

**Le sol visible autour reste inclus** : on exclut l'élément, pas la zone qui
le contient.

Un tel élément est dans le plan du sol, mais il n'est pas une surface
recouvrable — exactement comme un tapis n'est pas du sol visible. La règle est
donc la même que pour les objets, et elle se lit dans le même sens : ce qui
occupe le sol n'est pas le sol.

Ces éléments sont petits, donc presque sans effet sur l'IoU — mais ils
comptent pour la **F-mesure de contour**, qui est la métrique qui décide de ce
projet.

> Il ne s'agit **pas** ici d'occlusions au sens du LOT IA 5. Rien n'est
> reconstruit, rien n'est classé par nature d'objet : on décrit seulement la
> vérité terrain de la **segmentation visible**, et un élément encastré en est
> absent comme un canapé en est absent.

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

**Règle de tracé, vérifiée pendant le LOT 2A :** une zone `uncertain` doit
couvrir **toute la région dont la frontière est réellement ambiguë**, et non
une ligne symbolique au milieu de cette ambiguïté. Si vous ne savez pas où le
mur rencontre le sol à dix pixels près, la zone doit être large de ces dix
pixels — pas d'un trait.

La raison est mesurable et elle est démontrée au §11.5 : une frontière de
masque est **épaisse de plusieurs pixels**, et une zone tracée au ras du doute
laisse évaluer précisément ce que vous aviez déclaré indécidable. Les pixels
exclus sont comptés et publiés (`ignoredFraction`) : une zone honnêtement large
ne cache rien, elle se déclare.

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
#    Le champ « Passe » (A, B…) suffixe le fichier et est repris à l'import :
#    sans lui, deux passes de la même photo portent le même nom et la
#    seconde écrase la première, sans erreur.

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

### Quand `reviewer` est aussi `annotator` : auto-relecture

Le cas est admis — à une personne, il n'y a pas d'autre relecteur — et il doit
être **nommé pour ce qu'il est** :

| `annotator` et `reviewer` | ce que la relecture vaut |
| --- | --- |
| noms **identiques** | **auto-relecture** : la même personne constate son propre travail |
| noms **différents** | **revue indépendante** : un second regard |

Une auto-relecture attrape les fautes d'exécution — masque oublié, trou mal
fermé, contour rangé dans la mauvaise catégorie. Elle n'attrape pas les fautes
de **lecture**, puisque c'est la même lecture qui relit : une interprétation
erronée mais cohérente y survit intacte.

Un banc d'essai dont toute la vérité terrain est auto-relue n'est donc pas
faux, mais son plafond de fiabilité est plus bas qu'il n'y paraît. C'est
exactement ce que les deux passes indépendantes servent à mesurer — et c'est
pourquoi la répétabilité ne doit jamais être présentée comme un accord entre
deux personnes.

Un masque modifié après coup est détecté par son hash : le validateur signale
l'écart et demande d'incrémenter `revision`. Un résultat de banc d'essai reste
ainsi rattachable aux octets exacts sur lesquels il a été calculé.

---

## 6. Double annotation

Le but n'est pas de départager deux personnes. C'est d'**identifier les images
où même l'humain n'est pas certain** — parce qu'un modèle qui échoue là où deux
annotateurs se contredisent n'échoue pas, il constate.

Le dispositif est construit (`benchmarks/agreement.py`) ; il attend des
relevés.

### Le nom de la mesure dépend de qui a annoté

| qui | nom de la mesure | ce qu'elle vaut |
| --- | --- | --- |
| deux personnes différentes | `inter_annotator_agreement` | ce que le protocole transmet d'une tête à une autre |
| la même personne, deux passes | `intra_annotator_repeatability` | la stabilité d'une main — **borne optimiste** |

La seconde n'est **pas** un accord inter-annotateurs, et ne doit jamais être
nommée ainsi : personne ne reproduit ses propres hésitations aussi mal que
celles d'un autre. Le module déduit le nom des champs `annotator` et refuse de
le choisir à notre place, précisément parce que le chiffre servira de plafond
aux exigences posées aux modèles.

### Le mécanisme

Une seconde annotation de la même photo se range à côté de la première :

```bash
python -m scripts.import_annotation --draw salon.b.draw.json     --annotator jonathan --pass-label B --independent --seconds 240
```

`--pass-label` nomme la passe et suffixe les fichiers (`salon.B.json`,
`salon.floor_visible.B.png`) ; `photo_id` les rattache toutes les deux à la
même image. `paired_scenes()` retrouve les paires, `primary_scenes()` choisit
une passe par photo pour les agrégats — sans quoi une photo annotée deux fois
compterait double.

`--independent` déclare que la seconde passe a été faite **sans regarder la
première**. C'est une déclaration, invérifiable par l'outil, et le rapport la
publie comme telle : un accord élevé entre deux passes non indépendantes peut
ne mesurer que la mémoire de celui qui a dessiné.

### Ce qui est mesuré

1. **surface** — IoU, Dice, précision, rappel, avec pour `ignore` l'**union**
   des deux masques d'incertitude. Si A déclare un coin indécidable et B non,
   ce coin sort de la comparaison : on ne peut reprocher ni à B de l'avoir
   tranché ni à A de s'être abstenu ;
2. **contour, à plusieurs tolérances** — 0,25 %, 0,5 % et 1 % de la diagonale.
   Le but n'est pas de trouver la bonne, mais de voir **de combien le score
   bouge** quand on la change. Mesuré sur un tremblement de 5 px : F1 = 0 à
   0,25 % et 0,5 %, et 0,73 à 1 %. Le réglage compte donc plus que
   l'annotation, et cela doit être dit avant qu'un chiffre serve d'exigence ;
3. **désaccord sur l'incertitude** — `ignoredFraction` des deux relevés et leur
   écart. Deux personnes qui ne renoncent pas aux mêmes endroits ne lisent pas
   la même image ;
4. **où se concentre le désaccord** — le long de la jonction (un trait qui
   tremble), contre le bord du cadre, ou en **plein intérieur**. Le troisième
   est le plus instructif : c'est un tapis, une ombre, un reflet que l'un a
   compté comme sol et l'autre pas — un désaccord sur la **définition**, pas
   sur la main. Les cinq plus gros foyers sont localisés en coordonnées
   normalisées ;
5. **une image par paire** — `--render` écrit un PNG : vert = accord, bleu = A
   seul, rouge = B seul, jaune = incertain. Un désaccord se regarde avant de
   se moyenner.

Les quatre scènes retenues pour la campagne pilote sont fixées dans
`benchmarks/campaign.py`, avec la raison de chaque choix : `sejour` (`easy`),
`chambre` (`medium`), `couloir` (`hard`) et `petite-piece` (la plus ambiguë).
Le critère n'était pas de remplir les catégories — quatre pièces vides bien
réparties n'apprendraient rien — mais que chacune apporte un cas qu'aucune
autre ne porte : enfilade et reflets, extérieur et grille encastrée, jonction
sans plinthe, pieds fins et angle masqué.

Priorité pour d'éventuelles doubles annotations supplémentaires : les scènes
`hard`, et celles portant `low_wall_floor_contrast`, `hidden_corners` ou
`reflective_floor`. Ce sont celles où le désaccord est probable, donc celles où
il est informatif.

### Ce qu'on en fera

Un accord humain devient le **plafond** de ce qu'on peut exiger d'un modèle sur
cette photo. Exiger 0,95 là où deux personnes ne s'accordent qu'à 0,88 n'est
pas de l'exigence, c'est une erreur de lecture.

---

## 7. Le temps d'annotation est une mesure officielle

Ce que coûte une annotation décide de la taille du corpus qu'on peut se
permettre. Trente scènes à quatre minutes et trente scènes à vingt minutes ne
sont pas le même projet.

Trois durées, séparées parce qu'elles ne se réduisent pas de la même façon :

| champ | ce qu'il mesure |
| --- | --- |
| `firstPassSeconds` | le premier tracé, du chargement à l'export |
| `correctionsSeconds` | les reprises après relecture |
| `reviewSeconds` | la relecture elle-même |

`tools/annotate.html` chronomètre le premier tracé tout seul et l'exporte dans
`drawSeconds` : la mesure la plus fastidieuse à tenir à la main est la seule
automatisée. Le compteur **se met en pause après 60 s sans geste**, pour qu'une
pause-café ne devienne pas du temps d'annotation. Les deux autres durées se
saisissent à l'import (`--corrections`, `--review-seconds`).

L'outil ne mesure rien d'autre. Pas de trace de gestes, pas d'envoi, pas de
télémétrie : un chronomètre qui s'arrête quand la main s'arrête.

Le rapport publie moyenne, médiane, minimum, maximum, et les écarts par
difficulté — mais compte séparément les relevés **chronométrés** : une moyenne
sur trois relevés minutés parmi douze ne dit pas ce que coûte le corpus, et il
faut pouvoir s'en apercevoir.

---

## 8. Ce que le banc d'essai sépare

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

## 9. Les métriques, et ce qu'elles ne disent pas

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

La tolérance est exprimée en **fraction de la diagonale**, pour qu'une même
erreur visuelle donne le même score à toute résolution.

**Décision prise : aucune tolérance n'est définitive.** Les trois sont
calculées et publiées ensemble, pour les mesures pilotes comme pour les futurs
bancs d'essai :

| clé | fraction de diagonale | ~px sur 1600 × 1067 |
| --- | --- | --- |
| `BF@0.25%` | 0,0025 | ~5 |
| `BF@0.5%` | 0,005 | ~10 |
| `BF@1%` | 0,01 | ~19 |

**Aucune des trois n'est un objectif produit**, et aucune ne doit être retirée
des rapports de calibration humaine. La raison est mesurée : un tremblement de
5 px donne F1 = 0,000 aux deux premières et 0,734 à la troisième. Publier une
seule valeur ferait passer un choix de réglage pour un résultat — et le réglage
pèse ici plus lourd que l'annotation.

`config.boundary_tolerance_fraction` garde 0,5 % comme valeur d'un calcul
isolé, mais ce n'est **pas** un seuil retenu : c'est le milieu des trois.

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

## 10. Provenance, licence, confidentialité

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

### `private-real/` n'est pas un dépôt de photos d'utilisateurs

`private-real/` est un **corpus de développement contrôlé** : des images qu'une
personne a choisies une par une, dont elle a vérifié la provenance, et qu'elle
a inscrites au manifeste à la main. Rien n'y entre autrement.

Une photo envoyée un jour par un visiteur de pose-parquet.com **ne doit jamais
y entrer automatiquement**. Elle doit rester :

* **temporaire** — traitée en mémoire, jamais écrite pour être conservée ;
* **hors de Git** — aucune trace dans le dépôt, même privée ;
* **hors du corpus persistant** — aucune inscription au manifeste ;
* **hors du banc d'essai permanent** — jamais une référence contre laquelle on
  mesure ;
* **hors des journaux** — ni image, ni base64, ni chemin.

Le masque dérivé compte comme la photo. Un masque de sol décrit la **géométrie
d'une habitation** : la forme des pièces, l'emplacement des ouvertures, la
disposition du mobilier. Le conserver « parce qu'il ne contient pas l'image »
serait une erreur d'appréciation.

Une photo d'utilisateur ne pourra rejoindre le corpus que par une décision
humaine explicite, avec un consentement documenté — c'est-à-dire par le même
chemin que n'importe quelle autre image : `add_photo.py`, provenance saisie,
`verified_on` renseignée. Aucune infrastructure ne doit rendre ce chemin
automatique.

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

**Décision humaine déjà prise : elles ne constituent pas un corpus redistribué
dans ce dépôt.** L'API Pexels n'est pas utilisée, aucune collecte n'est
automatisée, et rien n'est présenté comme redistribuable.

Elles servent de **stress-tests privés locaux**, une entrée à la fois, avec
provenance documentée : `private-real/` (hors de Git), licence nommée,
`verified_on` renseignée, `redistributable: false`,
`usage: local_evaluation_only`. Onze scènes ont été retenues ainsi pour le
pilote du LOT 2A — voir `datasets/README.md`.

`redistributable: false` est une **décision conservatrice du projet**, et le
projet **ne conclut pas** ici sur la réutilisabilité de ces images dans un
dataset IA public ou redistribué. Le champ dit ce qu'on fait, et rien de plus :
il ne constate pas une interdiction et n'accorde pas une permission.

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

## 11. Ce que les vraies photos ont appris

Le corpus pilote a été collecté et **regardé** avant d'être annoté. Six
questions que le tableau du §1 ne tranchait pas sont apparues.

**Les deux premières sont tranchées** — décisions humaines prises après le
rapport du LOT 2A, reportées dans la définition officielle du §1. Elles sont
gardées ici avec leur raisonnement, parce qu'une règle dont on a perdu le motif
finit par être contournée.

`floor-annotation@1` **n'est pas modifié** : ces questions demandaient des
décisions, pas du code.

### 11.1 — La surface extérieure vue par une ouverture : **exclue** ✅

**Où** : `chambre`, terrasse visible par une porte-fenêtre
(trait `exterior_visible`).

Le tableau d'origine disait « sol aperçu à travers une porte ouverte → oui ».
La règle visait une pièce voisine. Sur `chambre` c'est une terrasse : une
surface qu'on voit franchement, qui est bien un sol, et sur laquelle **on ne
posera jamais de parquet**.

Les deux lectures possibles ne donnaient pas le même masque :

* *tout sol visible* — fidèle à la lettre du tableau, et laissait au LOT 6 le
  soin de trier l'intérieur de l'extérieur ;
* *sol intérieur candidat au parquet* — fidèle à la finalité, mais introduit
  dans `floor_visible` un jugement sur la **destination** de la surface.

**Décision : la seconde.** `floor_visible` est la cible d'un segmenteur dont le
but est de trouver *le sol à recouvrir* ; une terrasse n'en fait pas partie,
même de plain-pied et dans le prolongement exact du parquet. Le §1 porte
désormais la définition, la liste des cas exclus, et le rôle du seuil comme
contour.

Ce que la décision coûte : un annotateur doit désormais reconnaître le
**dehors**, ce qui est un jugement de plus. Le pilote dira si c'est une source
de désaccord — `chambre` fait partie des quatre scènes à double passe
précisément pour cela.

### 11.2 — Les éléments techniques encastrés : **exclus** ✅

**Où** : `chambre` (grille de ventilation dans le parquet), `salon` (bouche de
soufflage encastrée).

Ils sont dans le plan du sol, mais ne sont pas des surfaces recouvrables — au
même titre qu'une trappe technique ou un regard.

**Décision : hors de `floor_visible`, le sol visible autour restant inclus.**
La règle rejoint celle des tapis et des meubles, et se lit dans le même sens :
ce qui occupe le sol n'est pas le sol.

Effet mesurable : négligeable sur l'IoU — ce sont de petites surfaces — mais
réel sur la **F-mesure de contour**, puisque chaque élément ajoute un contour
fermé à retrouver. C'est donc la métrique qui compte qui en portera la trace.

### 11.3 — Deux sols différents dans la même photo

**Où** : `entree-cadree`, où le parquet cède la place à un sol clair de couloir
au-delà d'un seuil.

Les deux sont du sol **intérieur** visible et candidat au parquet : les deux
entrent donc dans le masque, la décision du §11.1 ne les sépare pas. Mais
`floor_visible` mélange alors deux surfaces que le Visualiseur traiterait
séparément — le front modélise exactement cela avec ses `surfaces` et ses
`planeRef`.

Ce n'est pas un défaut du format : c'est la limite de ce qu'un masque binaire
peut dire. La question à trancher est celle de la **cible du LOT 2** : segmenter
« tout sol visible », ou « le sol de cette pièce » ? Le premier est plus simple
à annoter et à mesurer ; le second est ce dont le produit a besoin.

**Recommandation** : garder « tout le sol intérieur candidat » pour le LOT 2,
tracer un contour `door_threshold` là où le revêtement change, et laisser la
séparation en surfaces au LOT 6, qui aura la perspective pour la faire. À
signaler dans les `notes` de la scène.

Encore ouvert, mais sans effet sur le tracé : le contour marque déjà la limite,
donc l'information ne sera pas perdue quel que soit le choix final.

### 11.4 — Les reflets francs

**Où** : `salon` (parquet foncé très réfléchissant), `sejour`.

Le §1 tranche déjà : un reflet est du sol, on annote la surface et non son
éclairement. Les photos confirment que la règle est **tenable** mais qu'elle
demande un effort : sur `salon`, le reflet de la fenêtre est assez lumineux
pour qu'on soit tenté de l'exclure. La raison d'incertitude `reflection`
existe ; l'usage dira si elle sert.

Aucune décision nécessaire. Signalé parce que c'est un endroit où deux
annotateurs divergeront, et où le désaccord sera *instructif* plutôt que
fautif.

### 11.5 — Une zone incertaine doit couvrir ce qu'elle excuse ✅

Trouvé en écrivant les tests, pas sur les photos, mais c'est une règle
d'annotation — reprise au §1 pour qu'on la lise avant de dessiner.

**La règle** : une zone `uncertain` couvre toute la région dont la frontière est
ambiguë, pas une ligne symbolique en son centre.

**Le cas observé.** Un décrochement de masque produit une frontière **épaisse
de plusieurs pixels** : le contour d'une marche occupe cinq colonnes, pas une. Une zone
incertaine tracée au ras de l'incertitude laisse ces colonnes évaluées, et
l'annotateur se voit reprocher exactement ce qu'il avait déclaré indécidable —
la précision de contour tombe alors à 0,93 au lieu de 1,00.

**Consigne** : tracez la zone incertaine **un peu plus large** que votre doute.
Elle ne coûte rien de trop — les pixels exclus sont comptés et publiés dans
`ignoredFraction` — et elle évite une pénalité que rien ne justifie.

Mesuré sur le cas exact : un décrochement à `x = 300`, une zone incertaine
tracée jusqu'à `x < 300` → précision de contour **0,929**. La même zone étendue
à `x < 308`, c'est-à-dire couvrant l'épaisseur du décrochement → **1,0000**.
Le masque n'avait pas changé ; seule la déclaration d'incertitude l'avait.

La métrique n'a **pas** été modifiée : elle respectait déjà la règle, et
`tests/test_boundary_uncertain.py` fige ce comportement pour que la consigne
reste rattachée à sa raison.

### 11.6 — Une scène `rejected` peut avoir un sol parfaitement annotable

**Où** : `contraste` — un mur, un rai de soleil, une lisière de sol.

`rejected` veut dire « on n'attend pas de `SceneData` exploitable », pas « le
sol est indéchiffrable ». Son sol se trace en quatre points. Le validateur
*autorise* un masque vide sur une scène `rejected` ; il ne l'exige pas, et
annoter le sol de `contraste` en fait un contrôle négatif utile : un segmenteur
qui échoue là échoue sur le cas le plus simple du corpus.

---

## 12. Ce que ce dispositif ne prouve pas

* **aucune photo réelle n'est annotée.** Le format, les contrôles et les
  métriques sont éprouvés sur des images synthétiques et sur un tracé produit
  par l'outil réel. Rien n'est éprouvé sur une vraie pièce — l'infrastructure
  est validée, l'expérience ne l'est pas ;
* **les deux décisions du §11 ne sont pas encore appliquées.** Extérieur exclu
  et élément encastré exclu sont écrites et testables ; c'est `chambre` qui
  dira si elles se laissent appliquer sans hésitation ;
* **aucun seuil n'est validé.** Ni la tolérance de contour, ni la cible d'IoU,
  ni la limite de zone incertaine ;
* **le temps d'annotation est inconnu.** Une pièce meublée aux pieds fins peut
  demander bien plus qu'une pièce vide, et c'est cette durée qui décidera si
  trente scènes sont réalistes ou s'il faut un outil externe ;
* **la définition du sol visible n'a pas été éprouvée à deux.** Le tableau du
  §1 paraît clair ; c'est la première paire d'annotations indépendantes qui
  dira s'il l'est. Le §11 montre qu'il ne l'est déjà pas sur deux points ;
* **le corpus pilote penche vers le facile.** Les onze photos viennent du dépôt
  du front, qui les avait choisies pour leurs sols **dégagés** — l'inverse de
  ce qu'un banc d'essai de segmentation demande. Aucun tapis, trois scènes
  meublées sur onze. Voir `docs/pilot-runbook.md`, §6.
