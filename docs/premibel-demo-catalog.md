# Mini-catalogue Premibel de démonstration

Cinq références Premibel réelles, relevées à la main pour une revue visuelle
du prototype `tools/product-concept.html`. Ce n'est pas une intégration
catalogue : pas d'API, pas de crawl, pas de scraper. Cinq fiches ouvertes dans
un navigateur, cinq relevés.

**Premibel n'a été que consulté.** Aucune écriture, aucune requête
automatisée répétée, aucun prix relevé — pose-parquet.com reste éditorial.

---

## 1. Ce qui a été vérifié, et ce qui a changé

Relevé le **8 septembre 2026**, sur les fiches en ligne, bandeau cookies
refusé (« Tout refuser »).

Sur les cinq références demandées, **quatre existent telles quelles**. La
cinquième a dû être remplacée :

| demandé | état au 8 septembre 2026 |
|---|---|
| `BTRPF39008` — « Bâton rompu Piccadilly Naturel » | **introuvable.** `…/BTRPF39008/` renvoie « Page non trouvée », et la recherche interne donne « Résultats pour « piccadilly » (0 produits) ». |

Remplacé par le bâton rompu réel le plus proche de la demande (chêne
contrecollé verni, **90 mm** comme demandé) :

`BTRPF39009` — « Baton rompu notting hill invisible 90X15X600mm ».

Ce choix est le nôtre, il n'est pas une donnée Premibel.

Une autre incohérence est laissée telle quelle, côté source :

> `CHENF39031` s'intitule « Chêne naturel houston 190X15X400mm » alors que son
> tableau de spécifications indique **Longueur : 1900mm**. Nous consignons les
> deux sans trancher : le nom commercial et le tableau ne disent pas la même
> chose, et ce n'est pas à nous d'arbitrer.

---

## 2. Les cinq produits

Colonnes relevées sur le tableau de spécifications de chaque fiche
(`Essence`, `Largeur`, `Longueur`, `Épaisseur`, `Finition`, `Aspect`,
`Famille`, `Chanfrein`) et sur le JSON-LD (`name`, `#primaryimage`,
`canonical`).

### A — POINF36005 · Point de Hongrie Zeus Naturel

| | |
|---|---|
| titre de la fiche | POINT DE HONGRIE ZEUS NATUREL 92X12X520 |
| référence | `POINF36005` |
| URL | https://www.premibel.fr/parquet-flottant-chene-verni/POINF36005/ |
| canonique | https://www.premibel.fr/parquet-flottant-chene-verni/POINF36005 |
| image source | https://www.premibel.fr/wp-content/uploads/2026/07/POINF36005.jpg (500 × 500) |
| essence | Chêne |
| motif | Point de Hongrie |
| largeur | 92 mm |
| longueur | 520 mm |
| épaisseur | 12 mm |
| finition | Verni |
| aspect | Brossé |
| chanfrein | 4 chanfreins |
| famille Premibel | FLCHEN08 |
| vérifié le | 2026-09-08 |

La légende de l'image ajoute : « POINT DE HONGRIE 45° CHENE CONTRECOLLE VERNI
BROSSE RUSTIQUE ZEUS NATUREL 92X12X520mm GO-4 — 2,5mm de couche d'usure ».

### B — BTRPF39009 · Bâton rompu Notting Hill Invisible

| | |
|---|---|
| titre de la fiche | Baton rompu notting hill invisible 90X15X600mm |
| référence | `BTRPF39009` |
| URL | https://www.premibel.fr/parquet-flottant-chene-verni/BTRPF39009/ |
| image source | https://www.premibel.fr/wp-content/uploads/2026/04/BTRPF39009.png (800 × 1200) |
| essence | Chêne |
| motif | Bâton rompu |
| largeur | 90 mm |
| longueur | 600 mm |
| épaisseur | 15 mm |
| finition | Verni |
| aspect | Brossé |
| chanfrein | 4 chanfreins |
| famille Premibel | FLCHEN08 |
| vérifié le | 2026-09-08 |
| note | **substitution** de `BTRPF39008` / Piccadilly, introuvable |

### C — CHENF39031 · Chêne naturel Houston

