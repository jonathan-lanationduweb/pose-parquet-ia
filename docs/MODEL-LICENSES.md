# Licences des candidats — grille de vérification

> **ACTIF.** Fait foi sur : la licence du code, la licence des poids, les
> restrictions d'usage et la source officielle de chaque candidat envisagé.
> Vérification faite le **10 septembre 2026** (LOT B.3).
>
> **LICENSE CHECK COMPLETE ≠ MODEL SELECTED.** Ce document lève un prérequis
> documentaire du passage de porte du LOT C. Il ne choisit aucun modèle, ne
> classe aucune performance, et n'autorise pas le LOT C — dont les autres
> conditions restent fausses (§9).
>
> **Ce n'est pas un avis juridique.** C'est une analyse technique et
> documentaire, faite à partir des textes publiés par les éditeurs. Aucune
> ligne ici ne dit « juridiquement sûr ».

## 1. Pourquoi cette grille existe avant tout essai

Un modèle non redistribuable choisi est un modèle à remplacer, et on ne
découvre pas sa licence après l'avoir intégré. Deux pièges ont motivé la règle
de vérifier le code et les poids **séparément** :

- **Mask2Former** : code sous licence MIT, et poids publiés sous CC BY-NC 4.0.
  Lire la licence du dépôt et en déduire celle des poids aurait conduit à
  évaluer, puis à retenir, un modèle inutilisable commercialement.
- **SegFormer** : licence maison de NVIDIA, non commerciale, qui autorise
  explicitement l'« évaluation ». Un essai serait donc permis — mais un essai
  concluant ne donnerait rien de livrable. L'évaluation aurait été du temps
  dépensé pour un candidat mort d'avance.

Un troisième piège n'est ni le code ni les poids : **les données
d'entraînement**. Voir §5.

## 2. Statuts employés, et leur sens exact

| statut | sens |
| --- | --- |
| `CLEAR_FOR_COMMERCIAL_EVALUATION` | assez clair pour être testé dans notre contexte commercial. Ne conclut **pas** sur l'usage final. |
| `CONDITIONAL` | utilisable potentiellement, avec une obligation ou une restriction à examiner avant tout essai. |
| `UNCLEAR` | ambiguïté réelle, ou information officielle insuffisante. |
| `REJECTED_LICENSE` | incompatible avec une cible commerciale. |

Et, indépendamment de la licence, une éligibilité au banc d'essai :

| éligibilité | sens |
| --- | --- |
| `ELIGIBLE_FOR_BENCHMARK` | licence et disponibilité permettent raisonnablement un futur test. |
| `NEEDS_REVIEW` | une décision humaine est nécessaire avant de le tester. |
| `NOT_ELIGIBLE` | bloqué par la licence, la disponibilité, ou l'absence de voie réaliste vers `floorVisible`. |

Aucune de ces valeurs ne dit qu'un candidat est bon. Aucun classement de
performance n'existe à ce stade, et il n'en existera pas avant que la vérité
terrain approuvée existe.

## 3. Segmentation du sol — la grille détaillée

Six lignes retenues comme testables, quatre écartées. Le besoin est le même
pour toutes : produire `floorVisible` sur des photos d'intérieur réelles.

### 3.1 Candidats testables

