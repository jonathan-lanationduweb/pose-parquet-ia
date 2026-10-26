# Projection métrique du sol — conventions et revue

État : READY_FOR_HUMAN_VISUAL_REVIEW.

Activation : tools/product-concept.html (projection métrique par défaut).
Les captures historiques ne servent plus de repli sur cette page : leur calibration diffère.
dev=1&renderer=legacy permet une comparaison explicite.
Backend, masques source, occluders, catalogue et modèles non modifiés.

## ROOT CAUSE

Le rendu précédent rastérisait une boîte image et inversait une homographie dans
le fragment. Une homographie de plan n'est pas intrinsèquement incorrecte, mais
les conventions caméra et l'échelle restaient implicites. L'arrondi des périodes
de texture modifiait les dimensions physiques. Le prototype V3 avait aussi un
défaut de branchement : uPhysical n'était pas envoyé au shader principal, bien
que sa fonction isolée soit testée.

## CAMERA MODEL

CameraModel est l'autorité CPU pour K, R, C, rayons et projection.
+X droite, +Y bas, +Z avant ; origine image en haut à gauche.
La vue est [R | -RC]. Matrices CPU row-major ; columnMajor change le stockage
pour WebGL. La projection inverse Y, transforme Z vers [-1,1], avec W = Z caméra.
K = [fx skew cx ; 0 fy cy ; 0 0 1].
Rotations non orthonormales ou réfléchies refusées.
resized redimensionne K sans changer la caméra physique.

Le compilateur adapte la géométrie déjà fournie par les scènes : décomposition
du plan existant et orthogonalisation de ses directions. Ce n'est ni un nouveau
CameraSolver ni une mesure réelle de la pièce. Une hauteur manquante reste une
hypothèse explicite de 1,5 m, avec statut dégradé.

## FLOOR PLANE

Plan orthonormal en mètres : P = origine + u × axeU + v × axeV.
L'origine du carré de référence est conservée pour la phase des zones continues ;
elle n'est pas le pied de la caméra. L'échelle absolue reste inconnue sans mesure.
Les étendues visibles calculées ne sont pas les dimensions mesurées de la pièce.

## VIEW TRANSFORM

ViewTransform fournit imageToViewport et viewportToImage, avec leurs alias
existants. Photo, rendus, overlays et pinceau partagent cette transformation.
Cover reste le choix du produit ; le cadrage complet utilise contain.
Zoom et recadrage ne modifient jamais la calibration.

## WEBGL

metric-runtime restaure les classes hors de SceneData sérialisable.
Un quad est l'AABB locale de l'intersection frustum/sol, trouvée par les douze
arêtes du frustum. Quatre sommets envoyés une fois par zone.
Le vertex calcule le point monde puis uViewProj × vec4(world,1).
Les coordonnées métriques sont interpolées en perspective.

Le fragment reprojette le point monde dans la caméra source pour les masques et
cartes lumière. Le viewport ne définit pas la position du masque.
La première version bornait tout le frustum : ses grands triangles produisaient
une erreur raster de 0,62 px. L'intersection avec le sol ramène le maximum testé
à 0,101 px, sans correction image-space.
Produit/angle ne reconstruisent pas le quad ; une nouvelle photo vide le cache.
Canvas utilise la même caméra via la forme analytique K[RU RV R(O-C)].

## PATTERNS

world-pattern définit cellules métriques, identifiant de lame, coordonnées
locales, orientation et distance aux joints. La texture fournit l'apparence.
Lames : dimensions métriques, décalage alterné d'une demi-longueur.
Point de Hongrie : bras à angle physique, coupes verticales et largeur normale.
Bâton rompu : rectangles orthogonaux et recherche bornée de la lame.
Joints : largeur en mètres, filtrage selon l'empreinte du pixel ; convergence
vers leur aire moyenne au fond pour éviter les bandes sombres.
Les joints déjà présents dans les textures ne sont pas supprimés.
Aucun réglage de motif ne recalcule K, R, C ou le plan.

## VALIDATION

Seuils nommés : horizon, hauteur, étendue visible, couverture et échelle projetée.
Le contrôle transversal au regard doit suivre 1/profondeur.
L'horizon scalaire fourni est comparé au point principal.
Couverture échantillonnée dans l'enveloppe convexe du contour, moins les objets
connus : ni pourcentage de toute la photo, ni preuve de segmentation correcte.

reliable permet le rendu, sous réserve du contrôle d'analyse déjà existant.
degraded affiche le rendu, « Sol détecté approximativement » et l'ajustement.
failed masque le rendu automatique et propose le parcours manuel existant.
Le pinceau corrige le masque, pas la caméra. Le fallback manuel réutilise sa
perspective approximative existante, annoncée comme telle.
La couverture calculée à la compilation ne revalide pas chaque coup de pinceau.

## PERFORMANCE

Chrome sur ce PC, matières préparées, trois familles. Ni analyse IA ni première
fabrication de matière incluses. Aucun benchmark sur téléphone physique.

| Viewport | Produit préchargé, médiane | Rotation, médiane | Cache image |
| --- | ---: | ---: | ---: |
| 1440 px | 61,6 ms | 45,3 ms | 0,1 ms |
| 390 px | 47,9 ms | 22,4 ms | 0,1 ms |

