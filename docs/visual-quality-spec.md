# Spécification de qualité visuelle S1–S8

Version 1 — 27 octobre 2026. Sol uniquement.
Roomvo est une référence de qualité perçue, sans accès à son code, ses
algorithmes ou son infrastructure. Une référence visuelle absente reste absente.

La question de validation est : « Le parquet semble-t-il présent dans la pièce
avant la prise de vue ? » Une frame, un shader compilé et des tests verts
ne répondent pas à cette question.

## Grille officielle

| Critère | PASS visuel | Écarts à relever | Diagnostic |
|---|---|---|---|
| S1 Perspective | Fuites cohérentes avec plinthes, murs et seuils | Convergence indépendante, inclinaison, flottement | D3, D6 ; vraie grille CameraModel/FloorPlane |
| S2 Échelle | Dimensions produit plausibles et progression near/mid/far naturelle | Explosion, écrasement, plateau ; comparaison porte/meuble | D4, D9 ; dimensions en mètres et grille |
| S3 Encadrement | Arrêt au vrai contact sol/plinthe, baie, seuil et renfoncement | Débordement, retrait, ancien sol visible, frontière inventée | D1, D8 ; floorMask et sol neutre |
| S4 Occlusions | Objets, pieds, tapis et câbles visibles devant le sol | Objet repeint, pied supprimé, découpe grossière ou masque périmé | D2, D8 ; occluderMask, sampling, compositing |
| S5 Lumière | Grandes lumières, ombres et contacts cohérents, identité produit conservée | Lumière indépendante, ancien grain réinjecté, couleur détruite | D7 ; original, neutre, matériau éclairé/non éclairé |
| S6 Finition | Réponse cohérente avec données produit et référence disponibles | Reflets inventés ou finition non documentée | Matériau/lumière ; NOT_EVALUABLE sans données suffisantes |
| S7 Matière | Grain, nœuds, diversité et joints naturels, variation stable | Papier peint, répétition, étirement ou flou | Source produit, atlas, cellules et rendu sans lumière |
| S8 Transitions | Bords naturels selon résolution et couverture réelle | Marches, halo, bord clair/noir ou découpe dure | D8 ; crops et alpha source, sans blur systématique |

190 mm signifie 0,190 m. Aucun nombre arbitraire de lames ne remplace un
critère physique. L'échelle basée sur une hauteur de caméra supposée n'est pas
une mesure de la pièce, même si sa plausibilité visuelle est notée PASS.

Statuts : PASS, PARTIAL, FAIL, NOT_EVALUABLE.
Sévérités : MINOR, MODERATE, SEVERE, BLOCKING.
Chaque statut exige une observation et un périmètre. Un critère PASS est
conservé lors de la correction d'un autre critère.

## Protocole

1. Original, rendu actuel, rapport initial S1–S8.
2. Grille réelle ; ne pas travailler matière/lumière sur une géométrie rejetée.
3. Masques : sol vert, objets rouges, recouvrement violet permis.
4. Sol neutre avec géométrie/masques/lumière identiques, sans grain de bois.
5. Matériau sans lumière comparé au rendu éclairé.
6. Cellules, joints et orientation du motif si nécessaire.
7. Localiser le premier étage incorrect, démontrer la cause et le test.
8. Corriger une ou deux familles de critères à la fois ; S8 peut accompagner
   localement S3/S4.
9. Capturer avant/après à caméra, plan, produit, motif, angle et viewport fixes.
10. Rejouer la matrice et conserver les critères précédemment PASS.

Ordre : S1 -> S2 -> S3 -> S4 -> S5 -> S6 -> S7 -> S8.
Ne pas compenser une limite de segmentation par un changement de focale,
de motif, de matière ou d'éclairage. Pas d'exception par nom de photo.

## Rapports et revue humaine

