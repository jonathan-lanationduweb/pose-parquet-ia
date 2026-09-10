# Stratégie de mesure — V2

> **ACTIF.** Ce qu'on mesure, et ce qui décide. Les métriques déjà implémentées
> et leur définition exacte restent documentées dans
> [benchmarks/README.md](../benchmarks/README.md) et
> [annotation-protocol.md §8](annotation-protocol.md) ; ce document dit
> **lesquelles on garde** et **celles qui manquent** pour la cible V2.

## 1. Le principe qui gouverne tout le reste

> Un masque juste ne prouve pas un rendu juste. Un rendu faux avec un bon IoU
> est possible, il est fréquent, et c'est exactement le piège dans lequel ce
> projet ne doit pas tomber.

Conséquence : **aucune décision de modèle ne se prend sur des métriques de
masque seules.** La validation finale passe par photo + analyse + moteur de
rendu, et par un œil humain (§6).

## 2. Ce qui est conservé, tel quel

Ces métriques sont implémentées, testées, et justes. Elles ne bougent pas.

| famille | métriques | remarque |
| --- | --- | --- |
| surface | IoU, Dice, précision, rappel, TP/FP/FN/TN, `ignoredFraction` | les pixels `uncertain` sont exclus de tout, et la part exclue est publiée |
| contour | F-mesure de contour, précision et rappel de contour, à tolérance paramétrable | frontière intérieure, bande de cadre exclue de la région évaluée |
| tolérances | **0,25 % · 0,5 % · 1 %** de la diagonale, comparées ensemble | aucune n'est un objectif produit ; elles restent multiples tant qu'aucune décision humaine n'a tranché |
| accord humain | IoU et contour entre deux passes, localisation du désaccord, points chauds, part d'incertain | le nom de la mesure suit qui a annoté : accord inter-annotateurs ou répétabilité intra |
| avertissements | matrice de confusion multi-label, faux positifs compris, `detectedOfExpected`, `falseAlarmsPerImage` | pas d'« exactitude » globale, refus documenté |

**Rappel à ne pas perdre : l'IoU seul est insuffisant.** La démonstration est
déjà dans le dépôt : un masque décalé de 30 pixels garde un IoU de 0,67 et voit
sa F-mesure de contour tomber à 0,002. L'œil voit le second chiffre, pas le
premier.

Deux cibles héritées du front — **IoU > 0,92** et **quadrilatère à moins de
2 %** — restent écrites mais **non validées**. Elles ne sont pas des seuils
produit, et aucune donnée réelle ne les a encore justifiées.

## 3. Ce qui manque : les métriques du problème réel

Elles sont définies conceptuellement ici et ne sont **pas** implémentées dans ce
lot. Chacune répond à un défaut visible que l'IoU ne voit pas.

| métrique | définition | pourquoi elle décide |
| --- | --- | --- |
| **wall bleed rate** | part de la prédiction qui tombe sur mur ou plinthe, rapportée au périmètre de contact mur/sol | trois pixels de parquet sur une plinthe blanche se voient immédiatement |
| **visible floor miss rate** | part du sol visible vrai non prédite, pondérée par la distance au contour | oublier une bande au milieu de la pièce est bien plus grave qu'un liseré au bord |
| **critical boundary error** | erreur de contour restreinte au voisinage de la jonction mur/sol, hors zones incertaines | c'est là que l'œil juge, et une seule métrique globale le noie |
| **occluder bleed** | part de la surface d'un occulteur peinte en parquet | un canapé repeint invalide l'image entière |
| **rug bleed** | idem, restreint aux tapis et paillassons | cas le plus fréquent et le plus coûteux |
| **thin-object preservation** | part conservée des occulteurs de faible épaisseur (pieds, montants), mesurée séparément | les pieds fins sont perdus par les masques grossiers, et ce sont eux qui trahissent un faux |
| **opening continuity error** | désaccord de `surfaceId` ou de plan de part et d'autre d'un seuil, et décalage du motif au raccord | une enfilade mal raccordée se voit à l'alignement des lames |

Deux principes de construction :

- **pondérer par la distance au contour.** Une erreur au milieu du sol et une
  erreur au ras du mur n'ont pas le même prix visuel, et une métrique qui les
  compte pareil ment.
- **mesurer par cas difficile, pas seulement en moyenne.** Une moyenne sur
  100 photos noie les six qui contiennent un tapis. Les agrégats par difficulté
  et par trait existent déjà dans le banc d'essai ; il faut les utiliser.

## 4. Objets et occlusions

| métrique | définition | note |
| --- | --- | --- |
| IoU de masque par rôle | par rôle fonctionnel, jamais globalement | un bon IoU global peut cacher zéro tapis détecté |
| contour d'objet | F-mesure sur le contour de l'occulteur | le liseré autour d'un meuble est très visible |
| préservation de l'objet au premier plan | part des pixels de l'objet restés d'origine dans l'image finale | c'est la question du produit, pas celle du masque |
| **préservation des objets fins** | même mesure, restreinte aux structures de moins de N pixels d'épaisseur | à mesurer à part, sinon la moyenne l'écrase |
| justesse de la ligne de contact | écart entre contact prédit et contact annoté, en pixels | un meuble flottant se voit tout de suite |

## 5. Profondeur, caméra, perspective : relier chaque métrique au rendu

Le besoin n'est pas « une belle carte de profondeur ». Le besoin est un rendu
juste. Donc on ne mesure que ce qui dégrade le rendu.