| | |
|---|---|
| titre de la fiche | Chêne naturel houston 190X15X400mm |
| référence | `CHENF39031` |
| URL | https://www.premibel.fr/parquet-flottant-chene-verni/CHENF39031/ |
| image source | https://www.premibel.fr/wp-content/uploads/2025/11/CHENF39031.jpg (500 × 582) |
| essence | Chêne |
| motif | Lames |
| largeur | 190 mm |
| longueur | 1900 mm au tableau, « 400mm » dans le titre — non arbitré |
| épaisseur | 15 mm |
| finition | Verni |
| aspect | Brossé, Satiné |
| famille Premibel | FLCHEN08 |
| vérifié le | 2026-09-08 |

### D — CHENF36014 · Chêne Colza

| | |
|---|---|
| titre de la fiche | CHENE COLZA 150X15 |
| référence | `CHENF36014` |
| URL | https://www.premibel.fr/parquet-flottant-chene-verni/CHENF36014/ |
| image source | https://www.premibel.fr/wp-content/uploads/2026/07/CHENF36014.jpg (900 × 675) |
| essence | Chêne |
| motif | Lames |
| largeur | 150 mm |
| longueur | 1900 mm |
| épaisseur | 15 mm |
| finition | Verni |
| aspect | Brossé, Mat |
| chanfrein | 4 chanfreins |
| famille Premibel | FLCHEN08 |
| vérifié le | 2026-09-08 |

### E — CHENF36015 · Chêne Invisible Pivoine

| | |
|---|---|
| titre de la fiche | CHENE INVISIBLE PIVOINE 150X15 |
| référence | `CHENF36015` |
| URL | https://www.premibel.fr/parquet-flottant-chene-verni/CHENF36015/ |
| image source | https://www.premibel.fr/wp-content/uploads/2026/07/CHENF36015.jpg (800 × 600) |
| essence | Chêne |
| motif | Lames |
| largeur | 150 mm |
| longueur | 1900 mm |
| épaisseur | 15 mm |
| finition | Verni |
| aspect | Brossé, Mat |
| chanfrein | 4 chanfreins |
| famille Premibel | FLCHEN08 |
| vérifié le | 2026-09-08 |

---

## 3. Mappage avec le vrai moteur de rendu

### D'où vient le mappage

Le front avait déjà commencé le travail :
`pose-parquet.com/data/products.premibel-pilot.json`, relevé du 3 septembre
2026, 14 références réelles, chacune avec un `visual.familyId` pointant vers
`data/render-families.json`. Sa propre note de provenance est sans ambiguïté :

> `familyId` : **CHOIX ÉDITORIAL de notre côté**, fait en regardant les photos
> produit. La teinte n'est pas toujours catégorisée chez Premibel, et un nom
> commercial (« Colza », « Artemis ») ne dit pas une teinte. Ces affectations
> sont à faire valider par Premibel.

Quatre de nos cinq produits y figurent, et nous reprenons son choix.
`CHENF39031` (Houston) n'y est pas : son affectation est **la nôtre**, faite
de la même manière, et elle vaut donc encore moins qu'un choix validé.

### Ce que le moteur sait faire exactement, et ce qu'il approxime

| attribut | statut | pourquoi |
|---|---|---|
| motif | **exact** | `lames`, `point-de-hongrie` et `baton-rompu` sont les trois motifs du moteur (`KNOWN_PATTERNS`), et ce sont exactement les trois de nos produits. |
| largeur de lame | **exact** | le moteur accepte une largeur en mètres (`config.width`, sinon `boardWidth` du matériau) et calcule le motif dans le plan du sol : 92 mm font 92 mm au premier plan comme au fond. |
| sens de pose | **exact** | `config.angle`. |
| teinte, veinage, nœuds, contraste | **approché** | la texture vient d'une famille de démonstration de `data/parquets.json`, dont l'en-tête dit `source: "demonstration"`. Ce ne sont pas les paramètres Premibel. |
| finition | **approché** | la famille porte une finition (« Vernis mat », « Huilé miel »…) qui n'est pas forcément celle du produit. Nos cinq produits sont tous `Verni`. |
| albédo, normale, rugosité du produit | **indisponible** | `visual.albedo`, `visual.normal`, `visual.roughness` sont `null` pour les 14 références du pilote. Le moteur n'a aucune texture Premibel. |

### Conclusion, produit par produit

