# Benchmark — Quick-Step RoomViewer et Karndean Floorstyle

Relevé **en utilisant réellement les deux outils dans un navigateur**, le
8 septembre 2026. Chaque observation ci-dessous vient d'un écran vu et d'un
bouton cliqué, pas du code source ni du texte de la page.

Ce document sert à décider de l'UX de `tools/product-concept.html`. On reprend
des **patterns d'interaction éprouvés** ; on ne reprend ni identité visuelle,
ni assets, ni code.

---

## 1. Quick-Step RoomViewer

Le visualiseur est un service embarqué dans la page produit
(`quick-step.b3dservice.de`, servi par `quickstep.esignserver1.com`). La page
d'atterrissage n'est qu'une vitrine : l'outil lui-même occupe un cadre plein.

### Entrée dans l'outil

**Aucun écran d'accueil, aucun wizard.** L'outil s'ouvre déjà sur une pièce
d'exemple avec un sol posé. On voit immédiatement un résultat.

Toute la navigation tient en **trois entrées empilées en haut à gauche**, très
compactes, et chacune **affiche sa valeur courante en sous-titre** :

```
📷  Charger votre pièce            ›
⇄   Choisir un sol                 ›
    Chêne naturel brossé
▦   Choisissez une pièce           ›
    Salon
```

C'est l'observation la plus utile du benchmark : trois lignes remplacent une
sidebar entière, et le sous-titre dispense d'ouvrir le panneau pour savoir où
l'on en est.

En haut au centre, une barre de **cinq icônes seulement** : zoom, partage,
rotation du sol, motif de pose, comparaison.

### Choisir une pièce d'exemple

Une modale « Choisir une pièce » :

* colonne de **catégories avec icônes** — Salon, Salle à manger, Cuisine,
  Chambre, Salle de bains, Entrée, Chambre d'enfant, Bureau ;
* et **dans la même colonne, en bas, un bouton rose « CHARGER VOTRE PIÈCE »** ;
* à droite, une **grille** de vignettes (3 par ligne), la pièce courante
  marquée d'une **coche** ;
* la pièce reste visible sur le bord droit : on ne perd jamais le contexte.

**Deux clics** pour changer de pièce, et le sol sélectionné est conservé.

Le point décisif : l'import de sa propre photo n'est pas ailleurs, il est
**dans le même sélecteur**, au même niveau que les pièces d'exemple.

### Importer sa pièce

Deux points d'entrée : la première des trois entrées, et le bouton dans le
sélecteur de pièce. Formulé « Charger votre pièce » — pas « uploader une
image ». Aucun jargon technique, aucune mention de format sur l'écran d'appel.

### Catalogue

Une modale large, titrée **« Choisir un sol (241) »** — le compte est affiché.

* colonne de filtres à gauche (~190 px) : champ **« Trouver un sol »**,
  **Type de sol** en cases à cocher, **Couleur** sous forme de **dix pastilles
  de couleur** — pas de libellés —, **Collection** en menu déroulant,
  **Résistant à l'eau** en interrupteur ;
* grille de **3 colonnes de grandes textures**, chacune avec son nom entre
  guillemets puis `CATÉGORIE - COLLECTION | RÉFÉRENCE` ;
* la vignette **est** la texture : aucune photo de pièce dans le catalogue.

**Un clic applique et referme la modale.** Aucun bouton « Appliquer ».

### Produit sélectionné

Carte flottante en haut à droite, **sur la photo** :

```
      ◕ (texture ronde)
   Chêne cannelle extra matt
  PARQUET - PALAZZO | PAL3096S
     ⊹ 2.2 x 0.19 mm
   ( PLUS D'INFORMATIONS )
        ‹    |    ›
```

Les flèches `‹ ›` font **défiler les produits un par un sans rouvrir le
catalogue**. Excellent : on compare en rafale sans quitter la pièce.

Le CTA renvoie vers la fiche produit — c'est exactement le pont dont nous
aurons besoin vers Premibel.

### Personnalisation

L'icône « motif de pose » ouvre un petit menu déroulant. Pour le produit
essayé, il ne contenait **qu'une entrée : « Irrégulier »**.

Autrement dit : **seules les capacités réelles du produit sont proposées.**
C'est la règle que nous avions déjà retenue, et elle est confirmée par un
concurrent sérieux.

### Comparaison

L'icône `‹›` scinde la **même photo** :

* séparateur vertical déplaçable, poignée en losange au centre ;
* étiquettes **« version A »** et **« version B »** de part et d'autre ;
* **deux cartes produit**, une à gauche, une à droite, chacune avec sa
  référence, son CTA et ses propres flèches `‹ ›` ;
* un bouton flottant « B ⇄ » pour changer le sol de la version B.

Même photo, même perspective, même lumière : la comparaison porte uniquement
sur le sol. Bien supérieur à deux images côte à côte.

### Avant / après

