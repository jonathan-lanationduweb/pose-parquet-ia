# Foreground V6 — annotation assistée et évaluation automatique préliminaire

## ASSISTED ANNOTATION TOOL

La nouvelle mission autorise les propositions automatiques comme point de départ **non validé**. Elle remplace la contrainte précédente de tracé entièrement manuel, sans autoriser de GT automatique.

Outil local : `http://127.0.0.1:8766/`. Démarrage :

```powershell
.\.venv\Scripts\python.exe -m scripts.foreground_annotation_v6
```

Deux workflows restent disponibles : **Annotation manuelle** et **Révision assistée**. En assisté, les masques V5.1 privés existants sont partitionnés à partir des classes ADE20K disponibles. Les propositions orange sont étiquetées **PROPOSITION AUTOMATIQUE — NON VALIDÉE**. Elles ne créent ni annotation enregistrée, ni PNG GT, ni validation humaine.

Le parcours rapide : renseigner son nom → cliquer l'objet proposé → vérifier sa catégorie et la ROI bleue → corriger avec Ajouter/Retirer, contour, pinceau, gomme ou Incertain → cocher la relecture de la catégorie, du contour et du vrai sol autour → **Valider cet objet** → **Objet suivant**. Ce clic est la confirmation humaine explicite de cet objet. La confirmation globale séparée sert à la validation en lot ; elle n'est pas nécessaire pour le bouton individuel.

Les actions de validation restent visibles au bas du panneau sur PC. Undo/redo, zoom, déplacement et visibilité des masques sont conservés. Une modification de l'objet révoque sa validation ; undo ne restaure jamais une ancienne approbation. Le bouton « Utiliser la proposition dans la zone » prépare uniquement un brouillon. « Retirer la proposition » conserve la possibilité de dessiner des corrections manuelles. « + Ajouter un objet manquant » reste disponible pour un objet absent du modèle.

ROI : boîte du composant sémantique avec marge et bande de sol à examiner, modifiable par l'humain. Les plantes, pots, vases et petits objets utilisent les classes réellement présentes dans le modèle existant ; leurs catégories restent des suggestions modifiables. Un même objet physique peut être fragmenté en plusieurs propositions, ou mal nommé. Une proposition n'est pas un inventaire humain d'objets.

Scènes prioritaires : sofa, thin-legs, plant, rug, old-floor, empty-room ; les trois autres restent accessibles. Le cache de suggestions est borné à trois photos. Aucune inférence n'est requise pour afficher les propositions archivées.

## HUMAN GT STATUS

Au contrôle final de ce lot : **aucun objet humain validé disponible**. Les tests n'ont enregistré aucune annotation sur les vraies photos. Les écritures de test appartiennent exclusivement à des fixtures synthétiques isolées dans des répertoires temporaires / `review/`, explicitement identifiées comme tests, jamais au dataset humain.

Une proposition utilisée, une case de relecture seule ou un brouillon sauvegardé ne suffisent pas. Seule une validation humaine explicite, avec nom, objet relu, ROI contenant du fond et confirmation, exporte la GT. Les régions non relues ne sont ni positives ni négatives. L'incertain est exclu. Une ROI positive doit conserver au moins 4 pixels ou 2 % de fond évalué (le plus grand des deux) : ce contrôle géométrique ne prouve pas qu'il s'agit de vrai sol, ce jugement reste humain.

Une zone négative se trace avec « + Zone de sol contrôlée », puis se relit et se confirme comme un objet. Elle ne peut pas inclure un foreground validé contradictoire. L'ancien contrôle « photo sans objet » est conservé pour une confirmation explicite de l'image entière ; préférer une ROI de vrai sol si l'image contient des éléments hors du champ à évaluer.

Stockage : `datasets/private-real/foreground-v6/<scene>/annotation.json`, avec révisions immuables privées. Les PNG binaires source `foreground.png`, `valid.png`, `uncertain.png` sont conservés globalement et par objet validé. Les objets non confirmés restent des brouillons, même si d'autres objets de la photo sont déjà validés (`partial-reviewed`). Les révisions se publient atomiquement, le pointeur JSON en dernier.

Provenance par objet : `annotationMode=manual|assisted-review`, référence/hash/source de la proposition, `proposalSource`, `humanReviewed`, `humanConfirmed`, annotateur et `humanDrawnFromScratch`. Une validation assistée porte `humanDrawnFromScratch=false`. La confirmation est une déclaration de la personne, pas une preuve cryptographique d'identité ou une revue indépendante.

Le lecteur vérifie le hash photo, la résolution, la révision courante, les PNG binaires et leurs hashes, les confirmations et les régions. Les anciens relevés manuels V6 sans hashes de masques sont contrôlés contre leurs gestes enregistrés. Aucun `.AI.json`, point de tige ou masque modèle n'est utilisé en remplacement de GT.

