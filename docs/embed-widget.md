# Widget revendeur — contrat v1 et déploiement

## État livré / limites

Prototype natif, sans dépendance front ni modification du moteur ou du backend.
Registre local : seul le revendeur demo / catalogue default est configuré.
Langue réellement disponible : fr-FR. Les autres locales sont refusées.
Le code est prêt à tester ; ce n'est pas un service hébergé multi-revendeurs.

IMPORTANT : le FastAPI actuel envoie X-Frame-Options: DENY. La page iframe est
donc bloquée tant que l'hébergement n'est pas configuré. Le loader propose une
ouverture dans un nouvel onglet après absence de READY. Les tests d'iframe
utilisent un override d'en-tête STRICTEMENT dans le harnais navigateur pour
simuler un hébergement autorisé. La protection du serveur réel reste inchangée.

## Architecture

Site revendeur → web/integration/widget.js → iframe dédiée →
tools/product-concept.html ↔ postMessage ↔ API JS du loader.

Le loader isole l'interface de la boutique. Il lit les data-*, crée son container
ou sa modale native, valide le handshake et met les commandes en file bornée.
L'hôte reste responsable de sa navigation et de ses favoris.

## Installation et fiche produit

Chemins relatifs ci-dessous pour la démo sur le même serveur. En production,
remplacer src par l'URL HTTPS réelle de votre déploiement, pas un domaine fictif.

    <script src="/web/integration/widget.js"
      data-retailer-id="demo"
      data-catalog-id="default"
      data-product-id="CHENF39031"
      data-locale="fr-FR"
      data-mode="inline"></script>

