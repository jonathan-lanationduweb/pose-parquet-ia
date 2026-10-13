# Matières Premibel : fidélité, import, vitesse

## Quatre statuts, et aucun mensonge

Chaque référence Premibel porte `materialFidelity` :

| statut | sens |
| --- | --- |
| `exact` | matière construite sur la photo du produit lui-même, validée |
| `representative` | matière générique proche (une des familles procédurales) |
| `preview_only` | vignette disponible, aucune matière rendable |
| `unavailable` | ni vignette ni matière |

« Exact » n'est jamais écrit à la main dans la page : le moteur le confirme au
démarrage, seulement si l'atlas de la matière est réellement servi
(`loadExactMaterials`, `web/product/local-renderer.js`). Les atlas dérivent de
photos dont la redistribution n'est pas établie : ils ne sont **pas
versionnés**. Dans un clone sans eux, le produit reste `representative`.

Une référence sans aperçu reste au catalogue ; au clic, une fiche légère
(« Aperçu 3D bientôt disponible », lien vers la fiche) — jamais une matière
inventée.

## Sources disponibles (inventaire du 13 octobre 2026)

`python -m scripts.premibel_asset_inventory` → `review/premibel-materials/inventory.md`.

* 382 vignettes commerciales de 324 px, exportées de la boutique ;
* l'export ne fournit **aucun** échantillon, aucune carte de matière, aucune
  variante de lame (0 sur 395) ;
* 15 vignettes sont des gros plans de lames, les autres des ambiances ;
* 5 images plus grandes (500 à 900 px) pour les produits du catalogue de
  démonstration.

Rien n'a été téléchargé pour ce lot.

## Pipeline d'import

1. Annoter les zones de bois dans `web/data/materials/premibel-sources.json`
   (quadrilatères le long des lames, ou lames entières de dimensions
   connues).
2. `python -m scripts.import_premibel_material [ID…]` : redressement (focale
   résolue ou supposée à 60°, fuite mesurée sur les ambiances), joints longs
   et de bout détectés, morceaux contenant un joint écartés, lumière égalisée
   le long de la lame, luminosité des lames resserrée à ±10 %, atlas à
   0,6 px/mm.
3. Validation : ≥ 0,3 px/mm au bord le plus lointain, ≥ 4 morceaux, ≥ 1,5 m de
   bois et au moins une longueur de lame. Sinon le produit reste
   représentatif, avec sa raison dans `web/data/materials/premibel/index.json`.
4. Revue : `review/premibel-materials/extraction/<id>.jpg`, puis
   `node tools/premibel-materials.capture.mjs` et
   `python -m scripts.premibel_material_review` pour les planches.

Dans le moteur, une matière exacte remplit chaque lame d'une vraie bande de
bois de l'atlas (`lameAtlas`, `web/scene/texture.js`) : rangée, départ et
retournements tirés au sort, étirement le long du fil jusqu'à 2×, miroir
au-delà. Joint, chanfrein et reflet de finition restent ceux du moteur.

## Vitesse

* **Tuile exacte** : quelques centaines de `drawImage` au lieu de 34 000 à
  74 000 tracés — 0,5 à 1,2 s à froid contre 1,6 à 5,4 s.
* **Préchargement du catalogue** : les cartes visibles (8 au plus) préparent
  leur matière en temps mort, une à la fois ; une demande de l'utilisateur,
  ou l'ouverture d'une pièce, le suspend.
* **Pièces** : l'éclairement se calcule dans un worker (la page ne gèle
  plus) ; les flous des cartes de résidus sont des sommes glissantes (même
  résultat, écart maximal 0) ; les scènes visibles d'une catégorie ouverte
  sont préparées d'avance.
* **GPU** : les quatre dernières matières gardent leurs textures ; revenir à
  un produit ne renvoie rien au GPU.

## Cache entre sessions (IndexedDB) : recommandé, pas encore fait

Une tuile coûte 13 Mo bruts (albédo + relief, 1280²), ~0,3 à 0,6 Mo en WebP.
Gain attendu pour un visiteur qui revient : une matière procédurale froide
passerait de 1,6–5,4 s à ~0,2 s de décodage. Invalidation simple : clé =
identifiant de matière + motif + largeur + longueur + empreinte de la
définition + version du générateur de tuiles. Non implémenté dans ce lot : le
préchargement couvre déjà les cartes visibles, et le stockage (quota,
navigation privée, nettoyage) mérite son propre lot et ses tests.