| candidat | organisation | version / famille | licence du code | licence des poids | réserve données | évaluation commerciale | redistribution des poids | attribution | restrictions | sources officielles | statut | éligibilité |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OneFormer | SHI-Labs | ADE20K, Swin-L / ConvNeXt-L | MIT | **MIT**, déclaré sur la fiche de modèle | ADE20K — §5 | oui | oui, sous MIT | avis de copyright MIT ; citation demandée | aucune dans le texte MIT | dépôt, fichier de licence, fiche de modèle | `CLEAR_FOR_COMMERCIAL_EVALUATION` | `ELIGIBLE_FOR_BENCHMARK` |
| UPerNet + ConvNeXt | OpenMMLab | MMSegmentation, ADE20K, 512² à 640² | Apache-2.0 | **MIT**, déclaré sur la fiche de modèle | ADE20K — §5 | oui | oui | avis Apache-2.0 et MIT | aucune | dépôt, configuration officielle, fiche de modèle | `CLEAR_FOR_COMMERCIAL_EVALUATION` | `ELIGIBLE_FOR_BENCHMARK` |
| SAM 2.1, **plus un étage de décision** | Meta | sam2 | Apache-2.0 | **Apache-2.0** — points de contrôle, code de démonstration et code d'entraînement | SA-V non nécessaire | oui | oui | avis Apache-2.0 | polices de la démonstration sous SIL OFL 1.1 | dépôt, fichier de licence, section licence du README | `CLEAR_FOR_COMMERCIAL_EVALUATION` | `ELIGIBLE_FOR_BENCHMARK` |
| DINOv2 en dorsale, **plus une tête entraînée sur notre vérité terrain** | Meta | dinov2 | Apache-2.0 | Apache-2.0 | **aucune** — la tête apprend notre définition | oui | oui | avis Apache-2.0 | aucune | dépôt, fichier de licence | `CLEAR_FOR_COMMERCIAL_EVALUATION` | `NEEDS_REVIEW` — exige une vérité terrain approuvée, qui n'existe pas |
| base de comparaison géométrique classique | OpenCV | déjà une dépendance du service | Apache-2.0 | sans objet — aucun poids | aucune | oui | sans objet | avis Apache-2.0 | aucune | dépendance déjà en place | `CLEAR_FOR_COMMERCIAL_EVALUATION` | `ELIGIBLE_FOR_BENCHMARK` |
| SAM 3 | Meta | sam3, ~0,9 milliard de paramètres | **SAM License**, maison | **SAM License** ; poids sous porte : il faut accepter de partager ses coordonnées | non documentée | non exclue par le texte | oui, mais **l'accord doit accompagner toute redistribution** | citation exigée en cas de publication | interdictions d'usage : ITAR et contrôles commerciaux, militaire, nucléaire, espionnage, armes | dépôt, fichier de licence, fiche de modèle | **`CONDITIONAL`** | `NEEDS_REVIEW` |

### 3.2 Candidats écartés, et la raison exacte

| candidat | licence du code | licence des poids | statut | pourquoi écarté |
| --- | --- | --- | --- | --- |
| Mask2Former | MIT | **CC BY-NC 4.0** — « All models available for download through this document are licensed under the Creative Commons Attribution-NonCommercial 4.0 International License » | `REJECTED_LICENSE` | les poids publiés sont non commerciaux. Le code reste MIT : un réentraînement sur nos données serait une **autre** voie, à instruire séparément, pas ce candidat. |
| SegFormer | NVIDIA Source Code License — « The Work and any derivative works thereof only may be used or intended for use non-commercially » | même licence | `REJECTED_LICENSE` | l'évaluation est explicitement permise, l'exploitation non. Tester un candidat qu'on ne pourra jamais livrer coûte du temps sans issue. |
| DeepLabV3 de torchvision | BSD-3-Clause | **non déclarée** dans la documentation officielle des poids | `UNCLEAR` | et surtout : les poids sont entraînés sur « a subset of COCO, using only the 20 categories that are present in the Pascal VOC dataset » — **il n'y a pas de classe sol**. Écarté sur la faisabilité, pas sur la licence. Reste une architecture réentraînable. |
| DINOv3 | **DINOv3 License**, maison | même licence | `CONDITIONAL` | même famille de texte que SAM 3 : redevance nulle, commercial non exclu, mais accord maison à propager et interdictions d'usage. Non retenu comme dorsale par défaut tant que DINOv2, sous Apache-2.0, couvre le même besoin. |

## 4. Modèle ≠ produit

Trois des six lignes testables ne sont pas des modèles de sol : ce sont des
**architectures candidates**, dont le modèle n'est qu'un étage.

- `SAM 2.1 + étage de décision` : SAM 2.1 découpe des régions sans les nommer.
  Décider laquelle est le sol demande un second étage — invite géométrique,
  classification, ou filtrage par perspective. Le candidat n'est complet que
  quand cet étage est spécifié.
- `DINOv2 + tête` : la dorsale ne segmente rien ; c'est la tête, entraînée sur
  **notre** vérité terrain, qui produit `floorVisible`.
- La base géométrique classique n'a pas de modèle du tout, et c'est son
  intérêt : elle donne le niveau à battre.

