# Feuille de route V2 — LOT A → LOT J

> **ACTIF. Remplace [roadmap.md](roadmap.md)**, qui décrivait les LOT IA 0 → 8
> et reste consultable comme historique. La correspondance entre les deux
> numérotations est en §2.
> Les principes transverses de l'ancienne feuille de route sont conservés :
> **savoir dire « je ne suis pas suffisamment sûr »** plutôt que produire une
> mauvaise géométrie, et **rien n'est bloquant** — chaque étage est dégradable.

## 1. État de départ

| | |
| --- | --- |
| livré et solide | décodage et EXIF, qualité d'image, distorsion mesurée, deux contrats de schéma, banc d'essai, protocole d'annotation, outil de tracé, 304 tests |
| livré côté produit | le visualiseur intégré du front, en mode manuel : photo importée, catalogue, comparaison, avant/après, favoris |
| absent | toute compréhension de scène : segmentation, objets, profondeur, caméra, occlusions |
| absent aussi | **la donnée humaine** : 0 annotation, 0 masque, 8 relevés pilote attendus, 0 collecté |

## 2. Correspondance avec l'ancienne numérotation

| ancien | nouveau | ce qui change |
| --- | --- | --- |
| LOT IA 0 — fondation | — | livré, absorbé |
| LOT IA 1 — qualité et distorsion | — | livré, absorbé |
| LOT IA 2 — segmentation du sol | **LOT C** | élargi : la segmentation seule ne suffisait pas comme objectif |
| LOT IA 2A — pilote humain | **LOT B** | élargi : le corpus doit être meublé, avec tapis |
| LOT IA 2B — choix de modèle | **dans LOT C** | mêmes conditions de départ, métriques produit ajoutées |
| LOT IA 3 — profondeur | **LOT E** | fusionné avec caméra et géométrie, car ils se déterminent mutuellement |
| LOT IA 4 — perspective et caméra | **LOT E** | idem |
| LOT IA 5 — occlusions | **LOT D** | avancé : les occlusions décident du rendu plus que la profondeur |
| LOT IA 6 — construction de SceneData | **LOT F** | recentré sur « le moteur obtient un résultat impeccable » |
| LOT IA 7 — confiance et correction | **dans LOT F et LOT G** | la confiance appartient à l'assemblage, la correction au produit |
| LOT IA 8 — connexion | **LOT G** | devient un lot produit de bout en bout |
| — | **LOT H, I, J** | nouveaux : multi-vues, visite, matière produit exacte |

## 3. Les lots

Chaque lot ne commence que lorsque ses dépendances sont satisfaites, et
s'arrête sur ses critères, pas sur l'épuisement du sujet.

### LOT A — Spécification et audit *(ce lot)*

| | |
| --- | --- |
| objectif | reprendre le projet à plat : audit, cible, contrats, données, mesures, feuille de route |
| entrées | le dépôt existant, la nouvelle cible produit |
| sorties | six documents actifs, une matrice de classement, un index documentaire |
| dépendances | aucune |
| mesures | aucune — lot documentaire |
| critères d'arrêt | les documents actifs ne se contredisent pas sur les neuf points de cohérence du §7 |
| décision humaine | **D1** — valider la cible produit et cette feuille de route |

### LOT B — Corpus réel meublé

| | |
| --- | --- |
| objectif | disposer de photos qui ressemblent à celles des utilisateurs, et de la vérité terrain associée |
| entrées | les 11 photos existantes, le protocole d'annotation, l'outil de tracé |
| sorties | palier 1 du corpus (12 à 16 photos dont ≥ 8 meublées et ≥ 4 avec tapis) ; 4 photos doublement annotées ; extensions de l'outil pour les rôles d'objets et les contacts ; temps d'annotation et accord humain mesurés |
| dépendances | LOT A validé |
| mesures | temps par photo, accord humain par difficulté, part d'incertain, zones de désaccord |
| critères d'arrêt | les 8 relevés de la campagne existent et sont approuvés ; l'accord humain est mesuré sur au moins 4 paires ; le protocole a été éprouvé sur un tapis et sur des pieds fins |
| décisions humaines | **D2** — deux revêtements intérieurs dans une même photo : une surface ou deux · **D3** — investissement d'annotation pour le palier 2 |