Modes : inline (ouvre immédiatement) ou modal (ouvrir avec l'API).
Option data-visualizer-url : adresse de la page hébergée. HTTPS requis hors
localhost. Aucun secret dans les attributs, URL ou messages.

Le registre de confiance est web/integration/retailer-config.js, livré par
l'exploitant du visualiseur. Définir pour chaque revendeur ses catalogues et
allowedParentOrigins exactes. parentOrigin dans l'URL ne crée AUCUNE confiance.
Les catalogues non configurés sont refusés. Un catalogue null représente
l'assortiment complet existant ; un tableau limite les IDs disponibles.
Ce filtrage UI ne remplace pas une autorisation serveur pour des données privées.

## Déploiement requis

- HTTPS stable pour le visualiseur et les QR imprimés.
- CSP frame-ancestors avec origines revendeurs explicites sur la page HTML.
  Retirer/adapter DENY seulement pour cette page autorisée ; garder les APIs
  et les autres routes protégées. SAMEORIGIN suffit pour la démo locale.
- CORS des modules statiques utilisés par l'import dynamique du loader :
  autoriser les domaines partenaires nécessaires, sans credentials pour ces
  fichiers publics. Configurer le type MIME JavaScript.
- Vérifier aussi la CSP script-src / frame-src du site marchand.
- Ne jamais héberger ce prototype en exposant les dossiers de revue privée,
  datasets, modèles ou fichiers locaux.
- Définir un vrai registre par revendeur et les URLs produit côté hôte.
- Tests Safari/iOS et téléphones physiques restent un préalable aux pilotes.

## API JS

Après l'événement window pose-parquet-widget-ready :

    const v = window.PoseParquetVisualizer;
    v.open();
    v.close();
    v.setProduct("CHENF39031");
    v.setCatalog("default");
    v.setFavorites(["CHENF39031"]);
    v.openRoomSelector();
    v.resetSession();
    const off = v.on("PRODUCT_SELECTED", ({productId}) => { /* votre code */ });
    off();

set* retourne l'acceptation locale de la commande, pas son application dans
l'iframe. COMMAND_RESULT donne le résultat métier asynchrone. L'ouverture du
dialogue et les API de presse-papiers restent liées aux gestes navigateur.
Un loader gère une instance : ne pas multiplier les scripts sur une même page.

Exemple modal :

    <button id="visualize">Visualiser chez moi</button>
    <script src="/web/integration/widget.js"
      data-retailer-id="demo" data-product-id="CHENF39031"
      data-mode="modal"></script>

    window.addEventListener("pose-parquet-widget-ready", () => {
      const v = window.PoseParquetVisualizer;
      document.querySelector("#visualize").onclick = () => v.open();
      v.on("PRODUCT_PAGE_REQUESTED", ({productId}) => {
        // Résoudre l'URL dans votre catalogue ; ne pas recevoir une URL arbitraire.
        openYourProductPage(productId);
      });
    });

## POSTMESSAGE CONTRACT

Envelope exacte :

    {
      source: "pose-parquet-visualizer",
      version: 1,
      type: "PRODUCT_SELECTED",
      payload: { productId: "CHENF39031" }
    }

Parent → iframe : source pose-parquet-retailer.
Iframe → parent : source pose-parquet-visualizer.
Les deux côtés valident origin, event.source (fenêtre exacte), version, type,
schéma du payload et absence de champs supplémentaires.
Aucun postMessage avec targetOrigin "*".
IDs : caractères alphanumériques, point, tiret, underscore, 128 caractères max.
1000 favoris max. Pas de photos, filename, pixels, SceneData ou secrets.
Les handlers analytics et callbacks parent sont isolés des exceptions hôte.

### Parent → visualiseur

| TYPE | PAYLOAD | COMPORTEMENT |
| --- | --- | --- |
| SET_PRODUCT | productId | ID connu, rendable et compatible, sinon refus |
| SET_CATALOG | catalogId | Catalogue enregistré seulement |
| SET_FAVORITES | favoriteIds | Remplacement canonique, sans écho de faux clics |
| OPEN_ROOM_SELECTOR | {} | Ouvre le sélecteur de pièces |
| RESET_SESSION | {} | Efface pièces, cache analyse en mémoire et configuration de cet onglet ; conserve favoris |

### Visualiseur → parent

| TYPE | PAYLOAD |
| --- | --- |
| READY | retailerId, catalogId, locale |
| ROOM_SELECTED | roomId |
| PHOTO_IMPORTED | source: uploaded |
| ANALYSIS_COMPLETED | status: ready / approximate / manual / unavailable |
| PRODUCT_SELECTED | productId |
| FAVORITE_ADDED | productId |
| FAVORITE_REMOVED | productId |
| COMPARE_OPENED | productId |
| SHARE_REQUESTED | kind: demo / private |
| DOWNLOAD_COMPLETED | productId |
| PRODUCT_PAGE_REQUESTED | productId |
| COMMAND_RESULT | command, ok, code |

READY signifie bridge disponible, pas modèle IA déjà chaud.
DOWNLOAD_COMPLETED signifie image générée et téléchargement demandé au
navigateur : l'application ne peut pas confirmer l'écriture disque.

## Favoris

    v.on("READY", () => v.setFavorites(favoriteIdsFromYourStore));
    v.on("FAVORITE_ADDED", ({productId}) => addFavoriteInYourStore(productId));
    v.on("FAVORITE_REMOVED", ({productId}) => removeFavoriteInYourStore(productId));

Le site parent choisit son stockage. Les favoris locaux sont séparés par
revendeur/catalogue ; demo/default conserve la clé historique. Aucun compte
Pose Parquet n'est imposé. RESET_SESSION ne supprime pas les favoris marchands.

## Deep link et QR produit

Route existante supportée :

    /tools/product-concept.html?retailerId=demo&catalogId=default&productId=CHENF39031&locale=fr-FR

Pour une configuration démo, ajouter roomId, pattern (informatif, dérivé du
produit) et angle. L'angle est validé dans [0,360[.
Une référence sans aperçu n'applique jamais une matière inventée.
Une référence incompatible avec une pièce est refusée.

Route canonique souhaitée pour QR imprimé : /v/{retailerId}/{productId}.
Ce rewrite stable doit être fourni par l'hébergement ; il n'est PAS ajouté à
FastAPI dans ce lot. Le domaine définitif est encore à choisir.
Ne pas imprimer les liens Cloudflare temporaires ni le QR de transfert photo.

## Partage et téléchargement

Le lien démo contient uniquement configuration publique, pièce, produit,
orientation. Aucune URL blob, clé de transfert ou paramètre DEV n'est copié.
Le lien utilise le moteur de la version publiée ; un essai DEV n'est pas un instantané partageable.
Sur localhost, l'interface précise que le lien fonctionne sur ce PC seulement.
Pour une photo privée : export JPEG du canvas final existant, aucun lien cloud.
Le dialogue de partage explique cette limite. Pas de screenshot DOM.

## SceneSession / cache

sessionStorage : source démo/photo, ID démo, produit, angle, échelle et date.
Pas de photo ni SceneData privé. Les pièces démo peuvent être restaurées après
reload. La photo doit être réimportée après reload. Dans la même page, le client
d'analyse réutilise déjà les réponses par SHA-256 (quatre entrées).
Il ne faut pas présenter cette reprise de configuration comme une restauration
complète de photo privée.

## AnalyticsAdapter

Aucun fournisseur ni requête analytics. Adapter local émet pose-parquet:analytics
avec name, payload réduit et date. L'hôte peut aussi brancher sa mesure depuis
les événements publics du loader. Il décide du sink et de la déduplication.
Performance locale désactivable : telemetry=0.

## BACKEND REQUIREMENTS FOR NEXT LOT

Contrats à concevoir et implémenter dans un lot dédié, absents aujourd'hui :
- GET /v1/retailers/{id}/config : origines autorisées, catalogues, thème et features.
- GET /v1/catalogs/{id}/products : pagination + catalogVersion, droits du revendeur.
- GET /v1/products/{id} et /material : identifiant, URL résolue et materialVersion.
- POST /v1/shares : accord de l'utilisateur, snapshot versionné, limites de taille,
  contexte revendeur, expiration et jeton opaque non devinable.
- GET /v1/shares/{token}, DELETE /v1/shares/{token} : lecture limitée au snapshot,
  révocation/suppression ; aucun chemin local exposé.
- Sessions privées : version modèle / SceneData / renderer, durée, invalidation,
  suppression ; contenu privé jamais cache public.
- Fast/refinement : révisions, génération et annulation, validation à chaque étape.

Ne pas réutiliser les clés du transfert téléphone comme tokens de partage.
Le top 50 matières et CameraModel restent hors de ce lot.