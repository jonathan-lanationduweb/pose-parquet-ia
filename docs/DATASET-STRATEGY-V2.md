# Stratégie de jeu de données — V2

> **ACTIF.** Cible du corpus et de la vérité terrain pour l'architecture V2.
> Les règles de provenance, de licence et de confidentialité restent celles de
> [annotation-protocol.md §9-10](annotation-protocol.md) et de
> [datasets/README.md](../datasets/README.md) : ce document ne les réécrit pas,
> il dit **quelles images et quelles annotations il faut maintenant**.
> Ce qui existe aujourd'hui est chiffré en §1 et audité dans
> [AUDIT-V2.md](AUDIT-V2.md).

## 0. Inventaire vérifié — LOT B, 10 septembre 2026

Onze photos réelles, **regardées une par une** pour cette révision. Les traits
du manifeste ont été corrigés là où l'image contredisait la fiche.

| photo | difficulté | pièce | ce qu'elle apporte de particulier |
| --- | --- | --- | --- |
| `petite-piece` | hard | petit bureau | **huit pieds fins** (bureau chêne + chaise métal), bureau **chêne sur parquet chêne**, rideau au sol, contre-jour, angle masqué |
| `appartement-ancien` | hard | couloir en enfilade | perspective forte, console et portant à pieds fins, boiseries sur parquet, plusieurs pièces visibles |
| `couloir` | hard | couloir | bois clair sur bois clair **sans plinthe** : où finit le mur ? |
| `salon` | hard | séjour vide | sol foncé très réfléchissant, porte bois foncé, lambris blanc |
| `piece-arcades` | hard | grande pièce | arcades maçonnées, faible contraste mur/sol |
| `piece-claire` | medium | chambre/séjour | meuble bas sur **quatre pieds métalliques fins**, porte-fenêtre de balcon avec seuil, tache de soleil au sol |
| `chambre` | medium | grande chambre | terrasse vue par la porte-fenêtre, grille encastrée, contre-jour |
| `sejour` | easy | séjour + salle à manger | **deux pièces en enfilade sur un seul parquet**, reflets francs |
| `bureau-vide` | easy | bureau vide | seconde pièce visible avec un **sol différent**, seuil net |
| `entree-cadree` | easy | entrée | sol coupé par le cadre, carrelage et bois, porte bois |
| `contraste` | **rejected** | — | ombre portée franche sur sol foncé, mais ce n'est pas une pièce |

Corrections apportées au manifeste, sur constat visuel :

| photo | ce qui manquait |
| --- | --- |
| `piece-claire` | pieds fins et surface extérieure visibles, non déclarés |
| toutes | les sept traits ajoutés au vocabulaire (§2.6) là où ils s'appliquent |

## 1. Ce qui existe, chiffré

| grandeur | valeur réelle |
| --- | --- |
| photos réelles au manifeste | **11** (cible du corpus annoncée : 20 à 30) |
| photos redistribuables | **0** — toutes en `local_evaluation_only` |
| photos avec vérité terrain caméra ou objectif | **0 / 11** |
| photos meublées | **3 / 11** |
| photos contenant un tapis | **0** |
| fichiers d'annotation | **0** |
| masques PNG | **0** |
| campagne pilote : attendu / collecté / approuvé | **8 / 0 / 0** |
| paires d'accord humain mesurables | **0** |
| entrées du corpus synthétique | 44, dont 38 notées |
| candidats de segmentation enregistrés | 3, tous triviaux |
| scènes du jeu visuel de référence | **5** (4 difficiles, 1 facile) |
| cas du jeu de référence non couverts | **2** : tapis, meuble massif |

Lecture honnête de ce tableau : **l'instrumentation est complète et testée, la
donnée humaine est intégralement absente.** Ce n'est pas un retard de code.

Le corpus synthétique n'aide pas ici : il ne contient ni pièce, ni sol, ni
meuble. Il a été conçu pour la netteté et la distorsion, où il a servi, et il ne
dit rien de la segmentation.

## 2. Ce qu'il faut photographier

La cible produit ne se joue pas sur des pièces vides et bien éclairées. Le
corpus doit contenir ce qui casse le rendu.

### 2.1 Par type de pièce

séjour · chambre · cuisine · bureau · entrée · couloir · petite pièce ·
grande pièce ouverte.

