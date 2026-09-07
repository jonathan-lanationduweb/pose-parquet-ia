# Méthodologie du LOT IA 1 — ce qui a été comparé, et ce qui a été mesuré

Ce document est le compte rendu du lot. Il dit quelles méthodes ont été mises
en concurrence, sur quelles données, avec quels chiffres, et **ce qui ne marche
pas**. Les décisions y sont justifiées par des mesures reproductibles :

```bash
python -m benchmarks.run_benchmark          # matrice de confusion, FP compris
python -m benchmarks.compare_candidates     # marges de séparation des candidates
```

Les deux rapports embarquent l'instantané complet des réglages
(`Settings.algorithm_config()`), sans lequel deux exécutions ne sont pas
comparables.

---

## 1. Le défaut méthodologique du LOT 0

Le banc d'essai du LOT 0 ne comptait que les défauts **manqués**, et
rapportait fièrement `withMissedIssues: 0`. Le chiffre était vrai et
trompeur : un détecteur qui déclare tous les défauts sur toutes les photos n'en
manque aucun non plus. Ne compter que les manques **récompense la
sur-détection** — précisément le comportement qui rend un service inutilisable,
puisqu'un utilisateur à qui l'on signale cinq problèmes sur une photo correcte
cesse de lire les avertissements.

Le comptage du LOT 1 est une matrice de confusion multi-label sur les neuf
codes que le pipeline sait émettre (`warnings.SCORED`) :

| | attendu | non attendu |
| --- | --- | --- |
| **détecté** | vrai positif | **faux positif** |
| **non détecté** | faux négatif | vrai négatif |

Trois choix à noter :

* `tn` a un **dénominateur explicite** — neuf étiquettes, pas tous les codes du
  projet. Un vrai négatif calculé sur un vocabulaire qui grandit à chaque lot
  gonflerait tout seul ;
* les codes **informationnels** (`stage_not_implemented`,
  `lens_analysis_undetermined`) n'entrent pas dans la matrice. Un aveu
  d'ignorance n'est pas une affirmation : le compter en faux positif punirait
  l'honnêteté, en vrai positif récompenserait un détecteur muet. Ils sont
  comptés à part ;
* **aucune « exactitude » n'est publiée.** Sur un problème multi-label
  majoritairement négatif, un taux de bonnes réponses est dominé par les vrais
  négatifs et flatte n'importe quel détecteur silencieux. Le rapport publie les
  comptes bruts, plus deux taux dont la définition est écrite dans la sortie
  elle-même.

Un test vérifie que le compteur sait condamner : sur le corpus réel, un
détecteur fictif qui déclarerait tout produit plus de cent faux positifs et
zéro image parfaite.

---

## 2. Le corpus

42 entrées synthétiques déterministes (`corpus/catalogue.py`, graine unique),
dont 39 gradées. Chaque entrée déclare ce qu'on lui a **imposé** — sigma de
flou, gain d'exposition, coefficient `k1` — et ce qu'on attend que l'analyse en
dise.

**Les attentes viennent de la transformation, jamais de la sortie du système.**
Un gain de 0,20 retire plus de deux diaphragmes : la photo est sous-exposée,
que le détecteur le voie ou non. Écrire l'attente d'après ce que le code
répond aujourd'hui ferait du banc d'essai un miroir. Conséquence assumée :
quand le système contredit une attente, c'est un **faux négatif à rapporter**.

Trois entrées ont vu leur étiquette corrigée en cours de lot, et il faut être
précis sur le motif : elles étaient **fausses sur l'image**, pas trop sévères
pour le code. Un champ de lignes est un fond uniforme sur 97 % de sa surface —
son contraste relatif mesuré vaut 0,054 à 0,060 contre 0,34 pour une scène
texturée ; le déclarer « sans défaut » était une erreur de ma part. Chaque
correction porte sa mesure dans la note de l'entrée.

Sept entrées sont **non gradées** (`graded=False`) : leur bonne réponse est
discutable — un flou de sigma 0,8, une pièce à moitié dans l'ombre. Les grader
serait inventer une vérité ; les exclure du corpus serait ne jamais regarder la
zone grise. Elles sont mesurées et rapportées, hors comptage.

### Ce que ce corpus ne prouve pas

Aucune de ces images n'est une photographie : pas de vignettage, pas
d'aberration chromatique, pas de bruit de capteur corrélé, pas de compression
JPEG agressive, **pas de vraie pièce**. Une distorsion polynomiale parfaite dit
si un détecteur voit ce qui est indiscutablement là ; elle ne dit pas s'il
marchera sur un téléphone. Le corpus réel est vide — voir §7.

