# Bibliothèque de pièces de démonstration

Une catégorie (« Chambre », « Séjour »…) est une **collection de scènes**. La
liste vit dans un seul fichier, `web/data/rooms.json`, lu par la galerie
(`web/product/room-library.js`) et par le moteur (`web/scene/analyzer.js`).
Le nombre affiché, « Chambre (3) », est calculé : il n'est écrit nulle part.

## Ajouter une pièce

1. Déposer la photo et sa vignette dans `web/assets/images/` :
   `room-<id>.jpg` (1 600 px de large) et `room-<id>-640.jpg`.
   Créditer l'auteur dans `web/assets/images/CREDITS.md`. Seules les images
   dont le projet a les droits : pas d'image récupérée au hasard.
2. Ajouter une entrée dans `rooms.json` (`id`, `name`, `category`,
   éventuellement `alsoIn`, `image`, `thumbnail`, `style`, `lighting`,
   `difficulty`, `source`).
3. Ajouter sa SceneData calibrée dans `web/data/scenes/<id>.json` et la
   référencer dans `sceneData`.
4. Lancer la revue géométrique :

   ```
   PPAI_PLAYWRIGHT_CORE=<playwright-core> node tools/scene-review.capture.mjs <id>
   ```

   Elle écrit une planche (original, masque, géométrie, lames, point de
   Hongrie, bâton rompu) et des contrôles chiffrés sous
   `review/rooms-and-render-fix/scenes/`.
5. Seulement si la planche est juste **et** les contrôles passent :
   `calibration.status = "validated"` et `renderReady = true`.

Aucune fonction JavaScript n'est à modifier.

## Deux portes

* `availableForGallery` : la photo a le droit d'être montrée.
* `renderReady` : sa géométrie a été relue ; un parquet peut s'y poser.

Une scène n'est proposée que si les deux sont vraies et que
`calibration.status` vaut `validated`. `tools/room-library.check.mjs` refuse un
manifeste où `renderReady` serait vrai sans calibration validée.

## Contrôles chiffrés de la revue

| contrôle | ce qu'il attrape |
| --- | --- |
| `solSousHorizon` | un sol peint au-dessus de l'horizon |
| `fuitesSurHorizon` | des fuites du plan hors de l'horizon déclaré |
| `fuitesAlignees` | un plan dont les fuites ne tombent pas sur celles mesurées sur les murs (le parquet ne suivrait pas les axes de la pièce) |
| `lamesCroissentVersAvant` | une perspective inversée |
| `echelleProchePlausible` | une lame proche hors de 1,2 à 9 % de la largeur d'image |

Ces contrôles ne remplacent pas l'œil : une scène n'est validée qu'après
lecture de sa planche.

## État au 12 octobre 2026

15 scènes au manifeste, 11 proposées. Refusées à la revue, avec la raison
dans `rooms.json` : `salon`, `couloir` (échelle et fuites), `petite-piece`,
`appartement-ancien` (masques qui laissent l'ancien sol visible).