### 2.2 Par sol existant — c'est la dimension la plus discriminante

| cas | pourquoi il compte |
| --- | --- |
| bois clair | risque de confusion avec un mur clair |
| bois foncé | contraste inverse, ombres écrasées |
| carrelage | joints réguliers, faux positifs de motif |
| béton, résine | absence de texture, frontière indécidable |
| stratifié | déjà proche de la cible, piège de « rien à faire » |
| tapis partiel | **le cas le plus coûteux** : il faut l'exclure sans exclure le sol autour |
| revêtement très proche du parquet cible | on ne verra pas si le rendu a eu lieu |

### 2.3 Par objets présents

canapé · table · chaises à pieds fins (**cas décisif**) · meuble bas · lit ·
tapis · rideau touchant le sol · radiateur · plante · objets posés au sol
(cartons, chaussures, jouets).

### 2.4 Par lumière

grande fenêtre latérale · faible lumière · contre-jour · ombres portées
marquées · sol réfléchissant.

### 2.5 Par géométrie

pièce rectangulaire simple · pièce avec ouverture sur une autre · pièce en L ·
couloir · plusieurs pièces visibles · perspective forte (grand angle proche).

### 2.6 Couverture réelle, cas par cas

Constatée sur les onze photos, sans indulgence.

| cas à couvrir | couvert ? | par quoi |
| --- | --- | --- |
| séjour **meublé** | **NON** | `sejour` et `salon` sont vides |
| chambre | partiellement | `chambre` est vide, `piece-claire` est meublée à peine |
| bureau | oui | `petite-piece` meublé, `bureau-vide` vide |
| entrée, couloir | oui | `entree-cadree`, `couloir`, `appartement-ancien` |
| petite pièce | oui | `petite-piece` |
| grande pièce | oui | `chambre`, `piece-arcades`, `salon`, `sejour` |
| **table et chaises** | **NON** | un seul bureau avec une seule chaise |
| plusieurs pieds fins | oui | `petite-piece` (8), `piece-claire` (4), `appartement-ancien` |
| **canapé, meuble massif** | **NON** | aucun canapé, aucun lit, aucun buffet |
| **tapis** | **NON** | zéro sur onze |
| ouverture vers une autre pièce | oui | `bureau-vide`, `sejour`, `appartement-ancien`, `couloir` |
| seuil | oui | `bureau-vide`, `entree-cadree`, `piece-claire` |
| lumière latérale forte, contre-jour | oui | `petite-piece`, `chambre`, `sejour` |
| ombres portées franches | **faiblement** | la meilleure photo (`contraste`) est refusée, donc ne compte pas |
| reflets | oui | `salon`, `sejour`, `petite-piece` |
| sol déjà en bois | oui | dix sur onze |
| bois sur bois, risque de confusion | oui | `petite-piece`, `couloir`, `salon`, `appartement-ancien` |
| perspective forte | oui | `appartement-ancien` |

**Quatre manques, dont trois n'en font qu'un** : il n'existe aucune pièce
réellement habitée. Un séjour meublé avec canapé, table, chaises et tapis
couvrirait d'un coup « séjour meublé », « table et chaises », « meuble massif »
et « tapis ».

### 2.7 Sept traits ajoutés au vocabulaire

Le vocabulaire fermé comptait vingt-quatre valeurs et ne savait pas nommer ce
qui décide du rendu. Sept ajouts, chacun parce qu'une mesure future devra
sélectionner ces scènes d'un seul trait :

`thin_occluders` · `massive_furniture` · `second_room_visible` · `threshold` ·
`wood_confusion` · `backlight` · `strong_shadow`

`rug` existait déjà et reste le nom du revêtement de sol à préserver — tapis,
carpette, paillasson. Aucun trait n'a été renommé ni retiré.

### 2.8 Acquisition : une proposition, pas une décision

Les quatre manques exigent des photos qui n'existent pas dans le dépôt. Aucune
acquisition n'a été faite : pas de moissonnage, pas d'appel d'API, aucune image
prise ailleurs. Ce qu'il faudrait, pour décision humaine :

