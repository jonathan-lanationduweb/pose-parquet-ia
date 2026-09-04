# Architecture

## Ce que ce service fait, et ce qu'il ne fait pas

```
PHOTO  →  pose-parquet-ai  →  SceneData  →  Visualiseur (JS/WebGL)
```

Python **comprend la pièce**. Il ne dessine pas le parquet, ne choisit pas de
matériau, ne compose pas d'image. Le moteur de rendu existe déjà, il est
éprouvé, et il ne doit rien apprendre de ce service : il reçoit une
`SceneData` normalisée et il peint, sans savoir d'où elle vient.

Cette frontière est la décision d'architecture la plus importante du projet,
et elle a été prise côté front avant qu'une ligne de Python n'existe. Elle a
une conséquence agréable : **le service peut être remplacé en entier** — autre
langage, autres modèles, ou même exécution dans le navigateur — sans qu'une
seule ligne du Visualiseur bouge.

### Ce service n'a pas de base de données

Aucun PostgreSQL, aucun état persistant, aucune file d'attente. Les demandes
des utilisateurs seront gérées ailleurs. Ici : une photo entre, des mesures
sortent, la photo est oubliée. Le service est donc réplicable et jetable, et
sa mise à jour n'implique aucune migration.

### Ce service ne conserve aucune photo

Les octets sont décodés en mémoire, le tableau NumPy vit le temps de la
requête. Rien n'est écrit sur le disque, à aucun moment, pas même en fichier
temporaire.

Ce n'est pas un détail d'implémentation : aujourd'hui le Visualiseur promet à
l'utilisateur que sa photo ne quitte jamais son navigateur, et cette promesse
est affichée dans l'interface. Un service distant change cela. Quand
l'analyse automatique sera proposée, elle devra être un **choix explicite**,
jamais un comportement par défaut, et le mode local devra rester accessible en
un clic.

---

## Le pipeline

```
octets
  │
  ├─► load_image ········· validation, décodage, redressement EXIF   ✅ LOT 0
  ├─► quality_analysis ··· netteté, luminance, contraste             ✅ LOT 0
  ├─► lens_analysis ······ courbure des arêtes (mesure seule)        ✅ LOT 0
  ├─► segmentation ······· masque du sol, zones distinctes           ⏳ LOT 2
  ├─► depth ·············· carte de profondeur relative              ⏳ LOT 3
  ├─► perspective ········ horizon, points de fuite, plans, échelle  ⏳ LOT 4
  ├─► occlusion ·········· meubles, tapis, radiateurs, lignes de contact ⏳ LOT 5
  └─► scene_builder ······ assemblage de la SceneData                ⏳ LOT 6
```

Deux propriétés à conserver :

**Chaque étage est indépendant et dégradable.** Sans profondeur, le rendu perd
la netteté variable ; sans détection d'objets, l'utilisateur retouche au
pinceau ; sans géométrie, on retombe sur le quadrilatère manuel. **Rien n'est
bloquant** — et c'est ce qui permet de livrer les étages un par un.

**L'ordre n'est pas arbitraire.** Le redressement EXIF vient en premier parce
que tout le reste mesure sur l'image droite ; l'analyse d'objectif vient avant
toute géométrie parce qu'une distorsion non détectée entre dans tous les
relevés suivants sans plus rien qui la distingue du reste.

### Où vit quoi

| module                        | responsabilité                                     |
| ----------------------------- | -------------------------------------------------- |
| `app/main.py`                 | application, CORS, identifiant de requête          |
| `app/api/health.py`           | `GET /health`                                      |
| `app/api/analyze.py`          | `POST /v1/analyze-room`, lecture plafonnée         |
| `app/core/config.py`          | **tous** les seuils, lus de l'environnement        |
| `app/core/warnings.py`        | **tous** les codes d'avertissement                 |
| `app/core/errors.py`          | refus métier et leur code HTTP                     |
| `app/core/timing.py`          | les étages, et leur chronométrage                  |
| `app/core/logging.py`         | journalisation structurée                          |
| `app/schemas/scene_data.py`   | miroir du contrat du front                         |
| `app/schemas/analysis.py`     | notre contrat de sortie                            |
| `app/services/pipeline.py`    | le seul module qui connaît l'enchaînement          |
| `app/services/*.py`           | un étage, une responsabilité, aucune connaissance des autres |

`app/services/scene_builder.py` s'écarte de la règle « pas de fichier vide » :
il ne fabrique rien aujourd'hui. Sa raison d'être est de tenir **le seul
endroit** où une scène pourra naître, pour qu'on n'en trouve jamais une
deuxième ailleurs. Son en-tête explique pourquoi `None` est la bonne réponse
au LOT 0.

