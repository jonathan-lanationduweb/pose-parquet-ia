# Architecture

## Ce que ce service fait, et ce qu'il ne fait pas

```
PHOTO  →  pose-parquet-ai  →  SceneData  →  Visualiseur (JS/WebGL)
```

Python **comprend la pièce**. Il ne dessine pas le parquet, ne choisit pas de
matériau, ne compose pas d'image. Le moteur de rendu existe déjà, il est
éprouvé, et il ne doit rien apprendre de ce service : il reçoit une
`SceneData` normalisée et il peint, sans savoir d'où elle vient.

Cette frontière est la décision d'architecture la plus importante du projet,
et elle a été prise côté front avant qu'une ligne de Python n'existe. Elle a
une conséquence agréable : **le service peut être remplacé en entier** — autre
langage, autres modèles, ou même exécution dans le navigateur — sans qu'une
seule ligne du Visualiseur bouge.

### Ce service n'a pas de base de données

Aucun PostgreSQL, aucun état persistant, aucune file d'attente. Les demandes
des utilisateurs seront gérées ailleurs. Ici : une photo entre, des mesures
sortent, la photo est oubliée. La route d’analyse reste réplicable et jetable. Le transfert QR décrit ci-dessous
ajoute uniquement un état temporaire, sans migration de base de données.

### Photos : analyse et transfert QR

L’analyse reçoit la photo, travaille en mémoire puis libère les octets à la
fin de la requête. Aucun fichier temporaire n’est créé par le pipeline.

L’import QR (`/v1/photo-transfers`) ajoute une boîte temporaire en mémoire
pour relier le téléphone au PC, sans compte ni mot de passe. Le lien reste actif tant que la page du PC interroge le transfert ; dix minutes
sans activité déclenchent son nettoyage. Le téléphone envoie une seule photo ; le PC la récupère,
puis confirme sa réception par suppression du transfert. Une tâche supprime
également les transferts expirés toutes les trente secondes. Aucun original,
nom de fichier ou métadonnée EXIF n’est conservé sur disque.

Limites : 32 transferts, 10 Mo par envoi et 64 Mo de photos en attente. Deux
envois peuvent être décodés simultanément. Le téléphone et le PC doivent
atteindre la même origine publique HTTPS ; une adresse 127.0.0.1 ne permet
pas un transfert depuis un autre appareil. La page compagnon
`tools/phone-upload.html` sert uniquement à envoyer la photo ; le rendu reste
dans le visualiseur principal.

**Déploiement :** cette boîte est propre à un processus. Utiliser un worker
pour cette version, ou router toute la famille `/v1/photo-transfers` vers un
service unique. Plusieurs workers sans ce routage ne partageraient pas les
transferts. Une évolution distribuée devra remplacer la boîte par un stockage
partagé avec expiration, sans changer le parcours utilisateur.

---

## Le pipeline

```
octets
  │
  ├─► load_image ········· validation, décodage, redressement EXIF   ✅ LOT 0
  ├─► quality_analysis ··· netteté, exposition, contraste, écrêtage  ✅ LOT 1
  ├─► lens_analysis ······ distorsion : sens et intensité estimés    ✅ LOT 1
  ├─► segmentation ······· masque du sol, zones distinctes           ⏳ LOT 2
  ├─► depth ·············· carte de profondeur relative              ⏳ LOT 3
  ├─► perspective ········ horizon, points de fuite, plans, échelle  ⏳ LOT 4
  ├─► occlusion ·········· meubles, tapis, radiateurs, lignes de contact ⏳ LOT 5
  └─► scene_builder ······ assemblage de la SceneData                ⏳ LOT 6
```

Deux propriétés à conserver :

**Chaque étage est indépendant et dégradable.** Sans profondeur, le rendu perd
la netteté variable ; sans détection d'objets, l'utilisateur retouche au
pinceau ; sans géométrie, on retombe sur le quadrilatère manuel. **Rien n'est
bloquant** — et c'est ce qui permet de livrer les étages un par un.

**L'ordre n'est pas arbitraire.** Le redressement EXIF vient en premier parce
que tout le reste mesure sur l'image droite ; l'analyse d'objectif vient avant
toute géométrie parce qu'une distorsion non détectée entre dans tous les
relevés suivants sans plus rien qui la distingue du reste.

### Où vit quoi

