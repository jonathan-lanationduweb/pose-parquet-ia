# Architecture IA — cible V2

> **ACTIF.** Cible d'architecture du service de compréhension de pièce.
> Ce document dit **où l'on va**. L'état livré aujourd'hui est décrit par
> [architecture.md](architecture.md), qui reste exact et n'est pas remplacé.
> La cible produit qui justifie tout ce qui suit :
> [PRODUCT-VISION.md](PRODUCT-VISION.md).
> Aucun modèle n'est choisi ici : voir §12.

## 1. Périmètre, en une ligne

```
capture ──► pose-parquet-ai ──► RoomAnalysis ──► navigateur : SceneData ──► moteur WebGL
             (comprendre)        (structuré)      (traduire)                 (dessiner)
```

Python comprend. Le navigateur dessine. Cette frontière est déjà énoncée par
`architecture.md` et `product-ai-contract.md` ; elle ne bouge pas, et la V2 ne
l'assouplit sur aucun point.

## 2. Comprendre une pièce, ce n'est pas produire un masque de sol

C'est l'erreur de cadrage qu'il faut corriger : le LOT IA 2 a été pensé comme
« trouver le sol », alors que le rendu final dépend d'au moins cinq choses
indépendantes. La cible de compréhension est la suivante.

| bloc | ce que le produit en fait, concrètement | sans lui |
| --- | --- | --- |
| `image` | dimensions de référence de toutes les coordonnées | rien n'est cadrable |
| `quality` | refuser une photo inexploitable, expliquer pourquoi | on rend n'importe quoi sur n'importe quoi |
| `camera` | orienter le motif, faire fuir les lames | parquet plat, collé sur l'image |
| `floor` | savoir quels pixels remplacer | pas de rendu |
| `floorExtent` | poser des lames continues sous les meubles | lames qui repartent à zéro derrière un canapé |
| `walls` | fiabiliser la limite basse du mur | la limite sol/mur, là où l'œil juge |
| `openings` | savoir où le sol candidat s'arrête | parquet sur la terrasse |
| `objects` | ne pas peindre ce qui n'est pas le sol | tapis et meubles repeints |
| `occlusions` | garder les objets devant le parquet | pieds de chaise avalés |
| `depth` | trier les occlusions, moduler la netteté, préparer la visite | tri arbitraire, netteté uniforme |
| `surfaces` | dire si deux zones sont le même sol | décalage au raccord d'une enfilade |
| `confidence` | choisir entre montrer, nuancer, ou demander une correction | on montre du faux avec aplomb |
| `warnings` | dire ce qui est incertain, en codes mesurables | l'utilisateur ne sait pas ce qui a raté |

**Rien de plus.** Ce tableau est la règle d'admission : un champ qui ne répond
pas à la colonne du milieu n'entre pas dans le contrat, quelle que soit
l'élégance du modèle qui pourrait le produire.

## 3. Le sol

### 3.1 La définition métier ne change pas

Elle est fixée, et elle reste la référence unique :
[annotation-protocol.md §1](annotation-protocol.md) —

> `floor_visible` représente les pixels du **sol intérieur réellement visible**
> appartenant à la surface **candidate au remplacement visuel par le parquet**.

Inclus : sol intérieur visible, y compris à travers une porte ou une enfilade ;
l'ombre portée sur le sol ; le reflet appartenant au sol ; le sol visible entre
et sous les pieds de meubles. Exclus : tapis et paillassons, meubles, pieds de
meubles, plinthes, murs, sol extérieur vu par une ouverture, éléments techniques
encastrés. Le tableau exhaustif et les trois décisions qui le précisent
(extérieur, encastré, incertain) vivent dans le protocole ; ce document ne les
recopie pas, pour qu'il n'existe jamais deux formulations.

**Un point reste ouvert et doit être tranché** (protocole §11.3) : deux
revêtements intérieurs différents dans la même photo. Aujourd'hui les deux
entrent dans le masque. Voir la porte de décision D2 dans
[ROADMAP-V2.md](ROADMAP-V2.md).

### 3.2 Deux notions distinctes, jamais confondues

