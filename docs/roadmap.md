# Feuille de route

Un principe traverse tous les lots : **le service doit savoir dire « je ne
suis pas suffisamment sûr » plutôt que produire une mauvaise géométrie.** La
confiance est une fonctionnalité, pas un ornement.

Un second, hérité du front : **rien n'est bloquant.** Chaque étage est
dégradable, et le Visualiseur continue de fonctionner en manuel quoi qu'il
arrive. Le service est une accélération, pas une dépendance.

---

## LOT IA 0 — Fondation, corpus, benchmark ✅

Livré. Voir `docs/architecture.md`.

* projet Python 3.12 autonome, dépendances légères, aucun modèle lourd ;
* `GET /health`, `POST /v1/analyze-room` ;
* validation d'upload, redressement EXIF, mesures de qualité, mesure de
  courbure des arêtes ;
* `SceneData` et `AnalysisResult` en Pydantic, le premier validé contre les
  douze scènes réelles du front ;
* structure de corpus et format de vérité terrain, tous deux vides et déclarés
  vides ;
* banc d'essai avec sortie JSON et CSV, corpus synthétique régénérable ;
* Dockerfile CPU.

Ce qu'il a déjà appris : le banc d'essai a produit un **faux positif de
distorsion** sur un damier synthétique. Un motif répétitif fournit des dizaines
de tracés courts dont la flèche n'est que du bruit d'ajustement, et en nombre
elle franchit n'importe quel seuil. D'où `lens_min_track_height_ratio`. C'est
exactement ce qu'on attend d'un banc d'essai construit avant les modèles.

---

## LOT IA 1 — Qualité et distorsion ✅

Livré. Compte rendu complet, chiffres et échecs :
`docs/quality-methodology.md`.

* corpus synthétique de 42 entrées déterministes, à vérité terrain **imposée** ;
* banc d'essai qui compte les **faux positifs** — le défaut méthodologique du
  LOT 0 ;
* trois mesures de netteté comparées par leur **marge de séparation**. La
  variance du Laplacien du LOT 0 est écartée : 18 faux positifs, marge
  négative. Le rapport de reflou est retenu ;
* séparation du **support** et de la netteté : une image pauvre en texture
  n'est plus déclarée floue, elle est déclarée indécidable ;
* contraste rendu **relatif** à la luminance : une photo sombre n'est plus
  déclarée plate en plus d'être déclarée sombre ;
* écrêtage mesuré séparément de la clarté ;
* trois détecteurs de distorsion comparés. `k1_fit` retenu : il estime le
  **sens** et l'**intensité**, exactement sur les cas centrés, et son test de
  cohérence est intégré à l'estimation ;
* suivi d'arêtes étendu aux **horizontales** et rendu bidirectionnel — il
  était aveugle aux distorsions fortes ;
* `no_distortion_detected` devient `no_distortion_evidence`.

**Ce lot ne corrige toujours pas la distorsion.** Il mesure, et il sait dire
quand il ne sait pas.

### Reste ouvert, et remis au LOT suivant

* **le corpus réel.** Vide, et le blocage est documenté : la licence des
  photos du front doit être reportée et non supposée, et une photo réelle
  n'apporte aucune vérité terrain de `k1` ni de sigma. Aucun seuil de ce lot
  n'est donc validé sur photo réelle ;
* **décider ce qui doit être bloquant.** Seul `image_too_small` l'est
  aujourd'hui. Une photo quasi noire, un panorama : refuser ou avertir ? La
  question reste ouverte exprès — elle demande de vraies photos ;
* **le bougé aligné sur un axe**, non détecté par la candidate C ;
* **le centre optique**, supposé au centre du cadre : 43 % d'erreur
  d'intensité sur une photo recadrée hors axe ;
* **les photos de 640 à 1024 px**, hors du domaine étalonné de la netteté ;
* la **correction** de distorsion, toujours pas envisagée.

---

## LOT IA 2 — Segmentation du sol

Le seul étage réellement indispensable.

### Préambule ✅ — cadre, format d'annotation, métriques

Livré. Voir `docs/annotation-protocol.md`. **Aucun modèle installé ni
comparé** : c'est la balance qui a été construite, pas ce qu'on y pose.

* format d'annotation humaine du sol, qui distingue **sol visible**,
  **étendue géométrique** (réservée, non annotée) et **incertain** ;
* zones incertaines exclues des métriques, avec leur raison enregistrée ;
* statuts `draft` → `reviewed` → `approved`, et seul `approved` entre au banc
  d'essai officiel — refus au niveau du schéma, pas seulement par convention ;
* métriques IoU, Dice, précision, rappel, et **F-mesure de contour** à
  tolérance relative à la diagonale. Mesuré : un masque décalé de 30 px garde
  un IoU de 0,67 et voit sa F-mesure de contour tomber à 0,002 ;
* contrôles automatiques : dimensions, valeurs de masque, hash d'image et de
  masque, licence, provenance, taille des zones incertaines ;
* séparation `public/` (versionné) et `private-real/` (hors de Git,
  référencé par hash), avec garde-fous dans les deux sens ;
* banc d'essai `run_segmentation` avec trois références triviales — masque
  vide, masque plein, tiers bas — pour vérifier la balance ;
* outil de tracé minimal (`tools/annotate.html`), sans dépendance, dont la
  sortie réelle est figée en fixture de test.

**Le corpus réel est vide.** Le blocage est documenté : voir
`datasets/README.md`. Aucun seuil n'est validé sur photo réelle, y compris la
tolérance de contour et la cible d'IoU.

### Reste à faire

