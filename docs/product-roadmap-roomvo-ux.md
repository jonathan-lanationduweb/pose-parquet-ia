# Plan produit — UX et distribution revendeur

26 octobre 2026. Le moteur métrique et le chantier matières prioritaires restent
des dépendances séparées. Les échéances sont des horizons de travail, pas des
promesses de livraison. S : faible, M : moyen, L : plusieurs lots.

## IMMEDIATE TOP 4

| ITEM | WHY NOW | USER IMPACT | RETAILER IMPACT | EFFORT | DEPENDENCIES | SUCCESS METRIC |
| --- | --- | --- | --- | --- | --- | --- |
| Résultat / analyse | La photo apparaît déjà avant l'analyse, mais le délai total manque de mesures | Élevé : savoir ce qui se passe | Élevé : moins d'abandon à diagnostiquer | S | Étapes actuelles de l'analyse | TTFV par appareil, à froid / à chaud |
| Correction mobile | Le pinceau existe ; les outils et libellés doivent être simples | Élevé : récupérer un cas difficile | Élevé : démonstrations récupérables | S | Validation et pinceau existants | Taux manuel, réussite après correction |
| Décision produit | Catalogue, favoris et export déjà présents ; manque le chemin de retour | Élevé : retrouver et partager son choix | Élevé : retour vers sa fiche | M | Identifiants et URL produits | Sélections/session, partage, Product Page CTR |
| Embed revendeur | Aucune interface publique, serveur actuel anti-iframe | Moyen : ouvrir depuis une fiche | Élevé : pilote intégrable | M | Hébergement, origines et catalogue autorisés | READY / ouvertures, fiches demandées |

## 6-MONTH ROADMAP

| PHASE | ITEM | DESCRIPTION | CUSTOMER BENEFIT | RETAILER BENEFIT | EFFORT | DEPENDENCIES | METRIC |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0–2 mois | Import simple | Aide courte implémentée ; photo immédiate conservée | Moins d'incertitude | Démonstration plus simple | S | Import existant | Sélection → photo affichée |
| 0–2 mois | Analyse lisible | États existants conservés, libellés simplifiés, marques locales ajoutées | Comprendre l'attente | Identifier les abandons | S | Contrat analyse | TTFV et taux d'échec |
| 0–2 mois | Correction | Quatre actions publiques mobile ; validation existante | Corriger sans jargon | Récupérer les cas difficiles | S | Pinceau existant | Taux manuel / réussite |
| 0–2 mois | Décision | Slider sur mobile, favoris, CTA et zoom matière explicite | Juger un produit | Retour vers la référence | M | Catalogue réel | Compare / Favorite Rate |
| 0–2 mois | Partage et export | Lien démo et export image existant ; photo privée sans lien cloud | Retrouver son choix | Faciliter l'échange client | M | Rendus finaux | Share / Download Rate |
| 0–2 mois | Deep link | productId, pièce démo et orientation ; contrôle des références | Ouvrir le bon produit | Entrée depuis fiche / QR | S | Produit rendable | Sélection après deep link |
| 2–4 mois | Pilote widget | Prototype livré ; installer sur un domaine pilote et lever DENY uniquement sur la page autorisée | Visualisation intégrée | Une ligne et isolation CSS | M | HTTPS, CSP, CORS modules, registre | Handshake READY / ouvertures |
| 2–4 mois | Catalogue revendeur | Remplacer le registre statique par un contrat de catalogue contrôlé | Choix pertinents | Assortiment et URL de sa boutique | L | API catalogue et autorisations | Produits valides / demandes |
| 2–4 mois | Favoris synchronisés | Adapter déjà livré ; connecter favoris parent | Retrouver ses références | Garder le parcours marchand | M | API du site parent | Écarts de synchronisation |
| 2–4 mois | QR produit | Générer des liens canoniques sur domaine stable ; séparés du transfert temporaire | Bon produit sur smartphone | Échantillons et PLV utilisables | M | Adresse publique stable | Ouvertures QR → rendu |
| 2–4 mois | Sessions | Configuration démo locale livrée ; définir restauration privée limitée | Reprise sans ressaisie | Utilisation en magasin | M | API privée versionnée | Return Session Rate |
| 2–4 mois | Analytics | Adapter sans fournisseur livré ; connecter le sink choisi | Parcours mieux mesuré | Mesurer la valeur du pilote | M | Choix analytics du revendeur | Funnel et qualité événements |
| 4–6 mois | API revendeur | Contrats versionnés, catalogues, matières et quotas | Catalogue stable | Industrialiser plusieurs sites | L | Hébergement et auth serveur | Erreurs / latence API |
| 4–6 mois | White-label contrôlé | Logo, accent, CTA et liens validés ; aucune page-builder | Continuité de marque | Marque conservée | M | RetailerConfig fiable | Adoption des pilotes |
| 4–6 mois | Partage privé | Jetons opaques, expiration, suppression et limite de stockage | Partager une pièce avec accord | Suivi des choix client | L | Lot backend dédié | Share / Restore Success Rate |
| 4–6 mois | Cache serveur | Versions de catalogue et matières ; contenu privé jamais public | Moins d'attente | Coûts et stabilité mesurables | M | Clés et politique de cache | Cache Hit / TTFV |
| 4–6 mois | R&D navigateur | Comparer backend, WASM et WebGPU sur appareils physiques | Délai total éventuellement réduit | Meilleure couverture mobile | L | Modèle exportable / benchmark | Temps froid, RAM, qualité |
| 4–6 mois | Capture guidée | Repère UX déjà préparé ; évaluer preview caméra et guidage réel | Meilleures photos | Moins de correction | M | HTTPS, permissions, tests iOS | Réussite première photo |