| module                        | responsabilité                                     |
| ----------------------------- | -------------------------------------------------- |
| `app/main.py`                 | application, CORS, identifiant de requête          |
| `app/api/health.py`           | `GET /health`                                      |
| `app/api/analyze.py`          | `POST /v1/analyze-room`, lecture plafonnée         |
| `app/core/config.py`          | **tous** les seuils, lus de l'environnement        |
| `app/core/warnings.py`        | **tous** les codes d'avertissement                 |
| `app/core/errors.py`          | refus métier et leur code HTTP                     |
| `app/core/timing.py`          | les étages, et leur chronométrage                  |
| `app/core/logging.py`         | journalisation structurée                          |
| `app/schemas/scene_data.py`   | miroir du contrat du front                         |
| `app/schemas/analysis.py`     | notre contrat de sortie                            |
| `app/services/blur_analysis.py` | trois mesures de netteté, et le **support**      |
| `app/services/edge_tracking.py` | suivi d'arêtes, courbure **signée**              |
| `corpus/`                     | générateur du corpus synthétique, vérité imposée   |
| `benchmarks/scoring.py`       | matrice de confusion, **faux positifs compris**    |
| `app/services/pipeline.py`    | le seul module qui connaît l'enchaînement          |
| `app/services/*.py`           | un étage, une responsabilité, aucune connaissance des autres |

`app/services/scene_builder.py` s'écarte de la règle « pas de fichier vide » :
il ne fabrique rien aujourd'hui. Sa raison d'être est de tenir **le seul
endroit** où une scène pourra naître, pour qu'on n'en trouve jamais une
deuxième ailleurs. Son en-tête explique pourquoi `None` est la bonne réponse
tant que les étages de géométrie n'existent pas.

---

## Les deux contrats

Ils sont distincts, et la distinction est délibérée.

**`SceneData`** (`app/schemas/scene_data.py`) est le contrat **du front**. Nous
ne l'inventons pas, nous le traduisons — voir `docs/scene-data.md`. Sa version
est portée par son propre champ `schema` : `pose-parquet/scene@1`.

**`AnalysisResult`** (`app/schemas/analysis.py`) est **le nôtre** :
`pose-parquet/analysis@2` depuis le LOT 1. Une analyse peut avoir beaucoup à
dire sans produire de scène du tout, et c'est encore le cas. Les deux versions
bougent indépendamment.

### Le statut, et pourquoi il est pessimiste

`AnalysisStatus` vaut `success`, `partial`, `needs_manual_adjustment`,
`rejected`, ou `analysis_incomplete`. La hiérarchie de décision est dans
`pipeline._decide_status`, et `success` n'est atteignable qu'avec **une scène
et aucun avertissement**.

C'est strict, et c'est le but : il est bien plus facile de détendre ce critère
plus tard que de rattraper une géométrie fausse déjà montrée à quelqu'un.

`analysis_incomplete` est la valeur des LOT 0 et 1 et disparaîtra quand les étages
de géométrie existeront. Elle dit « les contrôles techniques ont tourné,
l'analyse de la pièce n'existe pas encore ». Elle n'est pas un échec, et
surtout pas un succès partiel : la confondre avec `partial` ferait croire
qu'un sol a été cherché.

### La confiance

`confidence` vaut `None` tant qu'aucun étage de géométrie n'existe. Ce n'est
pas de la timidité : c'est sur ce nombre que le front décide d'ouvrir ou non
l'écran de correction. Publier un 0,8 dérivé d'une variance de Laplacien
serait le pire mensonge que ce service puisse dire.

Le principe, valable pour tout le projet : **savoir dire « je ne suis pas
suffisamment sûr » plutôt que produire une mauvaise géométrie.**

Le LOT 1 l'a étendu aux mesures elles-mêmes. `quality.blur.sharp` et
`lens.verdict` peuvent tous deux répondre « indéterminé », et ce n'est pas un
échec de mesure : c'est le seul résultat vrai quand l'image ne porte pas de
quoi conclure. `LensSupport` publie de son côté la quantité de preuve
géométrique disponible — nombre d'arêtes, longueur totale, couverture
spatiale, accord de signe — pour qu'un verdict ne soit jamais un score opaque.
C'est ce bloc qui alimentera la confiance du LOT 7.

---

## Journalisation

