# Mode Visite — architecture d'une navigation libre

> **ACTIF · CIBLE.** Fait foi sur : la différence entre les deux modes produit
> et leurs capacités, le pipeline visé pour une navigation libre, les trois
> familles de reconstruction et ce qui les sépare pour NOTRE besoin, la
> question du sol éditable, le format conceptuel d'une scène navigable, le
> protocole de capture d'une pièce pilote, et le plan d'expérimentation.
> Écrit le **10 septembre 2026** (VISITE.0).
>
> **Rien n'est implémenté, et rien ne doit l'être depuis ce document.** Aucune
> démonstration n'a été fabriquée : `MULTI_VIEW_DATA = 0`, aucun de nos assets
> ne peut prouver une navigation. Une fausse visite construite avec nos photos
> actuelles ne prouverait qu'une chose — qu'on sait faire un fondu.
>
> Pourquoi un document à part : aucun document actif ne couvrait le sujet.
> [PRODUCT-VISION.md](PRODUCT-VISION.md) §4 fixe l'intention produit,
> [ROADMAP-V2.md](ROADMAP-V2.md) LOT H et I fixent les lots ; l'architecture
> technique n'avait pas de place, et l'inventer dans l'un des deux les aurait
> rendus illisibles.

## 1. Deux modes, deux capacités, jamais mélangés

| | **Mode Photo** | **Mode Visite** |
| --- | --- | --- |
| entrée | une image | une capture spatiale |
| ce que Python produit | `SceneData` d'une vue | une représentation de pièce et des poses de caméra |
| ce que le navigateur fait | rendu du sol, pan et zoom 2D | rendu du sol **et** navigation d'une vraie caméra |
| `PAN_ZOOM` | **true** | true |
| `FREE_NAVIGATION` | **false** | **true** |

`FREE_NAVIGATION = false` sur une photo unique n'est pas une limitation
temporaire à lever par un effort d'ingénierie : une image plate ne contient
pas ce qui se trouve derrière le canapé. Rien ne doit laisser croire le
contraire — et **pan/zoom ne s'appelle jamais « Street View »**.

Conséquence sur l'état : deux jeux de variables, sans aucun lien.

| état | appartient à | exemple |
| --- | --- | --- |
| `floorAngle` | le **parquet** | `37°` |
| `cameraYaw`, `cameraPitch` | le **regard** | `212°`, `−8°` |
| `cameraPosition` | le déplacement | un point dans la zone navigable |

Tourner le sol ne tourne pas le regard ; tourner le regard ne tourne pas le
sol. Les mélanger donnerait un produit où l'on ne sait plus ce qu'on
manipule — et c'est le genre de confusion qu'on ne rattrape pas.

## 2. La cible n'est pas un fondu entre deux vues

Un enchaînement `point de vue A → fondu → point de vue B` est une **étape
intermédiaire acceptable**, pas la cible. Ce qu'on veut :

```
                    AVANCER
                       ↑
        REGARDER  ←  CAMÉRA  →  REGARDER
                       ↓
                    RECULER
```

et, indépendamment, une rotation du regard sur 360°.

Le critère de recette est un verdict humain, déjà écrit au LOT I :
**« je me suis déplacé »**, et non « j'ai changé d'image ». Un fondu bien fait
échoue à ce critère, et le savoir maintenant évite de le livrer.

## 3. Pipeline visé

```
capture (vidéo guidée, ou photos, ou 360, ou capteur)
   ↓  Python
sélection des images utiles          netteté, recouvrement, exposition
   ↓
points d'intérêt et correspondances
   ↓
poses de caméra + intrinsèques      structure-from-motion
   ↓
profondeur / géométrie densifiée
   ↓
reconstruction de la pièce
   ↓
sol et objets                        segmentation, occulteurs, zone navigable
   ↓
représentation spatiale exportée
   ↓  navigateur
visionneuse WebGL + navigation libre + rendu du parquet
```