| | ce que c'est | comment on l'obtient | qui l'annote |
| --- | --- | --- | --- |
| `floorVisible` | les pixels de sol qu'on voit | segmentation | **l'humain**, c'est la vérité terrain |
| `floorExtent` | la surface que le sol occupe vraiment, sous les meubles et les tapis | déduction géométrique depuis la caméra et le plan | **personne** — l'image ne la contient pas |

Le champ `masks.floorExtent` existe déjà dans le schéma d'annotation et reste
volontairement vide. Mesurer un segmenteur contre une cible que l'image ne
contient pas serait l'erreur la plus coûteuse du projet, et elle serait
invisible : les chiffres auraient l'air bons.

`floorExtent` est néanmoins **nécessaire au rendu** : sans lui, les lames ne
sont pas continues sous un canapé. Il est donc produit par l'étage de
géométrie, pas par la segmentation, et il est évalué par le rendu, pas par un
IoU.

## 4. Les objets : une taxonomie fonctionnelle, pas un zoo

Deux directions possibles.

**A — taxonomie sémantique** : canapé, fauteuil, table, chaise, plante,
radiateur, tapis, rideau… Avantage : c'est ce que produisent les modèles
préentraînés, donc l'étiquette arrive gratuitement. Inconvénients : le produit
n'a aucun usage de la différence entre un fauteuil et un pouf ; la liste est
ouverte et donc jamais complète ; et une classe manquante devient un objet
repeint, c'est-à-dire un défaut visible.

**B — taxonomie fonctionnelle** : cinq rôles, définis par ce que le rendu doit
en faire.

| rôle | ce que le moteur doit faire | exemples |
| --- | --- | --- |
| `OCCLUDER` | rester devant le parquet, pixels d'origine restitués | meuble, pied de chaise, carton, plante, rideau qui touche le sol |
| `FLOOR_COVERING` | ne jamais devenir du parquet, et rester tel quel | tapis, carpette, paillasson |
| `STRUCTURAL` | borner le sol par le bas | mur, plinthe, seuil, huisserie |
| `OPENING` | marquer où le sol candidat s'arrête ou continue | porte, passage, baie |
| `OTHER` | rien de particulier | le reste |

**Recommandation : B, avec l'étiquette sémantique conservée en second champ
facultatif.** La raison est une exigence de mesure : ce qui doit être évalué,
c'est « le parquet a-t-il été peint sur cet objet », question qui ne dépend pas
de son nom. Garder le nom en annexe coûte un champ et permet de comprendre un
échec (« ce sont tous des rideaux »), sans que la classification devienne le
critère.

Conséquence sur la vérité terrain : les humains annotent des **rôles**, ce qui
est décidable et rapide, pas des espèces de meubles.

## 5. Occlusion

Le principe de composition, déjà implémenté côté moteur :

```
image d'origine  +  sol rendu  +  composition par occlusion  =  image finale
        │                │                      │
        │                │                      └─ masques d'occulteurs, ordre en profondeur
        │                └─ parquet peint dans floorVisible ∪ (floorExtent ∩ visible)
        └─ pixels restitués partout ailleurs
```

Ce que Python doit fournir, et rien de plus :

- les masques des occulteurs, avec leur rôle (§4) ;
- leur **ligne de contact** au sol quand elle est visible : c'est elle qui fait
  qu'un meuble est posé et non flottant ;
- un **ordre de profondeur** entre occulteurs, pour les cas d'objets qui se
  recouvrent ;
- `floorExtent`, pour que le motif soit continu derrière eux.

Le schéma `Occluder` existe déjà et porte `polygon`, `contact`, `depth`,
`castsShadow`, `feather`. Il n'a pas besoin d'être refait ; il a besoin d'être
rempli, et d'accueillir le champ de rôle du §4.

**Le cas qui décide de tout** : les pieds fins. Une chaise a quatre contacts de
quelques pixels de large, et le sol se voit entre eux. Un masque d'occulteur
grossier les avale ; un masque de sol grossier les repeint. C'est la métrique
`thin-object preservation` de [BENCHMARK-STRATEGY-V2.md](BENCHMARK-STRATEGY-V2.md).

## 6. Profondeur : relative ou métrique

