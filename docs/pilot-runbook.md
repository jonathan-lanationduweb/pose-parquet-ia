# Marche à suivre du pilote — LOT IA 2A

Le corpus pilote est **collecté** : onze photos réelles dans
`datasets/private-real/`, chacune avec sa provenance. Le dispositif de mesure
est **prêt et testé**.

Ce qui reste est un travail humain que rien ici ne peut remplacer : **relever
le sol à la main.** Ce document dit exactement quoi faire.

> **Pourquoi je n'ai pas annoté.** Le LOT 2A mesure la difficulté d'annotation,
> le temps qu'elle prend, les hésitations humaines et le désaccord entre deux
> personnes. Ces quatre grandeurs sont des mesures *d'un humain qui annote*.
> Les produire moi-même reviendrait à fabriquer précisément les données que ce
> lot existe pour collecter — et une seconde passe faite par moi serait un
> deuxième annotateur simulé, ce que le protocole interdit.

---

## 1. Ce qui est déjà fait

```bash
python -m scripts.validate_dataset
# → 11 photo(s), 0 problème(s) · 0 scène(s) annotée(s)
```

| état | détail |
| --- | --- |
| photos | 11, dans `private-real/`, hors de Git |
| provenance | auteur, identifiant Pexels, URL, licence, hash — pour chacune |
| difficulté | 3 `easy`, 2 `medium`, 5 `hard`, 1 `rejected` |
| traits | assignés par observation des photos, **révisables** |
| annotations | **aucune** |

---

## 2. Annoter une scène

```bash
# 1. Ouvrir l'outil dans un navigateur (double-clic suffit)
#    tools/annotate.html
#
# 2. Charger la photo : datasets/private-real/bureau-vide.jpg
#    Saisir l'identifiant du manifeste : bureau-vide
#
# 3. Tracer. L'outil chronomètre tout seul et se met en pause après une
#    minute d'inactivité — inutile de noter le temps.
#
# 4. Télécharger le tracé, puis :
python -m scripts.import_annotation \
    --draw bureau-vide.draw.json --annotator votre-nom

# 5. Contrôler
python -m scripts.validate_dataset
```

L'annotation arrive en `draft`. Elle n'entre au banc d'essai qu'une fois
relue :

```bash
python -m scripts.import_annotation \
    --draw bureau-vide.draw.json --annotator votre-nom \
    --status approved --reviewer nom-du-relecteur --review-seconds 90
```

### L'ordre conseillé

Commencez par `bureau-vide`, la plus simple : elle sert à prendre la main sur
l'outil, et son temps d'annotation devient la référence à laquelle les autres
se comparent.

Gardez `petite-piece` et `appartement-ancien` pour la fin : ce sont les plus
laborieuses — huit pieds de meuble à contourner chacune — et leur durée est
l'information la plus utile du lot. C'est elle qui dira si trente scènes sont
réalistes ou s'il faut un autre outil.

---

## 3. Les quatre scènes à annoter deux fois

Choisies pour maximiser la chance de désaccord, donc d'information :

| scène | ce qui devrait faire diverger deux personnes |
| --- | --- |
| `couloir` | bois clair sur bois clair : où finit le mur ? |
| `petite-piece` | pieds fins, rideau au sol, angle masqué par le bureau |
| `salon` | reflets de fenêtre francs : sol ou pas sol ? |
| `chambre` | la terrasse vue par la porte-fenêtre compte-t-elle ? |

```bash
# Passe A
python -m scripts.import_annotation --draw couloir.draw.json \
    --annotator personne-1 --pass-label A --independent \
    --status approved --reviewer personne-1

# Passe B — SANS avoir regardé la passe A
python -m scripts.import_annotation --draw couloir.draw.json \
    --annotator personne-2 --pass-label B --independent \
    --status approved --reviewer personne-2
```