Un quad par zone, conservé pendant les changements produit/angle.

## VISUAL REVIEW

Revue privée : review/floor-projection-metric/index.html, hors Git.
Neuf scènes WebGL et trois Canvas : salons Premibel, piano, chambres, grande
pièce, terrasse, couloir, appartement ancien et photo privée avec tapis.
Original, contour, grille, trois motifs, final et comparaison historique.

Échelle et continuité métrique améliorées. Masques et lumière inchangés.
Quatre scènes à revoir : salon Premibel (étendue), chambre parisienne
(estimation), couloir (horizon, 21 px), appartement ancien (estimation).
Le couloir est refusé par le nouveau contrôle des directions architecturales.
Les trous sous le meuble TV et contours en escalier restent dans le masque source.

## TESTS

CameraModel, FloorPlane, ViewTransform, validateGeometry, cellules métriques,
GPU caméra, raster masque, parité cellules GPU, vrai branchement des uniforms,
conservation du quad, UX géométrie et mobile.
660 projections GPU ; 17 404 points raster ; 4 600 cellules GPU ;
4 608 apparences GPU ; 40 000 points de couverture bâton rompu.
Trois familles, 90/150 mm et angles 0/90/359 sur desktop/mobile.

Non-régression : product-concept, scene-engine, room-library, rooms-render-flow,
surface-product-compatibility, material-cache, occlusion-compositing et
occlusion-mobile. Aucun écart sur les pixels hors masque effectif sondés dans le banc
comparatif des neuf scènes WebGL et trois Canvas.

Revue reproductible : metric-floor-review.check.mjs,
metric-floor-performance.check.mjs et metric-review-report.mjs dans tools/.
Serveur local et PPAI_PLAYWRIGHT_CORE requis. Les cas privés nécessitent les
fichiers privés déjà présents localement.

## FILES

Noyau : camera-model, floor-plane, metric-runtime, geometry-validation.
Adaptation : floor-projection, geometry, renderer-gl, renderer-canvas, renderer,
world-pattern. Interface : local-renderer, view-transform, geometry-review,
product-concept. Tests JS, générateur de revue privée et cette documentation.

## LIMITATIONS

Calibration amont estimée ; pas d'échelle absolue garantie avec une seule photo.
Masques non améliorés par cette mission. Certaines textures représentatives.
Canvas plus lent. Les cas proches de l'horizon sont limités par le frustum
de rendu de 200 m. Les garde-fous ne prouvent pas le photoréalisme ni une
équivalence avec un simulateur tiers. Validation finale humaine.

## VERDICT

READY_FOR_HUMAN_VISUAL_REVIEW.
## Contrôle visuel — mise à jour du 26 octobre 2026

La cohérence interne du modèle (horizon et loi 1/profondeur) ne détecte pas
une orientation incorrecte par rapport à la photo. Le contrôle compare désormais
les deux familles de directions aux points de fuite déclarés, en plusieurs
positions du sol : <= 2 degrés sans alerte, entre 2 et 8 degrés approximatif,
au-delà de 8 degrés refus automatique. Les axes permutés et les fuites à
l'infini sont pris en charge. Sans deux directions disponibles : approximatif.
Ces seuils sont des garde-fous, pas une preuve de fidélité photographique.
La qualité des points de fuite fournis reste à vérifier humainement.

Les décisions exposées sont AUTO_RENDER, APPROXIMATE et MANUAL_REQUIRED.
Le statut concerne la géométrie ; la segmentation conserve ses propres contrôles.
Une largeur de 90 mm reste fondée sur une hauteur supposée, sans mesure réelle.

Le diagnostic de grille utilise maintenant le masque effectif du rendu, donc
ses trous, les meubles protégés et les corrections du pinceau.

Captures avant/après renouvelées : neuf scènes WebGL et trois scènes Canvas,
original, grille et trois motifs. Le cas refusé conserve la photo originale.
Les pixels sondés hors sol restent protégés. Tests des clics rapides, cache
photo et corrections mobiles exécutés. Le test de changement de produit sur
photo utilise une réponse d'analyse privée enregistrée : il ne mesure pas la
vitesse ni la qualité du service IA à froid.

Constat visuel : contours en escalier et manques sous le meuble TV toujours
visibles dans la photo privée ; matière et ombres ne suffisent pas à les masquer.
Aucun changement de texture n'a été tenté pour compenser ces défauts. Le pinceau
ne corrige pas une caméra erronée. Le résultat global demandé reste non validé.
La revue locale est review/floor-projection-metric/index.html ; elle reste privée.
Sur la page habituelle, contrôles de cadrage à 1440×900, 390×844,
844×390 et 900×1440 : même frame et même calibration avant/après resize,
transformations photo/canvas identiques, pas de débordement horizontal.
La photo affichée peut être une miniature de résolution différente ; l'écart
de ratio est contrôlé à moins de 0,5 pixel dans la photo source.
En paysage sur téléphone, le cadrage initial privilégie maintenant le sol et
la barre reste compacte. Un geste volontaire de zoom/déplacement reste prioritaire.
Test reproductible : tools/visual-quality.check.mjs.