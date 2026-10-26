# Diagnostic visuel du parquet

Objectif : observer → classer → isoler → tester → confirmer → corriger → vérifier → archiver.
Ces outils n'attribuent pas automatiquement une cause ou un verdict de réalisme.

## Ouvrir les couches

Ouvrir /tools/product-concept.html?dev=1, choisir une pièce et déplier **Diagnostic DEV**.
Les six cases sont indépendantes : Grille 50 cm, Masques, Caméra, Plan du sol,
Échelle et IDs/joints. Toutes sont décochées au départ. Le bouton « Comparer
sans lumière » produit une image du même moteur sans modulation lumineuse ;
« Rétablir les overlays » rétablit les couches sélectionnées.

La page normale ne charge pas les modules d'overlays. La branche GLSL sans
lumière est compilée uniquement avec dev=1. Ni nouvelle IA, ni dépendance front.
Le mode DEV est une convention de diagnostic, pas une authentification.

- **Grid** : intersections de lignes tous les 0,5 m, mêmes instances CameraModel /
  FloorPlane et même projection que le rendu ; masque effectif, trous et retouches
  inclus. Si la calibration manque, aucune grille de remplacement n'est inventée.
- **Masks** : sol vert, objets rouges, recouvrement violet. Le violet est normal
  lorsque le plancher continue sous un meuble ; il ne prouve pas une erreur.
  Les PNG bruts conservent les valeurs de couverture à résolution source.
- **Camera** : horizon et VP projetés par la caméra du renderer, pas recopiés
  depuis les estimations amont. Les VP hors champ sont signalés ; leurs vraies
  coordonnées homogènes figurent dans metadata.json.
- **FloorPlane** : origine et axes U/V de 1 m. Une origine hors champ n'est pas
  déplacée pour embellir l'image.
- **Scale** : dimensions du profil réellement affiché, multiplicateur, largeur
  projetée near/mid/far, normale à la lame réelle du motif. L'absence de sol
  visible dans une bande donne null, pas zéro. La hauteur de caméra est supposée :
  aucune largeur absolue n'est prouvée sans référence mesurée.
- **Pattern** : couleurs déterministes par boardId et joints jaunes. La partition
  CPU est celle de world-pattern.js, commune au moteur Canvas ; c'est une sonde
  de mapping, pas une preuve indépendante que le shader GPU n'a aucun défaut.
  Les tests de parité GPU existants complètent cette comparaison. La vignette et
  13-pattern-floor-space.png montrent le même partitionnement à plat sur 2×2 m,
  sans aucune caméra : comparaison directe avant/après projection pour D9/D10.

## Taxonomie et test minimal

Chaque constat : D-code, MINOR / MODERATE / SEVERE / BLOCKING et rectangle
normalisé {x0,y0,x1,y1}, entre 0 et 1, origine en haut à gauche. Les neuf
positions top-left…bottom-right sont aussi acceptées. BLOCKING : gros meuble
repeint, perspective/échelle manifestement fausse ou résultat faux présenté fiable.

| Code | Défaut | Test pour départager les causes |
| --- | --- | --- |
| D1 | Contour | Vert hors sol : floorMask/refinement. Vert correct mais rendu hors sol : sampling/ViewTransform/compositing. |
| D2 | Occlusion | Objet absent du rouge : génération. Rouge présent et objet repeint : sampling/compositing ; sonder le pixel source. |
| D3 | Perspective | Grid contre plinthes/seuils. Grille fausse : caméra/plan/projection. Grille juste, motif faux : shader/motif. |
| D4 | Échelle | Dimensions produit et Scale near/mid/far contre une référence mesurée. Distinguer échelle caméra et largeur produit. |
| D5 | Orientation | 0° puis 90°, même calibration. Une direction souhaitée est souvent un réglage ; ne pas changer la caméra. |
| D6 | Horizon | Camera + Grid contre les lignes de la photo ; horizon/focale/pose. Les VP fournis peuvent eux-mêmes être faux. |
| D7 | Lumière | Render contre unlit et original, mêmes caméra/masques/produit. Localiser l'ombre avant de toucher au relighting. |
| D8 | Edge | Masques bruts à 100 % ou plus. Escalier source : contour ; frontière source lisse mais halo rendu : filtrage/compositing. |
| D9 | Joints | JointWidth métrique, espace interlame extérieur et footprint ; comparer joints jaunes/boardIds à plat et projetés. |
| D10 | Motif | BoardId avant/après projection. Faux à plat : génération ; correct à plat mais faux projeté : caméra/shader. |

La table machine (noms, suspects et protocoles) est web/product/defect-report.js.
Un rapport retient **un ou deux modules suspects maximum par défaut**.

## Générer un pack

Serveur local déjà lancé. Node et playwright-core sont requis ; fournir
PPAI_PLAYWRIGHT_CORE avec le chemin du module installé dans l'environnement.
Aucun téléchargement de navigateur ou d'image concurrente n'est déclenché.