---

## 3. Netteté : trois candidates

Le point méthodologique du lot : **une image pauvre en détail n'est pas une
image floue**. Un mur lisse net et le même mur flouté contiennent tous deux
très peu de haute fréquence, et pour toute mesure fondée sur les dérivées ils
sont réellement indiscernables. La réponse n'est pas une mesure plus fine mais
**une mesure de plus** : le *support* (`strong_gradient_ratio`) décide s'il y a
de quoi conclure, avant toute netteté.

| candidate | mesure | FP | FN |
| --- | --- | --- | --- |
| A `laplacian_variance` | variance de la dérivée seconde (LOT 0) | **18** | 2 |
| B `reblur_ratio` | part de variation que le reflou ne change plus | **0** | **0** |
| C `edge_width` | largeur médiane des transitions, en pixels | 0 | 2 |

**A est disqualifiée par un chiffre**, pas par un avis : sa marge de séparation
est **négative** (−817), les groupes se chevauchent, et aucun seuil ne peut les
séparer. Elle produit 18 faux positifs, dont un `image_blurry` sur chacune des
sept scènes architecturales nettes et sur le mur lisse. C'est exactement le
défaut annoncé, mesuré.

**B est retenue.** Séparation 0,142, bornes mesurées : nets ≤ 0,3583,
flous ≥ 0,4778.

### Le choix a basculé deux fois

C'est désagréable à lire et c'est le fonctionnement normal d'un banc d'essai :
une comparaison ne vaut que sur les cas qu'elle contient.

1. sur un premier échantillon de quinze cas, B et C se valaient ;
2. le corpus complet a fait gagner **C** : les images rééchantillonnées par une
   distorsion sont réellement adoucies par l'interpolation, et B les plaçait à
   cheval sur sa borne (0,354 à 0,462) là où C les laissait toutes à 6,0 px ;
3. l'ajout du **bougé aligné sur un axe** a fait gagner **B**, définitivement.
   La marge de C y devient négative : ces images tombent à 8,0 px, dans
   l'intervalle des images nettes.

B et C ont longtemps été à égalité de nombre d'erreurs ; c'est leur **nature**
qui a tranché. La faiblesse de B est une instabilité sur un motif de traits
fins isolés sur fond uni — le rapport passe de 0,000 à 0,687 par le seul effet
du rééchantillonnage. Une pièce réelle ne ressemble pas à cela. La faiblesse de
C est de déclarer **nette, avec assurance**, une image franchement bougée
horizontalement, ce qu'une photo prise à main levée produit couramment. Entre
une faiblesse qui ne se rencontre que sur un motif de test et une faiblesse qui
se rencontre en vrai, le choix se fait tout seul.

### Deux bornes, pas un seuil

Chaque candidate a une borne « net » et une borne « flou », posées **sur les
bords des groupes mesurés** et non au milieu de la marge. Entre les deux, la
netteté est déclarée **indéterminée**. Un seuil unique au centre d'une marge
étroite trancherait des cas que la mesure ne sépare pas, avec l'assurance d'un
booléen.

Sur ce corpus, la bande capture les images rééchantillonnées par une
distorsion : réellement un peu adoucies, pas floues. C'est exactement ce pour
quoi elle existe — et cela évite d'annoncer un flou à chaque photo distordue.

`sharp` vaut donc `null` dans **trois** cas distincts, et aucun ne veut dire
« floue » : support insuffisant, mesure dans la bande, ou image hors du
domaine de résolution étalonné (§6).

### Deux corrections trouvées en mesurant

* **le bruit** fabrique des transitions d'un ou deux pixels, donc très
  « nettes », et en nombre elles tiraient la mesure vers le net : une image
  floutée à sigma 4 puis bruitée à 6/255 donnait 0,475, soit « nette ». Un
  médian 3×3 préalable la ramène à 0,635. Un médian et non un gaussien : il
  retire le bruit sans étaler les arêtes, donc sans fabriquer le flou qu'on
  mesure ;
* la conversion vers `uint8` **tronquait** au lieu d'arrondir, ce qui biaise
  chaque valeur d'un demi-niveau vers le bas. Sur un aplat dont la luma tombe
  juste sous un entier, la troncature n'arrondit pas tous les pixels du même
  côté et fabriquait un tramage de ±1/255 — donc des « arêtes » de 4 px de
  large sur une image parfaitement uniforme.

---

## 4. Exposition et contraste

