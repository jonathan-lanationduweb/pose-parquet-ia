# Stabilisation V1 — journal des défauts

Passe de stabilisation sur `tools/product-concept.html`, menée en **utilisant**
le prototype dans Chrome avant de lire son code. Aucune fonctionnalité
ajoutée. Chaque entrée : symptôme reproduit → cause → correction → test de
non-régression (dans `tools/product-concept.check.js`, sauf mention).

Le front (`pose-parquet.com`) n'a pas été modifié dans cette passe.

---

## Critiques

### 1. Cadrage initial : la pièce dans une vignette

| | |
| --- | --- |
| symptôme | à 1920 px, deux bandes sombres de 190 px de part et d'autre de la photo ; la pièce flotte au centre |
| reproduction | ouvrir le séjour dans une fenêtre plus large que 3:2 |
| cause | « 100 % » était l'échelle qui fait *tenir* la photo (`min`) ; le stage est sombre, d'où les bandes |
| correction | `fitScale()` devient l'échelle de **couverture** (`max`) ; `fitToView()` centre. « Ajuster » (`fitAll`, bouton cible) montre toute la photo, sous 100 %, sur demande explicite. Un geste de zoom ne descend jamais sous la couverture (`zoomFloor`) et, depuis « Ajuster », ne saute pas à 100 % |
| test | `100 % couvre le cadre`, `a 100 %, aucun vide autour de la photo`, `Ajuster passe sous 100 %`, `zoomer en arriere depuis Ajuster ne saute pas a 100 %`, `revenir en arriere s arrete a la couverture` |

### 2. Cinq commandes mortes quand `requestAnimationFrame` ne tourne pas

| | |
| --- | --- |
| symptôme | double-clic, boutons + et −, « Ajuster », « 100 % », raccourcis clavier : aucun effet ; molette et glisser fonctionnent |
| reproduction | onglet dont rAF ne se déclenche pas (arrière-plan, cadre embarqué — et le panneau de revue lui-même : 0 frame en 500 ms) |
| cause | `setVp(…, animate)` faisait avancer `state.vp` **frame par frame** dans rAF ; sans frame, l'état ne changeait jamais |
| correction | l'état est commis immédiatement ; seule l'image est interpolée, par minuteur, avec rappel à l'état exact à la fin |
| test | `un zoom anime commet son etat sans attendre une frame` (rAF et setTimeout neutralisés), `aucun etat n est porte par requestAnimationFrame` |

### 3. Pilotage concurrent du moteur → capture fausse dans le cache

| | |
| --- | --- |
| symptôme | potentiel : version B et clic produit lancés ensemble copiaient chacun le canevas de l'autre, et le retenaient sous leur clef |
| reproduction | ouvrir une comparaison puis cliquer un produit pendant le rendu de B |
| cause | `applyCompareB` appelait `adapter.applyProfile` hors du mutex `state.applying` ; `onRendered` prévient tous les abonnés du même rendu |
| correction | file d'attente dans l'adaptateur (`enFile`) : une opération moteur à la fois, `openRoom` compris ; B ouvre la pièce par la même file |
| test | `les operations moteur passent par une file`, `la file survit a un echec`, `la version B ouvre la piece par la meme file` |

### 4. `picking` survivait à la fermeture du catalogue

| | |
| --- | --- |
| symptôme | « Comparer », fermer le catalogue sans choisir, puis « Choisir un parquet » : le clic pose une comparaison au lieu de changer de sol |
| cause | `closeAll()` ne remettait pas `state.picking` à faux |
| correction | `closeAll()` annule le choix de B ; changer de pièce aussi |
| test | `fermer le catalogue annule le choix de B`, `le clic suivant change bien de sol`, `changer de piece annule un choix de B en cours` |

## Majeurs

### 5. Résultat asynchrone périmé
Cause : la couche A n'était protégée que par la clef ; B pas du tout. Correction : jeton `state.intent`, incrémenté à chaque geste ; A vérifie clef **et** jeton, B vérifie que la comparaison est toujours celle demandée. Tests : `chaque geste incremente l intention`, `le rendu live de A verifie la clef ET le jeton`, `le rendu live de B verifie que la comparaison est toujours la`.

### 6. A = B possible
Comparer une référence à elle-même donnait deux côtés identiques. Correction : refusé avec message, le catalogue reste ouvert. Test : `comparer une reference a elle-meme est refuse`.