Le module web/product/visual-quality-report.js valide les huit observations,
les statuts/sévérités, les confirmedCorrect et les notes subjectives /5.
Il n'infère pas un PASS de l'absence d'erreur console.
Un critère critique S1/S2/S4 partiel ou une note < 4 recommande APPROXIMATE.
Une géométrie rejetée recommande MANUAL_REQUIRED.
HUMAN_REVIEW_REQUIRED n'est jamais un certificat AUTO_RENDER.

Le rapport distingue la décision technique de géométrie et l'avis de revue
visuelle. L'avis est actuellement un artefact de revue, pas un override
automatique de la production fondé sur des notes subjectives.
Les mécanismes existants backend approximate_render et frontend MANUAL_REQUIRED
restent en place ; le couloir rejeté n'affiche pas de nouveau parquet.

Notes internes : Perspective, Scale, Boundary, Occlusion, Lighting, Material,
Overall /5. Elles comparent des versions ; ce ne sont pas des métriques
scientifiques. Les notes de cette mission sont une pré-revue par l'assistant,
pas une validation humaine indépendante. Le test des trois secondes doit
être confirmé par une personne, sur FINAL seul.

S6 est NOT_EVALUABLE dans la présente matrice : les paramètres de rendu
existants et les libellés commerciaux ne fournissent pas une BRDF fabricant.
S7 reste PARTIAL : une amélioration de masque n'autorise pas à certifier
l'identité matière. Les répétitions demandent une revue source/atlas dédiée
après les premiers étages. Aucun nouveau modèle ni recherche depth ici.

## Pack et matrice

Dossier privé ignoré : review/visual-quality-s1-s8/<scene>/.

- 01-original.jpg, 02-current.jpg, 03-grid.jpg, 04-masks.jpg.
- 05-neutral.jpg, 06-no-lighting.jpg, 07-final.jpg.
- Motif projeté / à plat lorsque disponible.
- crops/near.jpg (bas ~30 %), mid.jpg, far.jpg, objects.jpg, boundary.jpg.
- Comparaisons des mêmes crops avant/après.
- visual-report-before.json, visual-report.json, visual-report-mobile.json,
  visual-report.txt.
- Métadonnées : caméra, plan, dimensions, masque, viewport et ViewTransform.

Un rendu bloqué conserve l'original et ne fabrique pas de sol neutre ou de
matériau non éclairé. availableImages indique explicitement ces absences.
Une référence Roomvo privée n'est ajoutée que si elle est fournie.

Couverture : pièce vide, profondeur, canapé, table/pieds fins, tapis, chambre,
intérieur sombre, lumière forte, forte perspective, photo réelle difficile,
terrasse. Comparaison 1440 et 390. Canvas est contrôlé comme fallback, sans
réduire les capacités WebGL.

L'index natif HTML/JS permet de consulter original/avant/après, sélectionner
une couche et comparer les crops. Les tableaux défilent dans leur conteneur
sur téléphone ; l'index ne déborde pas de la page.

## Corrections et preuves de cette version

1. S3/S4/S8, D1/D2/D8 : les anciens contours OpenCV décrivaient des centres de
   pixels, alors que Canvas remplit des surfaces entre sommets. La conversion
   perdait partiellement la couverture des cellules du masque.
   mask_contours.cell_polygons trace leurs vrais bords, conserve trous,
   composantes diagonales, supports d'un pixel et îlots. Pas de dilation.
   rectangle : 66 pixels de couverture erronée avant, 0 après ; trou : 165 -> 0 ;
   diagonale : 76 -> 0 ; bord image : 39 -> 0. Cas aléatoire également exact.
2. S4/S8, D8 : la décision binaire de l'affineur convertissait un alpha observé
   64/191 en 0/255. La projection couleur entre graines avant/arrière fiables
   restitue 63/191, avec garde de contraste/résidu. Les zones ambiguës gardent
   le prior, les branches fines restent protégées. Aucun flou de tout le masque.