Les métriques restent **continues**, et l'avertissement large. Une scène
naturellement sombre et une photo sous-exposée ont la même luminance moyenne ;
les distinguer demanderait de savoir ce que la scène *devrait* valoir, ce
qu'aucune mesure d'une image seule ne sait. Le lot ne prétend pas trancher.

Deux corrections mesurées :

**Le contraste devient relatif.** L'écart-type de luminance est proportionnel à
la luminance : une photo sombre l'a mécaniquement bas. Le LOT 0 émettait donc
`image_low_contrast` sur *toute* image sous-exposée, en plus de
`image_too_dark` — deux avertissements pour un seul défaut, dont un faux. Le
rapport écart-type / moyenne est sans dimension et invariant : la même scène
texturée donne 0,34 en pleine lumière et 0,35 après un gain de 0,20, tandis
qu'une scène réellement plate donne 0,071. Facteur cinq entre les deux groupes.
`contrast_std` reste publié comme mesure, il n'est plus un critère.

**L'écrêtage est séparé de la clarté.** Une photo claire se rattrape ; une
photo dont les hautes lumières sont écrêtées a perdu l'information,
définitivement. `clipped_high_ratio` / `clipped_low_ratio` comptent les pixels
au blanc et au noir absolus, et portent le seul jugement solide qu'on puisse
faire sans connaître la scène.

Le cas `half-shadow-0.25` — moitié de l'image dans l'ombre franche, moitié
correcte, une pièce à une seule fenêtre — est délibérément **non gradé**. Sa
luminance moyenne est basse sans que la photo soit perdue, et rien dans l'image
seule ne permet de trancher. Il est là pour être observé.

---

## 5. Distorsion : trois candidates, vérité terrain exacte

Le générateur applique une distorsion radiale de coefficient **connu**, ce qui
permet de mesurer non seulement la détection mais le **sens** et
l'**intensité**. Convention vérifiée sur les pixels et non par raisonnement :
`k1 > 0` = barillet, `k1 < 0` = coussinet, `r` normalisé par la demi-diagonale.

| candidate | discriminant | résultat |
| --- | --- | --- |
| A `sagitta_magnitude` | amplitude de la flèche (LOT 0) | faux positif sur une texture sans droite |
| B `radial_consistency` | accord de **signe** entre arêtes | correct sur tout le corpus |
| C `k1_fit` | **retenue** — `k1` qui redresse le mieux | correct, plus sens et intensité |

Résultats de la méthode retenue sur les cas gradés à vérité terrain connue :

* **8 / 8** distorsions détectées (k1 de ±0,05 à ±0,30) ;
* **0 / 7** fausses alarmes sur les images non distordues ;
* **8 / 8** sens corrects ;
* erreur d'intensité |k1| : **moyenne 0,011, maximum 0,085**. Sur les sept cas
  centrés, l'erreur est **nulle** — le balayage retrouve le coefficient imposé
  exactement. Le maximum vient du seul cas recadré (§6).

### Ce que la candidate A ne pouvait pas faire

Une amplitude ne dit pas **d'où** vient la courbure. Le LOT 0 mesurait
`|a| · L² / 4`, non signée : sur un damier, des dizaines d'arêtes bombent un
peu dans tous les sens et la mesure ne voit que « ça bombe ». Une distorsion
radiale, elle, est **cohérente** : toutes les droites s'écartent du centre, ou
s'en rapprochent, sans exception. Garder le signe *relativement au centre*
rend cette cohérence mesurable, et c'est elle — pas l'amplitude — qui sépare un
objectif fautif d'un carrelage.

`k1_fit` va plus loin : le coefficient est ajusté sur **tous les tracés à la
fois**. Si les courbures ne sont pas compatibles avec une distorsion radiale,
aucun `k1` unique ne les redresse et `residual_gain` reste bas. Le test de
cohérence est intégré à l'estimation, et il porte sur les amplitudes autant que
sur les signes — une arête proche du centre doit bomber moins qu'une arête au
bord, dans un rapport que le modèle impose. Mesuré : gain de 0,000 sur une
scène rectilinéaire, 0,913 à 0,986 sur les scènes distordues.

### Deux bugs de suivi d'arêtes corrigés

**Le traqueur était aveugle aux distorsions fortes.** Au-delà de |k1| = 0,15 il
ne trouvait plus **aucune** arête exploitable et répondait « indéterminé » — un
faux négatif déguisé en prudence. Cause : il partait du haut du cadre, alors
que l'amorce est choisie sur l'énergie de gradient de toute une colonne, ce qui
pour une arête **courbée** désigne l'endroit où elle traverse cette colonne,
donc son milieu. Il partait donc à côté de l'arête, ne trouvait que du bruit
dans sa fenêtre, et abandonnait dès la première ligne. Il part maintenant de la
ligne la plus franche et s'étend **des deux côtés**.

