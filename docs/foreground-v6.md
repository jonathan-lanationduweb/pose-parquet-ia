# Foreground V6 — phase 1 : outil et vérité terrain humaine

## GROUND TRUTH

À la demande de l'utilisateur, préparer l'outil pour tracer les annotations humaines. **Aucun masque humain foreground complet n'est disponible ou inventé dans ce lot.** Les anciens fichiers `datasets/annotations/*.AI.json` sont des brouillons attribués à `claude-ai`, pour le sol ; ils ne sont pas réutilisés comme GT humaine foreground. Les dix points de tige du V5 ne constituent pas une segmentation complète des objets.

Outil local : `http://127.0.0.1:8766`. Démarrage :

```powershell
.\.venv\Scripts\python.exe -m scripts.foreground_annotation_v6
```

Aucun chargement de modèle. Serveur séparé, limité à 127.0.0.1 ; aucun montage du dataset privé dans le visualiseur public. Les neuf photos originales du V5 sont lues depuis `review/foreground-mask-v5/<scene>/01-original.png`. Elles ne sont ni recopiées dans Git, ni préannotées. L'outil ne montre aucune proposition sémantique ou masque V5 pendant le tracé.

Catégories : canapé, table, chaise, pieds fins, tapis, meuble bas, radiateur, plante, câbles, lit, autre meuble, petit objet. Les neuf photos permettent de couvrir les catégories demandées. Les catégories du menu ne prouvent pas que des objets aient été effectivement annotés.

### Comment tracer

1. Renseigner son nom et choisir une photo.
2. Choisir la catégorie et « Ajouter un objet ».
3. Avec « Zone à examiner », tracer un rectangle autour de l'objet incluant du fond visible.
4. Choisir « Objet » : placer des points sur le contour puis Entrée / « Fermer le contour », ou peindre au pinceau. Utiliser la gomme pour les trous entre les pieds. Zoom et déplacement servent à travailler à la résolution source.
5. Marquer les pixels réellement ambigus avec « Incertain ». Une ombre photographique ne devient pas un objet. Si un autre objet entre dans la zone, l'annoter aussi ou marquer cette partie incertaine.
6. Relire l'objet et **tout le fond de la zone**, cocher sa relecture. Répéter pour les autres objets.
7. Cocher la confirmation humaine et « Valider les zones relues ». Le brouillon peut être enregistré avant cela. Une scène sans objet nécessite une confirmation négative explicite.

Toutes les coordonnées sont des pixels source. Les dessins (polygones, pinceau, gomme et incertain) sont conservés ; Python les rasterise en PNG binaires 0/255 sans interpolation de masque ni suggestion de contour. La rasterisation travaille à 2× puis échantillonne les centres des pixels source : un rectangle [7,12) × [5,19) contient exactement 70 pixels, sans rangée supplémentaire de Pillow ; un pied tracé sur les centres à 1 px garde 1 px de large. Les prévisualisations SVG ne sont pas des seeds. Les pixels incertains sont exclus et leur union est exclue aussi du masque global évalué. Le périmètre est `reviewed-regions-only`, jamais assimilé à une annotation exhaustive de toute la scène.

Stockage privé : `datasets/private-real/foreground-v6/<scene>/annotation.json`. Ce répertoire est déjà ignoré par Git. Les versions validées écrivent `revisions/<hash>/foreground.png`, `valid.png`, `uncertain.png`, et les mêmes masques par objet. `annotation.json` pointe vers la révision courante. Un retour au brouillon supprime le pointeur GT courant, sans effacer l'historique. Les exports sont préparés avant publication ; le pointeur JSON est remplacé en dernier. Photo liée par SHA256 et résolution exacte.

Le nom + la confirmation sont une déclaration de l'annotateur, pas une preuve cryptographique de son identité ni une revue indépendante. Aucune annotation n'est approuvée automatiquement.

## CURRENT SEED FAILURE

Les observations qualitatives V5.1 restent des hypothèses : coussin partiel, câbles sous bureau, bandes sombres et franges. Elles ne deviennent pas des mesures par simple recopie. Le rapport `foreground-missing-seeds-v51.md` conserve la distinction ombre / objet / tapis déjà exclu.

## CASE A/B/C DISTRIBUTION

**N/A tant que la GT humaine n'est pas tracée.** Le seuil analytique candidat `coarse seed recall < 10 %` servira à identifier CASE C ; il ne sera ni une règle produit ni un score calibré. Aucun objet non annoté n'est arbitrairement classé A, B ou C.

## LOCAL SECOND PASS

Non développée dans cette phase : la mission exige d'abord la GT humaine. Les unions de tuiles V5.1 rejetées ne sont pas réactivées. Les futurs essais devront partir de CASE C mesurés et de ROI ciblées avec contexte vertical.

## FALSE POSITIVES

Pas de nouvel algorithme de foreground dans ce lot. Le fond explicitement examiné dans les ROI et les contrôles négatifs permettront de mesurer le budget FP. Les zones non annotées ne doivent pas compter comme négatif. La relecture humaine doit distinguer les objets et le sol entre eux.