Autorisé dans un log : `request_id`, nom d'étape, durée, dimensions, format,
codes d'avertissement, code d'erreur générique.

Jamais : l'image, un extrait d'image, du base64, un nom de fichier fourni par
l'utilisateur, un chemin absolu du serveur. Le nom de fichier est une donnée
personnelle en puissance — « salon-rue-des-lilas.jpg » — et n'apprend rien sur
l'analyse. Le service ne le lit pas et ne le garde pas.

`pipeline.Analysis` sépare exprès `result` (ce qui part au client) de
`log_fields` (ce qui part dans les logs), pour qu'on ne journalise jamais
l'objet entier « parce qu'il est là » — avec, demain, une carte de masque en
base64 dedans. Un test vérifie la liste exacte des champs journalisés.

---

## Configuration

Tout seuil numérique est déclaré dans `app/core/config.py`, surchargeable par
variable d'environnement préfixée `PPAI_`. Voir `.env.example`.

La raison n'est pas l'élégance : **aucun de ces seuils n'est universel**. Une
variance de Laplacien de 120 ne veut pas dire « photo nette » dans l'absolu —
elle le veut dire pour des photos d'intérieur ramenées à 1024 px de côté, et
il faudra la réviser quand le corpus sera assez grand pour la mesurer. Un
seuil éparpillé dans le code est un seuil qu'on ne révise jamais.

C'est aussi ce qui permet à un benchmark de rejouer d'autres seuils sur des
mesures déjà enregistrées, sans réanalyser les photos : `image_quality`
mesure, `quality_warnings` classe, et les deux sont séparés.

---

## Dépendances

La fondation est volontairement légère : FastAPI, Pydantic, Uvicorn, NumPy,
OpenCV (headless), Pillow.

**Aucun framework de deep learning n'est installé.** Pas de PyTorch, pas
d'ONNX Runtime, pas de poids de modèle. Ce n'est pas un oubli : installer
plusieurs centaines de mégaoctets « par anticipation » revient à choisir avant
de mesurer, et le but du LOT 0 est précisément de rendre la mesure possible.

Voir `docs/roadmap.md` pour les candidats et les critères de choix.

### Avant d'ajouter une dépendance lourde

Il faut l'écrire ici, avec :

1. l'étage qu'elle sert et pourquoi les alternatives légères ne suffisent pas ;
2. sa licence, et celle des poids si elle en télécharge ;
3. son temps d'exécution **sur CPU** pour une photo de 1600 px, mesuré ;
4. la taille de l'image Docker après ajout ;
5. le résultat du benchmark avant / après, sur le même corpus.

Les points 3 et 5 demandent le banc d'essai. C'est pour cela qu'il vient
d'abord.

## Risques connus, ouverts, et pourquoi ils le restent

Trois choses mesurées lors de la passe du 29 septembre 2026 n'ont **pas** été
corrigées ce jour-là. Elles sont écrites ici plutôt que perdues dans un
rapport : un risque qu'on ne retrouve pas est un risque qu'on redécouvre.

### CSP_DEFERRED_UNTIL_INLINE_CODE_REMOVED

Le service pose trois en-têtes de sécurité (`nosniff`, `Referrer-Policy`,
`X-Frame-Options`) et **aucune Content-Security-Policy**.

La raison est mécanique : `tools/product-concept.html` porte encore son script
dans la page — environ trois mille lignes en ligne. Une CSP honnête les
refuserait et casserait le visualiseur ; une CSP avec `unsafe-inline` les
autoriserait toutes et ne protégerait de rien, tout en donnant l'apparence
d'une politique. La passe du 29 septembre a commencé à sortir le code du HTML
(`tools/visualizer.css`, `tools/visualizer-drawer.js`) ; la CSP arrivera quand
le script de page aura suivi, et pas avant.

### Concurrence de l'analyse

`POST /v1/analyze-room` coûte **1,29 s de processeur** pour une photo de
1,7 Mpx (mesuré le 28 septembre 2026, CPU seul). L'analyse s'exécute dans le
fil d'exécution de Starlette (`run_in_threadpool`), dont le défaut est de
quarante fils : quarante photos simultanées, c'est quarante calculs OpenCV sur
le même processeur, sans file d'attente ni limite.