Aucun mappage n'est **EXACT**, et il serait malhonnête de l'écrire : la
géométrie est juste, la matière ne l'est pas.

| produit | famille de rendu | motif | largeur | statut | origine du choix |
|---|---|---|---|---|---|
| POINF36005 Zeus Naturel | `chene-sable` | point-de-hongrie | 92 mm | **APPROXIMATE** | pilote du front |
| BTRPF39009 Notting Hill | `chene-craie` | baton-rompu | 90 mm | **APPROXIMATE** | pilote du front |
| CHENF39031 Houston | `chene-naturel` | lames | 190 mm | **APPROXIMATE** | le nôtre, non validé |
| CHENF36014 Colza | `chene-sable` | lames | 150 mm | **APPROXIMATE** | pilote du front |
| CHENF36015 Pivoine | `chene-rustique` | lames | 150 mm | **APPROXIMATE** | pilote du front |

Récapitulatif : **exact 0 · approximate 5 · unavailable 0**.

Le code porte cette nuance dans `visualAccuracy: 'approximate'` sur chaque
produit, et l'interface parle donc d'« aperçu », jamais de « voici exactement
ce produit chez vous ».

**Avant qu'un rendu soit présenté au public comme fidèle à une référence
Premibel, il faudra les vraies textures ou les vrais paramètres de matière
Premibel, et la validation de leurs affectations.**

---

## 4. Images et rendus : où ils vivent

### Deux images par produit

Aucune des cinq fiches n'a de **vignette matière dédiée** : chacune n'a qu'une
image, et c'est une photo d'ambiance. Vérifié fiche par fiche, galerie par
galerie, dans un navigateur.

Il en faut pourtant une pour la carte du catalogue — on doit reconnaître le
bois avant de lire le nom. Quatre de ces photos montrent un gros plan net du
vrai sol au premier plan : la vignette y est découpée. La cinquième montre son
sol de loin, derrière un tapis et un canapé, donc découpage de notre rendu.

| référence | `catalogThumbnailSource` | découpé dans |
|---|---|---|
| POINF36005 | `premibel_photo_crop` | sa photo Premibel, chevron au premier plan |
| BTRPF39009 | `premibel_photo_crop` | sa photo Premibel, bâton rompu au premier plan |
| CHENF39031 | `renderer_crop` | notre rendu `sejour.CHENF39031` — sa fiche ne montre pas le sol de près |
| CHENF36014 | `premibel_photo_crop` | sa photo Premibel, lames larges au premier plan |
| CHENF36015 | `premibel_photo_crop` | sa photo Premibel, lames larges au premier plan |

Total : **4 découpages de photo Premibel, 1 de notre rendu.** Rien n'est
fabriqué, et `heroImage` garde la photo d'ambiance complète pour le contexte
de la fiche.

| quoi | où | dans Git ? |
|---|---|---|
| images produit Premibel | `tools/local-demo-assets/premibel/<REF>.jpg\|png` | **non** — ce ne sont pas nos images |
| vignettes matière | `tools/local-demo-assets/premibel/thumb.<REF>.jpg` | **non** — dérivées des précédentes |
| rendus des scènes | `tools/local-demo-assets/renderings/<scene>.<REF>.jpg` | **non** — ils dérivent de photos non redistribuables |
| métadonnées (nom, réf, URL, propriétés, mappage, date) | `tools/product-concept.html` et ce document | **oui** |

Les binaires ne sont ni versionnés, ni encodés en base64, ni hotlinkés depuis
l'interface : la maquette lit le cache local. Sur un clone frais, sans ces
dossiers, elle affiche un cadre de remplacement propre pour la vignette et la
photo d'origine pour la pièce — jamais un faux parquet.

Les rendus sont produits par le Visualiseur du front, servi en local et piloté
par son point d'accroche `window.__studio` (que `?perf=1` expose). Empreinte du
moteur utilisé : `assets/dist/9685ef637e`.

---

## 5. Ce que ce lot n'est pas

* Pas une intégration catalogue. Cinq produits saisis à la main.
* Pas un scraper : aucune boucle sur le catalogue, aucun appel d'API, une
  seule image par produit.
* Pas un tarif : aucun prix, aucune remise, aucune promotion, aucun stock.
* Pas une validation. Les affectations de famille de rendu restent à faire
  valider par Premibel.