### LOT C — Compréhension du sol

| | |
| --- | --- |
| objectif | un masque de sol visible et une frontière fiables, choisis sur mesure et sur revue visuelle |
| entrées | corpus annoté du LOT B, banc d'essai, métriques produit |
| sorties | métriques produit implémentées ; candidats évalués avec leur grille de licence ; un candidat retenu ou le constat qu'aucun ne convient ; jeu visuel de référence constitué |
| dépendances | **les six conditions du passage de porte** ([BENCHMARK-STRATEGY-V2.md §8](BENCHMARK-STRATEGY-V2.md)) |
| mesures | IoU, Dice, F-contour aux trois tolérances, plus wall bleed, visible floor miss, critical boundary error, rug bleed |
| critères d'arrêt | grille du §4 ci-dessous |
| décisions humaines | **D4** — modèle retenu · **D5** — seuils de confiance et tolérance de contour produit |

### LOT D — Objets et occlusions

| | |
| --- | --- |
| objectif | que rien de ce qui n'est pas le sol ne soit repeint, pieds fins compris |
| entrées | corpus avec rôles annotés, sol du LOT C |
| sorties | masques d'objets par rôle, lignes de contact, ordre entre occulteurs ; `Occluder.role` ajouté au schéma |
| dépendances | LOT C, et l'extension de l'outil livrée au LOT B |
| mesures | occluder bleed, rug bleed, préservation des objets fins, justesse de la ligne de contact |
| critères d'arrêt | sur le jeu visuel : aucun tapis repeint, aucun meuble repeint, pieds fins conservés sur au moins toutes les scènes qui en contiennent |
| décision humaine | **D6** — taxonomie fonctionnelle confirmée, ou étiquettes sémantiques exigées |

### LOT E — Profondeur, caméra, géométrie

| | |
| --- | --- |
| objectif | faire fuir le motif correctement et à la bonne échelle |
| entrées | sol et objets des lots C et D |
| sorties | profondeur relative ; horizon, points de fuite, plan de sol, échelle physique ; décision sur la nécessité d'une profondeur métrique |
| dépendances | LOT C obligatoire ; LOT D souhaitable — les objets aident la géométrie et réciproquement |
| mesures | erreur d'horizon, erreur de direction de fuite, **erreur d'échelle de lame projetée**, monotonie de la profondeur, inversions d'ordre |
| critères d'arrêt | l'échelle de lame projetée est juste à quelques pour cent sur le jeu visuel — seuil **à calibrer** ; la géométrie ne dégrade jamais un résultat de sol correct |
| décision humaine | **D7** — profondeur métrique : nécessaire ou non pour le Mode Photo |

### LOT F — Assemblage de la scène et contrat de rendu

Ce lot **n'est pas** « écrire un moteur de rendu en Python ». C'est faire en
sorte que ce que Python publie permette au moteur existant d'obtenir un résultat
impeccable.