Ces correctifs ne reconstruisent pas un objet absent de la segmentation.
Sous le meuble TV privé, la forme grossière issue de la source reste visible :
S3/S4/S8 restent PARTIAL. L'alpha n'est pas un pipeline complet d'unmixing des
couleurs de premier plan ; il ne garantit pas la suppression de tout halo.
Les gains inspectés sur les pieds de chaises/canapé restent locaux.

La lumière, les cellules du motif, CameraModel, FloorPlane et les solveurs
de perspective n'ont pas été modifiés. Les statistiques d'éclairement
dépendent déjà du masque, donc modifier la couverture peut modifier le gain
lumineux sans changement d'algorithme.

## Résultat de la matrice

P = PASS ; ~ = PARTIAL ; F = FAIL ; N/E = NOT_EVALUABLE.
Une note identique peut cacher un gain local ; les observations et crops
priment sur le nombre de cases vertes.

| Scène | S1 | S2 | S3 | S4 | S5 | S6 | S7 | S8 |
|---|---|---|---|---|---|---|---|---|
| Chambre dégagée | P | P | ~ | P | P | N/E | ~ | ~ |
| Grande pièce / console | P | P | P | ~ | P | N/E | ~ | ~ |
| Canapé | P | P | ~ | ~ | ~ | N/E | ~ | ~ |
| Table / pieds fins | P | P | P | ~ | P | N/E | ~ | ~ |
| Piano / tapis | P | P | ~ | P | ~ | N/E | ~ | ~ |
| Chambre / lit | P | P | ~ | P | ~ | N/E | ~ | ~ |
| Salon d'angle sombre | P | P | P | P | P | N/E | ~ | P |
| Séjour très lumineux | P | P | P | P | P | N/E | ~ | P |
| Couloir rejeté | F | N/E | N/E | N/E | N/E | N/E | N/E | N/E |
| Photo réelle difficile | P | P | ~ | ~ | ~ | N/E | ~ | ~ |
| Terrasse | P | P | P | P | P | N/E | ~ | P |

Les écarts les plus récurrents sont les contacts/masques (S3/S4/S8) et la
matière encore répétitive (S7). Cette itération corrige deux causes centrales
de la première famille, avant toute optimisation spéculative de la matière.
Le cas privé ne devient pas PASS. Le couloir reste un témoin négatif.

## Vérifications et performance

40 tests pytest ciblés ; couverture Python -> Canvas sur six masques ;
alpha mixte ; rapport strict ; sol neutre WebGL/Canvas ; diagnostics normaux
inchangés ; 12 configurations d'occlusion DPR/resize ; retouches mobiles ;
660 sondes GPU caméra et 4600 cellules/joints/AA ; 11 rapports complets.
Aucun PASS initial rétrogradé. Projection normalisée desktop/mobile :
erreur maximale mesurée 7,4e-13 pixel source (sondes), pas un score esthétique.

Chrome local, 12 actions ; caches documentés. Le premier rendu de scène
mesuré est 481,9 ms, hors démarrage réseau/modèle.

| Action | Médiane ms | p95 ms | Max ms |
|---|---:|---:|---:|
| Changer de produit | 2,6 | 242,1 | 242,1 |
| Rotation | 4,9 | 6,2 | 6,2 |
| Changer de pièce | 30,2 | 249,9 | 249,9 |

6 changements de produit sur 12 sont des hits cache. Changements de pièce :
mélange de préparation et de retour en cache. Échantillon court : p95 = max.
Ces mesures ne sont pas des promesses de latence sur téléphone.

Scripts : build_s1_s8_review.py, s1-s8-review.check.mjs,
s1-s8-performance.check.mjs. Les captures utilisent capture-defect-pack.mjs,
étendu avec le neutre ; les outils existants ne sont pas remplacés.

Verdict : **S1_S8_VISUAL_QUALITY_READY_FOR_HUMAN_REVIEW** pour cette itération
et ses gains locaux démontrés. Ni certification Roomvo ni acceptation finale
de toutes les scènes. Branche locale feature/visual-quality-s1-s8 ; push = NON.
