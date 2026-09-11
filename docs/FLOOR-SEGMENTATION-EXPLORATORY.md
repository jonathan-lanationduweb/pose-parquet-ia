# Segmentation du sol — passe exploratoire

> **EXPLORATOIRE · RÉFÉRENCES = BROUILLONS IA · PAS DE VÉRITÉ TERRAIN
> OFFICIELLE · AUCUN MODÈLE RETENU**
>
> **ACTIF.** Fait foi sur : ce que les candidats de la première vague font
> réellement sur nos photos, l'adaptation de la classe académique `floor` à
> notre `floorVisible`, les défauts observés par rôle, et les problèmes à
> régler avant tout banc d'essai officiel. Passe faite le **11 septembre
> 2026** (LOT C.0).
>
> **Le LOT C officiel reste bloqué**, et rien ici ne le débloque : vérité
> terrain approuvée = 0, tapis = 0, corpus du palier 1 incomplet, accord
> humain = 0 paire. Aucun chiffre de ce document ne désigne un gagnant ; ils
> comparent une prédiction à une autre prédiction.

## 1. Pourquoi ces chiffres ne sont pas un banc d'essai

Les quatre relevés de référence sont des **brouillons produits par une
machine** (`annotator = claude-ai`, `status = draft`, jamais approuvés).
Comparer un modèle à eux mesure une **ressemblance entre deux prédictions**,
pas une justesse. Un candidat qui obtiendrait 0,99 d'IoU contre un brouillon
faux serait faux avec lui.

Ce que la passe peut donc dire, et qu'elle dit : « ce candidat trouve le sol,
celui-là peint le mur, celui-là efface les pieds de chaise ». Ce qu'elle ne
peut pas dire : lequel est le meilleur.

## 2. La machine, telle qu'elle est

| | |
| --- | --- |
| processeur | Intel64 famille 6 modèle 186 (Raptor Lake), 12 cœurs logiques |
| mémoire | 15,7 Gio |
| carte graphique | Intel(R) Graphics, **intégrée** |
| CUDA | **absent** — `nvidia-smi` introuvable, aucun pilote NVIDIA |
| torch | 2.14.0+cpu, 10 fils |

**Toute inférence tourne sur processeur.** C'est le régime qui fixe les
durées : on mesure des secondes, jamais des millisecondes, et les temps de ce
document ne se comparent qu'entre eux.

## 3. Ce qui a été installé, et d'où

Déclaré avant tout téléchargement, comme le lot l'exige.

| élément | source | licence | taille |
| --- | --- | --- | --- |
| `torch` (roue CPU) | `download.pytorch.org/whl/cpu` | BSD-3 | ~250 Mo |
| `torchvision` (roue CPU) | idem | BSD-3 | ~2 Mo |
| `transformers` 5.17 | PyPI | Apache-2.0 | ~10 Mo |
| `scipy` | PyPI | BSD-3 | ~40 Mo |
| poids OneFormer | `shi-labs/oneformer_ade20k_swin_tiny` | **MIT** (fiche de modèle) | ~230 Mo |
| poids UPerNet | `openmmlab/upernet-convnext-small` | **MIT** (fiche de modèle) | ~240 Mo |

Emplacement : `models/hf-cache/`, **hors de Git** (`.gitignore` : `models/`).
Les licences sont celles déjà vérifiées dans
[MODEL-LICENSES.md](MODEL-LICENSES.md) §3.1 — cette passe n'en revérifie
aucune, elle s'y conforme.

**Deux écarts à déclarer, plutôt qu'à taire.**

1. **Variante `tiny` et non `large` pour OneFormer.** La grille de licences
   cite `Swin-L`. Sur processeur, la variante `tiny` inférait déjà en 4 à
   11 secondes ; la `large` (environ quatre fois plus de paramètres) aurait
   rendu la passe impraticable, et le lot interdit de télécharger plusieurs
   variantes du même modèle. La conséquence est à connaître : **ce document
   sous-estime probablement la famille OneFormer.**