Conséquence de méthode : une combinaison n'est pas un nouveau modèle et ne
prend pas une ligne de plus dans cette grille. Elle hérite des licences de ses
étages, et c'est la ligne de l'étage qui porte la vérification.

## 5. La réserve qui n'est ni le code ni les poids : ADE20K

Deux des candidats testables tirent leurs poids d'un entraînement sur ADE20K.
Les termes officiels du jeu de données disent deux choses distinctes :

- le logiciel et les annotations sont couverts par un accord de licence de type
  BSD-3 ;
- l'usage du jeu lui-même est restreint : « Researcher shall use the Database
  only for non-commercial research and educational purposes ».

Et une troisième chose, par omission : **les termes ne disent rien des modèles
entraînés sur ces données.** Les éditeurs des poids publient ceux-ci sous MIT,
ce qui est la permission opérante côté modèle. Mais l'articulation entre cette
permission et la clause non commerciale du jeu d'origine n'est **pas** résolue
par les textes consultés.

C'est une ambiguïté réelle, et elle est nommée ici plutôt que dissoute dans une
case « oui ». Elle n'empêche pas d'**évaluer** ces candidats — c'est exactement
le sens du statut `CLEAR_FOR_COMMERCIAL_EVALUATION`. Elle devra être tranchée
par une personne avant toute décision de livraison, et elle est une raison de
plus de garder la voie `DINOv2 + tête sur notre vérité terrain`, qui ne dépend
d'aucun jeu tiers.

## 6. Le risque « floor » trop générique

Une classe `floor` académique n'est pas notre besoin, et confondre les deux
ferait mesurer le mauvais chiffre.

Le jeu ADE20K distingue, dans ses 150 classes officielles,
`floor;flooring` (indice 4) et `rug;carpet;carpeting` (indice 29). C'est une
bonne nouvelle : un modèle qui les sépare peut, en principe, retirer le tapis
du sol. Mais notre définition de `floorVisible`
([annotation-protocol.md](annotation-protocol.md)) est **plus stricte** que la
classe académique. Elle exclut :

- les tapis et revêtements posés ;
- les objets et les meubles, y compris leurs pieds fins ;
- les éléments techniques encastrés, selon le protocole ;
- les surfaces extérieures vues par une ouverture ;
- toute zone non candidate au remplacement.

Et elle **inclut** ce qu'une classe générique tend à perdre : les ombres et les
reflets francs sont du sol.

Conséquence non négociable : **aucun candidat ne sera jugé sur son score
publié.** Il sera mesuré contre notre vérité terrain, avec nos métriques
produit, et la revue visuelle restera bloquante. Un modèle donné pour excellent
sur ADE20K peut échouer chez nous sur le seul cas du tapis — et le corpus n'en
contient encore aucun.

## 7. Critères techniques documentaires

Relevés **uniquement** là où une source officielle les donne. `UNKNOWN`
partout ailleurs : aucun chiffre n'est estimé, et aucun modèle n'a été
téléchargé ni exécuté pour le savoir.

| candidat | taille des poids | matériel annoncé | résolution d'entrée | type de sortie | classes fixes ou par invite | maintenance | maturité |
| --- | --- | --- | --- | --- | --- | --- | --- |
| OneFormer | UNKNOWN | UNKNOWN | UNKNOWN | masques sémantiques, panoptiques et d'instances | **fixes**, 150 classes ADE20K | UNKNOWN | publié à CVPR 2023, dépôt public |
| UPerNet + ConvNeXt | UNKNOWN | UNKNOWN | 512×512 à 640×640 selon la variante | masque sémantique | **fixes**, 150 classes ADE20K | UNKNOWN | dans le zoo officiel MMSegmentation |
| SAM 2.1 | UNKNOWN | UNKNOWN | UNKNOWN | masques, sans étiquette | **par invite** : points, boîtes, masques | UNKNOWN | dépôt public, code d'entraînement publié |
| SAM 3 | ~0,9 milliard de paramètres, format safetensors | UNKNOWN | UNKNOWN | masques, boîtes, scores de confiance, suivi vidéo | **par invite**, texte compris | UNKNOWN | poids sous porte |
| DINOv2 | UNKNOWN | UNKNOWN | UNKNOWN | descripteurs — aucun masque | sans objet | UNKNOWN | dépôt public |
| base géométrique | sans objet | processeur | sans objet | masque | sans objet | à jour | dépendance déjà en service |