| usage | profondeur relative suffit ? | pourquoi |
| --- | --- | --- |
| trier deux occulteurs qui se chevauchent | **oui** | seul l'ordre compte |
| moduler la netteté du parquet avec l'éloignement | **oui** | c'est un dégradé, pas une mesure |
| séparer le sol d'un mur de même teinte | **oui** | la discontinuité suffit |
| poser des lames de 190 mm qui font 190 mm | **non** | il faut une échelle |
| dire « votre pièce fait environ 18 m² » | **non** | il faut une échelle |
| relier deux points de vue d'une visite | **non** | il faut une échelle commune |

**Conclusion : la profondeur relative couvre le Mode Photo, sauf l'échelle
physique.** Et l'échelle physique n'a pas besoin d'une carte métrique : elle
peut venir de la géométrie du plan de sol combinée à une hypothèse de hauteur
d'appareil, ou d'un repère de taille connue dans l'image. C'est une piste
nettement moins coûteuse qu'une profondeur métrique, et c'est le premier
arbitrage de l'étage géométrie.

La profondeur **métrique** devient réellement nécessaire au Mode Visite, où
deux vues doivent partager une échelle. Elle n'est donc pas un prérequis du
Mode Photo, et ne doit pas en retarder la livraison.

## 7. Caméra et perspective

Le minimum utile, par mode :

| information | Mode Photo | Mode Visite | source possible |
| --- | --- | --- | --- |
| horizon | **nécessaire** | nécessaire | contour du sol, verticales |
| points de fuite | **nécessaire** | nécessaire | droites de la scène |
| orientation du plan de sol | **nécessaire** | nécessaire | homographie du quadrilatère |
| focale approximative | utile | nécessaire | EXIF, ou déduite des fuites |
| échelle physique | **nécessaire** pour la largeur de lame | nécessaire | plan + hypothèse de hauteur |
| pose de caméra (position, cap) | inutile | **nécessaire** | multi-vues, capteurs |
| coefficients de distorsion | souhaitable | nécessaire | mesure déjà implémentée, correction non |

Deux remarques qui viennent du travail déjà fait :

- la distorsion d'objectif est **mesurée** aujourd'hui et **jamais corrigée**.
  Toute la géométrie suppose que les droites du monde sont droites dans l'image.
  Le jour où une correction existe, elle vient **avant** tout relevé, et
  `SceneData` doit porter les coefficients et leur provenance — mesurée, lue, ou
  supposée. Voir [lens-distortion.md](lens-distortion.md).
- la pose de caméra ne sert à rien en Mode Photo. L'ajouter maintenant serait un
  champ ajouté « parce que ça semble IA ».

## 8. Géométrie de pièce : le minimum qui tient

Trois niveaux de représentation possibles :

| niveau | contenu | ce qu'il permet | coût |
| --- | --- | --- | --- |
| **plan de sol seul** | un plan par surface, un masque par zone | tout le Mode Photo | c'est le schéma actuel |
| plan + murs | ajoute les plans verticaux et la ligne mur/sol | fiabiliser la limite basse, éclairage | annotation des murs |
| enveloppe de pièce | polygone au sol + hauteurs + ouvertures | mesures, visite, plan 2D | reconstruction |

**Recommandation : rester au plan de sol pour le Mode Photo, et n'ajouter les
murs que comme aide à la limite sol/mur, pas comme géométrie à part entière.**
L'enveloppe de pièce est un besoin du Mode Visite, pas du Mode Photo, et rien
n'oblige à la payer d'avance.

Ce choix a une conséquence agréable : `SceneData@1` suffit (§10).

## 9. Continuité du sol

Une photo montre souvent plusieurs zones du même sol : une enfilade, un passage,
un seuil. Le mécanisme existe déjà et il est bon :

- `surfaces[]` déclare les sols distincts ;
- chaque `floorZone` porte un `surfaceId` : **deux zones de même `surfaceId` sont
  le même parquet** ;
- `planes{}` déclare un plan une fois, et les zones le référencent par
  `planeRef` : deux pièces sur la même dalle sont **un seul plan**, ce qui
  garantit une continuité exacte au raccord.

Ce que Python doit décider, et qui est un vrai problème de compréhension :
`sameSurface` ou `differentSurface`. Deux pièces séparées par un seuil avec le
même revêtement sont une seule surface ; un salon en parquet ouvert sur une
cuisine carrelée sont deux surfaces, et le carrelage n'est probablement pas
candidat au remplacement. Cette décision est la seule chose à ajouter ; le
contrat pour l'exprimer existe.