Aucune charge réelle ne l'a encore atteint, et corriger sans mesurer
produirait un réglage arbitraire de plus. Ce qu'il faudra : une borne de
concurrence explicite, et un `429` franc au-delà plutôt qu'une dégradation
silencieuse de tous les appels à la fois.

### DEMO_ASSET_GAP

Le visualiseur affiche cinq pièces de démonstration et cinq références
produit. Toutes ces images vivent dans `tools/local-demo-assets/`, qui est
**ignoré par Git** — les vignettes produit viennent de premibel.fr et ne sont
pas les nôtres, donc ni versionnées ni redistribuées (voir
`docs/premibel-demo-catalog.md` pour les URL sources et la date de relevé).

Conséquence à écrire noir sur blanc : **sur un clone frais, le visualiseur
s'ouvre sans une seule image.** Ce n'est pas un défaut de code, c'est une
dépendance à des fichiers qu'on n'a pas le droit de publier.

La sortie n'est pas technique : il faut un jeu d'images à nous —
photographies de pièces dont nous détenons les droits, et vignettes produit
issues de nos propres rendus. Tant que ce jeu n'existe pas, toute
« correction » consisterait à versionner les images de quelqu'un d'autre.

## Mode Photo expérimental (LOT PHOTO.1, 1ᵉʳ octobre 2026)

    EXPERIMENTAL PRODUCT PIPELINE · AUCUN MODÈLE RETENU · LOT C OFFICIEL SÉPARÉ

Une photo importée peut désormais recevoir un parquet. La chaîne, et ce que
chaque maillon sait vraiment :

    photo ─► quality/lens ─► segmentation (candidat expérimental)
          ─► FloorMaskRefiner ─► polygones + trous
          ─► perspective (rails du masque → point de fuite, ou horizon supposé)
          ─► SceneData @1 dans experimental.floor.sceneData
          ─► moteur local (openScene) ─► parquet, corrigible au pinceau

**Ce qui est mesuré et ce qui est supposé.** L'horizon est *mesuré* quand les
deux bords latéraux du sol sont visibles (méthode `vanishing-point`) ; il est
*supposé* un peu au-dessus du mur du fond sinon (`far-edge-fallback`), et la
confiance le dit. L'échelle est une *hypothèse* de sténopé : focale 0,85 ×
largeur, caméra à 1,50 m. Elle est plausible, pas mesurée — et sur les photos
d'essai la profondeur est surestimée (15 m rendus pour une chambre de 5 m) :
le rapport du lot le chiffre.

**Le contrat officiel ne bouge pas.** `sceneData` reste `null`. La scène vit
dans `experimental.floor.sceneData`, avec `sceneStatus`
(`auto_render` | `needs_manual_adjustment` | `no_floor`), `sceneConfidence`,
`perspective` et `sceneProvenance`. Un client qui ignore ce bloc ne voit rien.

**La porte de confiance** (`PPAI_EXPERIMENTAL_FLOOR_MIN_CONFIDENCE`, 0,55)
décide si le parquet se pose seul ou si la photo reste nue avec « Ajuster le
sol ». La correction est un pinceau — ajouter, retirer, annuler, terminer —
branché sur les traits que les masques du moteur savaient déjà recevoir.

**Occlusions : masque seul.** Un objet n'est protégé que là où le modèle de
sol l'a laissé hors du masque. Pieds fins préservés par le raffineur ;
aucune segmentation d'occulteurs. **LOT D n'est pas fait.** Le tapis est un
signal ADE20K marqué `EXPERIMENTAL / UNVALIDATED` : le corpus officiel n'en
contient aucun.

**Réseau pendant l'analyse.** Vu en situation : `from_pretrained` interrogeait
huggingface.co à chaque premier chargement malgré des poids en cache. Le
chargement est désormais `local_files_only` d'abord, réseau seulement si le
cache est vide — une analyse de photo de domicile ne dépend plus d'un tiers.

En développement, PPAI_PUBLIC_URL fournit au QR l’adresse HTTPS publique même
si le PC affiche 127.0.0.1. Un tunnel temporaire dépend toujours du PC.

La matière photographique Ipé (VLAME16012) provient des lames Premibel ;
sa longueur de présentation est estimée. Les autres essences sans matière
préparée restent consultables sans annoncer un aperçu disponible.

### Extension sols et murs — référence observée le 16/10/2026

