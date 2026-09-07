# Distorsion optique : ce qu'on mesure, ce qu'on ne corrige pas

**État : mesure implémentée, aucune correction.** Le service constate et
rapporte. `LensMetrics.correction_applied` est un `Literal[False]` — il ne peut
pas devenir vrai par accident.

Le LOT 1 a mis trois détecteurs en concurrence sur un corpus à coefficient
imposé, et retenu `k1_fit` : il estime le **sens** et l'**intensité**, et son
test de cohérence est intégré à l'estimation. Résultats chiffrés et échecs :
`docs/quality-methodology.md`.

Ce document résume ce que le front a établi dans
`pose-parquet.com/docs/photo-lens-distortion.md`, et dit ce que
`app/services/lens_analysis.py` en fait.

---

## Deux choses qu'on confond souvent

**La perspective** est projective : des parallèles convergent vers un point de
fuite, une lame de 18 cm paraît plus petite au fond. C'est exactement ce que
`SceneData` sait décrire — une homographie envoie le carré unité sur le
quadrilatère du sol, et tout suit. Propriété clé : **la perspective conserve
les droites.**

**La distorsion optique** est ce que fait la lentille. Elle déplace chaque
point le long du rayon qui le joint au centre optique, d'une quantité qui
croît avec la distance à ce centre. Signature inverse : **elle courbe les
droites**, d'autant plus qu'elles passent loin du centre. Sur l'axe optique,
elle ne courbe rien.

## Pourquoi ça compte

`SceneData` décrit une caméra sténopé : un horizon, une focale, des points de
fuite. **Aucun coefficient de distorsion.** Et toutes les mesures de calibrage
supposent que les droites du monde sont droites dans l'image :

* ajuster une droite sur un pied de mur ;
* croiser deux droites pour obtenir un point de fuite ;
* imposer le quatrième coin d'un quadrilatère par la perspective ;
* déduire la focale de l'orthogonalité de deux directions.

Sur une image distordue, ces quatre opérations donnent des résultats qui
**dépendent de l'endroit du cadre où on les fait**. Deux relevés de la même
direction, l'un au centre l'autre au bord, donnent deux points de fuite
différents ; il n'existe alors aucun horizon compatible avec les deux, et la
scène n'est pas représentable — pas approximativement : franchement pas.

C'est le cas qui attend « importer ma pièce ». Les téléphones photographient
volontiers en ultra grand-angle pour faire tenir une pièce dans le cadre.
Certains corrigent en interne, d'autres non, et **rien dans le fichier ne le
dit de façon fiable.**

---

## La mesure : la flèche d'arc

On prend une arête droite du monde réel, on la suit dans l'image, et on
regarde si elle est droite.

`analyse_lens()` renvoie, par arête suivie :

