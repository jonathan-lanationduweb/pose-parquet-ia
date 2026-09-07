# Corpus de test

Trois régimes, et la distinction est **juridique avant d'être technique**.

| dossier | contenu | dans Git |
| --- | --- | --- |
| `public/` | images dont la licence autorise la redistribution | **oui** |
| `private-real/` | tout le reste : usage local d'évaluation seulement | **non** |
| `synthetic/` | corpus généré, `scripts/build_corpus.py` | non, régénérable |
| `annotations/` | relevés humains du sol : JSON + masques PNG | **oui** |
| `manifest.json` | la description de tout, quel que soit le régime | **oui** |

Le manifeste référence une image privée **par chemin et par hash** sans que ses
octets entrent jamais dans le dépôt. C'est ce qui permet d'évaluer sur des
photos qu'on ne peut pas partager, tout en gardant un corpus décrit,
vérifiable et reproductible.

Deux garde-fous automatiques tiennent la frontière :

* `scripts/add_photo.py` refuse `--redistributable` sur un fichier de
  `private-real/` ;
* `scripts/validate_dataset.py` refuse une image non redistribuable rangée
  dans `public/` — puisque `public/` est versionné, donc redistribué de fait.

---

## La difficulté n'est pas dans le chemin

Les bacs `easy/ medium/ hard/ rejected/` du LOT 0 ont disparu comme dossiers.
La difficulté est une **métadonnée du manifeste**, pas une arborescence.

La raison est pratique : la difficulté est un jugement, et un jugement se
révise. Reclasser une photo de `medium` en `hard` après l'avoir annotée ne doit
pas demander de déplacer un fichier, de corriger un chemin dans le manifeste et
de casser au passage le lien avec ses masques. Le fichier ne bouge plus ; c'est
l'étiquette qui change.

| difficulté | ce qu'on y met |
| --- | --- |
| `easy` | sol dégagé, jonction mur/sol franche, perspective lisible |
| `medium` | quelques meubles, une ouverture, un contraste moyen |
| `hard` | les cas difficiles réellement rencontrés |
| `rejected` | photo dont on **attend qu'elle soit refusée** |

`rejected` n'est pas un rebut. C'est la seule catégorie qui vérifie que le
service sait dire non, et elle a autant de valeur que les trois autres. Un
analyseur qui accepte tout n'a pas 100 % de réussite : il n'a pas de garde-fou.

Les scènes `rejected` sont **exclues des agrégats** du banc d'essai de
segmentation : on n'attend pas qu'elles soient segmentables, et les compter
tirerait une moyenne vers le bas sans rien apprendre.

---

## Les traits de scène

Ce que la scène **contient**, par opposition à ce qu'elle vaut. Vocabulaire
fermé (`SceneTrait`, 22 valeurs) : un trait libre en texte ne se compte pas, et
une liste qu'on ne peut pas compter ne sert qu'à se rassurer.

| famille | traits |
| --- | --- |
| contenu | `empty_room` `furnished` `rug` `thin_furniture_legs` `radiator` `doors` |
| nature du sol | `existing_parquet` `tiles` `uniform_floor` `dark_floor` `reflective_floor` |
| difficulté du relevé | `low_wall_floor_contrast` `hidden_corners` `cropped` `wide_angle` `easy_perspective` `hard_perspective` `blurry` |
| géométrie | `corridor` `small_room` `large_room` |
| hors sujet | `not_a_room` |

Les séparer de la difficulté permet de répondre à la question qui décidera du
modèle : **« échoue-t-il sur les tapis, ou sur les sols sombres ? »** Un corpus
rangé seulement par difficulté ne peut pas y répondre. Le banc d'essai agrège
par trait pour cette raison précise.

---

## Ajouter une photo

Passez par le script plutôt que d'éditer le JSON : la provenance y devient
obligatoire de fait, et le hash est calculé plutôt que saisi.