Le simulateur public de La Maison Saint-Gobain intègre Roomvo. Le parcours
observé : import PC ou QR, catégories de pièces, catalogue en liste ou grille,
recherche et filtres, choix Sols/Murs, sélection de plusieurs murs, téléchargement
et partage. La sélection Murs observée propose des revêtements ; elle ne prouve
pas la disponibilité d'un catalogue de peintures.

Le projet actuel applique des revêtements au sol. Le bouton Murs ne sera activé
qu'avec des surfaces murales détectées et éditables et des produits compatibles.
Chaque surface devra avoir son propre masque, sa géométrie, ses exclusions
(fenêtres, portes, mobilier), son matériau et son état de comparaison. Le sol
et les murs devront rester simultanément personnalisables sans partager leurs
réglages de projection. Pour la peinture, préserver l'éclairage et la texture du
mur ; pour les carrelages, conserver les dimensions et la perspective du produit.

Validation requise : deux murs personnalisés indépendamment, fenêtres intactes,
changement de sol sans perte des murs, correction tactile des contours, annuler,
avant/après et comparaison incluant toutes les surfaces. Prévoir un catalogue
multisite avec références, marques et usages compatibles, sans inventer les
produits que Premibel ou Pose Parquet ne proposent pas encore.

Reproduire le parcours ne donne pas accès au moteur Roomvo. Une intégration du
moteur Roomvo lui-même nécessiterait un accord avec son fournisseur. Le moteur
autonome actuel reste distinct ; aucune équivalence de qualité n'est validée.
### Prototype peinture — essai fonctionnel du 16/10/2026

Le bouton Peinture ouvre un panneau compact, accessible sur téléphone. La pièce
« Pièce bleue » (chambre-parisienne) propose trois murs préparés manuellement,
avec ouvertures et prises exclues. Les autres scènes, y compris les photos
importées, utilisent un contour tracé par l'utilisateur et des polygones de
protection pour fenêtres et mobilier. Aucun détecteur de murs n'est annoncé.

Chaque mur garde une teinte indépendante en mémoire de session. La luminance
relative de la photo conserve les ombres et détails, sans simuler les propriétés
physiques d'une peinture réelle ni garantir une correspondance colorimétrique.
Les six teintes d'essai n'ont pas de référence commerciale. Le rendu composé
alimente les comparaisons et le téléchargement existants ; changer de parquet
ne réinitialise pas les murs. Les sauvegardes de canevas restent distinctes du
cache du moteur parquet pour éviter d'y enregistrer les peintures de session.

Contrôles : tools/wall-paint.check.mjs (320, 390 et 1440 px : couleurs indépendantes,
ouvertures/sol inchangés, changement de parquet, annulation, comparaison,
contours et isolation par pièce) ; tools/wall-paint-upload.check.mjs (photo
réellement importée, tracé tactile, zone protégée, annuler et retour aux pixels
originaux). Ce prototype remplace le constat « murs non fonctionnels » pour la
peinture manuelle uniquement. La segmentation automatique des murs, un nuancier
fournisseur et les revêtements muraux texturés restent à développer.
### Révision après retour utilisateur — 16/10/2026

La terrasse au coucher du soleil a été remplacée par la photo Pexels 24246924
(Thomas Parker), une terrasse couverte de maison. La terrasse Premibel très
meublée n'est plus proposée dans la galerie ; son original reste en référence.
Les cuisines et le bureau utilisent maintenant les deux faisceaux de lignes
mesurés dans les photos. La salle à manger utilise le premier axe mesuré ;
son axe conjugué et l'échelle restent estimés. Les scènes doivent encore faire
l'objet d'une appréciation utilisateur du rendu, au-delà des tests de chargement.

Le parcours Murs permet désormais de toucher directement une surface dans la
photo, puis d'appliquer une teinte en gardant les réglages du sol. Les pièces
préparées utilisent wallZones. Les imports utilisent experimental.walls.zones,
produit à partir des classes déjà calculées par OneFormer : aucune seconde
inférence. Une séparation par arêtes verticales propose des régions distinctes
aux angles visibles ; elle peut sous-segmenter des murs sans contraste ou
sur-segmenter un décor. Fenêtres, portes et meubles sont exclus par le masque
sémantique, qui reste une proposition corrigible. Le tracé est conservé en
secours ; les revêtements muraux texturés et le nuancier fournisseur restent
absents. Ce changement ne prétend pas égaler le moteur Roomvo.

