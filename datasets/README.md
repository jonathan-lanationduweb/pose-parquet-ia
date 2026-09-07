# Corpus de test

Ce dossier décrit un corpus de photos de pièces. **Les photos elles-mêmes ne
sont pas versionnées** — seul `manifest.json` l'est.

Deux raisons, et la seconde compte plus que la première :

1. quelques dizaines de photos d'intérieur en résolution utile pèsent vite
   plus lourd que tout le reste du dépôt, et Git ne sait pas les oublier ;
2. **une photo n'appartient pas au dépôt.** Elle a un auteur, une licence, et
   parfois une personne dessus ou derrière la fenêtre. Le manifeste, lui, dit
   d'où vient chaque image et à quelles conditions on peut s'en servir. C'est
   ce fichier qui rend le corpus partageable, pas les octets.

---

## Les quatre bacs

Le classement décrit **ce que la photo demande à l'analyse**, pas sa qualité
esthétique.

| bac        | ce qu'on y met                                                                    |
| ---------- | --------------------------------------------------------------------------------- |
| `easy`     | sol dégagé, jonction mur/sol franche, perspective lisible                         |
| `medium`   | quelques meubles, une ouverture, un contraste moyen                               |
| `hard`     | les cas difficiles réellement rencontrés (voir plus bas)                          |
| `rejected` | photo dont on **attend qu'elle soit refusée**                                      |

`rejected` n'est pas un rebut. C'est la seule catégorie qui vérifie que le
service sait dire non, et elle a autant de valeur que les trois autres. Un
analyseur qui accepte tout n'a pas 100 % de réussite : il n'a pas de garde-fou.

### Ce qui rend une photo difficile

Ces catégories ne sont pas devinées : ce sont les cas que le Visualiseur a
réellement rencontrés, et le dépôt du front en garde la trace scène par scène.

| défaut                     | ce qui casse                                                     |
| -------------------------- | ---------------------------------------------------------------- |
| faible contraste mur/sol   | la jonction n'offre aucune marche de teinte : rien à relever      |
| coins occultés             | l'intersection des murs est cachée : pas de second point de fuite |
| grand-angle                | les droites courbent, la perspective n'est plus projective        |
| perspective peu observable | une seule direction mesurable, donc pas de quadrilatère prouvé    |
| recadrage                  | le centre optique n'est plus le centre de l'image                 |
| meubles devant les plinthes| la frontière du sol est masquée là où on voudrait la mesurer      |

Voir `docs/dataset.md` pour la correspondance avec les scènes du front, qui
documentent chacun de ces cas avec un relevé chiffré.

---

## Ajouter une photo

1. Déposer le fichier dans le bac qui convient, par exemple
   `datasets/hard/room-014.jpg`.
2. Ajouter une entrée dans `manifest.json` :

```json
{
  "id": "room-014",
  "file": "hard/room-014.jpg",
  "difficulty": "hard",
  "source": "Pexels — https://www.pexels.com/photo/…",
  "license": "Pexels License",
  "credit": "Prénom Nom / Pexels",
  "expectedIssues": ["wall_floor_contrast_low", "occlusion_complex"],
  "groundTruth": { "available": false },
  "notes": "Parquet clair sur murs clairs ; plinthes masquées par un buffet."
}
```

3. Vérifier que le manifeste est valide et lancer le banc d'essai :

```bash
python -m benchmarks.run_benchmark --dataset datasets
```

`id` doit être stable : c'est la clé qui permet de comparer deux rapports de
benchmark à des semaines d'intervalle. Le renommer, c'est perdre l'historique
de cette photo.

`expectedIssues` prend des **codes machine** de `app/core/warnings.py`, jamais
des phrases, et seulement des codes de `warnings.SCORED` — hors de cette liste
un code attendu serait invisible au comptage. C'est cette colonne qui
transforme une image en test : le benchmark en déduit les faux négatifs (ce que
le corpus annonçait et que l'analyse n'a pas vu) **et les faux positifs** (ce
que l'analyse a signalé sans que le corpus l'annonce).

`graded: false` marque une photo dont la bonne réponse est discutable. Elle est
mesurée et rapportée, hors comptage. Mieux vaut une zone grise documentée qu'une
vérité inventée pour gonfler un score.

---

## Vérité terrain

Le bloc `groundTruth` est prévu pour recevoir un **relevé humain** :

| champ            | contenu                                                             |
| ---------------- | ------------------------------------------------------------------- |
| `floorMask`      | PNG binaire, même cadrage que la photo : le sol tel qu'un humain le voit |
| `floorBoundary`  | polygone normalisé de la jonction mur/sol                            |
| `occlusionMask`  | PNG binaire de ce qui doit rester devant le parquet                  |
| `vanishingPoints`| points de fuite relevés, normalisés                                  |
| `camera`         | `fovDeg`, `tiltDeg`, `heightM`, `focalPx` si connus                  |
| `lens`           | coefficients radiaux, centre optique, **et leur provenance**         |
| `notes`          | tout ce que les chiffres ne disent pas                               |

**Aucune de ces valeurs ne doit être générée automatiquement, estimée, ou
remplie « pour faire complet ».** Une vérité terrain inventée transforme un
banc d'essai en machine à valider ses propres erreurs : le modèle sera comparé
à sa propre sortie et trouvera qu'il a raison. `available: false` est un état
parfaitement acceptable, et c'est celui de tout le corpus aujourd'hui.

Pour la même raison, `lens` porte la provenance de ses coefficients —
**mesurée**, **lue** dans les métadonnées, ou **supposée**. La distinction
court dans tout le projet.

---

## Corpus synthétique

`datasets/synthetic/` est autre chose, et ne doit pas être confondu avec ce
qui précède. Ce sont des images fabriquées — scènes texturées, murs lisses,
champs de lignes, damiers, aplats — puis dégradées par une transformation
**dont le paramètre est connu** : sigma de flou, gain d'exposition, coefficient
de distorsion radiale. Aucune ne contient de pièce, de sol ni de meuble.

Elles servent de repère avant de s'attaquer à des photos réelles dont
personne ne connaît la vérité : une droite y est droite au pixel près, et une
mesure de flèche qui n'y renvoie pas zéro est un bug, pas un objectif.

Il est déclaré une fois dans `corpus/catalogue.py`, avec pour chaque entrée la
transformation appliquée, le paramètre **imposé** (sigma de flou, gain
d'exposition, coefficient `k1`) et l'avertissement attendu. Le banc d'essai le
construit en mémoire :

```bash
python -m benchmarks.run_benchmark
```

Pour l'écrire sur le disque et **regarder les images** — un corpus qu'on ne
peut pas ouvrir est un corpus qu'on croit sur parole :

```bash
python -m scripts.build_corpus
```

### La vérité terrain synthétique, et sa limite

C'est la seule vérité terrain que ce projet s'autorise à produire lui-même,
parce qu'elle n'est pas estimée mais **imposée** : on part d'une image saine et
on lui applique une dégradation dont on connaît le paramètre exact.

Elle ne remplace pas une photo réelle. Une distorsion polynomiale parfaite,
sans vignettage, sans aberration chromatique et sans bruit de capteur, dit si
un détecteur voit ce qui est indiscutablement là. Elle ne dit pas s'il marchera
sur un téléphone.
