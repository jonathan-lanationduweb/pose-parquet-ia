# Audit de l'existant — LOT A

> **ACTIF.** Inventaire vérifié dans le code et sur le disque le **10 septembre
> 2026**, avant toute écriture. Aucun chiffre de ce document n'est estimé : ce
> qui n'a pas été vérifié est marqué comme tel.

## 1. Ce qui a été fait avant, et ce qui doit encore guider

| lot | objectif d'alors | ce qui reste pertinent | ce qui ne doit plus guider |
| --- | --- | --- | --- |
| **LOT IA 0** — fondation | service, contrats, corpus synthétique, banc d'essai | l'ossature entière : un seul module connaît l'enchaînement, tous les seuils dans la configuration, tous les codes d'avertissement en un endroit, aucune photo sur le disque | le corpus synthétique comme mesure de quoi que ce soit qui touche au sol |
| **LOT IA 1** — qualité et distorsion | mettre trois mesures de netteté et trois détecteurs de distorsion en concurrence sur une vérité imposée | **la méthode** : candidats en concurrence, vérité imposée, matrice de confusion avec faux positifs, refus de conclure quand l'image ne porte pas de quoi conclure | les seuils eux-mêmes, calibrés sur du synthétique, avec une lacune assumée entre 640 et 1024 px |
| **LOT IA 2 préambule** — cadre de la segmentation | format d'annotation, contrôles, métriques de surface et de contour | tout : le format, les trois notions à ne pas confondre, les métriques, la démonstration que l'IoU seul ne suffit pas | l'objectif « trouver le sol » comme finalité, trop étroit pour le rendu |
| **LOT IA 2A** — pilote humain | mesurer le temps d'annotation et l'accord humain sur quatre scènes | l'instrumentation complète, et la règle mesurée sur la largeur des zones incertaines | le corpus pilote lui-même : 11 photos, 3 meublées, **aucun tapis** |
| **travaux UX** — prototype, catalogue Premibel, branchement moteur, stabilisation | valider l'expérience et la piloter sur le vrai moteur | l'UX validée, les latences mesurées, les 14 défauts corrigés, l'exactitude produit par attribut | le prototype comme base technique : il est gelé, et le produit vit maintenant dans le front |

## 2. Ce qui est réellement implémenté

Vérifié par lecture du code, pas par lecture des documents.

| capacité | présente ? | preuve |
| --- | --- | --- |
| décodage, validation, redressement EXIF | **oui** | `app/services/image_loader.py` |
| netteté : trois mesures et un support de texture | **oui** | `app/services/blur_analysis.py` |
| exposition, contraste, écrêtage : neuf mesures | **oui** | `app/services/image_quality.py` |
| suivi d'arêtes, courbure signée | **oui** | `app/services/edge_tracking.py` |
| distorsion d'objectif : trois détecteurs, estimation d'un coefficient | **oui**, mesure seule, **aucune correction** | `app/services/lens_analysis.py` |
| segmentation du sol | **non** | étage déclaré au chronométrage, jamais mesuré ; aucun module ne produit de masque |
| profondeur | **non** | étage déclaré, jamais mesuré ; le schéma existe, jamais instancié |
| caméra et perspective | **non** | étage déclaré, jamais mesuré ; aucun calcul d'horizon ni de fuite |
| détection d'objets | **non** | étage déclaré, jamais mesuré ; aucun détecteur dans le dépôt |
| modèle d'apprentissage, poids | **non** | dépendances : fastapi, pydantic, numpy, opencv, pillow ; aucun fichier de poids |
| construction de `SceneData` | **non** | `scene_builder.build_scene_data()` retourne `None` en dur |

Conséquence directe sur la réponse de l'API : `sceneData` est toujours `null`,
et parmi les cinq statuts déclarés, **seuls deux sont atteignables** aujourd'hui
(`rejected` et `analysis_incomplete`). `partial` n'est assigné nulle part.

## 3. État de la donnée