## Expérimentation profondeur relative — 16 octobre 2026

Depth Anything V2 Small (Apache-2.0) et MiDaS v2.1 Small (MIT) ont été comparés localement sur douze photos privées : onze sols exploitables et un refus sans sol. Les huit masques déjà disponibles viennent de vraies prédictions antérieures ; la géométrie a été recalculée. Aucun envoi de photo à un service externe. Les poids et résultats restent ignorés dans `models/` et `review/room-understanding-v2/`.

Verdict : `ROOMVO_90_DIRECTION_NOT_VALIDATED`. La profondeur relative seule ne détermine ni une échelle métrique ni un horizon absolu. La fusion expérimentale conserve le masque, les occlusions, la focale, l’horizon et l’axe de pose existants. Aucun gain visuel régulier ne justifie une intégration produit. Les scripts ne sont pas importés par le parcours normal ; ses temps de première analyse ne changent pas.

Reproduction après installation locale des poids : `python -m scripts.export_depth_openvino`, `python -m scripts.benchmark_room_depth --owner-photo <photo-privee>`, puis `python -m scripts.benchmark_midas_depth`. Les comparatifs navigateur sont produits par `tools/depth-review.check.mjs` ; le rapport privé `review/room-understanding-v2/index.html` expose les limites, durées à chaud, mémoire et variantes. Les backends CPU et résolutions diffèrent : ces temps ne prouvent pas une qualité égale.

La terrasse vue mer utilise désormais ses deux directions de fuite mesurées ; son échelle reste une référence estimée. L’ouverture d’une nouvelle géométrie photo invalide les images mises en cache sous l’identifiant partagé `uploaded`. Le produit choisi reste conservé lors d’un changement de pièce.

Sources : https://huggingface.co/depth-anything/Depth-Anything-V2-Small-hf ; https://github.com/isl-org/MiDaS ; https://github.com/isl-org/MiDaS/blob/master/LICENSE .


## Contours, placement et compatibilité V2.1

BoundaryRefiner régularise le masque dans une bande incertaine guidée par la photo, puis déplace localement le contour selon les gradients, les lignes et la couleur du côté sol. La recherche est bornée par la résolution ; les trous sémantiques restent protégés. La morphologie de recherche définit un voisinage et ne constitue pas une dilatation du sol final. Les candidats de caméra exposent leurs scores de lignes, plinthes/seuils, roulis et plausibilité d’échelle dans `perspective.plausibility.geometryCandidates`. La hauteur caméra et les dimensions de référence restent supposées. Le mode DEV Axes montre les guides 92/150/190 mm proches, intermédiaires et lointains.

Le manifeste des pièces porte `surfaceType` (`interior_floor` ou `exterior_terrace`). La compatibilité produit provient des métadonnées explicites, sinon vaut `unknown`. Lors du changement de pièce, un produit incompatible est remplacé par le premier compatible rendable ; la terrasse ouvre donc avec Ipé VLAME16012. La matière extérieure porte ses paramètres de joints, distincts du parquet intérieur ; le joint visuel de 5 mm et la longueur de 2 m restent des hypothèses, pas une prescription de pose.

Les clés RenderCache contiennent une révision de scène ; les ouvertures de scènes et les invalidations la font évoluer. Les préparations SceneCache utilisent le contenu SceneData avec l’identifiant de pièce ; MaterialCache reste indépendant. Les parcours A/B/A, géométrie/masque/lumière modifiés sous un même identifiant photo et le repli Canvas sont testés.

Revue privée : `review/room-understanding-v2-1/index.html`. Reproduction hors inférence : `python -m scripts.benchmark_boundary_placement`, puis `node tools/boundary-refinement.check.mjs`. Compatibilité et isolation : `node tools/surface-product-compatibility.check.mjs`. Les tests nécessitant les photos privées ne constituent pas une dépendance de démarrage. Le jeu privé et les résultats restent ignorés par Git. La profondeur n’est pas intégrée au parcours normal.

La branche inclut également les dépendances du visualiseur auparavant présentes dans l’arbre de travail (catalogue, import téléphone et murs), afin que le code publié soit reproductible. Les limites résiduelles sous les meubles et aux seuils demandent une revue humaine ; aucun rendu parfait ou pourcentage Roomvo n’est revendiqué.