| | |
| --- | --- |
| objectif | une `SceneData` complète, une confiance par composant, et le contrat d'occlusion |
| entrées | tous les étages précédents |
| sorties | `SceneData@1` + les trois extensions (`lens`, étendue de sol, rôle d'occulteur) ; `analysis@3` ; confiance par composant ; warnings structurés ; jeu visuel comparé de bout en bout |
| dépendances | LOT C, D, E |
| mesures | celles du rendu final : les huit critères de la définition de terminé |
| critères d'arrêt | sur le jeu visuel, le rendu issu de l'analyse automatique est jugé équivalent ou meilleur que le rendu issu d'une calibration manuelle, par une revue humaine écrite |
| décision humaine | **D8** — extensions de schéma acceptées |

### LOT G — Mode Photo de bout en bout

| | |
| --- | --- |
| objectif | le premier vrai produit utilisable : une photo arbitraire donne un parquet crédible |
| entrées | LOT F, le visualiseur intégré du front |
| sorties | branchement de l'analyse distante derrière un choix explicite ; brosse de correction ; statuts et écrans associés ; phrase de confidentialité réécrite |
| dépendances | LOT F |
| mesures | part de photos montrables sans correction, part nécessitant une correction, part refusée ; nature des échecs restants |
| critères d'arrêt | palier 3 du corpus mesuré ; aucune régression du mode manuel ; aucun écran bloquant |
| décisions humaines | **D9** — ouverture au public · **D10** — architecture de déploiement et coût par analyse |

### LOT H — Fondation de la capture multi-vues

| | |
| --- | --- |
| objectif | savoir laquelle des quatre méthodes de capture donne un corpus exploitable |
| entrées | protocole de prise de vue déjà écrit (`docs/room-tour-protocol.md`, dépôt du front) |
| sorties | un corpus multi-vues réel sur 2 à 3 lieux ; comparaison expérimentale des quatre options ; contrat d'analyse de capture, si justifié |
| dépendances | LOT E — sans échelle commune, aucune vue ne se relie à une autre |
| mesures | recouvrement obtenu, stabilité de l'échelle entre vues, cohérence du sol d'une vue à l'autre, effort demandé à l'utilisateur |
| critères d'arrêt | une méthode est démontrée exploitable, ou toutes sont démontrées insuffisantes |
| décision humaine | **D11** — méthode de capture retenue |

Comparaison à mener, aucune option n'étant écartée d'avance :

| option | simplicité utilisateur | qualité | coût de calcul | compatibilité mobile | données nécessaires |
| --- | --- | --- | --- | --- | --- |
| plusieurs photos guidées | moyenne — il faut guider le cadrage | bonne si le recouvrement est tenu | faible | totale | 4 à 6 vues calibrées |
| vidéo guidée | **la meilleure** — un seul geste | variable : flou de bougé, compression | élevé — extraction et sélection d'images | totale | une séquence + sélection |
| panorama 360 | bonne sur téléphone récent | rotation seule, pas de déplacement | moyen | dépend de l'appareil | une position par lieu |
| capteur de profondeur | excellente là où il existe | la meilleure géométrie | faible | **minoritaire** | profondeur + pose |

### LOT I — Visite de pièce

| | |
| --- | --- |
| objectif | une navigation à la Street View, sans en copier l'interface |
| entrées | corpus multi-vues du LOT H, contrat de visite déjà écrit côté front |
| sorties | indicateurs de déplacement discrets, transition de 250 à 450 ms, conservation du produit d'une vue à l'autre, préchargement des vues voisines |
| dépendances | LOT H obligatoire — **rien ne commence sans photos réelles** |
| mesures | verdict humain unique : « je me suis déplacé » ou « j'ai changé d'image » |
| critères d'arrêt | le verdict est le premier ; sinon la fonction n'est pas exposée |
| décision humaine | **D12** — exposition publique de la visite |

Décisions déjà prises et documentées : le parquet et l'orientation survivent au
déplacement, avant/après suit le point de vue, la comparaison A/B se ferme quand
on se déplace.

### LOT J — Matière produit exacte

Ce lot est **indépendant de l'IA de compréhension de pièce** et peut avancer en
parallèle.

| | |
| --- | --- |
| objectif | qu'une référence vendue soit rendue avec sa vraie géométrie et sa vraie matière |
| entrées | fiches fournisseur, relevé Premibel existant |
| sorties | chaîne `CommercialProduct → VisualAssetPackage → RenderProfile → Renderer` ; exactitude par attribut |
| dépendances | aucune sur l'IA |
| mesures | nombre d'attributs `exact` par référence, et la liste des `approximate` restants |
| critères d'arrêt | au moins une référence rendue avec tous ses attributs `exact` |
| décision humaine | **D13** — investissement dans la production d'assets fournisseur |

Architecture cible, volontairement indépendante du fournisseur :

```
CommercialProduct        ce qui est vendu : référence, nom, fiche, dimensions
      │                  peut venir de Premibel, de Pose Parquet, d'une marque
      ▼                  blanche, ou d'un autre fournisseur
VisualAssetPackage       ce qu'il faut pour le rendre exactement
      ▼
RenderProfile            ce que le moteur consomme
      ▼
Renderer                 le moteur WebGL existant
```

Contenu idéal d'un paquet d'assets, à produire, **aucun asset n'étant créé
ici** :

```
product-id/
    basecolor.webp        teinte et veinage réels
    normal.webp           relief, chanfreins
    roughness.webp        finition
    variation-*.webp      plusieurs lames, pour éviter la répétition visible
    metadata.json
```

Métadonnées : dimensions physiques (largeur, longueur, épaisseur), motif,
angle de coupe pour un chevron, finition, période de répétition, amplitude de
variation entre lames, chanfrein.

**L'exactitude se déclare par attribut**, jamais par un pourcentage global. Un
`visualAccuracy: 72 %` ne dit rien d'actionnable ; `pattern: exact,
width: exact, tone: approximate, grain: approximate, finish: unavailable` dit
exactement quoi produire. Le relevé Premibel existant applique déjà ce principe,
avec un bilan « exact 0 · approximate 5 · unavailable 0 » sur cinq références.

## 4. Grille d'arrêt du LOT C — les seuils restent à calibrer

Aucun seuil n'est inventé ici. Ceux marqués **À CALIBRER** seront fixés par une
personne, avec les données du LOT B sous les yeux.

| critère | seuil |
| --- | --- |
| IoU médian sur le corpus annoté | À CALIBRER — la cible héritée de 0,92 n'est **pas** validée |
| IoU du pire cas non refusé | À CALIBRER — plus important que la médiane |
| F-contour à la tolérance retenue | À CALIBRER, une fois la tolérance choisie (D5) |
| tolérance de contour produit | À CALIBRER parmi 0,25 % / 0,5 % / 1 % |
| wall bleed rate | À CALIBRER — candidat au seuil le plus strict |
| rug bleed rate | **zéro toléré** sur le jeu visuel : un tapis repeint est un défaut visible |
| part de photos en `needs_manual_adjustment` | À CALIBRER — c'est un arbitrage produit, pas technique |
| revue visuelle | **obligatoire et bloquante**, quel que soit le chiffre |
| accord humain | le modèle ne peut pas être jugé au-delà de la précision des annotateurs : l'accord humain **plafonne** le seuil exigible |

Ce dernier point est structurant : si deux personnes ne s'accordent qu'à 0,90
d'IoU sur une frontière, exiger 0,95 d'un modèle n'a pas de sens.

## 5. Portes de décision humaines

Aucune de ces décisions ne se prend par défaut, et aucune ne se prend sans les
données correspondantes.

| id | décision | quand | données nécessaires |
| --- | --- | --- | --- |
| D1 | cible produit et feuille de route | fin LOT A | ces documents |
| D2 | deux revêtements intérieurs : une ou deux surfaces | LOT B | photos concernées annotées |
| D3 | investissement d'annotation pour le palier 2 | fin LOT B | temps réel par photo |
| D4 | modèle de segmentation retenu | LOT C | classement + grilles de licence + jeu visuel |
| D5 | seuils de confiance et tolérance de contour | LOT C | accord humain + métriques produit |
| D6 | taxonomie d'objets | LOT D | échecs observés |
| D7 | profondeur métrique nécessaire ou non | LOT E | erreur d'échelle de lame mesurée |
| D8 | extensions de `SceneData` acceptées | LOT F | contrat proposé + accord du front |
| D9 | ouverture publique du Mode Photo | LOT G | taux de résultats montrables |
| D10 | processeur ou carte graphique, local ou serveur, coût par analyse | LOT G | latences et poids mesurés |
| D11 | méthode de capture multi-vues | LOT H | comparaison expérimentale |
| D12 | exposition publique de la visite | LOT I | verdict de sensation |
| D13 | investissement en assets fournisseur | LOT J | écart d'exactitude par attribut |

Questions ouvertes de D10, à instruire et non à trancher aujourd'hui : quels
modèles tournent sur processeur seul, quelles étapes exigent une carte
graphique, carte locale ou serveur, traitement par lots ou à la demande,
mémoire nécessaire, coût par analyse.

## 6. Registre des risques

| risque | impact | probabilité | atténuation |
| --- | --- | --- | --- |
| absence de données réelles annotées | **bloquant** — aucune décision de modèle possible | **certaine aujourd'hui** | LOT B avant tout ; c'est la seule dépendance qui ne se contourne pas |
| objets fins perdus (pieds de chaise) | élevé — défaut visible immédiat | élevée | métrique dédiée, cas obligatoire du jeu visuel |
| tapis repeints | élevé — défaut visible immédiat | élevée | 4 photos minimum au palier 1, zéro toléré au jeu visuel |
| sol bois confondu avec un mur bois | élevé | moyenne | axe de corpus explicite, métrique de wall bleed |
| perspective forte non gérée | moyen | moyenne | axe de corpus, erreur d'échelle de lame |
| reflets pris pour un autre matériau | moyen | moyenne | la définition métier tranche déjà : un reflet est du sol |
| portes ouvertes et sol extérieur | moyen | élevée | décision déjà prise : l'extérieur est exclu |
| plusieurs pièces visibles, continuité | moyen | élevée | `surfaceId` et `planeRef` existent ; c'est la décision D2 |
| absence d'échelle physique | élevé — largeur de lame fausse | moyenne | métrique dédiée, piste géométrique avant la profondeur métrique |
| textures produit insuffisantes | élevé pour la crédibilité | **certaine aujourd'hui** | LOT J en parallèle, exactitude par attribut |
| reconstruction multi-vues instable | moyen | élevée | LOT H expérimental, aucune promesse avant mesure |
| coût de calcul | moyen | moyenne | mesurer avant de choisir ; préférer le processeur quand c'est possible |
| licence de modèle incompatible | **élevé** — un modèle à remplacer après coup | moyenne | grille obligatoire avant tout statut « retenu » |
| confidentialité des photos | **élevé** — juridique et réputationnel | faible si les règles tiennent | traitement temporaire, aucun stockage, aucun journal d'image |
| dérive documentaire | moyen — on ne sait plus quel document fait foi | **déjà arrivée** | index documentaire, statut sur chaque document |

## 7. Cohérence entre documents actifs

Neuf points doivent dire la même chose partout. État après ce lot :

| point | référence unique | cohérent ? |
| --- | --- | --- |
| définition de `floorVisible` | [annotation-protocol.md §1](annotation-protocol.md) | oui — les autres documents y renvoient sans la reformuler |
| responsabilités Python / moteur | [architecture.md](architecture.md), rappelé en tête de [AI-ARCHITECTURE-V2.md](AI-ARCHITECTURE-V2.md) | oui |
| ce que le moteur fait | [product-ai-contract.md §5](product-ai-contract.md) | oui |
| Mode Photo | [PRODUCT-VISION.md §4](PRODUCT-VISION.md) | oui |
| Mode Visite | [PRODUCT-VISION.md §4](PRODUCT-VISION.md) et le protocole de prise de vue du front | oui |
| `SceneData` | [scene-data.md](scene-data.md) pour l'existant, [AI-ARCHITECTURE-V2.md §10](AI-ARCHITECTURE-V2.md) pour les extensions | oui |
| jeu de données | [DATASET-STRATEGY-V2.md](DATASET-STRATEGY-V2.md) | oui |
| confidentialité | [product-ai-contract.md §8](product-ai-contract.md), rappelé en §16 de l'architecture | oui |
| feuille de route | **ce document** ; `roadmap.md` marqué remplacé | oui |

Les écarts chiffrés relevés pendant l'audit et qui restent à corriger dans les
documents anciens sont listés dans [AUDIT-V2.md §6](AUDIT-V2.md).