## 10. SceneData : audit champ par champ

Version actuelle `pose-parquet/scene@1`, miroir fidèle du contrat du front,
verrouillé par un test contre les scènes réelles. Verdict global :
**suffisant pour le Mode Photo, extension nécessaire sur trois points, aucune
refonte.**

| champ | existe ? | suffisant ? | à étendre | pourquoi |
| --- | --- | --- | --- | --- |
| `schema`, `id`, `label`, `source` | oui | oui | — | `source: "ai"` distingue déjà notre production |
| `confidence` | oui | **non** | par composant (§11.3) | un scalaire global masque une frontière catastrophique |
| `image` | oui | oui | — | dimensions de référence, déjà mesurées |
| `camera.horizon`, `vanishingPoints` | oui | oui | — | exactement ce dont le moteur a besoin |
| `camera.fovDeg`, `tiltDeg`, `heightM` | oui | oui | — | facultatifs, non bloquants |
| `camera` — pose | **non** | oui pour le Mode Photo | **plus tard** | position et cap : Mode Visite seulement |
| `camera` — distorsion | **non** | **non** | **bloc `lens`** | coefficients + centre optique + provenance |
| `surfaces`, `planes`, `planeRef` | oui | oui | — | la continuité est déjà exprimable (§9) |
| `floorZones[].mask` | oui | oui | — | polygone + trous, aussi découpé qu'il faut |
| `floorZones[].plane` | oui | oui | — | homographie, fuite et échelle |
| `floorZones[]` — étendue | **non** | **non** | **`extentMask` ou `extentPolygon`** | continuité des lames sous les meubles (§3.2) |
| `occluders[]` | oui | presque | **champ `role`** (§4) | `kind` est libre ; le rôle doit être un vocabulaire fermé |
| `depth` (`plane` \| `image`) | oui | oui | — | relatif suffit au Mode Photo (§6) |
| `light` | oui | oui | — | valeurs verrouillées par test ; en diverger changerait le rendu |
| `warnings` | oui | presque | codes typés | aujourd'hui `list[str]` côté scène |
| `maps` (floorMask, depth, shading) | **non** | — | **à modéliser au moment du choix de modèle** | figer le format avant de savoir qui le produit serait prématuré |

Les trois extensions — `lens`, étendue de sol, rôle d'occulteur — sont
**additives** : une majeure `scene@1` reste valide, un consommateur ancien
ignore ce qu'il ne connaît pas. Aucune rupture de contrat n'est nécessaire, et
c'est un résultat, pas une chance : le contrat avait été conçu pour ça.

## 11. Le contrat de sortie de l'analyse

### 11.1 Version

Notre contrat s'appelle déjà `pose-parquet/analysis@2` et il est en place depuis
le LOT IA 1. La cible décrite ici est donc **`pose-parquet/analysis@3`**, et non
un « analysis v2 » qui existe déjà. Les deux versions peuvent coexister derrière
le préfixe d'URL.

```
analysis@3
├── schema, analysisId          ← analysisId est nouveau : corréler sans journaliser d'image
├── status                      ← les cinq valeurs, §11.2
├── image                       ← inchangé
├── quality                     ← inchangé (netteté, exposition, écrêtage)
├── lens                        ← inchangé (verdict, support, k1) ; la correction reste hors sujet
├── scene                       ← SceneData@1 + les trois extensions du §10
├── confidence                  ← par composant, §11.3
├── warnings                    ← structurés, §11.4
├── capabilities                ← ce que CETTE analyse a réellement produit
└── timings                     ← dev seulement, §13
```

`capabilities` est le champ qui évite le pire mensonge du système : il dit
quels étages ont tourné et abouti sur cette image (`floor: true, depth: false`),
au lieu de laisser l'interface déduire d'un statut global ce qu'elle peut
proposer. C'est aussi ce que `/health` doit annoncer au niveau du service.

### 11.2 Les statuts, et leur sens exact

Les cinq valeurs existent déjà. Leur sens est ici précisé, et il ne change pas :