2. **UPerNet exécuté par `transformers`, pas par MMSegmentation.** Les
   **poids** sont bien ceux du point d'accès officiel d'OpenMMLab ; le code
   qui les exécute est l'implémentation de référence de `transformers`.
   Installer MMSegmentation aurait demandé la chaîne `mmcv`/`mim` et sa
   compilation, pour un candidat qu'on n'a pas choisi. Le jour où les deux
   implémentations divergeraient, c'est ici qu'il faudrait revenir.

`torch` a chargé OneFormer avec un avertissement — quelques poids de
`layernorm` du dorsal Swin déclarés **manquants** et réinitialisés. Les
prédictions sont cohérentes malgré cela (classes plausibles, sol trouvé), mais
c'est une réserve de plus sur ce candidat, et elle est notée.

## 4. `floor` n'est pas `floorVisible` — l'adaptation, et ses limites

ADE20K distingue `floor;flooring` (3, base zéro) de `rug;carpet;carpeting`
(28). L'adaptation appliquée est **volontairement minimale et générale** :

```
floorVisible ≈ (classe floor)  −  (classe rug/carpet)
```

et **rien d'autre**. Pas de règle par scène, pas de seuil ajusté sur une
image, aucune information venue des relevés. La raison est méthodologique :
toute correction ajoutée ici serait créditée au modèle, et la comparaison
suivante en deviendrait fausse.

Ce que cette règle ne peut pas faire, et qui explique la plupart des défauts
du §6 :

| notre exigence | ce qu'ADE20K en dit |
| --- | --- |
| exclure les meubles et leurs pieds | des classes d'objets existent, mais aucune ne dit « ceci masque le sol » |
| exclure l'extérieur vu par une ouverture | `earth`, `grass`, `sidewalk`… sans notion de dedans/dehors |
| exclure les grilles et trappes encastrées | **aucune classe** |
| inclure les ombres et reflets francs | rien ne les nomme ; un modèle a tendance à les perdre |

Post-traitement : suppression des composantes de moins de 0,2 % de l'image.
Les **trous ne sont jamais comblés** — un trou est peut-être un pied de
chaise, et le boucher effacerait exactement ce que la préservation des objets
fins doit mesurer.

## 5. Matrice exploratoire

> **EXPLORATORY — AI DRAFT REFERENCES — NOT OFFICIAL GT — NOT MODEL
> SELECTION**

Quatre scènes pilotes, trois candidats, 1600 × 1067 en entrée comme en
inférence. Zones incertaines des brouillons exclues du calcul.

| scène | candidat | couverture | IoU | Dice | contour 0,25 % | 0,5 % | 1 % | inférence | défaut principal |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| sejour | opencv | 39,5 % | 0,893 | 0,944 | — | 0,482 | — | **0,04 s** | BOUNDARY_ERROR |
| sejour | oneformer | 35,2 % | 0,988 | 0,994 | — | **0,983** | — | 7,6 s | STRUCTURAL_BLEED (grille 93 %) |
| sejour | upernet | 35,0 % | 0,981 | 0,990 | — | **0,989** | — | 7,9 s | STRUCTURAL_BLEED (grille 51 %) |
| chambre | opencv | 28,1 % | 0,789 | 0,882 | — | 0,324 | — | 0,1 s | BOUNDARY_ERROR |
| chambre | oneformer | 25,5 % | 0,954 | 0,977 | — | 0,743 | — | 7,5 s | STRUCTURAL_BLEED (12 %) |
| chambre | upernet | 9,6 % | **0,322** | 0,486 | — | 0,275 | — | 7,2 s | **FLOOR_MISS massif** |
| couloir | opencv | 30,9 % | **0,316** | 0,480 | — | 0,139 | — | 0,05 s | **WALL_BLEED massif** |
| couloir | oneformer | 10,9 % | 0,932 | 0,965 | — | 0,789 | — | 5,6 s | BOUNDARY_ERROR léger |
| couloir | upernet | 10,9 % | 0,927 | 0,962 | — | 0,783 | — | 5,8 s | BOUNDARY_ERROR léger |
| petite-piece | opencv | 28,9 % | 0,482 | 0,650 | — | 0,121 | — | 0,05 s | OCCLUDER_BLEED 100 % |
| petite-piece | oneformer | 12,4 % | 0,839 | 0,913 | — | 0,414 | — | 5,7 s | THIN_OBJECT_LOSS 4/6 |
| petite-piece | upernet | 12,0 % | 0,805 | 0,892 | — | 0,359 | — | 5,7 s | THIN_OBJECT_LOSS 4/6 |