Pas de contrôle « avant/après » séparé : la comparaison scindée en tient lieu.

### Favoris

Non trouvé dans le visualiseur embarqué. La mise de côté passe par le panier
d'échantillons du site.

### Points très réussis

* trois entrées de navigation qui portent leur valeur courante ;
* application instantanée au clic, sans bouton de validation ;
* flèches produit précédent/suivant directement sur la scène ;
* filtre couleur en pastilles, pas en texte ;
* comparaison dans une seule photo scindée ;
* la photo occupe **100 %** du cadre, aucun panneau permanent.

### Points faibles

* aucun favori dans l'outil ;
* la carte produit masque un coin de la pièce en permanence ;
* les boutons flottants posés sur le sol sont jolis mais leur fonction n'est
  pas devinable ;
* l'outil vit dans un `iframe` qui se vide au défilement de la page hôte.

---

## 2. Karndean Floorstyle

### Entrée dans l'outil

Là aussi : **pas d'écran d'accueil, pas de wizard.** Une cuisine avec son sol
posé, plein cadre.

Deux **rails d'icônes verticaux** encadrent l'image, larges d'environ 64 px :

* à gauche — Upload Image, Select room, Select floor, Select colour, Rotate
  floor, Split screen, Search ;
* à droite — panier, Favourites, Share, Print, Zoom.

Un bandeau de site très fin au-dessus (~36 px). Le reste est la photo.

### Choisir une pièce d'exemple

Panneau superposé « Sélectionnez un espace » :

* liste verticale de catégories à gauche — Cuisine, Salon, Salle à manger,
  Chambre, Salle de bain, Jardin d'hiver, Entrée, Utility, Home Office ;
* rangée horizontale de vignettes à droite ;
* la pièce reste visible derrière, en transparence.

Détail notable : **cliquer la catégorie charge déjà la première pièce** de
cette catégorie. Un clic peut suffire.

### Catalogue

Panneau « Choisir un sol », plus dense que celui de Quick-Step :

* quatre **menus déroulants** de filtre (Wood, Teinte, Couleur, Gamme) et
  « Réinitialisez tous les filtres » ;
* grille de **5 colonnes** de textures, avec nom et référence
  (« White Painted Oak / Pine · KP105 ») ;
* en bas à gauche, un bloc **« Produit 1 »** : texture, référence, collection,
  dimensions (`1219mm × 178mm`, `3.0mm thick`) ;
* en bas, **« Modèles de pose »** — une rangée de **schémas** de calepinage
  (droit, chevron, brique, bâton rompu, panier…), le choix courant encadré ;
* et « Ajoutez des bandes décoratives ».

**Un bouton explicite « Voir dans la pièce › »** en haut à droite : Karndean
regroupe les choix puis applique. Moins immédiat que Quick-Step.

Les motifs de pose en **schémas** sont en revanche plus lisibles qu'un menu
déroulant : on comprend le calepinage d'un coup d'œil.

### Comparaison — « Split screen »

Le même principe que Quick-Step : la **photo est scindée** par un séparateur
vertical, chaque moitié avec son sol. Un message invite à ajouter un second sol
à la sélection. La notion de « Produit 1 » du catalogue prend alors son sens.

### Favoris

Le rail droit « Favourites » enregistre **un rendu**, pas un produit : une
vignette de la scène complète apparaît en haut à droite et le compteur du
bandeau passe à 1.

Distinction intéressante — on met de côté *une pièce avec son sol*, pas une
référence. C'est plus proche de ce que cherche un particulier.

### Changer de pièce

Deux clics au plus, le sol est conservé, panneau superposé.

### Densité visuelle

* photo : ~85 % de la largeur (deux rails de 64 px) et ~92 % de la hauteur ;
* bandeau de site : ~36 px ;
* aucun panneau permanent en dehors des deux rails d'icônes.

### Points très réussis

* la photo domine plus encore que chez Quick-Step ;
* rails d'icônes : sept fonctions dans 64 px de largeur ;
* clic sur une catégorie de pièce = pièce chargée ;
* motifs de pose en schémas ;
* favoris qui enregistrent un rendu ;
* sol couvert **intégralement**, avec tapis, canapé, paniers et fauteuil
  préservés en avant-plan.

### Points faibles

* rails d'icônes peu lisibles pour un novice : icônes petites, libellés de
  9 px, sept fonctions de même poids visuel ;
* « Voir dans la pièce » casse l'immédiateté ;
* le catalogue est dense : filtres, grille, produit, motifs et bandes
  décoratives dans un seul panneau ;
* rouge saturé omniprésent, fatigant.

---

## 3. Ce que nous reprenons