| statut | sens précis | l'interface |
| --- | --- | --- |
| `success` | le rendu automatique peut être présenté **sans intervention** | rend, ne demande rien |
| `partial` | le rendu peut être montré, mais **certaines zones ou propriétés sont moins fiables** | rend, réserve non bloquante si elle est visible |
| `needs_manual_adjustment` | le rendu **ne doit pas être présenté comme final** sans correction | rend et invite à la brosse |
| `rejected` | la photo **ne permet pas** une analyse exploitable | ne rend pas, explique, propose une sortie |
| `analysis_incomplete` | état de développement : les contrôles ont tourné, l'analyse de pièce n'existe pas | **jamais exposé au public** |

Deux constats de l'audit à corriger dans le code, le jour venu : `partial`
n'est **jamais assigné** aujourd'hui, et `success` exige « une scène et zéro
avertissement », ce qui le rend inatteignable dès qu'un avertissement bénin
apparaît. La hiérarchie devra distinguer les avertissements qui dégradent le
rendu de ceux qui ne parlent que de la photo.

**La règle de repli reste absolue** : aucune panne du service ne doit priver
l'utilisateur du visualiseur. Le mode manuel est le socle, l'analyse une
accélération.

### 11.3 La confiance : par composant, jamais un scalaire

Aujourd'hui `confidence` vaut `null`, ce qui est honnête. La cible :

```
confidence: {
  floor:       0.0 → 1.0    surface trouvée
  boundaries:  0.0 → 1.0    la limite sol/mur, là où l'œil juge
  camera:      0.0 → 1.0    horizon et fuites
  depth:       0.0 → 1.0    ordre et continuité
  occlusions:  0.0 → 1.0    objets et lignes de contact
  overall:     0.0 → 1.0    dérivé, jamais moyenné
}
```

**`overall` n'est pas une moyenne.** Une moyenne élevée peut masquer une
frontière catastrophique : sol 0,95, caméra 0,9, frontière 0,2 donne 0,68, qui
« passe », alors que le résultat sera manifestement faux à l'écran. La règle est
donc : `overall` est **borné par le minimum des composants qui décident du
rendu** — la frontière et le sol — et les autres ne peuvent que le dégrader.
Le détail du calcul est une décision à prendre avec des données réelles
(porte D5).

Deux principes conservés : `confidence` **ne s'affiche jamais** à
l'utilisateur ; il sert à choisir l'écran. Et publier un nombre dérivé de
mesures qui ne portent pas sur la géométrie serait le pire mensonge que ce
service puisse dire.

### 11.4 Les warnings : structurés, et ce n'est pas du copywriting

Aujourd'hui un warning est une simple chaîne d'un vocabulaire fermé — pas
d'objet, pas de sévérité, pas de composant. Trois ensembles jouent le rôle
d'une échelle : `BLOCKING`, `SCORED`, `INFORMATIONAL`. La cible :

```
{ code, severity, component, message? }
   │       │         │          │
   │       │         │          └─ phrase par défaut, remplaçable par le front
   │       │         └─ floor | boundaries | camera | depth | occlusions | image
   │       └─ blocking | degrading | informational
   └─ vocabulaire fermé, mesurable par le banc d'essai
```

Le `code` reste obligatoire et fermé : la matrice de confusion du banc d'essai
en dépend, et un banc d'essai aveugle aux codes ne mesure plus rien. Le
`message` est un **repli**, pas la vérité éditoriale : le backend ne doit pas
écrire le texte final de l'interface, qui a ses propres contraintes de ton et
de traduction.

`severity` remplace les trois ensembles implicites par un champ explicite, et
`component` permet de rattacher un avertissement à la confiance qu'il dégrade.

## 12. Le pipeline, et comment comparer des candidats

Les étages sont déjà déclarés dans le chronométrage et le pipeline connaît seul
l'enchaînement. La cible ajoute une frontière explicite par étage, pour qu'on
puisse mettre deux implémentations en concurrence sans disperser des `if` dans
le code.