---

## Les deux contrats

Ils sont distincts, et la distinction est délibérée.

**`SceneData`** (`app/schemas/scene_data.py`) est le contrat **du front**. Nous
ne l'inventons pas, nous le traduisons — voir `docs/scene-data.md`. Sa version
est portée par son propre champ `schema` : `pose-parquet/scene@1`.

**`AnalysisResult`** (`app/schemas/analysis.py`) est **le nôtre** :
`pose-parquet/analysis@1`. Une analyse peut avoir beaucoup à dire sans
produire de scène du tout, et c'est exactement le cas au LOT 0. Les deux
versions bougent indépendamment.

### Le statut, et pourquoi il est pessimiste

`AnalysisStatus` vaut `success`, `partial`, `needs_manual_adjustment`,
`rejected`, ou `analysis_incomplete`. La hiérarchie de décision est dans
`pipeline._decide_status`, et `success` n'est atteignable qu'avec **une scène
et aucun avertissement**.

C'est strict, et c'est le but : il est bien plus facile de détendre ce critère
plus tard que de rattraper une géométrie fausse déjà montrée à quelqu'un.

`analysis_incomplete` est la valeur du LOT 0 et disparaîtra quand les étages
de géométrie existeront. Elle dit « les contrôles techniques ont tourné,
l'analyse de la pièce n'existe pas encore ». Elle n'est pas un échec, et
surtout pas un succès partiel : la confondre avec `partial` ferait croire
qu'un sol a été cherché.

### La confiance

`confidence` vaut `None` tant qu'aucun étage de géométrie n'existe. Ce n'est
pas de la timidité : c'est sur ce nombre que le front décide d'ouvrir ou non
l'écran de correction. Publier un 0,8 dérivé d'une variance de Laplacien
serait le pire mensonge que ce service puisse dire.

Le principe, valable pour tout le projet : **savoir dire « je ne suis pas
suffisamment sûr » plutôt que produire une mauvaise géométrie.**

---

## Journalisation

Autorisé dans un log : `request_id`, nom d'étape, durée, dimensions, format,
codes d'avertissement, code d'erreur générique.

Jamais : l'image, un extrait d'image, du base64, un nom de fichier fourni par
l'utilisateur, un chemin absolu du serveur. Le nom de fichier est une donnée
personnelle en puissance — « salon-rue-des-lilas.jpg » — et n'apprend rien sur
l'analyse. Le service ne le lit pas et ne le garde pas.

`pipeline.Analysis` sépare exprès `result` (ce qui part au client) de
`log_fields` (ce qui part dans les logs), pour qu'on ne journalise jamais
l'objet entier « parce qu'il est là » — avec, demain, une carte de masque en
base64 dedans. Un test vérifie la liste exacte des champs journalisés.

---

## Configuration

Tout seuil numérique est déclaré dans `app/core/config.py`, surchargeable par
variable d'environnement préfixée `PPAI_`. Voir `.env.example`.

La raison n'est pas l'élégance : **aucun de ces seuils n'est universel**. Une
variance de Laplacien de 120 ne veut pas dire « photo nette » dans l'absolu —
elle le veut dire pour des photos d'intérieur ramenées à 1024 px de côté, et
il faudra la réviser quand le corpus sera assez grand pour la mesurer. Un
seuil éparpillé dans le code est un seuil qu'on ne révise jamais.

C'est aussi ce qui permet à un benchmark de rejouer d'autres seuils sur des
mesures déjà enregistrées, sans réanalyser les photos : `image_quality`
mesure, `quality_warnings` classe, et les deux sont séparés.

---

## Dépendances

La fondation est volontairement légère : FastAPI, Pydantic, Uvicorn, NumPy,
OpenCV (headless), Pillow.

**Aucun framework de deep learning n'est installé.** Pas de PyTorch, pas
d'ONNX Runtime, pas de poids de modèle. Ce n'est pas un oubli : installer
plusieurs centaines de mégaoctets « par anticipation » revient à choisir avant
de mesurer, et le but du LOT 0 est précisément de rendre la mesure possible.

Voir `docs/roadmap.md` pour les candidats et les critères de choix.

### Avant d'ajouter une dépendance lourde

Il faut l'écrire ici, avec :

1. l'étage qu'elle sert et pourquoi les alternatives légères ne suffisent pas ;
2. sa licence, et celle des poids si elle en télécharge ;
3. son temps d'exécution **sur CPU** pour une photo de 1600 px, mesuré ;
4. la taille de l'image Docker après ajout ;
5. le résultat du benchmark avant / après, sur le même corpus.

Les points 3 et 5 demandent le banc d'essai. C'est pour cela qu'il vient
d'abord.