| grandeur | valeur |
| --- | --- |
| photos réelles au manifeste | 11 (cible annoncée : 20 à 30) |
| difficultés déclarées | facile 3 · moyen 2 · difficile 5 · refus attendu 1 |
| photos redistribuables | 0 |
| vérité terrain caméra ou objectif | 0 / 11 |
| photos meublées | 3 / 11 |
| photos avec tapis | **0** |
| **fichiers d'annotation** | **0** |
| **masques PNG** | **0** |
| campagne pilote | 4 scènes × 2 passes = 8 attendus, **0 collecté**, 0 approuvé |
| paires d'accord humain | 0 |
| annotations chronométrées | 0 |
| corpus synthétique | 44 entrées, 38 notées, reproductible au bit près |
| jeu visuel de référence | **5 scènes** (LOT B), 4 difficiles ; 2 cas non couverts : tapis, meuble massif |
| split déclaré | 6 photos de travail, 5 de référence (LOT B) |
| candidats de segmentation enregistrés | 3, tous triviaux : masque vide, masque plein, tiers bas |
| rapports produits sur disque | 1, tous compteurs à zéro |
| tests | 304 fonctions sur 14 fichiers ; aucun marqueur de vitesse |

Les 44 rendus présents dans `datasets/private-real/_renders/` ne sont pas un
corpus d'évaluation : ce sont des captures du moteur du front, produites pour la
maquette, hors Git.

## 4. Matrice de classement

**35 composants classés.** Rien n'est supprimé dans ce lot.

### KEEP — bon tel quel (14)

| composant | pourquoi |
| --- | --- |
| fondation FastAPI, identifiant de requête, CORS fermé par défaut | sobre, sans état, sans base de données |
| `GET /health` | fait son travail ; n'a qu'à gagner un champ `capabilities` |
| validation d'image et garde-fous | plafond en flux, format décidé sur le contenu et non sur l'en-tête déclaré, bombe de décompression traitée |
| redressement EXIF | vient en premier, et tout le reste en dépend |
| netteté, exposition, écrêtage | mis en concurrence sur vérité imposée, avec un verdict « indéterminé » assumé |
| distorsion mesurée sans correction | l'honnêteté est ici une propriété du code |
| `app/core/config.py` | tous les seuils en un endroit, lus de l'environnement |
| `app/core/timing.py` | huit étages déclarés, « non exécuté » distinct de « instantané » |
| `app/core/errors.py` | aucun chemin ni contenu d'image dans les messages |
| journalisation | seul le type d'exception, jamais la trace |
| `SceneData@1` | miroir fidèle du contrat du front, verrouillé par un test contre les scènes réelles |
| schéma d'annotation | statuts, passes, chronométrage, empreintes de masques |
| métriques de surface et de contour | définitions justes, pixels incertains exclus et part publiée |
| corpus synthétique | vérité imposée, reproductible, honnête sur ce qu'il ne prouve pas |

### KEEP + EXTEND — fondation correcte, à compléter (10)

| composant | extension nécessaire |
| --- | --- |
| `POST /v1/analyze-room` | produire une scène ; le contrat d'entrée ne change pas |
| `analysis@2` | devient `analysis@3` : `analysisId`, `capabilities`, confiance par composant, warnings structurés |
| `SceneData` — trois points | bloc `lens`, étendue de sol, rôle d'occulteur — **tous additifs** |
| `warnings` | passer de la chaîne nue à `{code, severity, component, message?}` |
| statuts | rendre `partial` atteignable ; distinguer les avertissements qui dégradent le rendu de ceux qui parlent de la photo |
| `confidence` | par composant, avec un `overall` borné par le minimum des composants qui décident du rendu |
| chronométrage | les quatre étages jamais mesurés le seront ; timings détaillés réservés au développement |
| banc d'essai de segmentation | ajouter les métriques produit ; le registre de candidats est déjà bon |
| protocole d'annotation | ajouter les rôles d'objets, les contacts au sol, les ouvertures |
| outil de tracé | mêmes ajouts ; **un seul outil**, pas un second |