```
        bytes
          │
    ┌─────▼─────┐
    │ ImageLoad │  décodage, EXIF, garde-fous            ✅ livré
    └─────┬─────┘
    ┌─────▼─────┐
    │  Quality  │  netteté, exposition, écrêtage         ✅ livré
    └─────┬─────┘
    ┌─────▼─────┐
    │   Lens    │  distorsion mesurée, non corrigée      ✅ livré
    └─────┬─────┘
    ┌─────▼──────────┐
    │ FloorSegmenter │  masque de sol visible            ⏳ LOT C
    └─────┬──────────┘
    ┌─────▼───────────┐
    │ ObjectSegmenter │  rôles, masques, contacts        ⏳ LOT D
    └─────┬───────────┘
    ┌─────▼──────────┐
    │ DepthEstimator │  profondeur relative              ⏳ LOT E
    └─────┬──────────┘
    ┌─────▼───────────┐
    │ CameraEstimator │  horizon, fuites, plan, échelle  ⏳ LOT E
    └─────┬───────────┘
    ┌─────▼────────┐
    │ SceneBuilder │  assemblage, continuité, confiance  ⏳ LOT F
    └─────┬────────┘
       RoomAnalysis
```

**L'interface minimale d'un candidat**, à ne pas sur-abstraire — le banc d'essai
de segmentation utilise déjà exactement ce contrat, avec un registre par
décorateur et trois candidats triviaux :

| étage | signature | garanties exigées |
| --- | --- | --- |
| `FloorSegmenter` | `LoadedImage → mask bool` | dimensions exactes de l'image |
| `ObjectSegmenter` | `LoadedImage → [(role, mask, contact?)]` | rôles du vocabulaire fermé |
| `DepthEstimator` | `LoadedImage → depth float32` | valeurs croissantes avec l'éloignement, échelle libre |
| `CameraEstimator` | `LoadedImage, floor mask → camera` | coordonnées normalisées, hors [0,1] permis |
| `SceneBuilder` | tout ce qui précède `→ SceneData \| None` | `None` plutôt qu'une scène devinée |

Deux propriétés à conserver, elles viennent du travail déjà fait et elles sont
justes : **chaque étage est dégradable** — sans profondeur le rendu perd la
netteté variable, sans objets l'utilisateur retouche au pinceau, sans géométrie
on retombe sur le quadrilatère manuel, et rien n'est bloquant. Et **l'ordre
n'est pas arbitraire** : le redressement EXIF précède toute mesure, l'analyse
d'objectif précède toute géométrie.

### 12.1 Familles technologiques à évaluer — aucune n'est choisie

| besoin | familles classiques | familles apprises | risques à mesurer |
| --- | --- | --- | --- |
| segmentation du sol | seuillage par plan, croissance de région, contours + homographie | segmentation sémantique généraliste, segmentation par invite, segmentation de plans | frontière au pixel, sol bois sur mur bois, tapis pris pour du sol |
| segmentation d'objets | soustraction de fond, contours | segmentation d'instances, segmentation par invite, matting | pieds fins, transparence, rideaux |
| profondeur | fuite + plan (géométrique) | profondeur monoculaire relative, profondeur métrique | dérive sur surfaces unies, sols brillants |
| caméra | droites + points de fuite, homographie | estimation apprise d'horizon et de champ | pièces sans droites nettes, distorsion non corrigée |
| multi-vues | SfM, homographies inter-vues | profondeur multi-vues apprise, rendu de nouvelles vues | murs unis, échelle commune, coût |

Pour chaque candidat, avant tout statut « retenu », la grille de licence du §15
est obligatoire, et le poids et la latence doivent être **mesurés**, pas lus sur
une fiche.

## 13. Observabilité

Le chronométrage existe par étage et distingue déjà « non exécuté » de
« instantané ». La cible :

```
decodeMs · qualityMs · lensMs · floorMs · objectsMs · depthMs · cameraMs · sceneBuildMs · totalMs
```

Trois règles :

- **aucun contenu d'image dans les journaux.** Ni octets, ni base64, ni
  vignette, ni nom de fichier fourni par l'utilisateur. Sur exception, seul le
  type est journalisé, jamais la trace, parce qu'une trace expose des variables
  locales — dont des octets d'image.
- les timings détaillés sont **réservés au mode développement** ; en production
  seul `totalMs` a un usage légitime, et il ne s'affiche pas.
- `analysisId` corrèle une requête à ses journaux sans rien révéler de la photo.

## 14. Latence : des ordres de grandeur à mesurer, pas des promesses

