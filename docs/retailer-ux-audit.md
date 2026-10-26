# Audit UX / distribution revendeur — 26 octobre 2026

## CURRENT UX
Entrypoint : tools/product-concept.html. Home photo / catégories, photo principale,
catalogue latéral desktop et tiroirs mobile. État central etatProduit / phaseProduit.
Photo affichée avant analyse ; erreurs et correction déjà séparées.
Chantier métrique présent et non committé : conserver intégralement.

## EXISTING FEATURES
Import et transfert QR desktop/mobile ; catégories contenant plusieurs pièces ;
catalogue et filtres motif, teinte, largeur, usage, aperçu ; favoris localStorage ;
avant/après, comparaison A/B avec séparateur et deux vues ; téléchargement du
canvas final ; CTA fiche ; cache de rendus versionné et cache analyse SHA en mémoire.
Validation géométrique consommable et correction Ajouter / Retirer / Annuler / Terminé.

## MISSING FEATURES
Aide photo courte, capture guidée préparée, marques temporelles par import,
partage par lien de pièce démo, synchronisation favoris, deep link produit,
contexte revendeur, contrat postMessage, widget isolé et reprise de configuration.
Les sessions photos restent en mémoire de l'onglet. Ne pas persister leurs octets.

## INTEGRATION READINESS
Pas de loader / API revendeur existants. Plusieurs centaines de références, états
exact / représentatif / indisponible déjà présents. Un catalogId URL ne constitue
pas une autorisation : il faut un registre déployé côté intégrateur, puis une API
catalogue par revendeur au lot suivant. Hébergement, CSP frame-ancestors et
allowlist des origines à configurer au déploiement. Aucun push autorisé par ce lot.

## PERFORMANCE UX GAPS
Mesures locales de rendu existantes, mais pas de funnel sélection → interaction.
L'analyse réelle et la préparation de modèle dominent parfois le premier résultat.
Ne pas promettre 3 s. Le client évite déjà de réanalyser un fichier identique dans
la page ; reload perd ce cache. Les réponses photo ne doivent pas devenir publiques.

## SCREEN AUDIT
| Écran | KEEP | SIMPLIFY | MOVE | REMOVE |
| --- | --- | --- | --- | --- |
| Home | Photo + catégories | Aide trois conseils | Aide capture dans un panneau | Jargon calibration |
| Visualiseur | Grande photo + barre compacte | Messages | Partage dans options existantes | Aucun outil moteur ajouté |
| Catalogue | Recherche et filtres réels | Zoom matière explicite | Détail matière en dialogue | Filtre sans données |
| Personnaliser | Dimensions et orientation | Libellés | Réglages avancés hors correction | Aucun changement moteur |
| Comparer | Même caméra et orientation | Slider mobile | Deux vues réservées grand écran | Petites vues mobiles |
| Correction | Ajouter, retirer, annuler, terminé | Libellés courts | Taille de brosse hors mobile | Outils techniques publics |
| Mobile | Tiroirs bas | Cibles tactiles | Actions secondaires dans options | Débordements |

## IMMEDIATE TOP 4
1. Analyse / résultat : instrumentation réelle et aide import. Impact client élevé,
revendeur élevé ; effort S ; dépendance étapes existantes ; métrique TTFV.
2. Correction mobile : quatre actions compréhensibles et validation existante.
Impact client élevé, revendeur élevé ; effort S ; dépendance pinceau ; taux manuel.
3. Décision : deep link, partage démo, export, CTA et reprise locale.
Impact client élevé, revendeur élevé ; effort M ; dépendance produits ; CTR / partage.
4. Embed : loader isolé, messages contrôlés et favoris synchronisés.
Impact client moyen, revendeur élevé ; effort M ; dépendance hébergement / allowlist ;
métrique ouverture → sélection → fiche. Pas de gain de conversion chiffré inventé.