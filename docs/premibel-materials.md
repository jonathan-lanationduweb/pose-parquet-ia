# Matières Premibel : fidélité, import et cache

État du 13 octobre 2026. Mesures et captures : `review/premibel-materials/`.

## Fidélité

| Statut | Sens | Références Premibel locales |
| --- | --- | ---: |
| exact | Grain et couleur extraits de la photo de cette référence ; validation technique de l'extraction | 4 |
| representative | Famille de bois procédurale approchante | 181 |
| preview_only | Vignette disponible, aucune matière rendable | 200 |
| unavailable | Ni vignette ni matière rendable | 9 |

394 références, 185 rendables. Les 34 inspirations ne sont pas des références Premibel.
« Exact » décrit la provenance du bois, pas une matière PBR mesurée : joints,
chanfreins, relief calculé depuis l'albédo et finition restent des approximations.
Les sources photographiques ne permettent pas de garantir la teinte sous un
éclairage calibré ni la densité de nœuds de toute une livraison.

Le moteur confirme les quatre atlas réellement disponibles au démarrage. Les atlas
locaux ne sont pas versionnés ; un clone sans eux conserve le statut représentatif.
Une erreur de génération d'un atlas exact n'utilise jamais silencieusement une
texture procédurale. La photo reste disponible et le parcours d'erreur s'applique.

## Inventaire et import

`python -m scripts.premibel_asset_inventory` : A=382 vignettes commerciales,
B=367 ambiances, C=15 gros plans, D=4 atlas exploitables, E=0 échantillons ou
variantes de lame du fabricant, F=12 sans asset exploitable. Ces classes se recoupent.
Cinq photos du catalogue sont disponibles en 500–900 px ; aucun téléchargement
supplémentaire. Une vignette ne devient pas automatiquement une texture exacte.

1. Annoter les quadrilatères de bois et renseigner les dimensions de la référence
   dans `web/data/materials/premibel-sources.json`.
2. Lancer `python -m scripts.import_premibel_material ID...`. `--manifest PATH`
   permet un autre manifeste d'annotation. Les identifiants sont validés avant
   toute création de fichier.
3. Le script redresse la perspective, écarte les joints et égalise la lumière ;
   l'atlas utilise 0,6 px/mm. La source doit fournir au moins 0,3 px/mm,
   quatre fragments, 1,5 m de bois et une longueur nominale de lame. Les refus
   restent documentés dans `web/data/materials/premibel/index.json`.
4. Examiner les extractions, les captures et la comparaison source/rendu.
   La validation technique ne remplace pas une validation visuelle humaine.

Les quatre matières photographiques existaient déjà au HEAD fb35ec3. Ce lot les
régénère et fiabilise leur utilisation ; il ne crée pas quatre nouvelles références.
CHEN38163, CHENF36014, CHENF36015 et BTRPF39009 sont photographiques.
Le cinquième pilote POINF39011 reste représentatif. CHENF228, F52386574,
CHENF2681 et POINF38000 sont refusés : fragments, longueur ou résolution insuffisants.
Les autres candidats examinés ne fournissent pas assez de bois propre et de
métadonnées fiables pour ajouter un cinquième atlas sans inventer une matière.

Les fragments de l'atlas sont maintenant tirés selon leur quantité réelle de bois,
pour ne pas surreprésenter les petits fragments noueux. Départ et miroir varient,
mais une source limitée peut encore se répéter. Le fil peut être étiré jusqu'à 2×.

## Vitesse et résolution

512, 768, 1024 et 1280 px ont été comparés dans le moteur, à géométrie identique.
1024 est le compromis retenu : grain plus lisible que 512 et rendu proche de 1280
au cadrage normal. Cela ne valide pas un zoom extrême. La résolution de texture
est distincte de la géométrie du motif ; changer la première ne change pas la pose.
Le paramètre `textureSize` est réservé au banc DEV.

Mesures Chrome headless, 1440×900, localhost, cinq sessions distinctes, préchargement
automatique désactivé, produit initial hors des cinq pilotes pour isoler les essais froids.
Ce sont des délais choix → image réellement rendue, pas une durée de calcul seule.

| Produit | Fidélité | Froid médiane | Préchargé médiane | Cache médiane |
| --- | --- | ---: | ---: | ---: |
| CHENF36014 | exact | 320 ms | 59 ms | 16 ms |
| CHENF36015 | exact | 281 ms | 41 ms | 16 ms |
| BTRPF39009 | exact | 395 ms | 51 ms | 16 ms |
| CHEN38163 | exact | 344 ms | 73 ms | 16 ms |
| POINF39011 | representative | 1445 ms | 39 ms | 17 ms |

BTRPF39009 atteint 844 ms sur un passage ; POINF39011 atteint 2167 ms.
L'objectif froid <800 ms n'est donc pas garanti pour tous les pilotes.
Les anciens chiffres ne constituent pas un avant/après contrôlé : le produit
initial BTRPF39009 pouvait contaminer sa mesure froide. Le banc corrige ce biais.

Le profil sépare fetch, décodage ImageBitmap, dessin, lecture des pixels, relief,
attente/transfert worker, soumission des textures GPU et peinture. La lecture des
pixels (incluant la synchronisation du dessin Canvas) reste coûteuse sur le
procédural. La durée GPU mesurée est le temps CPU des appels d'upload/mips,
pas une mesure matérielle GPU. Les étapes imbriquées ne doivent pas être additionnées.
ImageBitmap est déjà employé pour décoder les atlas ; aucun nouveau chemin de
transfert ni cache persistant n'a été ajouté sans gain démontré.

## Cache et préchargement

Le cache CPU retient 12 tuiles ; clé = matière, motif, largeur, longueur,
résolution et version de l'atlas. La rotation réutilise la tuile. Les textures GPU
conservent quatre entrées avec la même distinction de longueur et de résolution.
À 1024², deux cartes RGBA coûtent environ 8 MiB par tuile, soit 96 MiB pour
12 entrées pleines, hors objets et buffers temporaires. Quatre matières GPU avec
mipmaps représentent environ 43 MiB, hors cartes de scène et framebuffer.

L'empreinte SHA-256 des pixels de l'atlas versionne sa définition et son URL,
pour éviter la réutilisation d'anciens pixels après un nouvel import.
Une demande utilisateur rejoint une génération identique déjà en cours ; sinon
elle interrompt les tâches de matière de fond, avec reprise sur un worker neuf.
Le catalogue prépare au plus huit cartes visibles, une à la fois, en temps libre.
Il ne prépare pas les 394 références au démarrage.

IndexedDB n'est pas implémenté. Son gain de décodage et son coût de stockage ne
sont pas mesurés dans ce lot. Une éventuelle étude devra comparer génération,
encodage, lecture et décodage, versionner la définition complète et le générateur,
limiter le quota et exclure les photos personnelles. Aucun gain chiffré n'est promis.

## Reproduction

- `node tools/premibel-materials.bench.mjs 5` : froid/préchargé/cache.
- `node tools/material-resolution.bench.mjs` : quatre résolutions et profils.
- `node tools/material-room.bench.mjs` : démarrage, pièces froide/chaude, rotation.
- `node tools/material-cache.check.mjs` : priorités, invalidation, échec exact.
- `node tools/premibel-materials.capture.mjs`, puis
  `python -m scripts.premibel_material_review` : planches comparatives.

Les outils navigateur demandent `PPAI_PLAYWRIGHT_CORE` et `PPAI_BASE`.
Le rapport de revue distingue les résultats réussis, les limites visuelles et
les objectifs encore non atteints. Pas de modification de géométrie ni d'analyse IA.