Python orchestre l'analyse ; le navigateur affiche et navigue. Cette frontière
ne bouge pas : **le rendu du parquet reste dans le navigateur**, en WebGL,
comme aujourd'hui.

## 4. Trois familles de reconstruction

Comparaison **qualitative et honnête** : aucune de ces lignes n'est un chiffre
mesuré chez nous, puisque nous n'avons encore aucune donnée multi-vues. C'est
une grille pour choisir **quoi expérimenter**, pas un classement.

| critère | **A — SfM + MVS + maillage** | **B — NeRF** | **C — Gaussian Splatting** |
| --- | --- | --- | --- |
| qualité en intérieur | correcte ; souffre des murs unis et du peu de texture | bonne, y compris sur les matériaux difficiles | bonne, souvent la plus nette à temps de calcul égal |
| navigation libre | **oui**, géométrie explicite | oui, mais le rendu dépend d'un réseau à évaluer par rayon | oui, rendu en rastérisation |
| coût GPU | modéré ; SfM tient sur processeur | **le plus élevé**, entraînement par scène | élevé mais nettement inférieur au NeRF |
| durée de reconstruction | minutes à dizaines de minutes | dizaines de minutes à heures | minutes à dizaines de minutes |
| lecture dans un navigateur | **la plus simple** : un maillage et des textures, WebGL sait déjà | difficile : demande une visionneuse spécialisée, coûteuse sur mobile | possible, visionneuses WebGL existantes, poids à surveiller |
| export | formats standards, outillage mûr | non standardisé | format de nuage de gaussiennes, écosystème jeune |
| taille livrée | maîtrisable (décimation, compression de textures) | poids de réseau | de dizaines à centaines de Mo selon la scène |
| objets fins (pieds de chaise) | **faible** — c'est là que le maillage échoue le plus | moyenne | **la meilleure** des trois |
| surfaces réfléchissantes | mauvaise, la géométrie se creuse | bonne | correcte |
| **sol remplaçable** | **oui, naturellement** — le sol est une surface identifiable | **difficile** — l'apparence est encodée dans le réseau | **difficile** — l'apparence est cuite dans les gaussiennes |

La dernière ligne est celle qui décide, et elle est développée au §5.

## 5. Le sol doit rester éditable — la contrainte qui commande tout

Une reconstruction photoréaliste de la pièce **ne suffit pas**. Notre produit
n'existe que si l'on peut remplacer le sol. Or le sol est précisément ce que
NeRF et Gaussian Splatting encodent le plus solidement : dans les deux cas,
l'apparence est apprise et **cuite** dans la représentation. Retirer le
parquet d'origine d'un nuage de gaussiennes n'est pas un réglage, c'est une
opération de retouche sur des dizaines de milliers de primitives — et ce qu'on
obtiendrait resterait une approximation de ce qui était là, pas une surface
qu'on repeint.

Autrement dit : **une belle reconstruction dont le sol est figé est un échec
produit**, quelle que soit sa qualité visuelle.

## 6. L'architecture hybride, et pourquoi c'est la piste sérieuse

```
REPRÉSENTATION DE PIÈCE            ce qui n'est pas le sol : murs, meubles,
   (maillage, ou splats, ou vues)  ouvertures, lumière — figé, c'est voulu
                +
SURFACE DE SOL EXPLICITE           un plan (ou quelques plans) avec son
   (géométrie, pas apparence)      contour, ses trous, son échelle en mètres
                +
MATÉRIAU PARQUET                   notre rendu WebGL actuel, inchangé
                +
OCCULTEURS ET PROFONDEUR           ce qui doit rester devant le parquet
```

Le sol n'est **pas** rendu par la reconstruction : il est retiré de la
représentation et redessiné par notre moteur, à chaque image, avec le produit
et l'angle choisis. La reconstruction fournit la caméra, la géométrie, les
objets et l'éclairement ; nous fournissons le sol.

Trois raisons de préférer cette voie :

