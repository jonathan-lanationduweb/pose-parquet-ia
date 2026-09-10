# Vision produit

> **ACTIF.** Source de vérité de la cible produit. Toute décision d'architecture
> ou de jeu de données doit pouvoir se justifier par une ligne de ce document.
> Ce qu'il ne contient pas : l'état actuel du service (voir
> [architecture.md](architecture.md)), le contrat d'échange avec l'interface
> (voir [product-ai-contract.md](product-ai-contract.md)).

## 1. Ce qu'on veut, en une phrase

Qu'une personne photographie sa pièce, voie immédiatement un vrai parquet
Premibel posé au sol, en change d'un clic, et — plus tard — s'y déplace comme
dans une visite.

## 2. Les références, et ce qu'on prend à chacune

**Roomvo est la référence fonctionnelle principale** — décision humaine du
10 septembre 2026. Trois simulateurs comparés relèvent de la même famille de
solution : `panaget.com/imaginebypanaget`, `lamaisonsaintgobain.fr/simulateur-3d`
et `parquet-carrelage.com` (simulateur 3D). Panaget l'annonce explicitement.

Ce qu'être « référence fonctionnelle » signifie ici, et ce que ça ne signifie
pas : Roomvo répond à **« comment ça fonctionne »**, jamais à « à quoi ça doit
ressembler ». Nous reproduisons des **capacités** et une simplicité de
parcours, avec notre architecture et notre design. Ni code, ni assets, ni
identité, ni interface au pixel. C'est une technologie propriétaire :
aucun algorithme obtenu par rétro-ingénierie, aucune intégration de leur
produit dans le nôtre. Le seul matériau du comparatif est ce qui est
publiquement visible en utilisant ces sites.

| référence | ce qu'on lui prend | ce qu'on ne lui prend pas |
| --- | --- | --- |
| **Roomvo** (et Quick-Step, Karndean, même famille d'expérience) | l'immédiateté : importer, voir, changer de produit au clic, comparer, avant/après, favoris. Interaction minimale, aucun assistant en plusieurs étapes. Photo au centre, catalogue visuel, attente signalée sans modale bloquante | leur qualité de sol, souvent approximative : bords qui montent sur la plinthe, tapis repeints. Et leur généralité — ils traitent murs, carrelage, moquette ; nous ne traitons que le parquet, et c'est là qu'on doit être meilleurs |
| IKEA Kreativ | la compréhension automatique de la pièce : géométrie, objets, profondeur, occlusions, une représentation exploitable de l'espace | l'ameublement virtuel et le catalogue d'objets, hors de notre sujet |
| Google Street View | la sensation de déplacement : regarder autour, aller d'un point de vue à un autre | l'interface : pas de Pegman, pas de mini-carte, aucun élément visuel repris |
| notre spécialité | tout le reste — voir §3 | — |

### 2.1 Le parcours cible, et où nous en sommes

Relevé le 10 septembre 2026, en testant notre propre visualiseur au
navigateur. « Partiel » n'est pas « presque fait » : c'est présent et
insuffisant.

| capacité du parcours | chez nous | état exact |
| --- | --- | --- |
| photo au centre de l'expérience | **présente** | la photo occupe le cadre, les panneaux sont escamotables |
| import très simple | **présente** | un clic, la photo est la pièce immédiatement (corrigé au LOT UX.1) |
| pièces d'exemple immédiates | **présente** | cinq pièces, `SceneData` déjà calibrée, rendu en 0,2 à 2 s |
| catalogue produit visuel | **présente** | cinq références réelles, vignettes, filtres motif/teinte/largeur |
| un clic produit = sol mis à jour | **présente** | aucun bouton « Appliquer » |
| changement **instantané** de produit | **partielle** | 0 ms si déjà vu, 1 à 3 s sinon, jusqu'à 17 s pour une tuile froide. Voir [RENDERER-AUTONOMY-PLAN.md §8](RENDERER-AUTONOMY-PLAN.md) |
| rotation du plan de pose | **partielle** | le moteur accepte **tout angle** (§2.2) ; notre interface n'en expose que trois |
| motifs lames, point de Hongrie, bâton rompu | **présente** | les trois rendus par le moteur réel |
| largeur de lame | **présente** | bornée 0,02–0,5 m par le moteur, refus explicite hors bornes |
| avant/après | **présente** | volet unique partagé avec la comparaison |
| comparaison A/B | **présente** | deux rendus live, deux fiches |
| favoris | **présente** | par session, non persistés |
| conservation de la lumière | **présente** | l'éclairement est **relu dans la photo** : carte d'éclairement floutée, lumière d'ambiance, part de teinte, assombrissement de contact. Ce n'est pas une texture opaque posée sur le sol |
| occlusions — parquet derrière les meubles, objets devant | **partielle** | le moteur sait restituer les pixels d'origine sur un `occluder` ; **personne ne produit ces polygones automatiquement**. Sur les cinq pièces d'exemple ils sont calibrés à la main, sur une photo importée il n'y en a aucun |
| analyse automatique de la pièce | **absente** | c'est l'objet des LOTS B à F. Aucune photo importée ne reçoit de parquet aujourd'hui, et c'est volontaire |
| continuité du sol sous les meubles (`floorExtent`) | **absente** | ni annotée, ni produite, ni déduite |
| fiche produit | **présente** | lien vers la fiche Premibel, référence, largeur, motif |

Deux dépendances expliquent tout ce qui est absent : **l'analyse Python**
(LOTS B→F) et **l'autonomie du moteur** (lot d'extraction). Aucune ne se
contourne par un masque esthétique — un parquet posé au hasard sur une photo
non analysée serait pire que pas de parquet.