| champ              | sens                                                       |
| ------------------ | ---------------------------------------------------------- |
| `orientation`      | `vertical` ou `horizontal` — les deux sont suivies         |
| `sagitta_px`       | écart de la parabole à sa corde, au milieu, non signé      |
| `radial_bulge_px`  | le même, **signé** : positif = s'écarte du centre = barillet |
| `fit_rms_px`       | écart-type d'ajustement de la parabole, en px              |
| `points`           | nombre de points du tracé                                   |
| `span_ratio`       | part de l'axe balayé que le tracé couvre                    |
| `center_offset`    | éloignement du centre optique (0 = sur l'axe, 1 = au bord)  |
| `usable`           | retenu comme preuve                                         |

Pour une parabole ajustée sur une base `L`, la flèche vaut `|a| · L² / 4`. Le
bombement croît donc **comme le carré de la longueur** — d'où l'importance de
`span_ratio`.

`radial_bulge_px` est l'ajout du LOT 1, et c'est lui qui change tout. Le LOT 0
ne mesurait qu'une amplitude, et une amplitude ne dit pas **d'où** vient la
courbure : sur un damier, des dizaines d'arêtes bombent un peu dans tous les
sens et la mesure ne voit que « ça bombe ». Une distorsion radiale, elle, est
cohérente — toutes les droites s'écartent du centre, ou s'en rapprochent, sans
exception. Garder le signe *relativement au centre* rend cette cohérence
mesurable.

`LensSupport` agrège cette information : nombre d'arêtes retenues, répartition
vertical/horizontal, longueur totale de tracé, couverture spatiale en
quadrants, **accord de signe**, flèche médiane signée. Un verdict ne doit
jamais être un score opaque.

### Quatre pièges, et comment le code les évite

**1. Suivre la mauvaise grandeur.** Un traqueur doit suivre *ce qui définit
l'arête*. Le front a d'abord suivi le **minimum de luminance** : sur un
jambage clair contre un mur clair, il n'y a pas de minimum. Le traqueur a
glissé sur le bois sombre de la porte et a mesuré **sa propre dérive** — un arc
de +3,1 / −4,0 / +4,0 px, sur 79 points, avec un résidu moyen de 2,8 px. Tout
avait l'air bon. Le même jambage suivi par le **maximum de gradient** donne
0,13 px de flèche pour un écart-type de 0,21 px sur 99 points : une droite.

> Se tromper de grandeur ne donne pas un résultat bruité. Il donne un résultat
> **faux et d'allure crédible**, ce qui est bien pire.

Le code suit le gradient, jamais la luminance.

**2. Sauter sur l'arête d'en face.** Un jambage a deux arêtes à quelques
pixels l'une de l'autre, et elles sont de **sens opposés** : clair → sombre
d'un côté, sombre → clair de l'autre. Un traqueur qui ne regarde que la
magnitude passe de l'une à l'autre dès que le contraste varie, et mesure alors
la largeur du jambage plutôt que sa courbure. Le code fixe la **polarité** au
départ et ne suit que les transitions de même sens ; l'arête opposée répond
négativement et ne peut jamais remporter l'argmax.

La polarité est lue **là où la transition est la plus franche**, pas en moyenne
sur la colonne : une arête qui dérive fait entrer les deux côtés du jambage
dans la même colonne, et leur somme s'annule au lieu de trancher.

**3. Lire la flèche sans l'écart-type.** `sagitta_px` seule ne veut rien dire :
c'est `fit_rms_px` qui dit si la parabole **décrit** le tracé. Les deux
voyagent ensemble dans `EdgeTrack`, et un tracé mal ajusté est écarté avant
tout verdict.

**4. Retenir des tracés courts.** Trouvé par notre propre banc d'essai : un
damier synthétique produisait `distortion_suspected`. Un motif répétitif —
carrelage, rayures, étagères — fournit des dizaines de petits segments
verticaux dont la flèche n'est que du bruit d'ajustement ; en nombre, elle
franchit n'importe quel seuil. D'où `lens_min_track_height_ratio` (25 % de la
hauteur par défaut).

### Deux règles de placement

**Choisir l'arête loin du centre.** La distorsion radiale ne déplace rien sur
l'axe optique : une verticale au milieu du cadre reste droite quelle que soit
la force de la distorsion. Les colonnes candidates sont pondérées par leur
éloignement du centre, et la bande centrale (25 %) est exclue.

**La prendre la plus longue possible.** Voir le piège 4.

### La résolution compte

La flèche est en pixels, donc proportionnelle à la taille de l'image. Le seuil
`lens_sagitta_suspect_px` (3 px) vaut pour `lens_reference_width` (1600 px) et
est mis à l'échelle de l'image réellement analysée. `max_sagitta_px_normalized`
ramène la mesure à la largeur de référence, pour comparer deux photos de
résolutions différentes.

Le front s'est fait piéger là aussi : son outil de calibrage chargeait l'image
réduite à 1100 px quand la fenêtre en faisait moins de 600. La résolution de
travail dépendait de la taille de la fenêtre, et un résidu de 8 px ne voulait
pas dire la même chose d'une session à l'autre.

---

## Le verdict, et sa prudence

| verdict                  | condition                                                       |
| ------------------------ | --------------------------------------------------------------- |
| `undetermined`           | moins de 2 arêtes exploitables                                  |
| `distortion_suspected`   | \|k1\| estimé ≥ seuil **et** gain de rectitude ≥ seuil          |
| `no_distortion_evidence` | assez d'arêtes, et aucun k1 ne les redresse significativement   |

`undetermined` est le cas **le plus fréquent** sur une photo d'intérieur
ordinaire, et c'est le seul honnête quand c'est vrai. Une arête unique ne
prouve rien. Sur le corpus synthétique, 13 des 42 entrées le reçoivent.

Le verdict négatif s'appelle **`no_distortion_evidence`** et non
`no_distortion_detected`, et le changement n'est pas cosmétique. « Rien
détecté » se lit comme « l'objectif est sain », alors que la mesure ne dit que
« les arêtes que j'ai su mesurer sont droites ». Une photo peut n'offrir que
des arêtes proches du centre optique — là où la distorsion radiale ne déplace
rien — et être franchement distordue aux bords. L'absence de preuve n'est pas
une preuve d'absence, et le nom du verdict doit le dire.

Une règle vaut pour les trois détecteurs : **sans support suffisant, on ne
conclut pas.** Aucun n'a le droit de répondre « pas de distorsion » sur une
image où il n'a rien pu mesurer.

---

## Ce qu'il faudrait faire, le jour où

La correction doit venir **avant** tout relevé, jamais après : une fois les
points de fuite calculés sur une image distordue, l'erreur est entrée dans
toutes les valeurs et plus rien ne la sépare du reste.

```
PHOTO → correction de distorsion → analyse géométrique → SceneData
```

Trois pistes, de la plus simple à la plus lourde :

1. **Refuser la photo.** Mesurer la flèche à l'import et expliquer que cette
   photo ne convient pas, en suggérant de reculer plutôt que d'élargir. Peu
   satisfaisant, mais honnête et immédiat.
2. **Estimer un coefficient radial depuis l'image.** ✅ **Fait au LOT 1** —
   pour l'estimation, pas pour la correction. `estimate_k1` cherche par
   balayage le `k₁` qui rend les tracés observés le plus droits possible.
   Mesuré sur vérité terrain imposée : le coefficient est retrouvé
   **exactement** sur les sept cas centrés, avec le bon sens dans les huit
   cas. Corriger l'image avec ce coefficient reste une autre décision, et
   elle n'est pas prise.
3. **Lire les métadonnées.** Marque, modèle et focale suffisent parfois à
   retrouver un profil d'objectif publié. Pratique quand ça marche, muet quand
   les métadonnées ont été retirées — ce que fait tout hébergeur d'images.

### La limite qui empêche d'aller plus loin

L'estimation suppose le **centre optique au centre du cadre**. C'est une
hypothèse, pas une mesure, et elle tombe sur une photo recadrée : mesuré sur le
corpus, `k1` vaut 0,115 au lieu de 0,20 sur un recadrage hors axe — 43 %
d'erreur, avec le bon sens et une détection correcte. Corriger une image avec
un coefficient faux de 43 % serait exactement ce que l'en-tête de ce document
interdit. Estimer le centre en même temps que `k1` demanderait un support bien
supérieur à ce qu'offre une photo d'intérieur ordinaire.

Dans les trois cas, `SceneData` gagnerait un bloc `lens` : coefficients,
centre optique, et **la mention de leur provenance** — mesurée, lue, ou
supposée. La distinction court dans tout ce projet.

---

## Ordres de grandeur

Relevés par le front sur ses propres photos, à résolution native
(1600 × 1067) : une arête franche donne une flèche de **0,1 à 2 px** pour un
écart-type inférieur à 2. Au-delà de **3 px de flèche avec un écart-type
faible**, l'objectif déforme.

Sur notre corpus synthétique, scène architecturale en 1600 × 1067 :

| `k1` imposé | flèche signée médiane | `k1` estimé | gain de rectitude |
| ----------- | --------------------- | ----------- | ----------------- |
| 0,00        | ≈ 0 px                | +0,000      | 0,000             |
| +0,05       | +4,5 à +9,0 px        | +0,050      | 0,913             |
| +0,15       | +12 à +24 px          | +0,150      | 0,967             |
| +0,30       | +21 à +39 px          | +0,300      | 0,979             |
| −0,15       | −12 à −24 px          | −0,150      | 0,978             |

Damier, courbes réelles, lignes courtes, lignes interrompues, mur lisse :
0 arête retenue, verdict `undetermined`.

## Deux bugs de suivi corrigés au LOT 1

**Aveugle aux distorsions fortes.** Au-delà de |k1| = 0,15, le traqueur ne
trouvait plus **aucune** arête exploitable et répondait « indéterminé » — un
faux négatif déguisé en prudence. Il partait du haut du cadre, alors que
l'amorce est choisie sur l'énergie de gradient de toute une colonne, ce qui
pour une arête **courbée** désigne son milieu. Il partait donc à côté de
l'arête et abandonnait dès la première ligne. Il part maintenant de la ligne la
plus franche et s'étend des deux côtés.

**Support surévalué sur un mur vide.** Le traqueur suivait les marches de
quantification d'un dégradé lisse et rapportait onze arêtes « utilisables » là
où il n'y a rien à voir. Le verdict restait juste, mais le support est
précisément ce sur quoi reposera la confiance. Un contraste minimal par tracé
les élimine : une marche de quantification répond vers 0,016, une arête franche
vers 1,4, la même arête floutée à sigma 6 encore 0,09.

---

## Voir aussi

* `app/services/lens_analysis.py` — l'implémentation, commentée
* `tests/test_lens_analysis.py` — la vérité terrain synthétique
* `pose-parquet.com/docs/photo-lens-distortion.md` — l'analyse d'origine
* `pose-parquet.com/data/scenes/couloir.json` — la scène qui a servi de leçon