**Le support était surévalué sur un mur vide.** Le traqueur suivait les
**marches de quantification** d'un dégradé lisse et rapportait onze arêtes
« utilisables » là où il n'y a rien à voir. Le verdict restait juste — ces
fausses arêtes ne bombent pas — mais le support est précisément ce sur quoi
reposera la confiance du LOT 7. Un contraste minimal par tracé (médiane de
|gradient| ≥ 0,05) les élimine : une marche de quantification répond vers
0,016, une arête franche vers 1,4, la même arête floutée à sigma 6 encore 0,09.

### Les arêtes horizontales comptent autant

Le LOT 0 ne suivait que les verticales, ce qui n'échantillonne qu'un axe et
rend aveugle aux photos dont les seules longues droites sont les plinthes et
les corniches — beaucoup de photos d'intérieur. Le suivi est écrit une fois et
appliqué à l'image **transposée** : transposer est exact, sans interpolation,
donc sans courbure introduite par le traitement.

### Sémantique des verdicts

`no_distortion_detected` devient **`no_distortion_evidence`**. Le changement
n'est pas cosmétique : « rien détecté » se lit comme « l'objectif est sain »,
alors que la mesure ne dit que « les arêtes que j'ai su mesurer sont droites ».
Une photo peut n'offrir que des arêtes proches du centre optique — là où la
distorsion radiale ne déplace rien — et être franchement distordue aux bords.

Les trois verdicts sont `undetermined`, `no_distortion_evidence`,
`distortion_suspected`. Une règle vaut pour les trois candidates : **sans
support suffisant, on ne conclut pas.** Aucun détecteur n'a le droit de
répondre « pas de distorsion » sur une image où il n'a rien pu mesurer.

Sur les 42 entrées, 13 reçoivent `undetermined` — mur lisse, aplats, lignes
courtes, lignes interrompues, damier, courbes réelles. C'est le verdict le plus
fréquent, et c'est normal : la plupart des images ne portent pas de quoi juger
un objectif.

### Support exposé

`LensSupport` publie le nombre d'arêtes retenues, leur répartition
vertical/horizontal, la longueur totale de tracé, la **couverture spatiale**
(quadrants touchés), l'**accord de signe** et la flèche médiane signée. Un
verdict ne doit jamais être un score opaque. Ce bloc alimentera la confiance du
LOT 7 ; ici il sert déjà à comprendre *pourquoi* une réponse est indéterminée.

---

## 6. Ce qui ne marche pas

Quatre limites mesurées. Aucune n'est corrigée dans ce lot, et c'est
volontaire : les corriger en ajoutant des métriques choisies pour ces cas
précis serait calibrer sur des fixtures.

**1. Bougé aligné sur un axe, candidate C.** Non détecté. Sur une texture
dense, un noyau en créneau transforme les arêtes voisines en ondulations
rapprochées et la largeur médiane reste celle d'une image nette (8 px). Le
gradient de crête chute pourtant de 1,55 à 0,37 : le signal existe, cette
mesure-là ne le lit pas. La candidate retenue (B) n'a pas ce défaut ; deux
entrées du corpus et un test l'épinglent pour qui voudrait repasser à C.

**2. Recadrage décentré : intensité biaisée.** L'estimation suppose le centre
optique **au centre du cadre**. Sur une photo recadrée hors axe, `k1` mesuré
vaut 0,115 au lieu de 0,20 — 43 % d'erreur — avec le bon sens et une détection
correcte. Estimer le centre en même temps que `k1` demanderait un support bien
supérieur à ce qu'offre une photo d'intérieur ordinaire.

**3. Domaine de résolution de la netteté.** Les bornes sont mesurées sur des
images ramenées à `blur_working_side` (1024 px). En dessous, l'image n'est pas
réduite — agrandir fabriquerait du flou d'interpolation — et la mesure change
d'échelle. Le verdict est donc `null` sous cette taille. **Lacune assumée** :
les photos entre `min_long_side` (640 px) et 1024 px ne reçoivent aucun verdict
de netteté. Un étalonnage à 640 px a été essayé et rejeté : la marge y tombe à
0,077 contre 0,167.