Les tolérances 0,25 % et 1 % sont calculées et enregistrées dans
`review/floor-candidates/rapport-exploratoire.json` ; seule la médiane est
reprise ici pour que la table reste lisible.

**Aucune colonne « score », aucun classement.** Une solution peut être bonne
en surface et mauvaise à la frontière : `upernet` sur `sejour` a la meilleure
F-mesure de contour du tableau **et** l'échec le plus grave sur `chambre`.

## 6. Défauts observés, par rôle d'exclusion

Rendu calculable par le LOT B.2 : chaque exclusion porte son rôle, donc on
peut dire **sur quoi** un candidat a débordé.

| scène | candidat | débordement structurel | débordement occulteur | objets fins perdus |
| --- | --- | --- | --- | --- |
| sejour | opencv | 245/245 px (100 %) | — | 1/1 |
| sejour | oneformer | 228/245 px (93 %) | — | 1/1 |
| sejour | upernet | 124/245 px (51 %) | — | 1/1 |
| chambre | opencv | 13 399/17 000 px (79 %) | — | 1/1 |
| chambre | oneformer | 2 082/17 000 px (**12 %**) | — | 1/1 |
| chambre | upernet | 14 704/17 000 px (86 %) | — | 1/1 |
| petite-piece | opencv | — | 10 965/10 965 px (100 %) | 6/6 |
| petite-piece | oneformer | — | 3 743/10 965 px (34 %) | 4/6 |
| petite-piece | upernet | — | 3 386/10 965 px (31 %) | 4/6 |

**`rug bleed` = NOT MEASURABLE.** Le corpus n'a aucun tapis
(`floor_covering = 0`), et il n'y a rien à mesurer sur un cas absent. C'est le
manque le plus coûteux du corpus, et il ne se comble que par acquisition.

### Ce que l'œil voit, et que les chiffres ne disent pas

- **`couloir` / opencv** : la base peint **les deux murs** du couloir et
  manque le sol. Elle fait exactement ce qu'on attendait d'elle — dire à quoi
  ressemble « rien d'appris ».
- **`chambre` / upernet** : la moitié ensoleillée du parquet est classée
  autrement et **perdue**. Un échec de lumière, pas de géométrie : le sol est
  là, le modèle ne le voit pas.
- **`chambre` / oneformer** : le sol entier est trouvé, la grille de
  convecteur **exclue**, le seuil arrêté à la porte, la terrasse extérieure non
  peinte. C'est le meilleur résultat visuel de la passe.
- **`petite-piece` / oneformer** : les pieds fins de la chaise et du bureau
  sont **découpés** dans le masque — visible à l'œil. Ce que le chiffre
  « 4/6 perdus » compte en plus, ce sont les quatre petits disques de contact
  pied/reflet, qui disparaissent.
- **`sejour` / oneformer** : le parquet continue **par l'ouverture vers la
  pièce du fond**, sans rupture. La continuité de surface fonctionne sans
  qu'on la demande.
- **grilles encastrées** : aucun candidat ne les exclut de façon fiable. C'est
  attendu — **aucune classe ADE20K ne les nomme**.

## 7. Les onze photos, qualitativement

Couverture prédite sur les sept photos sans relevé, pour repérer une
prédiction absurde plutôt que pour la noter :

| photo | opencv | oneformer | upernet |
| --- | --- | --- | --- |
| appartement-ancien | — | 18,1 % | 24,5 % |
| bureau-vide | — | — | — |
| entree-cadree | 30,3 % | 27,5 % | 27,4 % |
| piece-arcades | 40,7 % | 37,6 % | 37,5 % |
| piece-claire | 33,8 % | 23,5 % | 23,2 % |
| salon | 43,6 % | 37,7 % | 37,6 % |
| contraste | — | — | — |

Les deux modèles appris sont **remarquablement d'accord** hors `chambre` et
`appartement-ancien` — à 0,1 point de couverture sur quatre photos. Deux
lectures possibles, et la passe ne permet pas de trancher : soit la tâche est
facile sur ces images, soit les deux partagent un biais d'ADE20K.