Compatibilité PyTorch et ONNX : `UNKNOWN` pour tous. Elle se vérifiera au lot
qui installera quelque chose, et pas avant.

## 8. Pré-grille des autres briques

Volontairement plus légère : ces choix appartiennent aux LOT D, E et H, et rien
n'y est retenu aujourd'hui.

| besoin | candidat | licence du code | licence des poids | statut | note |
| --- | --- | --- | --- | --- | --- |
| objets, occlusions | SAM 3 | SAM License | SAM License, sous porte | `CONDITIONAL` | la sortie par invite textuelle est directement pertinente pour les rôles d'exclusion |
| objets, occlusions | Grounding DINO | Apache-2.0 | **Apache-2.0**, fiche de modèle | `CLEAR_FOR_COMMERCIAL_EVALUATION` | détection par texte ; ne produit pas de masque seul |
| objets, occlusions | Mask2Former, instances | MIT | CC BY-NC 4.0 | `REJECTED_LICENSE` | même cause que pour le sol |
| objets, occlusions | Ultralytics YOLO | **AGPL-3.0** | AGPL-3.0 | `REJECTED_LICENSE` | l'article 13 impose d'offrir le code source correspondant à tout utilisateur qui interagit avec le service par le réseau. Incompatible avec notre cible, sauf licence commerciale distincte à instruire. |
| profondeur | Depth Anything V2, variante *Small* | Apache-2.0 | **Apache-2.0** | `CLEAR_FOR_COMMERCIAL_EVALUATION` | la licence des poids **change avec la taille** : voir la ligne suivante |
| profondeur | Depth Anything V2, variantes *Base*, *Large*, *Giant* | Apache-2.0 | **CC-BY-NC-4.0** | `REJECTED_LICENSE` | le piège le plus discret de la liste : même dépôt, même code, poids non commerciaux dès qu'on monte en taille |
| profondeur | Depth Pro | licence maison Apple | `apple-amlr`, Apple Machine Learning Research License | `UNCLEAR` | licence maison des deux côtés ; à lire en entier avant tout essai |
| caméra, géométrie | GeoCalib | Apache-2.0 | UNKNOWN — non vérifiée séparément | `CONDITIONAL` | la licence des poids reste à vérifier, précisément parce qu'on ne la déduit pas de celle du code |
| multi-vues | COLMAP | New BSD | sans objet | `CLEAR_FOR_COMMERCIAL_EVALUATION` | le texte précise ne couvrir que COLMAP, ses dépendances étant licenciées à part |
| multi-vues | MASt3R et DUSt3R | **CC BY-NC-SA 4.0** | même licence | `REJECTED_LICENSE` | non commercial, et *ShareAlike* de surcroît |
| multi-vues | VGGT | **VGGT License**, maison, v1 du 29 juillet 2025 | même licence | `CONDITIONAL` | les mots « non-commercial », « noncommercial » et « research purposes only » sont **absents** du texte, vérifié ; les restrictions passent par une politique d'usage acceptable |

## 9. Ce que cette grille change, et ce qu'elle ne change pas

Elle lève **une** des six conditions du passage de porte
([BENCHMARK-STRATEGY-V2.md §8](BENCHMARK-STRATEGY-V2.md)) : « licences des
candidats vérifiées ». Deux sur six sont désormais vraies, avec le banc d'essai.

Restent fausses, et chacune est bloquante :

| condition | état |
| --- | --- |
| protocole validé sur des photos meublées, tapis compris | **non** — aucun tapis dans le corpus |
| corpus minimum du palier 1 | **non** — 11 photos, dont 3 meublées |
| annotations **approuvées** | **non** — 4 brouillons IA, 0 approuvée |
| accord humain mesuré | **non** — 0 paire doublement annotée |

Le LOT C reste donc interdit. Cette grille ne l'autorise pas ; elle enlève un
obstacle sur quatre.

## 10. Sources officielles, une par décision

Chaque statut ci-dessus vient d'un de ces textes, consultés le 10 septembre
2026. Aucun blog, aucun comparateur, aucune copie non officielle de modèle.