| pattern | source | pourquoi |
| --- | --- | --- |
| **la photo occupe tout**, aucun panneau permanent | les deux | c'est le sujet ; nos trois colonnes l'étouffaient |
| **navigation en trois entrées** portant leur valeur courante | Quick-Step | remplace une sidebar entière |
| **application au clic**, sans bouton « Appliquer » | Quick-Step | l'essai en rafale est le cœur de l'usage |
| **flèches produit précédent/suivant** sur la scène | Quick-Step | comparer sans rouvrir le catalogue |
| **catalogue en modale** : filtres à gauche, grille de textures à droite, compte dans le titre | Quick-Step | la texture est l'information, pas une photo de pièce |
| **couleur/teinte en pastilles** | Quick-Step | un filtre de couleur ne se lit pas en mots |
| **motifs de pose en schémas** | Karndean | le calepinage se comprend en image |
| **import dans le sélecteur de pièce**, au même niveau que les exemples | Quick-Step | les deux entrées sont symétriques |
| **catégories + grille, courante cochée** | les deux | deux clics, contexte conservé |
| **comparaison dans une seule photo scindée**, versions A/B étiquetées, une carte produit par côté | les deux | même perspective, même lumière |
| **fiche produit avec référence et dimensions**, et un lien sortant | les deux | c'est le pont vers Premibel |
| **seules les capacités réelles du produit sont offertes** | Quick-Step | confirme notre règle |

## 4. Ce que nous ne reprenons pas

* **les rails d'icônes de Karndean** — sept fonctions au même poids visuel,
  libellés de 9 px : illisible pour un particulier. Nous préférons trois
  entrées nommées ;
* **le bouton « Voir dans la pièce »** — il casse l'immédiateté ;
* **le catalogue tout-en-un de Karndean** — filtres, grille, produit, motifs et
  bandes décoratives ensemble. Nous séparons *choisir un parquet* de
  *personnaliser* ;
* **les boutons flottants posés sur le sol** — décoratifs, fonction non
  devinable ;
* **le rouge saturé** de Karndean et le **rose** de Quick-Step. Notre accent
  reste le brun terre ;
* **les bandes décoratives** — hors périmètre parquet ;
* aucun logo, aucune police, aucun asset, aucune capture, aucune ligne de code
  de l'un ou de l'autre.

## 5. Ce que Pose Parquet fera mieux

1. **Un écran d'entrée qui pose le choix.** Les deux concurrents ouvrent sur
   une pièce arbitraire. Nous demandons d'abord : votre photo, ou une pièce ?
   C'est plus honnête, et cela évite de croire que l'outil ne marche que sur
   leurs images.
2. **Un vrai avant/après.** Aucun des deux ne l'offre : ils n'ont que la
   comparaison entre deux sols. Comparer au **sol existant** est pourtant la
   première question d'un particulier.
3. **Des favoris qui gardent le parquet ET la pièce.** Karndean garde un
   rendu, Quick-Step ne garde rien. Nous gardons le produit, retrouvable dans
   n'importe quelle pièce.
4. **La spécialisation parquet.** Trois motifs traités correctement — lames,
   point de Hongrie, bâton rompu — plutôt que douze calepinages génériques de
   sol souple.
5. **L'honnêteté sur l'automatique.** Quand nous ne savons pas détecter le sol
   d'une photo inconnue, nous le disons au lieu de poser un masque approximatif.
6. **Le même parquet d'une pièce à l'autre.** Changer de pièce conserve le
   produit : on juge un parquet dans plusieurs lumières.

---

## 6. Adaptation future Premibel

Le même visualiseur devra servir dans les deux sens. Les deux concurrents le
font déjà, et c'est ce qui justifie la carte produit avec référence.

**Depuis une fiche produit** — `?product=<id>` ouvre le visualiseur avec ce
produit déjà posé, sur la dernière pièce ou une pièce d'exemple par défaut.

**Depuis le visualiseur** — la carte produit porte un lien vers la fiche, comme
« PLUS D'INFORMATIONS » chez Quick-Step.

Le catalogue de droite devient alors le **vrai catalogue Premibel** : les
`DEMO_PRODUCTS` du prototype ont déjà la forme attendue — `id`, `name`, `url`,
`pattern`, `tone`, `availableWidths`, `availableFinishes`, `tags`. Le champ
`url` est la seule addition nécessaire.

**Ce qui n'appartient pas à `SceneData` :** le produit choisi, les favoris, les
emplacements de comparaison. Une scène décrit ce que la photo montre ; une même
scène supporte cent parquets. Voir `docs/product-ai-contract.md`, §6.

Rien de cette connexion n'est développé ici, et Premibel n'a pas été consulté.

---

## Méthode

Les deux outils ont été ouverts et manipulés dans un navigateur, le 8 septembre
2026 : état initial, sélection de pièce, catalogue, sélection de produit, menu
de motif, comparaison, favoris, changement de pièce. Le bandeau de cookies de
Quick-Step a été refusé (« Tout refuser »).

Des captures temporaires ont servi à la comparaison ; aucune n'est conservée
dans le dépôt, et aucun asset des deux sites n'a été téléchargé.
