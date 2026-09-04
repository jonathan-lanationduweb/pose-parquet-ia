# Banc d'essai

Il ne choisit aucun modèle. Il mesure, dans un format stable, ce qu'un
pipeline donné produit sur un corpus donné. Comparer deux approches, ce sera
comparer deux rapports.

C'est pour cela qu'il est construit **avant** les modèles : choisir sans
mesurer, c'est choisir la première chose qui marche à peu près.

## Lancer

```bash
python -m scripts.make_fixtures
python -m benchmarks.run_benchmark --dataset datasets/synthetic
```

Sur le corpus de photos réelles (vide au terme du LOT 0, voir
`datasets/README.md`) :

```bash
python -m benchmarks.run_benchmark --dataset datasets
```

Options : `--dataset` (dossier contenant `manifest.json`), `--out` (dossier de
sortie, défaut `benchmarks/out`, non versionné).

## Deux sorties, deux usages

**`benchmark.json`** — tout, y compris les tracés d'arêtes de chaque photo.
C'est la trace qu'on rejoue plus tard avec d'autres seuils **sans réanalyser
les photos** : `image_quality` mesure et `quality_warnings` classe, et les
deux sont séparés exprès.

**`benchmark.csv`** — une ligne par photo, colonnes fixes. Les colonnes sont
déclarées explicitement dans `CSV_COLUMNS` plutôt que déduites du contenu :
une colonne qui apparaît ou disparaît selon le corpus rendrait deux rapports
incomparables.

## Ce qui est mesuré au LOT 0

| famille    | colonnes                                                                  |
| ---------- | ------------------------------------------------------------------------- |
| image      | `width`, `height`, `aspect_ratio`, `megapixels`, `format`, `exif_applied` |
| netteté    | `blur_laplacian_variance`, `blur_sharp`                                    |
| exposition | `luma_mean`, `contrast_std`, `dark_pixel_ratio`, `bright_pixel_ratio`      |
| objectif   | `lens_verdict`, `lens_usable_edges`, `lens_max_sagitta_px`                 |
| verdict    | `status`, `warnings`, `expected_issues`, `missed_issues`                   |
| durées     | `load_image_ms`, `quality_analysis_ms`, `lens_analysis_ms`, `scene_builder_ms`, `total_ms` |

Les étages à venir — `segmentation_ms`, `depth_ms`, `perspective_ms`,
`occlusion_ms` — sont déjà déclarés dans `AnalysisResult.timings` et valent
`None`. `None` veut dire « pas exécutée » ; `0.0` voudrait dire
« instantanée ». La distinction compte pour lire un rapport.

## La colonne à lire en premier

**`missed_issues`** : ce que le manifeste annonçait et que l'analyse n'a pas
vu. Elle mesure un manque, pas une durée — et un manque coûte cher, puisque le
service aura promis un résultat sûr sur une photo qui ne l'était pas.

Son symétrique n'a pas de colonne mais se lit dans `warnings` : un défaut
signalé qu'aucun manifeste n'annonçait est un **faux positif**, et il coûte
aussi. C'est ainsi qu'a été trouvé le faux positif de distorsion sur damier
qui a donné naissance à `lens_min_track_height_ratio` — voir
`docs/lens-distortion.md`.

## Ce qu'il ne mesure pas encore

L'IoU du masque de sol contre la vérité terrain humaine, et l'écart du
quadrilatère de plan. Ce sont les deux critères de réussite du LOT 2, déjà
écrits (IoU > 0,92 ; quadrilatère à moins de 2 %). Ils demandent une vérité
terrain, et **aucune ne doit être inventée** pour faire tourner un chiffre :
voir `datasets/README.md`.
