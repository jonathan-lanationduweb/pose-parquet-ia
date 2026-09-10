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
| [BENCHMARK-STRATEGY-V2.md](BENCHMARK-STRATEGY-V2.md) | **CIBLE** | les métriques conservées, les métriques produit à construire, le jeu visuel de référence, le passage de porte du premier lot technique |
| [ROADMAP-V2.md](ROADMAP-V2.md) | **CIBLE** | les lots A à J, les portes de décision humaines, le registre des risques, la grille d'arrêt du LOT C |
| [AUDIT-V2.md](AUDIT-V2.md) | **ÉTAT COURANT** | l'inventaire de l'existant, la matrice KEEP / KEEP+EXTEND / REWORK / LEGACY / DROP, les manques, les écarts documentaires |
| [annotation-protocol.md](annotation-protocol.md) | **DÉCISION** | **la définition officielle de `floor_visible`**, les trois notions à ne pas confondre, **le rôle d'une exclusion**, les natures de contour, les conventions de masque, le cycle `draft`→`reviewed`→`approved`, l'accord humain, la confidentialité du corpus |
| [architecture.md](architecture.md) | **ÉTAT COURANT** | la frontière Python / moteur, le pipeline livré, les deux contrats de schéma, les statuts existants, la journalisation, la configuration, les conditions avant toute dépendance lourde |
| [scene-data.md](scene-data.md) | **DÉCISION** | la structure de `SceneData@1`, les coordonnées normalisées et non bornées, `plane` ≠ `mask`, `planeRef` comme clé de continuité, les valeurs de `light` verrouillées, la table champ → lot |
| [product-ai-contract.md](product-ai-contract.md) | **DÉCISION** | le partage des rôles, les cinq statuts et l'écran associé, la règle de repli, `confidence` jamais affiché, le classement des capacités du moteur, les appels réseau, la confidentialité |
| [product-visualizer-ux.md](product-visualizer-ux.md) | **CIBLE** | l'expérience publique visée, les interdits d'affichage, le traitement UX des statuts. Attention : décrit une maquette gelée ; le visualiseur en service vit dans le dépôt du front |
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
CURRENT FRONT IMPLEMENTATION = pose-parquet.com/outils/visualiseur-produit.html
FRONT STATUS                 = external consumer / frozen during AI lots
ANNOTATION ENTRYPOINT        = tools/annotate.html          (actif)
UX REFERENCE                 = tools/product-concept.html   (legacy, gelée)
```

Ces lignes **décrivent l'existant, elles n'autorisent rien**. Pendant les lots
IA, le front est un **consommateur externe gelé** : décision humaine du
10 septembre 2026. Aucune modification de `pose-parquet.com` n'est permise,
et le fait que le produit visuel vive dans un autre dépôt est un sujet
d'architecture d'intégration **futur**, pas un problème à résoudre pendant les
lots B à F. L'autorisation d'y toucher sera donnée explicitement, au lot
d'intégration de bout en bout, et ne s'anticipe pas.

Dans ce dépôt, `tools/annotate.html` est le seul HTML actif — il produit la
vérité terrain. `tools/product-concept.html` est gelé : on le consulte, on ne
le développe plus. Pas de troisième HTML.

## Où vivent les choses hors de ce dossier

| sujet | emplacement |
| --- | --- |
| le visualiseur produit en service | dépôt du front, `outils/visualiseur-produit.html` — **une seule page**, les évolutions se font en JavaScript, CSS et données |
| le protocole de prise de vue d'une visite | dépôt du front, `docs/room-tour-protocol.md` |
| le contrat de visite et sa validation | dépôt du front, `data/room-tours.json`, `js/product/tour.js` |
| la maquette UX gelée | `../tools/product-concept.html`, marquée d'un bandeau |
| tous les seuils du service | `app/core/config.py`, préfixe `PPAI_` |
| tous les codes d'avertissement | `app/core/warnings.py` |

## Règle de tenue

Un nouveau document ne se crée que si aucun document actif ne couvre son sujet.
Le cas contraire se traite par mise à jour. Cette règle vaut aussi pour la
documentation : pas de version 3 d'un document dont la version 2 était encore
juste.
