# Le corpus, et pourquoi il vient avant les modèles

`datasets/README.md` dit **comment** ajouter une photo. Ce document dit
**quoi** ajouter, et pourquoi.

---

## Le test qui compte est déjà écrit

Les scènes calibrées à la main du front sont la vérité terrain géométrique du
projet. Le critère de réussite d'un modèle de segmentation n'est donc pas
« segmente-t-il bien » mais, selon les termes du front :

> l'IoU entre le masque produit et le masque calibré à la main dépasse-t-il
> 0,92, et le quadrilatère de plan est-il à moins de 2 % de celui calibré ?

C'est mesurable, et c'était écrit avant le code. Le LOT 2 n'aura pas à
inventer son critère de succès — seulement à l'implémenter contre ces
fixtures.

Aucun de ces masques n'a encore été importé ici, et c'est volontaire : les
importer demande de convertir des polygones normalisés en masques PNG, ce qui
est un travail du LOT 2, pas une case à cocher au LOT 0. Le format d'accueil
existe (`groundTruth` dans le manifeste) ; il est vide et déclaré vide.

---

## Ce que le front a déjà appris, scène par scène

Le manifeste du front (`data/scenes/index.json`) porte deux statuts par scène
— `geometryStatus` et `visualStatus` — parce qu'**une scène peut être juste et
laide**. Trois scènes étaient déclarées valides sur la seule foi de leur
géométrie et ne l'étaient pas au rendu. Aucun chiffre géométrique ne dit
cela : il faut regarder.

Ces jugements sont de l'information gratuite pour notre corpus. Chaque échec
documenté est un cas de test dont on connaît déjà la difficulté **et sa
raison**.

| scène du front       | difficulté visée | ce qu'elle éprouve                                                        |
| -------------------- | ---------------- | ------------------------------------------------------------------------- |
| `sejour`             | `easy`           | deux pièces en enfilade, un seul parquet — continuité par `planeRef`      |
| `chambre`            | `easy`           | lumière franche, perspective profonde                                     |
| `bureau-vide`        | `easy`           | vue d'angle, deux plinthes mesurées, sol dégagé                           |
| `chambre-parisienne` | `easy`           | sol entièrement dégagé                                                    |
| `cuisine-ouverte`    | `easy`           | grand sol dégagé, plinthes blanches sur lames foncées                     |
| `piece-claire`       | `medium`         | meuble et radiateur devant le sol ; masque qui monte sur le mur           |
| `appartement-ancien` | `medium`         | couloir profond, meubles à pieds fins ; une bande de sol non couverte     |
| `petite-piece`       | `hard`           | frontière du sol non vérifiable (`boundary-not-verifiable`)               |
| `couloir`            | `hard`           | **bois clair sur bois clair** : la jonction mur/sol n'offre presque aucune marche |
| `salon`              | `hard`           | quatre sols à travers trois ouvertures, parquet foncé très réfléchissant  |
| `contraste`          | `rejected`       | ce n'est pas une pièce : un mur, un rai de soleil, une lisière de sol     |

Ces photos viennent de Pexels et sont créditées scène par scène dans le front.
Les réutiliser ici demande de **reporter le crédit et la licence** dans notre
manifeste — c'est précisément ce que le champ `credit` sert à ne pas oublier.
Aucune n'a été copiée automatiquement.

### Les deux cas les plus instructifs

**`couloir`** a d'abord été rejetée pour « distorsion en barillet ». C'était
faux, et l'erreur est plus intéressante que la scène : le traqueur suivait le
**minimum de luminance**, a glissé sur le bois sombre d'une porte, et a mesuré
sa propre dérive — un arc de +3,1 / −4,0 / +4,0 px, avec 79 points et un
résidu moyen de 2,8 px. Tous les indicateurs semblaient bons. Le même jambage
suivi par le **maximum de gradient** donne une flèche de 0,13 px pour un
écart-type de 0,21 px sur 99 points : c'est une droite.

La vraie difficulté de `couloir` est ailleurs : bois clair sur bois clair, la
jonction mur/sol n'a presque pas de marche de teinte. Le relevé automatique y
échoue franchement — résidus de 46 et 61 px sur huit colonnes. C'est le cas
type de ce que « importer ma pièce » va recevoir en quantité.

**`contraste`** est géométriquement juste et parfaite pour éprouver le report
de lumière, mais ce n'est pas une pièce. Elle appartient donc au bac
`rejected` : non parce qu'elle est mauvaise, mais parce que le comportement
attendu est un refus.

---

## Les six défauts à couvrir

Ils ne sont pas devinés : ce sont ceux que le Visualiseur a réellement
rencontrés.

| défaut                      | code machine                  | pourquoi ça casse                                     |
| --------------------------- | ----------------------------- | ----------------------------------------------------- |
| faible contraste mur/sol    | `wall_floor_contrast_low`     | aucune marche à relever, donc pas de frontière        |
| coins occultés              | `wall_intersection_occluded`  | pas de second point de fuite                          |
| grand-angle                 | `lens_distortion_suspected`   | les droites courbent : la perspective n'est plus projective |
| perspective peu observable  | `perspective_uncertain`       | une seule direction, donc pas de quadrilatère prouvé  |
| recadrage                   | `lens_analysis_undetermined`  | le centre optique n'est plus le centre de l'image     |
| meubles devant les plinthes | `occlusion_complex`           | la frontière est masquée là où on veut la mesurer     |

Les codes sont ceux de `app/core/warnings.py`. Ceux des LOT 2 à 5 sont déjà
déclarés, jamais encore émis : le vocabulaire est fixé avant d'être produit,
pour que le front puisse être écrit contre la liste complète.

---

## Cible de composition

Une trentaine de photos suffisent pour commencer à discriminer des modèles —
et une trentaine bien choisies valent mieux que trois cents ramassées.

| bac        | cible | ce qu'on y cherche                                          |
| ---------- | ----- | ----------------------------------------------------------- |
| `easy`     | ~10   | la référence : si un modèle échoue ici, il est hors course  |
| `medium`   | ~10   | le cas courant, celui qui décidera du modèle retenu         |
| `hard`     | ~8    | les six défauts ci-dessus, au moins un exemplaire chacun    |
| `rejected` | ~5    | vérifier que le service sait dire non                       |

Deux règles de sélection :

**Pas de photo sans licence claire.** Une photo sans provenance ne peut pas
être partagée, donc pas servir de référence commune, donc ne sert à rien.

**Pas de photo dont on ne sait pas dire ce qu'elle éprouve.** Si
`expectedIssues` est vide et que la photo n'est pas dans `easy`, elle
n'apporte rien qu'une autre n'apporte déjà — et un corpus qui grossit sans
gagner en couverture coûte du temps de benchmark à chaque itération.

---

## Ce que le benchmark mesure aujourd'hui

Voir `benchmarks/README.md`. La colonne à lire en premier est
`missed_issues` : ce que le corpus annonçait et que l'analyse n'a pas vu. Elle
mesure un manque, pas une durée — et c'est un manque qui coûte cher, puisque
le service aura promis un résultat sûr sur une photo qui ne l'était pas.