```bash
python -m scripts.add_photo \
    --file private-real/salon.jpg --id salon-01 --difficulty medium \
    --source "photo personnelle" --license "propriétaire" \
    --verified-on 2026-09-07 \
    --traits furnished,rug,existing_parquet,easy_perspective
```

`--id` doit être **stable** : c'est la clé qui rattache une photo à ses
annotations et qui permet de comparer deux rapports à des semaines
d'intervalle. Le renommer, c'est perdre son historique.

Puis annoter — voir `docs/annotation-protocol.md` — et contrôler :

```bash
python -m scripts.validate_dataset
```

---

## Provenance : ce qui est exigé, et pourquoi

| champ | rôle |
| --- | --- |
| `source` | d'où vient la photo. Obligatoire |
| `sourceUrl` | l'adresse, quand il y en a une |
| `author` | l'auteur, quand il est connu |
| `license` | **nom exact**. Obligatoire |
| `verifiedOn` | date à laquelle une personne a *regardé* les conditions |
| `redistributable` | **faux par défaut** |
| `usage` | `local_evaluation_only` ou `redistributable` |
| `sha256` | empreinte du fichier local, calculée |

**Une licence absente ne doit jamais devenir une licence supposée.**
« inconnue » est une réponse acceptable ; l'inventer ne l'est pas. Le
validateur refuse la combinaison « licence inconnue » + « redistribuable ».

`verifiedOn` est la date de la vérification, pas celle du téléchargement. Sans
elle, une licence recopiée il y a deux ans se lit comme une licence vérifiée
aujourd'hui.

`sha256` est ce qui permet à un rapport d'affirmer sur quels octets il a été
calculé, **même pour une image absente du dépôt**. Si le fichier change, le
validateur le dit.

---

## Les photos Pexels du front

**Décision humaine déjà prise : elles ne constituent pas un corpus redistribué
dans ce dépôt.** L'API Pexels n'est pas utilisée, rien n'est présenté comme
redistribuable, et rien n'est copié en masse.

Elles servent de **tests privés locaux**, une entrée à la fois, avec provenance
documentée : `private-real/`, licence nommée, `redistributable: false`,
`usage: local_evaluation_only`.

### Le corpus pilote du LOT 2A

Onze scènes ont été retenues ainsi, une par une, par
`scripts/collect_pilot.py` : copie depuis le dépôt du front (lu, jamais
modifié), hash calculé, provenance inscrite au manifeste. Elles restent **hors
de Git** ; le dépôt n'en garde que la description.

`redistributable: false` y enregistre une **décision humaine**, pas une limite
de licence : la licence Pexels autoriserait la redistribution, et le choix de
ne pas s'en servir a été pris en amont. Le champ dit ce qu'on fait, pas ce
qu'on pourrait faire.

Deux de ces scènes portent des cas que le LOT 1 n'avait mesurés que sur images
**synthétiques**, et sont les seules photos réelles connues à les porter :
`entree-cadree` (recadrage, centre optique décentré) et `piece-arcades`
(courbes architecturales réelles).

### Ce que le pilote ne couvre pas

Deux manques prioritaires : **aucun tapis**, et **trois scènes meublées sur
onze**. Les photos du front avaient été choisies pour leurs sols dégagés —
l'inverse de ce qu'un banc d'essai de segmentation demande.

Le futur corpus devra donc ajouter, par ordre d'utilité :

| à ajouter | pourquoi |
| --- | --- |
| **tapis** | le cas d'école du sol *caché* : il teste la définition même de `floor_visible` |
| canapé ou fauteuil **avec pieds** | du sol visible dessous, et un contact au sol large |
| table et chaises à **pieds fins** | le geste d'annotation le plus coûteux, à chronométrer |
| mobilier **au contact des murs** | la jonction mur/sol disparaît derrière l'objet |
| **radiateur** | présent une fois seulement, et toujours en second plan |
| **faible contraste** mur/sol | présent deux fois, jamais avec du mobilier |
| sol **sombre ou réfléchissant** | présent deux fois, jamais avec un tapis |