## KPIs et définitions

- Time to First Visualization : photoSelected → premier parquet réellement présenté.
  TARGET interne : environ 3 s quand l'infrastructure le permet ; aucun résultat
  réel de ce lot ne valide ce chiffre.
- Analysis Success Rate : analyses exploitables / analyses terminées.
- Manual Correction Rate : sessions avec correction / sessions analysées.
- Product Selections / Session : choix utilisateurs, distincts des restaurations.
- Favorite / Compare / Share Rate : sessions avec action / sessions actives.
- Product Page CTR : sessions avec PRODUCT_PAGE_REQUESTED / sessions actives.
- Visualizer Completion Rate : sessions atteignant un résultat puis une action
  de décision / sessions ouvertes. Ce n'est pas une vente.
- Return Session Rate : reprises de session / sessions ouvertes.
- Les dénominateurs, fenêtres et déduplications doivent être identiques dans le
  site parent. Aucune statistique de conversion n'est inventée ici.

## ANALYTICS

Events : visualizer_open → photo_import ou demo_room_selected →
analysis_success ou analysis_manual_required → product_selected →
favorite / compare / share / download → product_page_click.
analysis_unavailable distingue les pannes des corrections demandées.
product_view est émis à l'ouverture du zoom matière, pas à toutes
les cartes injectées dans le DOM. session_restored marque la reprise d'une démo.
L'adapter permet track(name,payload) ; ce lot
n'ajoute aucun tracker publicitaire ni stockage distant.
Ne transmettre ni photo, ni nom de fichier, ni SceneData, ni URL de transfert.
Le site marchand décide des règles de collecte et des conversions.

## PERFORMANCE UX

Marques locales par import : photoSelected, photoDisplayed, analysisStarted,
sceneReady, firstFloorRender, interactiveReady. Les cinq intervalles adjacents
sont exposés via window.__retailerUX.performance.snapshot().
telemetry=0 désactive les marques. Aucun pourcentage simulé.
photoDisplayed correspond à la présentation DOM actuelle, pas à une mesure du
premier pixel par le navigateur. Une mesure de peinture dédiée serait un ajout
distinct ; les résultats actuels ne doivent pas être présentés comme telle.
L'analyse inclut le chemin de préparation / santé du service, pas seulement
l'inférence. Les tests UX à réponse interceptée ne sont pas un benchmark IA.

Résultat progressif : point d'extension déclaré, non branché à un faux résultat.
Contrat futur : generation, revision, stage fast/refined, SceneData et validation.
Accepter uniquement la génération courante et une révision plus récente ; ignorer
un refinement après une correction utilisateur, sauf accord explicite.
tapCorrection reste unsupported : le pinceau est la solution disponible.

## CACHE / PRIVACY

Existant : quatre réponses SHA-256 en mémoire dans room-analysis-client ; images
et SceneData réutilisées pendant la page, rendus/matières versionnés côté moteur.
Ce lot persiste seulement les choix publics et la provenance démo/photo en
sessionStorage. Aucun octet photo ni SceneData privé n'y est enregistré.
Après reload, une photo doit être réimportée ; le cache mémoire ne survit pas.
Le partage privé restaurable et sa durée de conservation attendent le lot backend.

Proposition de clés publiques : retailerId + catalogId + catalogVersion ;
materialId + materialVersion + rendererVersion + paramètres physiques.
Ne jamais inclure une photo personnelle dans un cache CDN public.
Le serveur DEV est volontairement no-store ; ne pas en déduire une politique
de cache de production. Le lot n'ajoute pas de cache serveur.

## R&D segmentation navigateur — aucune migration

Aucun modèle ONNX n'a été ajouté, converti ou téléchargé. L'état est NON MESURÉ
pour le poids du modèle candidat, son téléchargement, la RAM et la latence mobile.
WASM et WebGPU sont des options à comparer ; leurs contraintes diffèrent selon
l'appareil. Le multithreading WASM nécessite une isolation cross-origin, ce qui
doit être testé avec l'embed. Sources primaires :
[Compatibilité ONNX Runtime Web](https://onnxruntime.ai/docs/get-started/with-javascript/web.html),
[Diagnostic de performance](https://onnxruntime.ai/docs/tutorials/web/performance-diagnosis.html).

Matrice à produire : iPhone Safari, Android Chrome entrée/milieu de gamme,
tablette magasin et desktop. Pour chaque variante : poids transféré à froid,
download + initialisation + inférence + rendu, RAM/pic mémoire, blocage UI,
énergie et qualité sur les mêmes photos autorisées. Répéter à chaud, hors ligne
si pertinent, et avec WebGPU absent. Le backend existant reste la référence.
Décider sur le délai total et la qualité, jamais sur le seul temps d'inférence.