| piste | licence | redistribution | risque |
| --- | --- | --- | --- |
| photographier des pièces réellement habitées, chez nous ou chez des proches consentants | la nôtre | totale si consentement écrit | organiser les prises de vue ; **c'est la piste la plus propre** |
| banque d'images sous licence permissive, sélection manuelle scène par scène | à lire pièce par pièce | rarement acquise | la licence d'une banque autorise l'usage, pas toujours la redistribution du corpus |
| jeux de données académiques de scènes intérieures | souvent recherche uniquement | **non** pour un usage commercial | disqualifiant pour un produit vendu |
| photos d'utilisateurs | — | — | **exclu** : voir §7, aucune ingestion automatique, jamais |

Recommandation : la première piste. Six à huit photos suffiraient à couvrir les
quatre manques, et leur licence serait la nôtre.

## 3. Trois paliers, avec leur justification

Aucun nombre n'est choisi pour faire volume. Chaque palier répond à une question
différente, et le nombre découle de la question.

### Palier 1 — PILOTE : « le protocole tient-il debout ? »

| | |
| --- | --- |
| volume | **12 à 16 photos**, dont au moins 8 meublées et 4 avec tapis |
| double annotation | 4 photos × 2 passes, choisies pour couvrir facile / moyen / difficile / le plus ambigu |
| ce qu'on en tire | temps d'annotation réel, accord humain, zones où les humains divergent, tolérance de contour plausible |
| ce qu'on n'en tire pas | **aucune conclusion sur un modèle** |

Justification du volume : mesurer un accord humain demande peu de photos mais
des photos bien choisies ; au-delà de quatre paires, on paie du temps sans
apprendre. Le pilote actuel visait 4 scènes × 2 passes, ce qui reste le bon
ordre de grandeur — il manque seulement les photos meublées et les tapis.

### Palier 2 — BENCHMARK INTERNE : « quel candidat est le meilleur ? »

| | |
| --- | --- |
| volume | **60 à 100 photos annotées**, réparties sur les cinq axes du §2 |
| répartition visée | facile 20 % · moyen 40 % · difficile 30 % · refus attendu 10 % |
| contrainte | chaque axe du §2 représenté au moins **cinq fois**, sinon un écart n'est pas interprétable |
| ce qu'on en tire | un classement de candidats avec des écarts qui veulent dire quelque chose |
| ce qu'on n'en tire pas | une garantie sur la population réelle des photos d'utilisateurs |

Justification : avec cinq exemples par cas difficile, un candidat qui échoue sur
les tapis se voit. Avec un seul, on ne distingue pas un défaut d'une anecdote.
C'est le raisonnement qui fixe le plancher, pas une convention.

### Palier 3 — VALIDATION PRODUIT : « peut-on le montrer à un client ? »

| | |
| --- | --- |
| volume | **150 à 250 photos**, dont une part non annotée servant uniquement à la revue visuelle |
| provenance | des photos qu'on n'a pas choisies : téléphones différents, cadrages maladroits, pièces réellement habitées |
| ce qu'on en tire | le taux de résultats montrables sans correction, et la nature des échecs restants |

Le palier 3 n'est pas atteignable avec des photos de banque d'images seules : la
population diffère de celle des vraies photos d'utilisateurs. C'est une porte de
décision (D7 dans [ROADMAP-V2.md](ROADMAP-V2.md)), pas un travail d'annotation.

## 4. Le corpus multi-vues — spécification distincte

Rien de ce qui précède ne sert au Mode Visite : il faut un corpus dédié, dont
l'unité n'est pas la photo mais **le lieu**.

Pour une même pièce :

| exigence | valeur | pourquoi |
| --- | --- | --- |
| positions | 4 à 6 | moins de 4 ne donne pas la sensation de déplacement, plus de 6 perd l'utilisateur |
| recouvrement entre deux vues reliées | **≥ 1/3 du champ** | c'est le repère commun qui fait le déplacement |
| sol visible | sur chaque vue, et le même sol | c'est lui qu'on habille |
| hauteur d'appareil | constante, ≈ 1,50 m | une hauteur qui change se lit comme une autre pièce |
| lumière | identique : même heure, même éclairage, même balance | le moteur reporte l'éclairement de la photo |
| focale | constante, 24 à 28 mm en équivalent 35 mm | pas de fisheye : la calibration ne le rattrape pas |
| mobilier | inchangé entre les vues | un objet déplacé trahit un montage |