## NUMBER OF REVIEWED OBJECTS

**0** au contrôle réel de ce lot. Le compteur de l'interface affiche les nombres vérifiés par le serveur, pas le nombre de propositions sélectionnées.

L'évaluation s'ouvre à **5 objets positifs validés**, **3 catégories**, **1 région négative relue**. Les régions négatives ne gonflent ni le nombre d'objets positifs, ni celui des catégories. Pas besoin d'annoter les neuf scènes.

## CATEGORIES

Canapé, table, chaise, pied fin, tapis, meuble bas, radiateur, plante, câble, lit, autre meuble et petit objet. La catégorie finale est relue/modifiable par l'humain. Au contrôle réel : **0 catégorie validée**. Les noms et nombres de propositions automatiques ne sont pas présentés comme des catégories de GT.

## GLOBAL SEED METRICS

Dès le seuil atteint, une tâche en arrière-plan lit les labels sémantiques globaux et le masque V5.1 archivés pour les mêmes pixels source. Elle calcule aire GT, TP, FP, FN, précision, rappel et Dice par objet et par catégorie. Domaine : région humaine relue ET NOT incertain. Les zones non annotées sont ignorées ; les autres objets GT connus ne sont pas comptés comme des faux positifs de l'objet courant.

Les dénominateurs nuls restent N/A. Une région négative possède des FP mesurables, pas un rappel d'objet inventé. Le rapport affiche un tableau par objet, des agrégats par catégorie et les crops photo / GT / global / V5.1 / local / candidat V6. Les métriques ne sont pas extraites des 10 points de tige, ni de l'impression visuelle.

Résultats réels de ce lot : **N/A, GT humaine encore absente**. Le rapport reste marqué **PRELIMINARY HUMAN GT** lorsque le minimum est disponible ; une annotation assistée n'est pas une annotation indépendante du modèle évalué.

## CASE A/B/C

Seuils analytiques visibles : `NO_SEED` si rappel coarse < 0,10 ; `GOOD_SEED` si rappel >= 0,90 ; sinon `PARTIAL_SEED`. Les négatifs ont leur propre classe et ne sont pas classés C. Ces seuils ne deviennent pas un gate produit ou une confiance calibrée. Distribution réelle actuelle : N/A.

## LOCAL OBSERVATION RESULTS

Si des CASE C apparaissent dans les GT validées, le travailleur enchaîne automatiquement l'expérience locale, sans nouveau prompt. Il contrôle aussi les régions négatives du corpus. Une scène GOOD_SEED sans contrôle négatif pertinent évite cette passe.

Le générateur de ROI ne reçoit **aucun masque GT, ID d'objet ou nom de scène** : photo, domaine de sol figé et foreground existant seulement. Il classe des structures verticales/gradients dans et près du domaine/contact, puis retient au plus trois ROI non redondantes. Deux crops décalés par ROI sont envoyés au même OneFormer local. **Maximum six observations par scène** ; pas de tiling global.