**`--independent` est une déclaration**, et l'outil ne peut pas la vérifier. Ne
la posez que si c'est vrai : le nom de la mesure en dépend, et un accord élevé
entre deux passes non indépendantes ne mesurerait que la mémoire.

### Si vous êtes seul

C'est le cas le plus probable, et il est prévu. Faites deux passes espacées —
idéalement à des jours différents — et **ne rouvrez pas la première**.

La mesure s'appellera alors `intra_annotator_repeatability` et non
`inter_annotator_agreement`. Le module le déduit des noms d'annotateur et
refuse de choisir à votre place. La différence n'est pas de vocabulaire :

* la répétabilité mesure la stabilité d'**une main**. C'est une **borne
  optimiste** — personne ne reproduit ses propres hésitations aussi mal que
  celles d'un autre ;
* l'accord mesure ce que le **protocole** transmet d'une tête à une autre.
  C'est lui qui plafonne ce qu'on peut exiger d'un modèle.

Si une seconde personne est disponible, même pour deux scènes seulement, cela
vaut mieux que quatre passes solitaires.

---

## 4. Lire les résultats

```bash
python -m benchmarks.run_pilot --render
```

Le rapport arrive dans `benchmarks/out/pilot/pilot.json`, avec une image de
comparaison par paire. La légende des couleurs :

| couleur | sens |
| --- | --- |
| vert | les deux annotateurs sont d'accord : c'est du sol |
| bleu | seule la passe A l'a compté |
| rouge | seule la passe B l'a compté |
| jaune | déclaré indécidable par au moins l'un des deux — exclu des scores |

Les chiffres à regarder, dans cet ordre :

1. **le temps**, par difficulté. C'est lui qui décide de la taille du corpus ;
2. **l'IoU minimum** entre passes. C'est le plafond réaliste, pas la moyenne ;
3. **la F-mesure de contour selon la tolérance.** Si le score bouge beaucoup
   entre 0,25 % et 1 %, le choix de tolérance compte plus que le choix de
   modèle, et il faudra le trancher avant tout benchmark ;
4. **la répartition du désaccord** — jonction, cadre, ou surface entière. Un
   désaccord de surface porte sur la **définition** du sol visible, donc sur le
   protocole ; un désaccord de jonction porte sur la main.

---

## 5. Ce qu'il faut noter en annotant

Le format prévoit un champ `notes` par annotation. Utilisez-le pour ce que les
masques ne diront pas :

* un endroit où vous avez hésité **sans** le marquer incertain, et pourquoi ;
* une catégorie du protocole qui ne collait pas ;
* un geste que l'outil rend pénible ;
* une raison d'incertitude qui manque à la liste.

Ces notes sont la matière première de la calibration de `floor-annotation@1`.
Les cinq questions ouvertes que l'examen des photos a déjà soulevées sont dans
`docs/annotation-protocol.md`, §11 — lisez-les **avant** de commencer : deux
d'entre elles changent ce que vous tracerez.

---

## 6. Ce qui manque au corpus, et que vous seul pouvez fournir

Les onze photos viennent du dépôt du front, qui les avait choisies pour leurs
**sols dégagés** — l'inverse de ce qu'un banc d'essai de segmentation demande.
Trois traits sont donc absents ou presque :

| trait | état | pourquoi c'est un manque |
| --- | --- | --- |
| `rug` | **absent** | un tapis est le cas d'école du sol *caché* : il teste la définition même de `floor_visible` |
| `furnished` | 3 sur 11 | huit scènes sur onze sont des pièces vides |
| `tiles` | 1, aperçu au loin | aucun carrelage en premier plan |

Une seule photo de votre salon avec un tapis apporterait plus au corpus que
trois pièces vides supplémentaires. Si vous en prenez, `add_photo.py` les
enregistre avec `--source "photo personnelle"` et
`--license "propriétaire"` — provenance certaine, et le corpus gagne
exactement ce qui lui manque.