### 2.2 Rotation du plan de pose — exigence produit

L'utilisateur doit pouvoir tourner **le plan de pose**, en continu de 0° à
359°, avec des raccourcis (0°, 45°, 90°, 135°, et −45° si l'usage le demande).
Un contrôle simple — deux flèches et une valeur, ou un cadran, éventuellement
glissable. Pas de panneau technique, pas de matrice, pas de coordonnées :
la personne doit comprendre « je tourne mes lames ».

Quatre invariants, et ils ne sont pas négociables :

1. **la photo ne tourne pas.** La pièce reste fixe, le plan du sol reste fixe
   dans l'espace ; seules les coordonnées de texture tournent ;
2. **l'échelle ne change pas.** Une lame de 190 mm mesure 190 mm à 0° comme à
   46° ;
3. **la perspective est conservée.** La rotation se fait *dans le plan du
   sol*, après l'homographie — jamais par une rotation d'image ;
4. **le motif entier tourne**, pas chaque lame indépendamment : un point de
   Hongrie tourné reste un point de Hongrie.

Et la rotation ne relance **jamais** l'analyse Python : une fois la pièce
analysée, tourner le sol est un travail de moteur.

**Deux rotations, à ne jamais confondre.** La rotation A est celle du plan de
pose, ci-dessus. La rotation B sera celle du **regard** dans une pièce à
plusieurs vues (Mode Visite, §4). Elles sont indépendantes, et leurs états ne
doivent jamais se mélanger.

## 3. Notre avantage doit être le sol, et seulement le sol

C'est le seul terrain où l'on peut être meilleur que des acteurs mieux dotés :
personne n'a intérêt à traiter le sol aussi finement que nous.

**Ce que « bien traiter le sol » veut dire, exhaustivement :** la limite
sol/mur, les plinthes, les seuils, les ouvertures, les tapis, les pieds de
meubles, les objets posés au sol, la continuité d'une surface d'une pièce à
l'autre, la perspective, l'échelle physique, la largeur et la longueur réelles
des lames, les lames, le point de Hongrie, le bâton rompu, l'orientation, les
joints, les chanfreins, la variation entre lames, le veinage, la finition, la
lumière, les réflexions, les occlusions.

Trois de ces points décident de la crédibilité, et ce sont ceux que la
concurrence rate : **la limite sol/mur au pixel**, **les pieds fins**, **les
tapis**. Un parquet qui monte de trois pixels sur une plinthe blanche se voit
immédiatement ; une largeur de lame fausse ne se voit pas mais se paie au
devis.

## 4. Deux modes produit, à ne jamais confondre

### Mode Photo — une image, tout de suite

**Entrée** : une photographie ordinaire, prise au téléphone.

**Objectif** : un parquet crédible dans cette photo, en quelques secondes.

```
photo → validation → qualité → segmentation du sol → objets → profondeur
      → caméra / perspective → occlusions → SceneData → moteur de rendu
```

**Parcours attendu**, sans assistant ni étapes numérotées :

1. Importer ma photo.
2. La photo s'affiche immédiatement, avant toute analyse.
3. L'analyse tourne en arrière-plan.
4. Si elle réussit, un premier parquet est posé automatiquement.
5. L'utilisateur peut aussitôt changer de produit, comparer, basculer
   avant/après, garder un favori, et personnaliser **les seules options
   réellement disponibles** pour la référence choisie.
6. Si une correction est nécessaire, une brosse Ajouter / Retirer, jamais un
   formulaire.

L'étape 2 est déjà livrée dans le front et ne doit pas régresser : la photo
importée est la pièce, sans écran intermédiaire.

### Mode Visite — plusieurs vues, se déplacer

**Entrée future**, à trancher par expérimentation (voir
[DATASET-STRATEGY-V2.md](DATASET-STRATEGY-V2.md) §4) : capture vidéo guidée,
série de photos guidée, panoramas 360, ou capteur de profondeur quand il
existe.

**Objectif** : regarder autour de soi et se déplacer dans la pièce, en gardant
le parquet choisi.

**Ce mode n'est pas un pan/zoom.** Déplacer une image plate dans son cadre
n'est pas une visite, et l'appeler ainsi serait le même mensonge qu'un faux
masque de sol.

**Parcours attendu** : Scanner ma pièce → capture guidée → traitement annoncé
comme long → ouverture de la visite. Puis : glisser pour regarder, zoomer,
cliquer une direction pour avancer, changer de produit sans perdre sa position.

## 5. Trois niveaux d'immersion

| niveau | ce que l'utilisateur peut faire | prérequis | état |
| --- | --- | --- | --- |
| 1 — photo simple | déplacer et zoomer dans une image | une photo | **livré** dans le front |
| 2 — multi-vues et panoramas | passer d'un point de vue réel à un autre dans le même lieu ; tourner le regard si panorama | plusieurs captures calibrées du même lieu | contrat de données écrit côté front (`data/room-tours.json`), **aucune donnée** |
| 3 — reconstruction spatiale | se déplacer librement | des dizaines de vues, une chaîne de traitement lourde, un moteur de rendu différent | **non engagé** |

**Aucune technologie de niveau 3 n'est choisie**, et ce lot n'en choisit pas.
Les options connues, avec ce qu'elles coûtent :

| option | ce qu'elle donne | ce qu'elle exige | risque principal |
| --- | --- | --- | --- |
| photogrammétrie classique (SfM + MVS) | maillage et nuage de points métriques | beaucoup de vues, surfaces texturées | échoue sur les murs unis et les sols brillants, très fréquents chez nous |
| NeRF | rendu de nouvelles vues très fidèle | entraînement par scène, GPU | pas de surface explicite : on ne sait pas où « poser » un parquet |
| Gaussian Splatting | rendu rapide et fidèle, entraînement plus court | GPU, tuilage mémoire | même problème : représentation non surfacique, donc à convertir |
| profondeur multi-vues apprise + fusion | surfaces exploitables, coût modéré | calibration inter-vues fiable | dérive d'échelle entre vues |

Le point commun de ces options est qu'elles produisent une apparence, pas une
surface qualifiée. Or notre problème n'est pas de refabriquer la pièce : c'est
de savoir **où est le sol et jusqu'où il va**. C'est un critère de sélection à
part entière pour le jour où le niveau 3 sera étudié.

## 6. Ce qu'est pose-parquet-ai, et ce qu'il n'est pas

```
                       ┌──────────────────────────────┐
   image / capture ───► │        pose-parquet-ai       │ ───► représentation
                       │  compréhension de la pièce   │      structurée
                       └──────────────────────────────┘            │
                                                                   ▼
                                            navigateur : moteur de rendu WebGL
```

**Il est** le cerveau de compréhension de scène : il regarde une capture et en
publie une description structurée.

**Il n'est pas** l'interface utilisateur, et il n'est pas un moteur de rendu de
parquet. Le moteur existe, il est éprouvé, il vit dans le front, et il n'a rien
à apprendre de ce service. Toute tentation de dessiner un parquet en Python est
une erreur d'architecture, y compris « juste pour une maquette ».

## 7. Définition de « terminé »

Le produit n'est pas terminé quand l'API répond 200. Il est terminé quand, sur
une photo réelle qu'on n'a pas choisie :

- le bon sol est identifié ;
- tout le sol qui devait l'être est remplacé ;
- aucun mur, aucune plinthe n'est peint ;
- les meubles sont préservés, pieds fins compris ;
- les tapis sont préservés ;
- la perspective est cohérente avec la pièce ;
- le parquet est crédible et sa matière lisible ;
- la largeur de lame est physiquement juste ;
- la référence est identifiable par quelqu'un qui connaît le produit ;
- l'expérience est fluide, sans étape imposée.

Et pour le Mode Visite :

- la pièce est réellement navigable ;
- les vues sont bien le même lieu ;
- les transitions donnent la sensation d'un déplacement ;
- le parquet choisi est conservé d'une vue à l'autre ;
- aucune géométrie n'est inventée grossièrement.

Ces listes sont les critères de la revue visuelle humaine décrite dans
[BENCHMARK-STRATEGY-V2.md](BENCHMARK-STRATEGY-V2.md) §6.

## 8. Ce que la vision n'autorise pas

- présenter un masque approximatif comme une détection ;
- appeler « visite » un déplacement dans une image plate ;
- déclarer un modèle bon parce que son IoU est bon, sans regarder le rendu ;
- offrir un réglage que le moteur ne sait pas rendre, ou que la fiche produit
  ne porte pas ;
- faire dépendre l'utilisateur de l'analyse : le mode manuel reste le socle,
  l'analyse est une accélération.