* **constituer le corpus** : 20 à 30 scènes couvrant les traits de
  `SceneTrait`, avec provenance vérifiée entrée par entrée ;
* **annoter, et faire relire.** Les scènes `hard` méritent une double
  annotation : le protocole dit comment mesurer le désaccord, le dispositif
  n'est pas construit faute de données ;
* masque du sol, et découpage en zones distinctes (une pièce vue à travers une
  ouverture est une zone de plus, pas un trou) ;
* critère de réussite hérité du front : **IoU > 0,92** contre le masque humain.
  Écrit avant toute donnée, il reste la cible et rien ne le valide encore ;
* benchmarker plusieurs approches sur le même corpus, avec le même rapport.

Candidats à comparer, aucun n'étant retenu à ce stade : segmentation
sémantique d'intérieur entraînée sur ADE20K (classes `floor`, `rug`,
`carpet`), modèles de segmentation par invite avec un point bas de l'image
comme amorce, et une ligne de base sans réseau de neurones pour avoir un plancher
de comparaison. À vérifier pour chacun : licence, licence des **poids**, taille
téléchargée, et temps CPU pour une photo de 1600 px.

---

## LOT IA 3 — Profondeur

* carte de profondeur monoculaire relative ;
* calage métrique approché — les modèles monoculaires ne donnent pas d'échelle
  absolue, et il faudra la déduire du plan de sol ;
* le front calcule déjà la profondeur analytiquement depuis le plan, ce qui est
  **exact pour les pixels de sol**. La carte sert donc à ce qui n'est *pas* le
  sol : trier les occlusions, atténuer la netteté au fond, poser un contact.

---

## LOT IA 4 — Perspective et caméra

`horizon`, `vanishingPoints`, `fovDeg`, `tiltDeg`, `heightM`, et le
quadrilatère de plan.

**À tenter sans réseau de neurones.** Le contour du sol, une fois segmenté
proprement, contient déjà les droites mur/sol dont on déduit l'horizon et les
points de fuite. Un solveur de moindres carrés de 200 lignes peut suffire, et
il aura l'avantage énorme de fournir des résidus au pixel — donc une confiance
qui veut dire quelque chose.

Critère : quadrilatère à moins de 2 % de celui calibré à la main.

Vigilance : ces mesures supposent toutes que les droites du monde sont droites
dans l'image. Sur une photo distordue, deux relevés de la même direction, l'un
au centre l'autre au bord, donnent deux points de fuite différents, et il
n'existe alors aucun horizon compatible avec les deux. La scène n'est pas
approximativement représentable : franchement pas. D'où l'ordre des lots.

---

## LOT IA 5 — Occlusions

Meubles, pieds fins, tapis, radiateurs, objets. Polygones, lignes de contact
au sol, et profondeur relative pour le tri.

C'est l'étage où le front a le plus souffert : `piece-claire` a été rejetée
parce que ses occulteurs étaient des **boîtes englobantes**, et cela se voyait
au rendu. Une boîte n'est pas un pied de chaise.

---

## LOT IA 6 — Construction de la SceneData

Assembler les sorties des étages en `SceneData`, dans
`app/services/scene_builder.py` — le seul endroit prévu pour cela depuis le
LOT 0. Propager les confiances de chaque étage vers `confidence`, zone par
zone.

Le schéma Pydantic est déjà validé contre les scènes réelles : aucun champ ne
sera inventé le jour où cette fonction produira quelque chose.

Un test de non-régression est prévu : `MISSING_STAGES` doit s'être vidé.

---

## LOT IA 7 — Confiance et correction manuelle

* agréger les confiances des étages en un nombre unique, défendable ;
* le calibrer : `confidence` sous 0,6 doit ouvrir l'écran de correction plutôt
  que d'aller droit au rendu — c'est la règle du front ;
* mesurer la **calibration** : parmi les analyses annoncées à 0,9, combien
  étaient réellement bonnes ? Une confiance non calibrée est pire qu'aucune
  confiance, parce qu'on lui obéit.

---

## LOT IA 8 — Connexion WordPress et Visualiseur

* enregistrer l'analyseur `remote` côté front, en un seul endroit ;
* l'envoi de la photo doit être un **choix explicite**, jamais le comportement
  par défaut, et le mode local rester accessible en un clic ;
* réécrire la phrase de confidentialité affichée : aujourd'hui la photo ne
  quitte jamais le navigateur, et c'est écrit dans l'interface ;
* dégradation : panne, quota, timeout, 422 → le Visualiseur continue en manuel.

---

## Une alternative à étudier avant tout serveur

Exécuter la segmentation **dans le navigateur** — ONNX Runtime Web, WebGPU,
modèle quantifié de quelques dizaines de Mo. Plus lent au premier chargement,
mais la photo ne bouge pas, il n'y a pas de serveur à payer ni à sécuriser, et
la promesse actuelle du site reste vraie telle quelle.

Le contrat JSON est identique : seul l'analyseur enregistré change. Ce lot 0
n'engage donc rien — et c'est une raison de plus de n'avoir installé aucun
modèle.

---

## Vocabulaire

Tant que les étages de géométrie n'existent pas, **l'interface ne dit ni
« analyse », ni « détection », ni « intelligence artificielle »**. Les pièces
d'exemple sont *précalibrées*, la photo importée est *délimitée par
l'utilisateur*. C'est exact, et ça reste vrai.

C'est aussi pourquoi `source: "ai"` n'est jamais émis aujourd'hui : ce champ
autorise le front à changer de vocabulaire, et il ne doit le faire que quand
c'est mérité.