### REWORK — principe utile, conception à revoir (4)

| composant | ce qui doit changer |
| --- | --- |
| `scene_builder.py` | reste le seul endroit où une scène peut naître ; devra assembler, résoudre la continuité et agréger la confiance |
| objectif du LOT segmentation | « trouver le sol » devient « sol + frontière + objets + rendu jugé » |
| tolérance de contour unique par défaut | reste multiple jusqu'à une décision humaine ; le défaut actuel n'est pas un seuil retenu |
| corpus pilote | conçu autour de pièces vides ; à refaire meublé, avec tapis et pieds fins |

### LEGACY REFERENCE — utile comme historique, plus comme base (6)

| composant | statut |
| --- | --- |
| `tools/product-concept.html` | maquette gelée, désormais marquée d'un bandeau ; référence UX uniquement |
| `tools/product-concept.check.js` | contrôles de cette maquette ; suit son sort |
| `docs/product-renderer-integration.md` | compte rendu du branchement par pont et iframe, abandonné comme base technique ; les mesures de latence restent utiles |
| `docs/stabilization-v1.md` | journal de 14 défauts trouvés sur la maquette ; les leçons ont été portées dans le produit |
| `docs/benchmark-quickstep-karndean.md` | relevé daté d'outils tiers ; l'analyse concurrentielle reste valable, les captures non |
| `docs/roadmap.md` | **remplacé** par [ROADMAP-V2.md](ROADMAP-V2.md) |

### DROP — doit cesser d'être utilisé (1)

| composant | pourquoi |
| --- | --- |
| la cible **IoU > 0,92** et **quadrilatère à moins de 2 %** comme critères de réussite | héritées du front, jamais validées, et le dépôt le consigne déjà comme mise en garde. Les garder donnerait une fausse impression de seuil décidé. Elles sont remplacées par la grille du [LOT C](ROADMAP-V2.md) dont les seuils sont explicitement **à calibrer** |

Aucun fichier n'est supprimé. « DROP » porte ici sur un critère, pas sur du code.

## 5. Ce qui manque vraiment

Classé par ce qui bloque quoi.

| manque | ce qu'il bloque | contournable ? |
| --- | --- | --- |
| **annotations humaines** — zéro | tout choix de modèle, toute mesure d'accord, tout seuil | **non**. C'est la seule dépendance dure du projet |
| **photos meublées et avec tapis** | la validité du protocole sur les cas qui cassent le rendu | non |
| métriques produit | mesurer ce qui décide, au lieu de l'IoU | non, mais peu coûteux |
| segmentation, objets, profondeur, caméra | le rendu automatique | non |
| assemblage de scène et confiance | le choix d'écran, la correction manuelle | non |
| corpus multi-vues | le Mode Visite entier | non |
| assets matière produit | la crédibilité de la matière, pas de la géométrie | partiellement : la géométrie exacte est déjà possible |
| grille de licences remplie | tout statut « modèle retenu » | non |
| banc matériel | tout objectif de latence | non, mais tardif |

## 6. Écarts documentaires relevés, à corriger dans les documents anciens

L'audit a trouvé sept divergences chiffrées. Aucune n'est corrigée dans ce lot —
les documents concernés sont des comptes rendus datés, et les réécrire
maintenant reviendrait à réécrire l'histoire. Elles sont listées ici pour que
personne ne s'appuie dessus.