Le gate exige accord de classe entre deux observations, appartenance au domaine de sol, composantes non minuscules et budget de taille (1 % du domaine par composante, avec plancher 16 px ; boîte <= 8 % de l'image). Les propositions trop grandes, dont les faux tapis globaux, sont rejetées. Ce sont des seuils expérimentaux génériques, non calibrés sur une GT inexistante. Ils peuvent être trop conservateurs et ne garantissent pas l'absence de FP.

Les seeds acceptés complètent la base existante et passent dans ForegroundUnderstanding V5.1. Les changements restent bornés autour des ajouts ; la base V5.1 est préservée. **Ce pipeline reste une expérience privée, pas une activation automatique dans le visualiseur.** Aucun composant de production app/web n'est modifié dans ce lot.

Le premier chargement éventuel utilise le graphe et les poids déjà en cache, mode offline imposé. Aucun nouveau modèle, export ou téléchargement. Le rapport conserve ROI, appels, métadonnées et timings (génération ROI, inférences, gates, fusion, raffinement, total). Il distingue les labels globaux archivés d'une nouvelle inférence globale ; aucun temps global n'est inventé.

Résultats locaux réels : **N/A**. Aucun appel modèle n'a été déclenché dans ce lot faute de GT suffisante. Les tests du chemin d'exécution utilisent des doubles synthétiques identifiés, jamais comme résultat de qualité réel.

## TP / FP

Le rapport mesure `addedTP`, `addedFP` et ratio TP/FP sur les seuls domaines humains. Budget de validation expérimentale : gain TP > 0 et addedFP <= max(8, 10 % addedTP), avec aucun nouveau FP dans les régions négatives. Une expérience sans gain ne devient pas positive parce que son masque est identique ou son code plus rapide.

Les crops automatiques ne reçoivent pas les contours GT. La couverture de l'objet par les crops et le rappel local brut sont mesurés **après** les observations. Cela distingue une ROI manquée, un échec de consensus/gate et un réel échec sémantique du modèle.

Valeurs actuelles : N/A, aucun gain TP/FP réel revendiqué.

## ONEFORMER DECISION

Décision réelle : **en attente de GT humaine**. Le verdict de récupération locale n'est admissible que si plusieurs objets progressent et les budgets / négatifs passent sur cette GT préliminaire.

Une conclusion `V6_SECOND_MODEL_EVALUATION_REQUIRED` exige plusieurs objets / catégories restant NO_SEED, une couverture GT >= 90 % par au moins deux observations locales effectives et un rappel brut local < 10 %. Un objet hors crop ou retrouvé avant rejet par le gate ne suffit pas à blâmer OneFormer. Aucun deuxième modèle n'est recherché/téléchargé automatiquement.

`confidenceCalibrated=false` reste explicite. Aucun score foregroundQuality de production n'est artificiellement augmenté.

## NEXT STEP

Dans l'outil : choisir Révision assistée, cliquer une proposition, corriger, vérifier catégorie/contour/fond, valider l'objet, puis objet suivant. Valider cinq objets de trois catégories et une zone de sol négative. L'interface montrera la progression puis le lien vers les métriques et crops.

Le serveur réagit aux sauvegardes, pas à une boucle d'inférence périodique. Une empreinte du contenu GT effectivement évalué et des baselines évite de relancer les expériences lors d'un simple changement de brouillon non validé. Les sauvegardes rapprochées sont regroupées ; un résultat dépassé par une nouvelle GT n'est pas publié comme courant. Le suivi UI est une lecture toutes les quatre secondes, sans appel modèle.

Les états et rapports sont locaux ; le serveur doit rester lancé. Un redémarrage reprend les GT validées et recalcule le bilan. Le rapport privé est dans `review/foreground-v6-phase2/`, consultable sur `/api/evaluation/report` uniquement quand l'évaluation courante est terminée. Les photos, GT, masques et rapports privés restent hors Git et hors du serveur public du visualiseur.

## TESTS

Suite complète : **584 tests passent**, deux avertissements de dépendances, 450,92 s. Après les derniers renforcements, **42 tests ciblés passent** : mode manuel, proposition non GT, références périmées, provenance assistée, validation partielle, fond de ROI, négatifs contradictoires, incertains, fichiers GT/source modifiés, métriques A/B/C, seuil 5/3/1, reprise automatique, empreinte stable malgré les brouillons, local/contrôles négatifs, budget FP et décision modèle conditionnée par couverture effective.

Parcours Chrome réel sur fixture synthétique isolée : sélection, correction, undo/redo, confirmation explicite, validation partielle, objet suivant, négatif, compteur de GT, sauvegarde/reprise. Les vraies photos sont seulement consultées dans les tests : zéro POST sur le dataset réel. Vérifications 1440 et 390×844 DPR2, absence de débordement horizontal. Le mode manuel est rejoué séparément.

Ruff et Mypy app + modules d'annotation/évaluation passent. Captures et logs dans `review/foreground-assisted-v6/` et `review/foreground-assisted-*.log`, hors Git. Les tests synthétiques ne sont pas comptés comme annotations humaines ou comme amélioration du visualiseur.

## FILES

- `scripts/foreground_annotation_v6.py` : validation partielle, exports avec hashes et provenance, raccord au travailleur.
- `scripts/foreground_proposals_v6.py` : propositions V5.1/labels en lecture seule, ROI, empreintes et cache borné.
- `scripts/foreground_evaluation_v6.py` : GT loader, minimum humain, métriques, A/B/C, rapports et orchestration conditionnelle.
- `scripts/foreground_local_experiment_v6.py` : ROI sans GT, observations locales bornées et gate expérimental.
- `tools/foreground-annotate.html`, `.js`, `.css` : manuel + révision assistée.
- `tests/test_foreground_assisted_v6.py`, outils de test navigateur manuel et assisté.

## GIT

Branche `feature/foreground-seed-recovery-v6`, continuité de V5.1 / outil V6. Commits logiques après tests/revue. Aucun merge/rebase main, force push, photo ou annotation privée dans Git. Le changement local de logo préexistant reste hors de ce lot.

## VERDICT

`V6_WAITING_FOR_HUMAN_GROUND_TRUTH`.

**Workflow assisté et reprise automatique prêts ; aucune récupération réelle V6 déclarée validée.** La limite actuelle est l'absence de régions confirmées par une personne. Les défauts du parquet ne sont pas annoncés corrigés et aucune décision modèle n'est fabriquée.
