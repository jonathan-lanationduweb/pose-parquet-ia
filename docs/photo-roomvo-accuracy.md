# Photo utilisateur : géométrie, masques et exécution Intel

Le visualiseur local utilise toujours `scripts.product_dev`, avec chargement du
modèle en arrière-plan, file d'attente d'import et correction manuelle possible.
Les photos ne sont ni servies depuis `datasets/private-real/`, ni versionnées.

## Corrections

- Les lignes de texture à l'intérieur du sol ne dominent plus les lignes
  structurelles de la pièce. Toutes les paires de points de fuite sont évaluées.
  Horizon et focale proviennent de la même hypothèse cohérente.
- Quand deux directions sont mesurées, le plan conserve le tangage et le roulis.
  Son carré de référence de 4×4 mètres définit une homographie ; il ne prétend pas
  mesurer une pièce de quatre mètres. La hauteur de caméra reste supposée à 1,50 m.
- Les largeurs projetées de 92, 150 et 190 mm sont vérifiées dans le plan réel.
- Le raffinement utilise les couleurs de l'image originale seulement autour des
  frontières incertaines, avec des graines de chaque côté. Pas de dilatation globale.
  Les trous intérieurs et les petits polygones de pieds sont conservés.
- La décision rapporte confiance sémantique (non calibrée), modification du masque,
  géométrie, plausibilité de l'échelle et validité SceneData. Une scène utilisable
  incertaine peut être rendue avec une carte de correction. Un masque trop limité
  conserve le parcours manuel ; « Poser quand même » ne contourne pas les erreurs
  géométriques bloquantes.
- Les requêtes d'analyse sont sérialisées pour éviter plusieurs modèles concurrents.
  Une requête déconnectée en attente ne déclenche pas de nouvelle inférence.

## Runtime optionnel

Le même checkpoint OneFormer peut être exporté pour OpenVINO. Aucun téléchargement
ni export ne se produit au moment d'une photo. Sans graphe local validé, `auto`
conserve PyTorch. `PPAI_INFERENCE_BACKEND=openvino` exige les graphes préparés.
`PPAI_OPENVINO_DEVICE=GPU` utilise le GPU Intel disponible ; à défaut, le CPU.
Le cache de compilation reste dans `models/openvino-cache/`, hors Git.

Après installation des dépendances d'inférence décrites dans
[FLOOR-SEGMENTATION-EXPLORATORY.md](FLOOR-SEGMENTATION-EXPLORATORY.md) :

```powershell
.\.venv\Scripts\python.exe -m pip install '.[openvino]'
.\.venv\Scripts\python.exe -m scripts.export_oneformer_openvino --device GPU
.\.venv\Scripts\python.exe -m scripts.product_dev
```

L'export utilise des images synthétiques. `--validation-photo` peut vérifier les
résultats sur une photo locale privée sans la copier dans un dossier public.
`--reuse-raw` évite une nouvelle conversion si les graphes bruts sont présents.
Le manifeste exige la conformité numérique ; il ne constitue pas une vérité terrain.
La compilation initiale et les premiers kernels peuvent prendre plusieurs minutes
sur ce poste chargé. Ils sont séparés des mesures d'analyse chaude.

Le profil rectangulaire 352×512 conserve mieux le contexte des photos larges que
le padding carré. Les autres proportions utilisent 512×512. Aucun choix par nom
ou empreinte de photo. Les essais de fusion du post-traitement FP16 ont échoué au
seuil de fidélité fixé ; ils restent désactivés par défaut. Le chemin retenu utilise
le modèle GPU et un post-traitement OpenVINO CPU FP32 ; le repli PyTorch conserve
l’argmax par blocs. Les deux profils sont préchauffés avant le statut ready.
Le modèle GPU brut accepte au maximum 1 % d’écart de surface relatif à PyTorch
(conformité numérique, pas vérité terrain). Une fusion supplémentaire exige
un seuil plus strict afin de ne pas cumuler une nouvelle perte de précision.

Cette intégration suit les interfaces officielles de
[conversion OpenVINO](https://docs.openvino.ai/2024/openvino-workflow/model-preparation/convert-model-to-ir.html).
L'option d'export `--fuse-postprocessing` reste expérimentale et doit repasser
la validation numérique ; une réussite de vitesse seule ne suffit pas à l'activer.

## Revue privée et tests

`tools/photo-pipeline.check.mjs` exige `PPAI_OWNER_PHOTO` et
`PPAI_PLAYWRIGHT_CORE`. `PPAI_PHOTO_MATRIX=1` ajoute les sept photos de régression.
Il utilise l'API réelle et les moteurs locaux, teste produit, rotation, avant/après,
comparaison et absence de réanalyse. Une issue manuelle est un parcours fonctionnel,
pas une validation de la segmentation automatique.

Les traces, réponses contenant les masques et captures vont uniquement dans
`review/roomvo-photo-accuracy/`, ignoré par Git. Les journaux de service ne
contiennent que dimensions, durées, statuts et avertissements, jamais de pixels.
Le masque brut et le masque raffiné restent distincts dans la revue. L'échelle
absolue d'une seule photo et les occlusions non reconnues demandent toujours une
relecture humaine ; les captures permettent de vérifier le cas concret.