| moment | objectif | statut |
| --- | --- | --- |
| photo affichée après l'import | immédiat, sans réseau | **tenu** aujourd'hui côté front |
| premier retour d'analyse (accusé, ou refus) | quelques centaines de ms | à mesurer |
| première pose de parquet après analyse réussie | quelques secondes, avec une attente expliquée | à mesurer |
| préparation d'une visite | peut être longue si elle est annoncée et interruptible | à mesurer |

Ces valeurs sont des **objectifs de mesure**, pas des engagements : aucun banc
matériel n'existe encore. Les seules latences déjà mesurées dans le projet sont
celles du moteur de rendu, pas celles de l'analyse.

## 15. Modèles, dépendances, licences

Aucun modèle, aucun poids, aucun framework d'apprentissage n'est installé
aujourd'hui — c'est un état vérifié, et un acquis à ne pas perdre par
inadvertance. Avant qu'un candidat passe au statut « retenu », cette grille est
obligatoire et archivée :

| colonne | ce qu'on y écrit |
| --- | --- |
| nom, version | l'identifiant exact évalué |
| source | dépôt ou publication d'origine |
| licence | le texte, pas le résumé |
| usage commercial | oui / non / conditionnel — avec la clause |
| redistribution | peut-on livrer les poids |
| poids du modèle | licence des poids, souvent différente de celle du code |
| restrictions | usage, domaine, attribution, part de revenus |
| statut juridique projet | à vérifier / vérifié / refusé, avec la date |

Les cinq conditions déjà en vigueur avant d'ajouter une dépendance lourde
restent en vigueur ([architecture.md](architecture.md)).

## 16. Vie privée

**Une photo de domicile est une donnée sensible, et un masque de sol l'est
aussi** : il décrit la géométrie d'une habitation. Les règles, déjà écrites et
convergentes dans cinq documents, sont reprises telles quelles :

- traitement **temporaire**, en mémoire ; rien sur le disque, pas même en
  fichier temporaire ;
- aucun stockage permanent par défaut, aucune base de données ;
- aucun ajout automatique au jeu de données ; l'entrée au corpus est une
  décision humaine explicite, avec consentement documenté et distinct ;
- aucun contenu d'image dans les journaux ;
- suppression des fichiers temporaires si un traitement long en impose ;
- séparation stricte entre le **corpus de développement** (`private-real/`,
  photos sous licence, jamais des photos d'utilisateurs) et les **envois
  d'utilisateurs** (jamais dans un corpus).

Un point de tension à traiter au moment du branchement : le front promet
aujourd'hui que la photo ne quitte pas le navigateur. Appeler un service distant
rend cette phrase fausse. L'analyse distante devra donc être un choix explicite,
avec un mode local à un clic, et la phrase affichée devra être réécrite.

## 17. Les API, par famille

| route | rôle | statut |
| --- | --- | --- |
| `GET /health` | le service répond, et **ce qu'il sait faire** (`capabilities`) | existe ; `capabilities` à ajouter |
| `POST /v1/analyze-room` | **une image** → une analyse pour le Mode Photo | existe |
| `POST /v1/analyze-capture` | une capture multi-vues → un traitement long | **à ne pas créer** avant le LOT H |
| `GET /v1/jobs/{id}` | avancement et résultat d'un traitement long | **à ne pas créer** avant le LOT H |

Deux décisions de conception :

**`/v1/analyze-room` ne doit pas apprendre la vidéo ni le multi-vues.** Son
contrat est « une image, une analyse ». Lui greffer des entrées de nature
différente rendrait sa réponse ambiguë — que vaut `status: success` pour une
capture de douze vues dont trois ont échoué ?

**Le Mode Visite mérite un contrat séparé et asynchrone.** Les entrées, les
durées et les modes d'échec n'ont rien de commun. La forme conceptuelle est
`job → progress → status → result`, mais **rien n'est développé** : le nombre
d'endpoints n'augmente pas tant que leurs responsabilités ne sont pas validées.

Il subsiste un écart d'URL à ne pas oublier : le contrat du front écrit
`POST /analyze-room`, ce service expose `POST /v1/analyze-room`. Le préfixe est
délibéré et se règle en un seul endroit côté front.