Métadonnées à porter par capture, en plus de la provenance habituelle :

```
tourId · viewpointId · room (le lieu réel) · captureOrder
camera : hauteur, cap approximatif, focale, appareil
connections : [{ to: viewpointId, réciproque }]
```

Le contrat de données correspondant est **déjà écrit et validé côté front**
(`data/room-tours.json`, `js/product/tour.js`), avec une garde qui refuse une
visite dont deux vues ne sont pas le même lieu. Il n'y a donc rien à concevoir :
il faut photographier.

**Aucune série multi-vues n'existe aujourd'hui**, ni ici ni dans le front — 16
scènes calibrées, 16 lieux différents.

## 5. La vérité terrain : ce qu'on demande aux humains

Règle d'admission : **on ne demande jamais d'annoter ce qui n'est pas
décidable en regardant l'image.**

| annotation | décidable ? | qui | statut |
| --- | --- | --- | --- |
| `floorVisible` | oui | humain | **format existant**, protocole écrit, outil prêt |
| zones `uncertain` | oui | humain | existant, et la règle de largeur est mesurée |
| `boundary` par nature | oui | humain | existant, 6 natures |
| masques d'objets par **rôle** (§4 de l'architecture) | oui | humain | **à ajouter** — 5 rôles, décidables |
| lignes de contact au sol | oui, quand visibles | humain | **à ajouter** |
| ouvertures et seuils | oui | humain | **à ajouter**, en partie couvert par `boundary` |
| `floorExtent` | **non** | personne | reste vide, par décision — l'image ne le contient pas |
| horizon, points de fuite | partiellement | humain outillé | **à étudier** : traçable mais lent et bruité |
| profondeur | **non** | capteur ou pseudo-vérité | seulement si un capteur la fournit |
| relations multi-vues | oui | humain, à la prise de vue | **à ajouter** avec le corpus du §4 |

Deux conséquences pratiques :

- la profondeur ne sera **pas** annotée à la main. Elle sera évaluée par ses
  effets sur le rendu (ordre des occlusions, continuité), pas contre une carte
  de référence qu'on n'a pas.
- l'horizon et les points de fuite peuvent recevoir une vérité terrain
  approchée sur un petit sous-ensemble seulement. Le manifeste porte déjà les
  champs pour l'accueillir (`groundTruth.vanishingPoints`, `groundTruth.camera`),
  et ils sont vides sur les 11 photos.

## 6. L'outil d'annotation : étendre, ne pas multiplier

État réel : `tools/annotate.html`, 1 700 lignes, fichier unique sans
dépendance, sans réseau. Il sait tracer des polygones de sol, des exclusions,
des zones incertaines avec motif, et des polylignes de contour avec nature. Il
chronomètre en excluant les inactivités de plus de 60 secondes. Il exporte un
seul JSON normalisé ; la rastérisation appartient à Python.

**Recommandation : étendre cet outil, ne pas en créer un second.**

| ajout nécessaire | difficulté | pourquoi ici et pas ailleurs |
| --- | --- | --- |
| ~~polygone d'objet avec **rôle**~~ — **fait au LOT B.2** | faible, confirmé | même image, même session, même chronomètre |
| polyligne de **contact au sol** | faible — même primitive que `boundary` | l'annotateur voit déjà le contact quand il trace l'objet |
| marquage d'**ouverture** | faible | c'est une nature de contour de plus |
| relations multi-vues | **hors outil** | c'est une donnée de prise de vue, pas de tracé : elle se saisit au manifeste |

La raison de fond : ces annotations portent sur **la même image, au même
moment**. Les séparer en deux outils obligerait à charger deux fois la photo, à
chronométrer deux fois, et à réconcilier deux fichiers — pour un gain nul.

Un point de dette à traiter en même temps : les vocabulaires de l'outil sont
recopiés à la main depuis le schéma Python. Deux tests rejouent une sortie
réelle de l'outil à travers l'import, ce qui attrape une divergence, mais
tardivement. Générer les listes depuis le schéma serait mieux ; ce n'est pas
bloquant.