| écart | version A | version B | qui a raison |
| --- | --- | --- | --- |
| taille du corpus synthétique | 42 (`roadmap.md`, `lens-distortion.md`) | **44** (`quality-methodology.md`) | 44, vérifié dans le code |
| résolution minimale annoncée | 800 px (`product-visualizer-ux.md`) | **640 px** (configuration) | 640, c'est le seuil implémenté |
| nombre de codes d'avertissement | 11 déclarés (`product-ai-contract.md`) | 9 notés (`quality-methodology.md`) | les deux : 19 codes existent, 9 entrent dans la matrice de confusion |
| scènes calibrées du front | douze (`scene-data.md`) | onze (`dataset.md`) | **seize** aujourd'hui, vérifié dans le front |
| état du manifeste | vide (`dataset.md`) | onze photos (`quality-methodology.md`) | onze |
| chemin du contrôle de santé | `/health` | `/v1/health` | `/health`, vérifié dans le code |
| statut de la maquette | gelée, référence UX (`product-visualizer-ux.md`) | objet de travail actif (trois autres documents) | gelée — et elle porte désormais un bandeau |

**Corrigé au LOT B** : deux photos étaient sous-décrites dans le manifeste
(`piece-claire` portait des pieds fins et une surface extérieure non déclarés).
Le vocabulaire de traits est passé de 24 à 31 valeurs pour nommer ce qui décide
du rendu. Deux traits que j'avais d'abord ajoutés ont été retirés après contrôle
de l'image — un contre-jour et un sol réfléchissant que la photo ne justifiait
pas franchement.

Le vocabulaire imposé par l'ancienne feuille de route reste valable et n'est pas
un écart : pas d'« analyse », de « détection » ni d'« intelligence
artificielle » dans l'interface publique tant que la géométrie n'existe pas.

## 7. Les dix décisions les plus importantes de cet audit

1. **La donnée humaine est le seul blocage réel.** Tout le reste est du travail
   ordonnançable ; elle ne se contourne pas, et aucun lot technique ne doit
   commencer en prétendant l'inverse.
2. **`SceneData@1` n'est pas à refondre.** Trois ajouts additifs suffisent pour
   toute la cible Mode Photo. Un nouveau contrat incompatible aurait coûté cher
   sans rien apporter.
3. **Le contrat d'analyse s'appelle déjà `analysis@2`.** La cible est donc
   `analysis@3`, et non un « v2 » qui existe.
4. **La confiance devient un objet par composant**, avec un `overall` borné par
   le minimum de ce qui décide du rendu, jamais une moyenne.
5. **Les objets se classent par rôle, pas par espèce.** Ce que le rendu doit
   savoir, c'est « faut-il préserver ces pixels », pas « est-ce un pouf ».
6. **`floorExtent` ne s'annote pas** et reste vide, mais devient une sortie de
   l'étage géométrie : sans lui, pas de lames continues.
7. **La profondeur relative suffit au Mode Photo**, sauf l'échelle physique, qui
   passe d'abord par la géométrie et non par une profondeur métrique.
8. **Les occlusions passent avant la profondeur** dans l'ordre des lots : elles
   décident davantage du rendu.
9. **La cible IoU > 0,92 est abandonnée comme critère** au profit d'une grille
   dont les seuils sont explicitement à calibrer, plafonnés par l'accord humain.
10. **Le Mode Visite ne commence pas sans photos réelles.** Le contrat de
    données est écrit et validé, aucune série multi-vues n'existe, et fabriquer
    une visite à partir de pièces différentes est interdit.

## 8. Ce qu'on arrête définitivement de faire

- **plus de faux masque** pour rendre une maquette présentable ;
- **plus de pseudo-moteur de rendu** en HTML ou en Python ;
- **plus de duplication du visualiseur** : une seule page HTML, les évolutions
  se font en JavaScript, en CSS et en données ;
- **plus de nouvel HTML à chaque itération**, ni dans le front, ni ici ;
- **plus de modèle choisi sur trois images** ;
- **plus de validation par nombre de tests** : 304 tests ne disent rien de la
  qualité d'un rendu ;
- **plus de « ça marche »** sans revue visuelle humaine écrite ;
- **plus de seconde personne fictive** pour une double annotation ;
- **plus de banc d'essai sur des données fabriquées** pour favoriser notre
  approche ;
- **plus de mélange** entre l'interface publique et l'outil d'annotation
  interne : l'un doit être beau, l'autre précis.