1. **elle garde le sol éditable par construction** — c'est la contrainte du §5 ;
2. **elle réutilise notre moteur** : le rendu du sol en perspective à partir
   d'un plan et d'une caméra est exactement ce que fait déjà
   `perspective.js` + `renderer-gl.js` ([RENDERER-AUTONOMY-PLAN.md](RENDERER-AUTONOMY-PLAN.md)) ;
3. **elle découple les risques** : la qualité de la reconstruction et la
   qualité du parquet deviennent deux problèmes séparés, mesurables séparément.

Ce qu'elle ne résout pas, et qu'il faudra mesurer : le **raccord**. Le sol
redessiné doit s'aligner au pixel sur la géométrie reconstruite, sous
n'importe quel angle de caméra. C'est le risque principal de cette
architecture, et il ne se juge que sur une pièce réelle.

## 7. Format conceptuel d'une scène navigable

Esquisse, à valider par l'expérimentation — **aucun contrat n'est figé ici**,
et rien n'est implémenté. L'esprit reste celui de `pose-parquet/scene@1` :
coordonnées normalisées, unités déclarées, aucune donnée qu'on ne sache
produire.

```
RoomTour
  schema            "pose-parquet/room@1"  (à créer, pas à supposer)
  units             mètres
  camera
    intrinsics      focale, centre optique, distorsion
    poses[]         position + rotation par point de vue ou par image
  representation
    kind            "mesh" | "splats" | "views"
    payload         référence de fichier — jamais des pixels dans le JSON
  floor
    planes[]        équation du plan, origine de trame, échelle en mètres
    boundary        contour du sol en 3D
    holes[]         ce qui perce le sol
    surfaceId       la continuité, comme aujourd'hui
  occluders[]       géométrie de ce qui doit rester devant
  navigable
    area            polygone au sol où la caméra peut aller
    eyeHeightM      hauteur du regard
  light             ce qu'on sait de l'éclairement
  confidence        par composant, jamais un scalaire unique
```

Le lien avec le Mode Photo est volontaire : `floor.planes` joue le rôle de
`plane.quad`, `surfaceId` garde le même sens, les occulteurs gardent le leur.
Une pièce navigable n'est pas un autre produit, c'est la même scène vue de
plusieurs endroits.

## 8. Navigation — contrôles

| geste | effet |
| --- | --- |
| glisser (souris ou doigt) | tourner le regard |
| molette, pincement | zoom |
| clic ou tap sur un point du sol | avancer vers ce point |
| touches fléchées, en option sur ordinateur | avancer, reculer, pivoter |

Ni personnage, ni mini-carte, ni bonhomme jaune : rien de l'interface d'un
service de cartographie n'est repris. Les indicateurs de déplacement restent
discrets, comme déjà décidé au LOT I.

**Zone navigable** (`NAVIGABLE FLOOR AREA`) : la caméra ne doit traverser ni
les murs, ni les meubles, et ne doit pas sortir de la pièce. Cela demande un
polygone au sol et la hauteur du regard — donc de la géométrie que la
reconstruction doit fournir. **Tant que cette géométrie n'existe pas, la
contrainte n'est pas implémentée**, et une navigation sans contrainte ne doit
pas être exposée : voir un mur de l'intérieur détruit l'illusion plus
sûrement que tout autre défaut.

## 9. Le produit survit au déplacement

Si la personne a choisi Zeus, point de Hongrie, 92 mm, orientation 37°, puis
se déplace : **l'état produit reste exactement le même.** La caméra change, le
parquet non. Aucune réinitialisation, aucun rechargement de catalogue, aucune
nouvelle analyse Python. C'est la même règle qu'en Mode Photo, où tourner le
sol ne relance jamais l'analyse.

## 10. Protocole de capture — UNE pièce pilote

Recommandation pour la **première** expérience : **vidéo guidée**. C'est le
geste le plus proche de ce qu'une personne fera vraiment, et c'est celui dont
l'échec nous apprendrait le plus. Une seule pièce, d'abord.