**4. Instabilité de B sur les motifs de traits fins.** Le rapport de reflou
passe de 0,000 à 0,687 sur un champ de traits de 4 px par le seul effet du
rééchantillonnage — soit autant qu'un flou gaussien de sigma 3. Testé avec les
trois interpolations d'OpenCV (0,687 / 0,737 / 0,727) : aucune ne préserve des
traits si fins. L'entrée concernée porte donc l'étiquette `image_blurry`,
puisque l'image est réellement adoucie. Une pièce réelle n'a pas de traits de
4 px isolés sur fond uni.

### Et ce qu'un corpus propre ne prouve pas

Le tableau final affiche 0 faux positif et 0 faux négatif. **Cela ne prouve pas
que les détecteurs sont bons** — cela prouve qu'ils passent *ce* corpus, qui
est synthétique et que j'ai écrit. Les quatre limites ci-dessus sont les
résultats du lot autant que la matrice.

---

## 7. Corpus réel : blocage documenté

`datasets/manifest.json` est **vide**, et le rester est un choix.

Les scènes du front (`pose-parquet.com/data/scenes/`) sont des photos Pexels,
créditées scène par scène. Elles sont utilisables et constitueraient un bon
point de départ — `docs/dataset.md` en donne la correspondance avec les quatre
bacs de difficulté. Deux raisons de ne pas les avoir importées :

1. **la licence doit être reportée, pas supposée.** Chaque photo a un auteur
   nommé dans le manifeste du front. Copier les fichiers en recopiant
   mécaniquement les crédits est faisable, mais vérifier que la licence Pexels
   couvre cet usage-ci — corpus d'évaluation d'un service, redistribué avec le
   dépôt — est une décision qui n'est pas technique ;
2. **aucune vérité terrain ne serait disponible.** Sur une photo réelle, le
   `k1` est inconnu, le sigma de flou est inconnu, et l'exposition « correcte »
   est un jugement. On ne pourrait mesurer que des faux positifs — utile, mais
   à ne pas confondre avec ce que mesure le corpus synthétique.

**Ce que ce blocage empêche :** aucun des seuils de ce lot n'est validé sur
photo réelle. Ils sont tous établis sur des dégradations parfaites, et ils sont
**attendus comme révisés**.

Voir `datasets/README.md` pour la procédure d'ajout.

---

## 8. Performance, sur CPU

Mesurée sur les 42 entrées, en millisecondes :

| étape | moyenne | maximum |
| --- | --- | --- |
| `load_image` | 23 | 44 |
| `quality_analysis` | 61 | 93 |
| `lens_analysis` | 109 | 259 |
| **total** | **190** | **358** |

L'analyse d'objectif est l'étage le plus coûteux, l'essentiel venant du
balayage de 181 valeurs de `k1`. Aucune optimisation n'a été faite : à 190 ms
en moyenne le budget est large, et le lot avait mieux à prouver que sa vitesse.
Une descente locale remplacerait le balayage si besoin — au prix du risque de
minimum local, ce qui est cher payé pour gagner cent millisecondes.

---

## 9. Réglages et traçabilité

Tous les seuils sont dans `app/core/config.py`, surchargeables par variable
d'environnement préfixée `PPAI_`. `Settings.ALGORITHM_FIELDS` liste les trente
réglages qui changent un **résultat**, par opposition à ceux qui changent
l'environnement, et `algorithm_config()` en produit l'instantané que tout
rapport embarque.

La liste est explicite plutôt que déduite du modèle : c'est un peu de
redondance contre un vrai risque, celui d'un réglage ajouté puis oublié, qui
influencerait les mesures sans laisser de trace dans les rapports.

Deux réglages choisissent la méthode active — `blur_method`, `lens_method` — et
**toutes les mesures sont calculées quelle que soit la méthode choisie**. Un
rapport porte donc de quoi rejouer les trois candidates sans réanalyser le
corpus.

---

## 10. Ce que le lot n'a pas commencé

Ni segmentation du sol, ni profondeur, ni perspective, ni occlusions, ni
`SceneData`. `scene_builder.build_scene_data()` renvoie toujours `None`,
`confidence` reste `null`, et `MISSING_STAGES` est inchangé. Aucun modèle lourd
n'est installé — ni PyTorch, ni ONNX, ni poids.

`ANALYSIS_SCHEMA` passe à `pose-parquet/analysis@2` : `lens.verdict` renomme sa
valeur négative, `quality.blur.sharp` devient nullable, et les blocs de mesure
s'étoffent. Le front n'est pas branché (LOT 8), donc aucun consommateur n'est
cassé — mais la version bouge quand même, parce que c'est le seul signal qu'un
client aurait pu lire.