Le premier ajout de cette table est livré : l'outil demande le rôle d'une
exclusion à sa fermeture, et l'exporte dans `floorHoleRoles`, parallèle à
`floorHoles`. La recommandation « étendre, ne pas multiplier » a été tenue à la
lettre — un seul fichier HTML touché, aucun second outil, et le rôle est
demandé sur la primitive qui existait déjà plutôt que sur une nouvelle.

**L'outil interne n'a pas à être beau.** Il doit être précis, rapide,
reproductible et vérifiable. Aucun élément de l'interface publique n'y entre, et
réciproquement.

## 7. Découpage des jeux

| jeu | rôle | règle |
| --- | --- | --- |
| `synthetic/` | vérité imposée, régénérable au bit près | reste réservé à la netteté et à la distorsion |
| `private-real/` | corpus de développement, licence vérifiée, non redistribuable | **jamais** de photo d'utilisateur |
| `public/` | ce qu'on pourrait redistribuer | vide aujourd'hui ; le rester est acceptable |
| `tours/` | corpus multi-vues, unité = le lieu | à créer avec le LOT H |
| envois d'utilisateurs | — | **n'entrent dans aucun jeu** sans consentement explicite et documenté |

Pour le palier 2, le découpage entraînement/validation ne s'applique pas tant
qu'on n'entraîne rien : on **évalue** des candidats préentraînés. Le jour où un
réglage fin est envisagé, le découpage devra être fait **par lieu** et non par
photo — deux vues d'une même pièce dans deux jeux différents fuiteraient
l'information.

### 7.1 Le split réel, et sa règle

Un train/validation/test sur onze photos serait statistiquement trompeur : on
ne mesure aucune généralisation sur un échantillon de cette taille. La
séparation utile est ailleurs, et elle est portée par le manifeste
(`split`) :

| split | photos | ce qu'on s'autorise |
| --- | --- | --- |
| `pilot_development` | 6 | tout : regarder, commenter, régler des seuils dessus |
| `golden_holdout` | 5 | **aucun réglage.** Revue visuelle humaine uniquement |

**La règle, en une phrase :** on annote les scènes du jeu de référence comme
les autres, on mesure dessus comme sur les autres, mais **on n'ajuste jamais un
seuil, un paramètre ou un choix de modèle en regardant leurs résultats.** Elles
ne servent qu'à répondre à « est-ce que ça s'est dégradé ? ».

Deux scènes du jeu de référence (`couloir`, `petite-piece`) appartiennent aussi
à la campagne d'annotation pilote. Ce n'est pas une contradiction : mesurer
l'accord d'une personne avec elle-même n'est pas régler un algorithme.

### 7.2 Le jeu visuel de référence

Cinq scènes, chacune déclarant **le cas qu'elle est la mieux placée pour
exposer** (`goldenCase`). Sans cette déclaration, un jeu de référence dérive en
collection de jolies photos et personne ne sait plus ce qu'il couvre.

| cas | scène | difficulté |
| --- | --- | --- |
| `wall_floor_hard` | `couloir` | hard |
| `thin_occluders` | `petite-piece` | hard |
| `strong_perspective` | `appartement-ancien` | hard |
| `wood_on_wood` | `salon` | hard |
| `opening` | `bureau-vide` | easy |
| `rug` | **NON COUVERT** | — |
| `massive_furniture` | **NON COUVERT** | — |

Quatre scènes difficiles sur cinq : un jeu de référence majoritairement facile
donnerait de beaux chiffres et aucune information. `validate_dataset.py` publie
cette table à chaque contrôle, y compris les cas manquants, et un test verrouille
le fait qu'il en reste deux — il tombera le jour où les photos existeront, ce
qui est exactement le but.

Le jeu de référence contient aujourd'hui, pour chaque scène, la photo et ses
métadonnées. La vérité terrain viendra avec les annotations ; les sorties de
modèle, plus tard.

**Décision LOT B.2 — les métadonnées du jeu de référence ne changent pas.**
La question était d'y ajouter un résumé des rôles présents dans chaque scène.
Ce serait une donnée dérivée : les rôles vivent dans les annotations, et
`corpus_report` les compte déjà. Un champ recopié se désynchronise dès la
première correction d'annotation, et le jeu de référence deviendrait faux sans
que rien ne le signale. Le lien `goldenCase` ↔ rôle est de toute façon déjà
lisible : `thin_occluders` se vérifie par les exclusions `occluder` fines de
`petite-piece`, et `rug` restera non couvert tant qu'aucune exclusion
`floor_covering` n'existera.