| paramètre | consigne | pourquoi |
| --- | --- | --- |
| appareil | un téléphone récent, caméra arrière principale ; trépied inutile | c'est le matériel du produit |
| type de capture | **vidéo continue**, 4K si disponible, sinon 1080p, 30 im/s | la résolution sert la netteté des images extraites |
| stabilisation | laissée active | le flou de bougé est l'ennemi n° 1 de la mise en correspondance |
| durée | **60 à 90 secondes** pour une pièce ordinaire | assez d'images utiles sans séquence ingérable |
| trajet | marcher **lentement le long des murs**, puis traverser la pièce en diagonale, en gardant le sol dans le cadre | le déplacement latéral est ce qui donne la parallaxe ; tourner sur soi-même n'en donne aucune |
| vitesse | environ **0,3 m/s** — deux fois plus lent que la marche normale | au-delà, le flou et les sauts d'images dominent |
| hauteur de caméra | **1,4 à 1,6 m**, stable, appareil légèrement incliné vers le bas (10 à 20°) | hauteur du regard, et le sol doit rester le sujet |
| recouvrement | tout point du sol doit apparaître dans **au moins 3 images** prises d'endroits différents | c'est la condition de la triangulation |
| rotation | **jamais de rotation sur place seule** ; toujours associée à un déplacement | une rotation pure ne reconstruit rien |
| lumière | lumière du jour, volets ouverts, éclairages allumés, **sans changer** pendant la prise | un changement d'exposition en cours de séquence fausse la mise en correspondance et l'éclairement |
| pièce | rangée mais **meublée** — au moins un meuble aux pieds fins et **un tapis** | ce sont nos cas difficiles, et le corpus n'en a aucun |
| à éviter | miroirs face à la caméra, sols très brillants, pièce à moitié sombre, marche rapide, zoom pendant la prise, doigt sur l'objectif, changement d'orientation du téléphone | chacun de ces défauts a une conséquence connue sur la reconstruction |
| complément utile | 6 à 8 photos fixes des mêmes lieux, en plus de la vidéo | elles servent de référence de netteté et de repli si la vidéo échoue |
| confidentialité | même régime que `datasets/private-real/` : **jamais dans Git** | c'est un domicile |

Matériel minimum : **un téléphone**. Rien d'autre n'est nécessaire pour la
première expérience — et si la vidéo guidée exige un trépied ou un LiDAR, elle
a déjà échoué comme geste grand public.

## 11. Plan d'expérimentation

| étape | question à trancher | livrable | ce qui la bloque |
| --- | --- | --- | --- |
| V1 | une vidéo au téléphone donne-t-elle des poses de caméra exploitables dans une pièce ordinaire ? | une pièce pilote capturée, poses estimées, taux d'images retenues | **la capture** — personne ne l'a faite |
| V2 | la géométrie obtenue permet-elle d'isoler le sol comme surface explicite ? | plan(s) de sol, contour, échelle en mètres | V1 |
| V3 | notre moteur sait-il repeindre ce sol depuis plusieurs points de vue, sans décalage visible ? | rendus comparés depuis 3 caméras | V2, et le moteur autonome |
| V4 | quelle famille de reconstruction pour le reste de la pièce ? | comparaison A / B / C sur la **même** pièce | V1 |
| V5 | la navigation donne-t-elle « je me suis déplacé » ? | verdict humain écrit | V3, V4 |

Aucune de ces étapes ne commence sans V1, et V1 ne commence pas sans une
capture réelle. C'est le seul point de blocage, et il ne se lève pas par du
code.

## 12. Ce que ce document n'autorise pas

- fabriquer une démonstration de navigation avec nos photos actuelles ;
- appeler « visite » un pan/zoom, ou un fondu entre deux images ;
- choisir une famille de reconstruction avant la comparaison V4 ;
- retenir une représentation dont le sol serait figé (§5) ;
- exposer une navigation sans zone navigable (§8) ;
- mélanger l'angle du parquet et l'angle du regard (§1) ;
- créer un second HTML de visualiseur : la visite vivra dans
  `tools/product-concept.html`, avec ses modules.