## 8. Coûts mesurés

| étape | opencv | oneformer | upernet |
| --- | --- | --- | --- |
| chargement du modèle | 0 ms | 3 400 ms (après téléchargement) | 33 400 ms (téléchargement compris) |
| inférence à froid | — | 6,2 s | 8,4 s |
| inférence à chaud | 0,04 – 0,3 s | 4,2 – 11,1 s | 5,6 – 10,7 s |
| post-traitement | 4 – 160 ms | 4 – 160 ms | 4 – 160 ms |
| bout en bout par l'API | — | **26,9 s** (chargement compris) | — |

Mémoire : non instrumentée faute de `psutil`, et **aucun chiffre n'est
inventé**. Ce qui est constaté : aucun échec mémoire sur 15,7 Gio, avec un
seul modèle chargé à la fois.

## 9. Sortie API expérimentale

`PPAI_EXPERIMENTAL_FLOOR=1` joint à la réponse un bloc `experimental.floor` :
candidat, masque **PNG binaire encodé en base64** (6,6 Ko pour 1600 × 1067),
dimensions, couverture, contour normalisé, durées, et une mention
`EXPERIMENTAL` dans les données elles-mêmes.

Format du masque : le PNG a été retenu pour sa simplicité — relisible par
n'importe quoi, comparable octet à octet, quelques kilo-octets. Un tableau
JSON de pixels serait illisible et énorme ; un codage par plages serait plus
compact mais demanderait un décodeur de plus, pour un gain invisible à cette
échelle. Le polygone existe déjà par ailleurs, sous le nom `boundary`.

**Faux par défaut**, et le défaut est une garantie de contrat : sans le
drapeau, la réponse est exactement celle d'avant ce lot — `sceneData` nul,
aucun champ de plus, étage `segmentation` non exécuté. Le champ `experimental`
est **additif** (optionnel, nul par défaut), donc `analysis@2` reste
`analysis@2` ; la rupture viendrait du jour où quelque chose y deviendrait
obligatoire ou entrerait dans `sceneData`, et ce jour-là il faudra une version
majeure et une décision humaine.

**Aucun parquet n'est posé sur une photo importée**, même quand un masque
existe. Le visualiseur le **signale** en `?dev=1` — « masque experimental :
oneformer-ade20k, 11 % — non fiable, aucun rendu » — et s'arrête là.

## 10. Ce qu'il faut régler avant tout banc d'essai officiel

Par ordre de coût, pas d'enthousiasme.

1. **La vérité terrain.** Zéro relevé approuvé. Tant qu'elle manque, aucun
   chiffre de ce document ne peut devenir un critère.
2. **Les tapis.** `floor_covering = 0`. Le cas le plus visible et le plus
   fréquent du produit n'est ni annoté ni mesurable, et la classe `rug`
   d'ADE20K n'a donc **jamais été éprouvée** sur nos photos.
3. **Les éléments encastrés.** Aucune classe ne les nomme : un modèle
   sémantique seul ne les exclura jamais. C'est un travail de LOT D, ou une
   règle géométrique à inventer.
4. **Les objets fins.** Les deux modèles perdent 4 exclusions fines sur 6.
   Le critère « plus de la moitié repeinte » est grossier et mériterait d'être
   affiné avant d'en faire une métrique produit.
5. **La latence.** 4 à 11 secondes par image sur processeur. Acceptable pour
   une analyse unique, impossible pour un aller-retour interactif — mais le
   produit n'en demande pas : l'analyse est faite **une fois** par photo.
6. **Le doute sur `tiny`.** Ce document sous-estime probablement OneFormer.
   Une comparaison honnête de la famille demanderait la variante `large`, donc
   une machine avec carte graphique.

## 11. Ce que ce document n'autorise pas

- conclure « modèle retenu », « meilleur modèle », ou « prêt pour la
  production » ;
- transformer un masque expérimental en `sceneData` ;
- poser un parquet sur une photo d'utilisateur ;
- utiliser ces chiffres comme critère de passage du LOT C ;
- ajuster un candidat scène par scène, ou avec l'aide d'un relevé ;
- présenter les brouillons IA comme une vérité terrain.