### 7. « Enregistrer » et « Partager » : boutons placebo
Ils n'affichaient qu'un message disant qu'ils ne faisaient rien. Retirés (le besoin reste documenté dans `product-visualizer-ux.md`). Test : `aucun bouton placebo dans l en-tete ni le menu`.

### 8. Fondu du sol collé
`beginFade()` retirait `.fading` par double rAF : sans frame, la classe restait. Correction : minuteur. Test : `le fondu du sol ne depend pas de rAF`.

### 9. Import : lecture périmée et URL qui fuit
Deux imports rapprochés : la première lecture pouvait aboutir après la seconde et remettre la première photo ; son `ObjectURL` n'était jamais libéré. Correction : jeton d'intention, révocation de l'URL périmée et en cas d'erreur. Test : `un import perime est ignore et son URL liberee`. Vérifié en Chrome : deux imports rapides → dernier gagne, 2 URL révoquées.

### 10. Vue « Favoris » remplacée par le catalogue entier
Retirer un favori depuis la liste des favoris repeignait tout le catalogue. Correction : `state.catalogueView`. Test : `retirer un favori garde la vue favoris`.

## Mineurs

### 11. Séparateur : `setPointerCapture` non protégé
`NotFoundError` non rattrapée (vue en console) ; sans capture, le séparateur aurait suivi la souris indéfiniment. Correction : `try/catch`, relâchement écouté aussi sur le stage. Test : `la capture du separateur est protegee`.

### 12. Champ fichier non remis à zéro
Choisir deux fois le même fichier ne déclenchait rien. Correction : `value = ''` après lecture. Test : `le champ fichier est remis a zero apres lecture`.

### 13. Viewport non reborné quand le cadre change sans `resize`
11 px de vide observés après un changement de taille en zoom. Correction : `ResizeObserver` sur le stage + rebornage au retour de visibilité. Test : `le stage est observe en taille`. Note : le panneau de revue ne livre ni `resize` ni observation (il ne peint pas de frames) ; le gestionnaire a été vérifié par un `resize` synthétique — la photo passe de 3840 à 3200 px de large pour un cadre de 1600.

### 14. Carte B : « Comparer » fermait la comparaison
Le même libellé sur les deux cartes faisait deux choses différentes. La carte B dit « Changer » et ouvre le choix de B. Test : `la carte B propose de CHANGER B, la carte A de fermer`.

---

## Ce qui a été éprouvé sans défaut

Après corrections, dans Chrome (fenêtre 1920 × 1080 émulée, pièce séjour) :

- chaque bouton visible cliqué deux fois : effet, fermeture, second effet ;
- pièces séjour → chambre → pièce claire → pièce-arcades → bureau-vide → séjour : scène juste, `z = 1`, aucun vide, produit conservé, repli propre sans rendu ;
- produits dans l'ordre, à l'envers, au hasard (17 changements) : nom, référence, motif, largeur cohérents entre carte, navigation et clef d'état ;
- 20 puis 50 clics rapides : le dernier gagne, stable 2 s après ;
- orientation 0 → 90 → 45 → 0 lentement et très vite : le dernier gagne ;
- comparaison Zeus/Houston, Houston/Colza, Colza/Pivoine, Notting Hill/Zeus : A ≠ B, trois couches dans la même boîte, viewport inchangé ; ouvrir → fermer → rouvrir → changer B ;
- comparaison + zoom + pan + séparateur + changer B + zoom : transformations identiques sur les trois groupes à chaque étape ;
- avant/après à 100, 200, 300 % après déplacement, 4 bascules par niveau : viewport et tailles de canevas inchangés ;
- favoris : ajout, retrait, ouverture, changement de pièce, retrait depuis la liste ;
- import JPEG, PNG, WebP, type refusé, deux imports rapides, retour pièce : URL révoquées, cadrage couvrant, aucun masque ;
- immersif : header et navigation masqués, photo plein cadre ; `requestFullscreen` refusé par le cadre → mode CSS sans erreur ;
- 1920, 1600, 1440, 1280, 1100 px et 600–1080 px de haut : aucun vide, commandes dans l'écran ; redimensionner à 250 % : valeurs finies, aucun saut ;
- moteur indisponible (page sans `__studio`) : repli statique, raison exacte, pièces/produits/comparaison utilisables ;
- rechargement de l'iframe : renégociation, scène et cache remis à zéro, rendu live de retour, 3 abonnements pris / 3 rendus ;
- **session continue de 635 s : 418 itérations du parcours complet, 7 315 actions, 0 échec, 0 erreur console, 0 rejet, mémoire 139 Mo, aucun état bloqué, aucun rechargement.**
