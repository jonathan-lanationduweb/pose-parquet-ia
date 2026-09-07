# Banc d'essai

Il ne choisit aucun modèle. Il mesure, dans un format stable, ce qu'un
pipeline donné produit sur un corpus donné. Comparer deux approches, ce sera
comparer deux rapports.

C'est pour cela qu'il est construit **avant** les modèles : choisir sans
mesurer, c'est choisir la première chose qui marche à peu près.

## Lancer

```bash
python -m benchmarks.run_benchmark          # corpus synthétique, en mémoire
python -m benchmarks.compare_candidates     # marges des candidates de netteté
```

Sur le corpus de photos réelles (vide, voir `datasets/README.md`) :

```bash
python -m benchmarks.run_benchmark --source dataset --dataset datasets
```

Options : `--source` (`synthetic` ou `dataset`), `--dataset` (dossier contenant
`manifest.json`), `--out` (défaut `benchmarks/out`, non versionné).

## Deux sorties, deux usages

**`benchmark.json`** — tout, y compris les tracés d'arêtes de chaque photo.
C'est la trace qu'on rejoue plus tard avec d'autres seuils **sans réanalyser
les photos** : `image_quality` mesure et `quality_warnings` classe, et les
deux sont séparés exprès.

**`benchmark.csv`** — une ligne par photo, colonnes fixes. Les colonnes sont
déclarées explicitement dans `CSV_COLUMNS` plutôt que déduites du contenu :
une colonne qui apparaît ou disparaît selon le corpus rendrait deux rapports
incomparables.

## Ce qui est mesuré

| famille       | colonnes                                                                    |
| ------------- | --------------------------------------------------------------------------- |
| identité      | `id`, `difficulty`, `graded`, `status`, `blur_method`, `lens_method`        |
| image         | `width`, `height`                                                           |
| netteté       | `strong_gradient_ratio`, `laplacian_variance`, `reblur_ratio`, `edge_width_px`, `blur_sharp`, `blur_low_texture` |
| exposition    | `luma_mean`, `contrast_std`, `clipped_high_ratio`, `clipped_low_ratio`      |
| objectif      | `lens_verdict`, `lens_suspected_sign`, `lens_usable_edges`, `lens_total_track_px`, `lens_spatial_coverage`, `lens_sign_agreement`, `lens_k1_estimate`, `lens_k1_residual_gain` |
| vérité terrain| `truth_k1`, `truth_sign`, `truth_blur_sigma`, `truth_exposure_gain`, `k1_absolute_error`, `sign_correct` |
| comptage      | `expected`, `detected`, `false_positives`, `false_negatives`, `informational` |
| durées        | `load_image_ms`, `quality_analysis_ms`, `lens_analysis_ms`, `total_ms`     |

Les **trois** candidates de netteté sont enregistrées à chaque ligne, quelle
que soit celle qui conclut : un rapport permet donc de rejouer un choix de
méthode sans réanalyser le corpus. `blur_method` et `lens_method` disent
laquelle a tranché.

Les étages à venir — `segmentation_ms`, `depth_ms`, `perspective_ms`,
`occlusion_ms` — sont déjà déclarés dans `AnalysisResult.timings` et valent
`None`. `None` veut dire « pas exécutée » ; `0.0` voudrait dire
« instantanée ». La distinction compte pour lire un rapport.

## Reproductibilité

Chaque rapport embarque sa version, la graine du corpus, l'environnement, et
**l'instantané complet des réglages d'algorithme**
(`Settings.algorithm_config()`, trente valeurs). Sans ce dernier, deux rapports
ne sont pas comparables : on lit deux séries de chiffres sans savoir lequel des
deux seuils était en vigueur.

## Les deux colonnes à lire en premier

**`false_negatives`** : ce que le corpus annonçait et que l'analyse n'a pas vu.
Un manque coûte cher — le service aura laissé passer une photo inexploitable.

**`false_positives`** : ce que l'analyse a signalé et que le corpus n'annonçait
pas. Le LOT 0 ne comptait pas cette colonne, et c'était son défaut
méthodologique : un détecteur qui déclare tout sur tout ne manque rien non
plus. Un utilisateur à qui l'on signale cinq problèmes sur une photo correcte
cesse de lire les avertissements.

**Aucun chiffre de rappel n'est publié sans son faux positif**, et aucune
« exactitude » n'est publiée du tout : sur un problème multi-label
majoritairement négatif, elle est dominée par les vrais négatifs et flatte un
détecteur muet. Voir `benchmarks/scoring.py` et
`docs/quality-methodology.md`.

## Ce qu'il ne mesure pas encore

L'IoU du masque de sol contre la vérité terrain humaine, et l'écart du
quadrilatère de plan. Ce sont les deux critères de réussite du LOT 2, déjà
écrits (IoU > 0,92 ; quadrilatère à moins de 2 %). Ils demandent une vérité
terrain, et **aucune ne doit être inventée** pour faire tourner un chiffre :
voir `datasets/README.md`.