~~~powershell
$env:PPAI_BASE = 'http://127.0.0.1:8000'
$env:PPAI_PLAYWRIGHT_CORE = '<chemin vers playwright-core>'
node tools/capture-defect-pack.mjs --scene piece-claire --product BTRPF39009 --pattern baton-rompu --angle 0 --viewport 1440x900 --case case-001
~~~

Autre scène : --scene chambre. Photo privée déjà analysée : --scene-file
<SceneData.json> --image <photo-originale.png>. Cette commande réutilise la scène
fournie ; elle ne relance pas d'analyse. Sans SceneData, ouvrir/importer la photo
dans l'application puis utiliser ses diagnostics après analyse.

Options : --report <rapport.json>, --reference <capture-locale.png>, --no-pattern.
La référence est facultative, copiée localement, jamais téléchargée depuis Roomvo.
Un produit incompatible avec une pièce connue est refusé.

Résultat : review/defects/<case>/, ignoré par Git, avec original, rendu, grille,
masks, caméra, scale, plan, IDs/joints, unlit, deux masques bruts, metadata.json,
defect-report.json, defect-report.txt et index.html. review/defects/index.html
réunit les packs. Une calibration refusée donne l'original comme rendu et un
indicateur renderBlocked ; pas de recyclage du rendu précédent.

Les PNG de diagnostic sont en coordonnées source du renderer, sans recadrage viewport. Si celui-ci réduit une photo privée, le pack conserve aussi 00-original-native avec la photo fournie intacte ; originalNativeSize et rendererImageSize décrivent les deux résolutions. exportTransform
est donc l'identité ; ViewTransform décrit séparément l'affichage UI quand la
scène y est attachée. Pour une capture directe de SceneData hors UI, il est
explicitement indisponible. viewportSize conserve la taille du navigateur.
Aucune URL de transfert, chemin de photo privée ou SceneData complète n'est écrite
dans les métadonnées. Le contenu des photos reste privé : ne pas publier review/.

API DEV : window.__visualDiagnostics.setFlags({debugMasks:true}), capture(),
sample({x,y}) en pixels source. Le résultat capture().images contient des canvas ;
capture().metadata contient les valeurs numériques. L'ancien
window.__geometryReview.show() reste compatible.

## DefectReport

Format validé par defectReport() ; exemple minimal :

~~~json
{
  "id": "case-010",
  "sceneId": "piece-claire",
  "imageSize": {"width":1600,"height":1067},
  "defects": [{
    "code":"D2",
    "severity":"SEVERE",
    "region":{"x0":0.35,"y0":0.55,"x1":0.5,"y1":0.72},
    "description":"Constat visuel à vérifier, pas une cause déjà confirmée.",
    "suspectedModules":["occluderMask","compositing"],
    "confirmationTest":"Comparer rouge et pixel rendu dans cette zone.",
    "status":"OBSERVED"
  }],
  "confirmedCorrect": [],
  "references":{"original":true,"roomvo":false}
}
~~~

CONFIRMED CORRECT est toujours présent. Vide signifie « rien encore confirmé ».
Chaque PASS doit indiquer scope et evidence. Par exemple : « D3 PASS — matrices
inchangées lors d'une retouche de masque », sans prétendre que la perspective
est architecturalement exacte. Ne pas convertir un test numérique en PASS
esthétique. Un code avec défaut non résolu ne peut pas être marqué PASS.

OBSERVED → CONFIRMED exige résultat et cause démontrée ; RESOLVED exige aussi
fix, regression et visualResult (better/same/worse). Aucun rapport généré à
partir de seules captures ne s'autovalide. Les exemples de coordonnées ci-dessus
sont fictifs, pas un diagnostic automatique de cette pièce.

## Résoudre et archiver

1. Lire le rapport et regarder seulement les zones déclarées ; vérifier les PASS.
2. Choisir la couche appropriée et un test qui départage un ou deux suspects.
3. Exécuter le test avant toute correction. Conserver la preuve avant.
4. Corriger uniquement la cause confirmée ; aucune exception par scène/fichier.
5. Rejouer scène, tests et invariants déclarés corrects ; regarder original,
   rendu, grille et masques. Toute régression sévère annule le correctif.
6. Ajouter le test et l'entrée dans docs/defects_log.md ; conserver le pack privé.

Tests : tools/defect-report.check.mjs, tools/visual-diagnostics.check.mjs,
tools/diagnostic-state.check.mjs, tools/diagnostic-source-state.check.mjs et tools/defect-pack.check.mjs. Les tests navigateur utilisent Chrome local ; defect-pack.check valide les packs déjà générés. PPAI_PRIVATE_ORIGINAL permet en plus de vérifier la conservation octet pour octet de l'original privé.
Les tests de caméra GPU, de cellules métriques et de ViewTransform existants
restent les références numériques ; les captures servent au jugement humain.