| sujet | source |
| --- | --- |
| Mask2Former — code | `https://raw.githubusercontent.com/facebookresearch/Mask2Former/main/LICENSE` |
| Mask2Former — poids | `https://raw.githubusercontent.com/facebookresearch/Mask2Former/main/MODEL_ZOO.md` |
| SegFormer — code et poids | `https://raw.githubusercontent.com/NVlabs/SegFormer/master/LICENSE` |
| OneFormer — code | `https://raw.githubusercontent.com/SHI-Labs/OneFormer/main/LICENSE` |
| OneFormer — poids | `https://huggingface.co/shi-labs/oneformer_ade20k_swin_large` |
| MMSegmentation — code | `https://raw.githubusercontent.com/open-mmlab/mmsegmentation/main/LICENSE` |
| UPerNet + ConvNeXt — poids | `https://huggingface.co/openmmlab/upernet-convnext-small` |
| UPerNet + ConvNeXt — jeu et résolution | `https://raw.githubusercontent.com/open-mmlab/mmsegmentation/main/configs/convnext/README.md` |
| SAM — code et poids | `https://raw.githubusercontent.com/facebookresearch/segment-anything/main/LICENSE`, `.../README.md` |
| SAM 2.1 — code et poids | `https://raw.githubusercontent.com/facebookresearch/sam2/main/LICENSE`, `.../README.md` |
| SAM 3 — licence | `https://raw.githubusercontent.com/facebookresearch/sam3/main/LICENSE` |
| SAM 3 — poids, porte et taille | `https://huggingface.co/facebook/sam3` |
| DINOv2 — code et poids | `https://raw.githubusercontent.com/facebookresearch/dinov2/main/LICENSE` |
| DINOv3 — licence | `https://raw.githubusercontent.com/facebookresearch/dinov3/main/LICENSE.md` |
| torchvision — code | `https://raw.githubusercontent.com/pytorch/vision/main/LICENSE` |
| DeepLabV3 — jeu et classes des poids | `https://docs.pytorch.org/vision/stable/models/generated/torchvision.models.segmentation.deeplabv3_resnet101.html` |
| ADE20K — termes du jeu | `https://ade20k.csail.mit.edu/terms/` |
| ADE20K — les 150 classes officielles | `https://raw.githubusercontent.com/CSAILVision/sceneparsing/master/objectInfo150.csv` |
| Grounding DINO — code | `https://raw.githubusercontent.com/IDEA-Research/GroundingDINO/main/LICENSE` |
| Grounding DINO — poids | `https://huggingface.co/IDEA-Research/grounding-dino-base` |
| Ultralytics YOLO — licence | `https://raw.githubusercontent.com/ultralytics/ultralytics/main/LICENSE` |
| Depth Anything V2 — code et poids par taille | `https://raw.githubusercontent.com/DepthAnything/Depth-Anything-V2/main/README.md` |
| Depth Pro — code | `https://raw.githubusercontent.com/apple/ml-depth-pro/main/LICENSE` |
| Depth Pro — poids | `https://huggingface.co/apple/DepthPro` |
| GeoCalib — code | `https://raw.githubusercontent.com/cvg/GeoCalib/main/LICENSE` |
| COLMAP — licence | `https://raw.githubusercontent.com/colmap/colmap/main/COPYING.txt` |
| MASt3R — licence | `https://raw.githubusercontent.com/naver/mast3r/main/LICENSE` |
| VGGT — licence | `https://raw.githubusercontent.com/facebookresearch/vggt/main/LICENSE.txt` |

Deux relevés méritent d'être signalés comme **vérifications négatives**, qui
valent autant qu'une clause trouvée : le texte de la licence VGGT ne contient
ni « non-commercial », ni « noncommercial », ni « research purposes only » —
recherché explicitement ; et la documentation officielle des poids DeepLabV3 de
torchvision ne déclare **aucune** licence, ce qui est la raison de son
`UNCLEAR`.

## 11. Ce que ce document n'autorise pas

- télécharger des poids, ou installer un modèle ;
- lancer une inférence, ou un banc d'essai ;
- désigner un gagnant, ou publier un classement de performance ;
- déduire la licence des poids de celle du code ;
- traiter une case `UNKNOWN` comme un « oui » implicite ;
- présenter l'une de ces analyses comme un avis juridique.