**Profondeur** — trois erreurs seulement importent :

| erreur | effet visible | mesure |
| --- | --- | --- |
| ordre inversé entre deux occulteurs | un objet passe derrière ce qui est devant | taux d'inversions sur paires d'occulteurs qui se recouvrent |
| discontinuité au contact sol/objet | meuble qui flotte ou s'enfonce | erreur locale à la ligne de contact |
| gradient faux sur le plan du sol | netteté ou éclairement qui varie à l'envers | monotonie de la profondeur le long des fuites |

Les métriques académiques de profondeur (erreur absolue relative, seuils δ) sont
inutiles ici : elles récompensent la précision là où nous n'avons besoin que de
l'ordre et de la continuité.

**Caméra et perspective** — chaque métrique se traduit en défaut visible :

| métrique | définition | défaut visible correspondant |
| --- | --- | --- |
| erreur d'horizon | écart vertical à l'horizon vrai, en fraction de hauteur | le parquet ne fuit pas au bon endroit |
| erreur de direction de fuite | angle entre direction prédite et vraie, au sol | les lames partent de biais |
| **erreur d'échelle de lame projetée** | écart relatif entre la largeur d'une lame rendue et sa largeur physique attendue, mesurée en plusieurs points de l'image | une lame de 190 mm qui fait 150 mm à l'écran : invisible à l'œil nu, fausse au devis |
| erreur d'alignement | décalage angulaire entre le motif rendu et une référence de la pièce | un point de Hongrie qui n'est pas d'aplomb |

L'erreur d'échelle de lame projetée est la métrique la plus proche de notre
spécialité, et personne ne la publie. C'est celle qu'il faut construire avec le
plus de soin.

## 6. Le jeu visuel de référence

Un petit ensemble stable de scènes, choisies pour couvrir les cas qui cassent le
rendu, et **jamais modifié pour arranger un résultat**.

| propriété | valeur |
| --- | --- |
| taille | 12 à 20 scènes |
| composition | au moins : un tapis, une chaise à pieds fins, un sol bois clair, une enfilade avec seuil, un contre-jour, une perspective forte, un sol réfléchissant |
| pour chaque scène | la photo d'origine · la vérité terrain · le résultat du modèle · **le rendu de parquet final** |
| déclenchement | à **chaque** changement notable de modèle, de seuil ou de contrat |
| verdict | humain, écrit, daté, avec le nom de la personne |

Les critères de la revue visuelle sont ceux de la définition de terminé
([PRODUCT-VISION.md §7](PRODUCT-VISION.md)) : parquet uniquement sur le sol,
objets préservés, tapis préservés, perspective crédible, largeur physique
cohérente, matière lisible, lumière conservée, aucune zone d'ancien sol
visible, aucune coupure absurde.

**Un modèle qui améliore les chiffres et dégrade le jeu visuel n'est pas
retenu.** C'est la règle qui protège le produit des optimisations aveugles.

## 7. Ce que le banc d'essai doit séparer

Trois choses sont mesurées séparément et ne doivent jamais être additionnées :

1. **la qualité de la photo** — netteté, exposition, distorsion : déjà mesurée,
   avec sa matrice de confusion ;
2. **la compréhension de la scène** — sol, objets, profondeur, caméra ;
3. **le rendu final** — ce que l'utilisateur voit.

Un échec au niveau 3 peut venir de n'importe lequel des trois. Les mélanger
rendrait tout diagnostic impossible.

## 8. Le passage de porte du premier lot technique

Un lot de choix de modèle de segmentation ne commence **que** lorsque les six
conditions suivantes sont vraies. Ce n'est pas un vœu de méthode : chacune
correspond à une manière connue de se tromper.

| condition | pourquoi, précisément |
| --- | --- |
| protocole d'annotation validé sur des photos meublées | le protocole actuel n'a jamais été éprouvé sur un tapis |
| corpus minimum disponible (palier 1, §3 de la stratégie de données) | comparer sur 3 images désigne un gagnant au hasard |
| annotations minimum disponibles et **approuvées** | seul `approved` entre au banc d'essai, et il y en a zéro |
| banc d'essai prêt | il l'est : registre de candidats, agrégats par difficulté et par trait |
| métriques produit définies | §3 : sans elles, on mesurera le mauvais chiffre |
| licences des candidats vérifiées | un modèle non redistribuable choisi est un modèle à remplacer |

État actuel de ces six conditions : **deux sont remplies**. Le banc d'essai
l'était déjà ; les licences des candidats ont été vérifiées au LOT B.3, à la
source officielle et en distinguant le code des poids —
[MODEL-LICENSES.md](MODEL-LICENSES.md). Cette vérification lève **un** obstacle
sur quatre : elle ne choisit aucun modèle et n'autorise pas le lot technique.
Les quatre conditions manquantes tiennent toutes au corpus et à la vérité
terrain — pas de tapis, corpus du palier 1 incomplet, zéro annotation
approuvée, accord humain non mesuré.

## 9. Ce que la mesure n'autorise pas

- déclarer un modèle bon sur la foi d'un IoU ;
- fabriquer des données de test qui favorisent notre approche ;
- modifier une annotation pour faire passer une métrique ;
- compter le nombre de tests qui passent comme une preuve de qualité produit ;
- publier une moyenne sans la répartition par cas difficile ;
- retenir un seuil « parce qu'il ressemble à ceux de la littérature ».