## MODEL DECISION

Aucun nouveau modèle recherché, téléchargé ou intégré. La condition « plusieurs catégories critiques NO_SEED malgré les observations locales ciblées » ne peut pas être évaluée sans ces annotations.

## SEED FUSION

Non développée, aucune fusion automatique appliquée. Pipeline de production V5.1 conservé.

## VISUAL IMPROVEMENTS

Outil de tracé uniquement : photos source, zone examinée bleue, objet rouge, incertain jaune, zoom, déplacement, contour, pinceau, gomme, annulation et sauvegarde/reprise. Aucune amélioration du rendu parquet n'est revendiquée dans cette phase.

## METRICS

| Catégorie | GT area | Coarse recall | V5 recall | V6 recall | Precision V6 | FP | Boundary error |
|---|---|---|---|---|---|---|---|
| Canapé | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| Table / chaises / pieds | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| Tapis | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| Meuble bas / radiateur | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| Plante / câbles / lit | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| Scène complexe | N/A | N/A | N/A | N/A | N/A | N/A | N/A |

Pas de recall, précision, Dice ou erreur de bord calculés sur les données synthétiques de test comme s'il s'agissait de photos annotées par une personne. Le stockage par objet, la catégorie, la zone examinée, l'incertain et le hash permettront une évaluation reproductible après le tracé humain. Le rapprochement avec les seeds/V5 se fera à ce moment, sans les afficher pendant l'annotation.

## PERFORMANCE

Aucun appel à OneFormer, aucun recalcul de caméra. Pas de temps first/final V6 disponible. Les valeurs V5.1 précédentes restent un bilan historique, pas un benchmark de cette phase. Aucun gain de latence du visualiseur revendiqué.

## MOBILE

Interface contrôlée à 390×844 DPR2 et desktop 1440 DPR2 : pas de débordement horizontal. Le zoom et les tracés utilisent les coordonnées de la photo, indépendamment du DPR. Pour les contours fins, l'annotation sur PC reste plus pratique. L'adresse loopback est prévue pour ce PC, pas pour un téléphone en 5G.

## REGRESSIONS

Aucun fichier app/, renderer, géométrie, segmentation, matériaux, lumière V4 ou contact compositor modifié. Le logo local préexistant est conservé hors des commits. Les vraies photos sont restées sans tracés pendant les tests automatiques : **zéro POST** sur le dataset réel dans les tests UI.

## TESTS

15 tests Python ciblés passent sur images synthétiques : drafts exclus de GT, confirmation humaine requise, dimensions/hash, masques binaires source, incertains et trous, contrôles négatifs, union des incertains, atomicité et routes privées. Parcours navigateur synthétique complet : points source, brouillon, refus de validation non confirmée, validation/relecture explicite, sauvegarde/rechargement, zoom. Captures des vraies photos en lecture seule à 1440 et 390 px.

Suite complète : **559 tests passent**, deux avertissements de dépendances, 217,67 s. Après les deux derniers ajouts (rasterisation au centre des pixels et refus de la déclaration « scène vide » contradictoire), **15 tests ciblés passent** et le parcours UI est rejoué avec succès. Ruff et Mypy app + serveur d’annotation passent. Le changement raster est couvert par des tests d’aire exacte et de trait 1 px ; il ne touche aucun composant du visualiseur.

## FILES

`scripts/foreground_annotation_v6.py`, `tools/foreground-annotate.html`, `.js`, `.css`, `tools/foreground-annotation-v6.check.mjs`, `tests/test_foreground_annotation_v6.py`, ce rapport. Captures et tests synthétiques dans `review/foreground-v6/`, hors Git. Les enregistrements de test synthétiques sont isolés dans ce répertoire de test ; ils ne sont pas dans le dataset humain.

## GIT

Branche `feature/foreground-seed-recovery-v6` depuis V5.1. Publication du lot d'annotation uniquement après tests/revue. Aucun merge/rebase main ni force push. Aucune photo ou annotation privée dans Git.

## LIMITATIONS

Il reste à tracer les annotations humaines, puis mesurer les seeds actuels, établir A/B/C, tester l'observation ciblée et la fusion, et vérifier les TP/FP et la latence. La confirmation humaine seule n'assure pas une qualité parfaite : une seconde relecture et des ROI de fond soigneusement examinées sont nécessaires. Les seuils de gate et les sept familles de tests de récupération V6 ne sont pas simulés alors qu'aucune méthode V6 n'a encore été choisie.

## VERDICT

`FOREGROUND_SEED_RECOVERY_V6_NEEDS_WORK`.

**Outil d'annotation humaine prêt ; phase de découverte V6 en attente des tracés.** La consigne « annotations humaines uniquement, avant de développer une nouvelle méthode » et la réponse utilisateur « Préparer l'outil pour les tracer » déterminent cet arrêt de phase.