**Rien ne sera téléchargé pour combler ces cases**, et aucune recherche
automatique d'images externes ne sera lancée : une photo dont la provenance
n'est pas certaine ne peut pas servir de référence commune, donc ne sert à
rien. Ces manques se comblent par des photos dont on connaît l'origine — voir
`docs/pilot-runbook.md`, §6.

### Ce qui ne doit jamais entrer ici tout seul

Une photo envoyée un jour par un visiteur de pose-parquet.com **ne rejoint pas
ce dossier automatiquement**. Elle reste temporaire, hors de Git, hors du
manifeste, hors du banc d'essai permanent et hors des journaux — masques
dérivés compris, puisqu'un masque de sol décrit la géométrie d'une habitation.
Voir `docs/annotation-protocol.md`, §10.

---

## Vérité terrain

### Le sol

Elle a son propre format depuis le préambule du LOT 2 :
`app/schemas/annotation.py`, fichiers dans `annotations/`. Voir
`docs/annotation-protocol.md` pour les définitions — et surtout pour la
distinction entre **sol visible**, **étendue géométrique** et **incertain**,
qu'il ne faut jamais confondre.

### Le reste

Le bloc `groundTruth` du manifeste ne porte plus que ce qui concerne la caméra
et l'objectif : points de fuite, paramètres caméra, coefficients d'objectif et
leur provenance. Il servira aux LOT 3 et 4.

**Aucune de ces valeurs ne doit être générée automatiquement, estimée, ou
remplie « pour faire complet ».** Une vérité terrain inventée transforme un
banc d'essai en machine à valider ses propres erreurs : le modèle est comparé à
sa propre sortie et trouve qu'il a raison. `available: false` est un état
parfaitement acceptable, et c'est celui de tout le corpus aujourd'hui — les
onze photos du pilote comprises : personne n'a mesuré leur objectif.

---

## Cible de composition

Une vingtaine à une trentaine de scènes suffisent pour commencer à discriminer
des modèles — et une trentaine bien choisies valent mieux que trois cents
ramassées.

| bac | cible | ce qu'on y cherche |
| --- | --- | --- |
| `easy` | ~6 | la référence : si un modèle échoue ici, il est hors course |
| `medium` | ~8 | le cas courant, celui qui décidera du modèle retenu |
| `hard` | ~8 | les traits difficiles, au moins un exemplaire chacun |
| `rejected` | ~4 | vérifier que le service sait dire non |

Deux règles de sélection :

**Pas de photo sans licence claire.** Une photo sans provenance ne peut pas
être partagée, donc pas servir de référence commune, donc ne sert à rien.

**Pas de doublon de complaisance.** Une photo qui n'apporte aucun trait qu'une
autre n'apporte déjà ne fait que rallonger le temps d'annotation et de
benchmark. Le nombre est un objectif de couverture, pas un quota.

---

## Corpus synthétique

`synthetic/` est autre chose, et ne doit pas être confondu avec ce qui précède.
Images fabriquées — scènes texturées, murs lisses, champs de lignes, damiers,
aplats — puis dégradées par une transformation **dont le paramètre est connu**.
Aucune ne contient de pièce, de sol ni de meuble.

Déclaré une fois dans `corpus/catalogue.py`. Le banc d'essai de qualité le
construit en mémoire :

```bash
python -m benchmarks.run_benchmark
python -m scripts.build_corpus      # pour l'écrire sur le disque et le regarder
```

### La vérité terrain synthétique, et sa limite

C'est la seule vérité terrain que ce projet s'autorise à produire lui-même,
parce qu'elle n'est pas estimée mais **imposée** : on part d'une image saine et
on lui applique une dégradation dont on connaît le paramètre exact.

Elle ne remplace pas une photo réelle. Une distorsion polynomiale parfaite,
sans vignettage, sans aberration chromatique et sans bruit de capteur, dit si
un détecteur voit ce qui est indiscutablement là. Elle ne dit pas s'il marchera
sur un téléphone. Et pour la segmentation du sol, elle ne dit **rien du tout** :
aucune de ces images n'a de sol.
