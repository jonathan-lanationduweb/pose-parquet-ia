# Index documentaire

> **ACTIF.** Quel document fait foi, et sur quoi. En cas de désaccord entre deux
> documents, la colonne « fait foi sur » de ce tableau tranche.
> Dernière révision : **10 septembre 2026** (LOT A, puis LOT B.2 — rôles
> d'exclusion).

## Comment lire les statuts

| statut | sens |
| --- | --- |
| **CIBLE** | dit où l'on va. Fait foi pour toute décision à venir. |
| **ÉTAT COURANT** | décrit ce qui est livré et fonctionne aujourd'hui. Exact, et daté par nature. |
| **DÉCISION** | fixe une définition ou une règle. Ne se reformule pas ailleurs. |
| **HISTORIQUE** | compte rendu d'un travail terminé. Utile pour comprendre pourquoi ; ne guide plus. |
| **REMPLACÉ** | un autre document dit désormais la même chose, mieux. |

## Documents actifs

| document | statut | fait foi sur |
| --- | --- | --- |
| [PRODUCT-VISION.md](PRODUCT-VISION.md) | **CIBLE** | la cible produit, les deux modes, les trois niveaux d'immersion, la définition de « terminé » |
| [AI-ARCHITECTURE-V2.md](AI-ARCHITECTURE-V2.md) | **CIBLE** | le périmètre de compréhension de scène, les objets par rôle, les occlusions, la profondeur, la caméra, les extensions de `SceneData`, `analysis@3`, la confiance par composant, les warnings structurés, les familles de modèles, la grille de licences, l'observabilité, les API |
| [DATASET-STRATEGY-V2.md](DATASET-STRATEGY-V2.md) | **CIBLE** | le corpus à constituer, les trois paliers, le corpus multi-vues, ce qu'on demande aux humains, la direction de l'outil d'annotation |
| [ROOM-TOUR-ARCHITECTURE.md](ROOM-TOUR-ARCHITECTURE.md) | **CIBLE** | les deux modes produit et leurs capacités (`PAN_ZOOM`, `FREE_NAVIGATION`), la séparation stricte entre l'angle du parquet et l'angle du regard, le pipeline d'une navigation libre, la comparaison maillage / NeRF / splatting pour **notre** besoin, la contrainte du sol éditable, l'architecture hybride, la zone navigable, le protocole de capture d'une pièce pilote et le plan V1→V5 |
| [RENDERER-AUTONOMY-PLAN.md](RENDERER-AUTONOMY-PLAN.md) | **CIBLE** | ce qu'est réellement le moteur de rendu, la seule dépendance d'exécution restante vers le front gelé, le noyau minimal de 15 fichiers, les champs de `SceneData` réellement consommés et l'écart avec la cible Python, les coûts mesurés, la stratégie d'extraction en cinq étapes et son test d'autonomie bloquant |
| [MODEL-LICENSES.md](MODEL-LICENSES.md) | **DÉCISION** | la licence du code et **celle des poids, vérifiée séparément**, pour chaque candidat envisagé ; les quatre statuts de licence et les trois d'éligibilité ; la réserve ADE20K ; l'écart entre notre `floorVisible` et une classe `floor` académique ; la source officielle de chaque décision. **LICENSE CHECK COMPLETE ≠ MODEL SELECTED** : ce document n'autorise pas le LOT C |
| [BENCHMARK-STRATEGY-V2.md](BENCHMARK-STRATEGY-V2.md) | **CIBLE** | les métriques conservées, les métriques produit à construire, le jeu visuel de référence, le passage de porte du premier lot technique |
| [ROADMAP-V2.md](ROADMAP-V2.md) | **CIBLE** | les lots A à J, les portes de décision humaines, le registre des risques, la grille d'arrêt du LOT C |
| [AUDIT-V2.md](AUDIT-V2.md) | **ÉTAT COURANT** | l'inventaire de l'existant, la matrice KEEP / KEEP+EXTEND / REWORK / LEGACY / DROP, les manques, les écarts documentaires |
| [annotation-protocol.md](annotation-protocol.md) | **DÉCISION** | **la définition officielle de `floor_visible`**, les trois notions à ne pas confondre, **le rôle d'une exclusion**, les natures de contour, les conventions de masque, le cycle `draft`→`reviewed`→`approved`, l'accord humain, la confidentialité du corpus |
| [architecture.md](architecture.md) | **ÉTAT COURANT** | la frontière Python / moteur, le pipeline livré, les deux contrats de schéma, les statuts existants, la journalisation, la configuration, les conditions avant toute dépendance lourde |
| [scene-data.md](scene-data.md) | **DÉCISION** | la structure de `SceneData@1`, les coordonnées normalisées et non bornées, `plane` ≠ `mask`, `planeRef` comme clé de continuité, les valeurs de `light` verrouillées, la table champ → lot |
| [product-ai-contract.md](product-ai-contract.md) | **DÉCISION** | le partage des rôles, les cinq statuts et l'écran associé, la règle de repli, `confidence` jamais affiché, le classement des capacités du moteur, les appels réseau, la confidentialité |
| [product-visualizer-ux.md](product-visualizer-ux.md) | **CIBLE** | l'expérience publique visée, les interdits d'affichage, le traitement UX des statuts. S'applique à `tools/product-concept.html`, le visualiseur actif |
| [quality-methodology.md](quality-methodology.md) | **HISTORIQUE** | la méthode de mise en concurrence, et les deux bornes de netteté retenues, qui sont toujours celles du code |
| [lens-distortion.md](lens-distortion.md) | **ÉTAT COURANT** | ce que la mesure de distorsion constate, les trois verdicts, la règle « la correction vient avant tout relevé », le besoin d'un bloc `lens` |
| [dataset.md](dataset.md) | **HISTORIQUE** | les axes de composition du corpus qualité. Son état chiffré est dépassé — voir [AUDIT-V2.md §3](AUDIT-V2.md) |
| [pilot-runbook.md](pilot-runbook.md) | **CIBLE** | le mode opératoire de la campagne d'annotation, l'ordre imposé, la procédure de double passe |
| [premibel-demo-catalog.md](premibel-demo-catalog.md) | **HISTORIQUE** | le relevé des cinq références et **l'exactitude par attribut**, principe repris par le LOT J |
| [../benchmarks/README.md](../benchmarks/README.md) | **ÉTAT COURANT** | les métriques implémentées et leur usage |
| [../datasets/README.md](../datasets/README.md) | **ÉTAT COURANT** | les trois régimes de jeux de données, la provenance obligatoire |

## Documents historiques ou remplacés

| document | statut | remplacé par |
| --- | --- | --- |
| [roadmap.md](roadmap.md) | **REMPLACÉ** | [ROADMAP-V2.md](ROADMAP-V2.md) |
| [product-renderer-integration.md](product-renderer-integration.md) | **HISTORIQUE** | l'architecture par pont et iframe est abandonnée ; le visualiseur intégré vit dans le dépôt du front. Les latences mesurées restent utiles |
| [stabilization-v1.md](stabilization-v1.md) | **HISTORIQUE** | journal de défauts sur la maquette gelée ; les leçons sont dans le produit |
| [benchmark-quickstep-karndean.md](benchmark-quickstep-karndean.md) | **HISTORIQUE** | relevé daté d'outils tiers ; l'analyse concurrentielle reste valable, elle est résumée dans [PRODUCT-VISION.md §2](PRODUCT-VISION.md) |

## Les points d'entrée, une fois pour toutes

Une application = un fichier HTML. Ce dépôt en contient deux, et ils ne
remplissent pas la même fonction — les confondre a déjà coûté une revue.

```
VISUALIZER ENTRYPOINT = tools/product-concept.html
STATUS                = ACTIVE PRODUCT VISUALIZER
RENDERER              = web/  (LOCAL, WebGL — extrait le 10 septembre 2026)
ANNOTATION ENTRYPOINT = tools/annotate.html
EXTERNAL FRONT        = pose-parquet.com — FROZEN, ZERO RUNTIME DEPENDENCY
```

**Décision humaine du 10 septembre 2026**, qui remplace la précédente :
`tools/product-concept.html` n'est plus une référence UX gelée, c'est **le
visualiseur que nous faisons évoluer**. Toute évolution de l'interface, de la
pièce, du rendu, de l'import de photo, de la navigation, du pan/zoom, de la
comparaison, du catalogue et de la personnalisation se fait dans ce fichier et
ses fichiers associés. Aucun second HTML de visualiseur ne doit exister — ni
`product-concept-v2.html`, ni `visualizer.html`, ni aucune variante.

Le nom « concept » est désormais imparfait, et le fichier **n'est pas renommé** :
le renommer créerait une nouvelle source de confusion, ce qui est exactement ce
que cette règle sert à éviter. Décision ultérieure.

`tools/annotate.html` reste séparé parce qu'il fait autre chose : produire la
vérité terrain. Deux HTML dans le dépôt, deux outils, et c'est normal.

`pose-parquet.com` est **gelé**, et depuis le 10 septembre 2026 le visualiseur
n'en dépend **plus du tout à l'exécution** : le moteur WebGL vit dans `web/`,
copié depuis le commit `8380ceb` et identique octet pour octet. La parité a été
mesurée avant la bascule, l'iframe n'est plus créée en fonctionnement normal, et
`?engine=external` la rallume pour la seule comparaison. Provenance, écarts
d'audit, parité et performances : [RENDERER-AUTONOMY-PLAN.md §16](RENDERER-AUTONOMY-PLAN.md).

## Où vivent les choses hors de ce dossier

| sujet | emplacement |
| --- | --- |
| le front public, gelé | dépôt `pose-parquet.com`, `outils/visualiseur-produit.html` — consommateur externe, **aucune modification pendant les lots IA** |
| le protocole de prise de vue d'une visite | dépôt du front, `docs/room-tour-protocol.md` |
| le contrat de visite et sa validation | dépôt du front, `data/room-tours.json`, `js/product/tour.js` |
| le moteur de rendu réellement utilisé aujourd'hui | dépôt du front, `outils/studio.html`, piloté par `window.__studio` depuis `tools/product-concept.html` — dépendance d'exécution à rendre autonome |
| les captures de repli | `datasets/private-real/_renders/`, hors de Git |
| tous les seuils du service | `app/core/config.py`, préfixe `PPAI_` |
| tous les codes d'avertissement | `app/core/warnings.py` |

## Règle de tenue

Un nouveau document ne se crée que si aucun document actif ne couvre son sujet.
Le cas contraire se traite par mise à jour. Cette règle vaut aussi pour la
documentation : pas de version 3 d'un document dont la version 2 était encore
juste.
