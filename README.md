# pose-parquet-ai

Service d'analyse de photo de pièce pour le Visualiseur Parquet de
[pose-parquet.com](https://pose-parquet.com).

```
PHOTO  →  pose-parquet-ai  →  SceneData  →  Visualiseur (JS/WebGL)
```

Python **comprend la pièce**. Il ne dessine pas le parquet : le moteur de rendu
existe déjà, il est éprouvé, et il n'a rien à apprendre de ce service.

> ## État : LOT IA 0 — fondation, corpus, banc d'essai
>
> Ce service **ne fait pas encore d'analyse de pièce.** Il valide et redresse
> une photo, mesure sa netteté, son exposition et la courbure de ses arêtes
> verticales, et renvoie ces mesures. Il ne cherche pas le sol, n'estime ni
> profondeur ni perspective, et ne renvoie donc **jamais** de `sceneData`.
>
> **Aucun modèle lourd n'est installé** — ni PyTorch, ni ONNX, ni poids. C'est
> l'objet même de ce lot : rendre possible la comparaison de plusieurs
> approches avant d'en choisir une. Voir [docs/roadmap.md](docs/roadmap.md).

---

## Démarrer (Windows)

Python **3.12 ou plus** est requis.

```powershell
git clone <url-du-depot> pose-parquet-ai
cd pose-parquet-ai
```

Créer l'environnement virtuel :

```powershell
python -m venv .venv
```

L'activer :

```powershell
.\.venv\Scripts\Activate.ps1
```

Si PowerShell refuse le script d'activation, autoriser les scripts locaux pour
l'utilisateur courant :

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Installer le projet et ses outils de développement :

```powershell
pip install -e ".[dev]"
```

Lancer les tests :

```powershell
pytest
```

Lancer l'API :

```powershell
uvicorn app.main:app --reload
```

Puis ouvrir <http://127.0.0.1:8000/health> — réponse attendue :

```json
{ "status": "ok", "service": "pose-parquet-ai" }
```

La documentation interactive est sur <http://127.0.0.1:8000/docs>.

### Sans activer l'environnement

Toutes les commandes marchent aussi en préfixant par l'interpréteur du venv,
ce qui évite la question de la politique d'exécution :

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

### Linux / macOS

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]" && pytest
uvicorn app.main:app --reload
```

---

## L'API

### `GET /health`

```json
{ "status": "ok", "service": "pose-parquet-ai" }
```

Volontairement pauvre : ni version d'OS, ni chemin, ni nom de machine. Le
front s'en sert pour une seule décision — proposer ou non l'analyse
automatique.

### `POST /v1/analyze-room`

`multipart/form-data`, champ `image`. Formats acceptés : **JPEG, PNG, WebP**.
Taille maximale : **20 Mo** (`PPAI_MAX_UPLOAD_BYTES`).

```powershell
curl.exe -F "image=@ma-piece.jpg" http://127.0.0.1:8000/v1/analyze-room
```

Réponse, au LOT 0 :

```json
{
  "schema": "pose-parquet/analysis@1",
  "status": "analysis_incomplete",
  "confidence": null,
  "warnings": ["lens_analysis_undetermined", "stage_not_implemented"],
  "image": {
    "width": 1600,
    "height": 1067,
    "aspectRatio": 1.49953,
    "megapixels": 1.707,
    "format": "JPEG",
    "exifOrientationApplied": false
  },
  "quality": {
    "blur": { "laplacianVariance": 284.7, "workingSide": 1024, "sharp": true },
    "exposure": {
      "lumaMean": 0.4831,
      "lumaMedian": 0.4712,
      "contrastStd": 0.1904,
      "contrastP5P95": 0.6118,
      "darkPixelRatio": 0.0041,
      "brightPixelRatio": 0.0009
    }
  },
  "lens": {
    "verdict": "undetermined",
    "maxSagittaPx": null,
    "usableEdges": 1,
    "suspectThresholdPx": 3.0,
    "correctionApplied": false
  },
  "sceneData": null,
  "timings": {
    "load_image_ms": 41.2,
    "quality_analysis_ms": 18.7,
    "lens_analysis_ms": 96.4,
    "segmentation_ms": null,
    "depth_ms": null,
    "perspective_ms": null,
    "occlusion_ms": null,
    "scene_builder_ms": 0.0,
    "total_ms": 157.1
  }
}
```

Codes de refus : `413` fichier trop volumineux, `415` format non pris en
charge, `422` fichier vide ou image indécodable.

`None` dans `timings` veut dire **« étage pas exécuté »** ; `0.0` voudrait dire
« instantané ». La distinction compte pour lire un benchmark.

### La photo n'est jamais conservée

Les octets sont décodés en mémoire, le tableau NumPy vit le temps de la
requête. Rien n'est écrit sur le disque, pas même en fichier temporaire.

### Aucune confiance n'est publiée

`confidence` vaut `null` tant qu'aucun étage de géométrie n'existe. C'est sur
ce nombre que le front décide d'ouvrir ou non l'écran de correction : publier
un 0,8 dérivé d'une variance de Laplacien serait le pire mensonge que ce
service puisse dire.

Le principe, valable pour tout le projet : **savoir dire « je ne suis pas
suffisamment sûr » plutôt que produire une mauvaise géométrie.**

---

## Banc d'essai

```powershell
python -m scripts.make_fixtures
python -m benchmarks.run_benchmark --dataset datasets/synthetic
```

Sorties dans `benchmarks/out/` : `benchmark.json` (tout, rejouable avec
d'autres seuils sans réanalyser) et `benchmark.csv` (colonnes fixes, triables).

Voir [benchmarks/README.md](benchmarks/README.md) et
[datasets/README.md](datasets/README.md).

---

## Qualité de code

```powershell
ruff check .
ruff format --check .
mypy
pytest
```

---

## Docker

CPU uniquement, aucun GPU.

```powershell
docker build -t pose-parquet-ai .
docker run --rm -p 8000:8000 pose-parquet-ai
curl.exe http://127.0.0.1:8000/health
```

---

## Configuration

Tous les seuils sont centralisés dans `app/core/config.py`, surchargeables par
variable d'environnement préfixée `PPAI_`. Copier `.env.example` en `.env`
pour surcharger localement — `.env` n'est jamais versionné.

**Aucun de ces seuils n'est universel.** Une variance de Laplacien de 120 ne
veut pas dire « photo nette » dans l'absolu : elle le veut dire pour des
photos d'intérieur ramenées à 1024 px de côté, et il faudra la réviser quand
le corpus sera assez grand pour la mesurer. C'est le rôle du LOT 1.

---

## Documentation

| document                                             | contenu                                              |
| ---------------------------------------------------- | ---------------------------------------------------- |
| [docs/architecture.md](docs/architecture.md)         | pipeline, contrats, journalisation, dépendances       |
| [docs/scene-data.md](docs/scene-data.md)             | SceneData **actuel** et SceneData **futur**          |
| [docs/dataset.md](docs/dataset.md)                   | quoi mettre dans le corpus, et pourquoi              |
| [docs/lens-distortion.md](docs/lens-distortion.md)   | ce qu'on mesure, ce qu'on ne corrige pas             |
| [docs/roadmap.md](docs/roadmap.md)                   | LOT IA 0 → 8                                         |
| [benchmarks/README.md](benchmarks/README.md)         | lancer et lire un rapport                            |
| [datasets/README.md](datasets/README.md)             | ajouter une photo, vérité terrain                    |

---

## Rapport avec le dépôt du front

Le dépôt `pose-parquet.com` a été inspecté **en lecture seule** pour établir le
contrat `SceneData`. Aucun de ses fichiers n'a été modifié, et **le contrat du
front ne doit pas l'être** : c'est à ce service de s'y conformer.

Un test valide notre schéma Pydantic contre les douze scènes réelles du front
quand le dépôt est présent localement, et s'ignore sinon
(`POSE_PARQUET_FRONT` pour le désigner ailleurs). C'est le seul test qui
prouve que le schéma n'a rien inventé.

Rien n'est connecté : ni WordPress, ni le Visualiseur. Voir LOT IA 8.