## 8. Ce que ces annotations permettront de mesurer, et ce qu'elles ne permettront pas

Contrôle fait maintenant, parce que découvrir après cinq cents relevés qu'une
métrique est incalculable coûterait le corpus entier.

| métrique | calculable avec la passe A ? | ce qu'il faut, sinon |
| --- | --- | --- |
| IoU, Dice, précision, rappel | **oui** | — |
| F-mesure de contour, aux trois tolérances | **oui** | — |
| accord humain, répétabilité | **oui**, dès deux passes | — |
| `visible floor miss rate` | **oui** | — |
| `critical boundary error` | **oui** | les polylignes `wall_floor` localisent déjà la jonction |
| `wall bleed rate` | **approchée** | exacte demanderait un masque de mur ; la dilatation au-dessus des polylignes `wall_floor` en donne une bonne approximation, à valider |
| `occluder bleed`, toutes catégories confondues | **oui** | les exclusions tracées forment l'union des occulteurs |
| `occluder bleed` et `structural bleed` séparés | **oui, depuis le LOT B.2** | le rôle de chaque exclusion est annoté : 5 `occluder`, 2 `structural` sur le pilote |
| `rug bleed` | **NON — et la cause a changé** | le rôle existe désormais (`FLOOR_COVERING`) ; ce qui manque est le sujet lui-même : **le corpus pilote n'a aucun tapis**. Aucun code ne lèvera ce blocage, seule une acquisition |
| `thin-object preservation` | **oui, depuis le LOT B.2** | la finesse est dérivée du rayon inscrit maximal et comparée à la tolérance de contour du projet ; 8 exclusions fines sur les 12 du pilote |
| `opening continuity error` | **partiellement** | les seuils sont tracés comme contours ; dire « même surface ou non » demande un champ que le protocole ne collecte pas encore |
| erreurs de profondeur, de caméra | **non**, et c'est assumé | aucune vérité terrain dense n'est demandée à un humain ; ces métriques passent par leurs effets sur le rendu |

Deux conclusions concrètes, mises à jour au LOT B.2. **Le manque de rôle est
levé** : la ventilation d'`occluder bleed` et la préservation des objets fins
sont désormais calculables, et le rôle est un champ additif — une annotation
antérieure reste valide et ses exclusions valent `unknown`. **Il reste un seul
blocage, et il n'est pas technique** : `rug bleed` demande des tapis, et le
corpus pilote en compte zéro (`floor_covering : 0` au bilan, avec
avertissement explicite du validateur). C'est un manque d'acquisition, pas de
schéma, et il est le seul de la liste qu'aucun lot de code ne peut résoudre.

Ce que le rôle n'est pas : une classe d'objet. Rien dans le corpus ne dit
« chaise » ou « radiateur ». Deux exclusions de rôle identique peuvent être des
objets sans rapport, et c'est voulu — la question mesurée est « le parquet a-t-il
été peint là où il ne devait pas », qui ne dépend pas du nom de l'objet.

## 9. Le contrôle visuel d'un relevé

Un relevé qu'on ne peut pas regarder est un relevé qu'on approuve sans le voir.
`scripts/import_annotation.py --overlay <fichier>` écrit la photo avec le relevé
posé dessus : le sol en vert, l'incertain en ambre, le contour en trait blanc.

Les quatre fautes que cet aperçu attrape et qu'un JSON ne montre pas : un
morceau de mur happé, une bande de sol oubliée le long d'une plinthe, un tapis
resté dedans, un pied de chaise effacé.

L'aperçu n'entre ni au manifeste, ni à Git : c'est une image de travail, écrite
là où on la demande, et la photo d'origine n'est jamais modifiée.

## 10. Ce que ce document n'autorise pas

- annoter `floorExtent` à la main ;
- compléter le corpus avec des photos dont la licence est supposée ;
- faire entrer une photo d'utilisateur dans un jeu de données ;
- remplacer des photos meublées manquantes par des photos synthétiques
  meublées : le but est précisément de mesurer ce que le réel a de désordonné ;
- annoter une nature d'objet là où un rôle suffit.
