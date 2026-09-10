# Expérience publique du Visualiseur — spécification UX

> **VISUALIZER ENTRYPOINT = `tools/product-concept.html` · STATUS = ACTIVE
> PRODUCT VISUALIZER.** Décision humaine du 10 septembre 2026 : ce fichier est
> le visualiseur que nous faisons évoluer, et ce document décrit ce qu'il doit
> devenir. `pose-parquet.com` est gelé et n'est plus une cible de
> développement.
>
> Ce que la décision ne change pas : le fichier pilote toujours le moteur du
> front dans une iframe par `window.__studio`, avec les captures
> préfabriquées en repli. C'est une **dépendance d'exécution vers un dépôt
> gelé**, constatée et non résolue — la rendre autonome est un sujet à part,
> et personne n'a décidé comment.

Ce document décrit l'expérience **publique cible** : ce que voit une personne
qui envoie une photo de sa pièce. Le visualiseur doit pouvoir servir plusieurs
sites — Premibel, Pose Parquet, d'autres, éventuellement en marque blanche —
donc rien ici ne suppose un site commercial particulier, et aucun nouveau
couplage à `pose-parquet.com` ne doit être ajouté.

> **Ce document ne décrit pas `tools/annotate.html`.** Cet outil-là fabrique la
> vérité terrain du banc d'essai : il est interne, destiné à une personne qui
> mesure, et il demande un travail précis. L'expérience publique demande
> l'inverse — que l'utilisateur ne travaille pas. Les deux ne doivent plus être
> confondus, et aucune décision de l'un ne contraint l'autre.

Rien ici n'est implémenté. Ce document existe pour qu'une autre conversation,
ou un autre développeur, puisse intégrer l'expérience sans réinventer les
décisions — et pour que le service Python sache ce qu'on attendra de lui.

---

## 1. Le principe, en une phrase

> **L'utilisateur ne travaille pas pour l'outil. L'outil prépare la pièce, puis
> laisse l'utilisateur créer.**

Tout le reste en découle. Chaque fois qu'une décision hésite, c'est cette
phrase qui tranche : si un écran demande un effort dont le système est capable,
l'écran a tort.

### Trois niveaux qui coexistent

| niveau | ce que fait l'utilisateur | ce qu'il obtient |
| --- | --- | --- |
| **1 · Simple** | il envoie une photo | un parquet posé, tout de suite |
| **2 · Inspiration** | il touche une carte | une direction visuelle complète |
| **3 · Personnalisation** | il reprend la main | essence, teinte, motif, largeur, finition, réglages |

Les trois sont sur **le même écran**. Personne ne « passe en mode avancé » :
le niveau 3 est simplement plus bas dans le panneau de droite, et le niveau 2
plus bas dans l'écran. On descend si on veut.

**Ce que le public ne fait pas par défaut : dessiner le contour du sol.** C'est
le geste que le service supprime. Il reste possible, mais comme réparation, pas
comme étape.

---

## 2. Le parcours

```
1. Votre photo  →  2. Analyse  →  3. Personnalisation  →  4. Résultat
```

Visuellement, **2 et 3 se fondent** : l'analyse est un moment, pas un écran, et
le premier parquet est déjà posé quand elle se termine. L'utilisateur passe de
« ma photo » à « ma pièce avec du parquet » sans avoir rien demandé.

L'étape 4 n'est pas une page : c'est l'état où l'on enregistre, compare,
partage ou demande un devis. Le fil des quatre étapes reste affiché en haut
parce qu'il rassure — on sait où on en est — mais il ne segmente pas le
travail.

### Étape 1 — Votre photo

Un seul geste : déposer ou choisir une photo. Aucun paramètre.

| état | ce que voit l'utilisateur | actions |
| --- | --- | --- |
| **EMPTY** | zone de dépôt, une phrase, deux exemples de pièces à essayer | déposer, choisir, essayer un exemple |
| **UPLOADING** | la photo apparaît en fondu, une barre fine | annuler |
| format refusé | « Cette image n'est pas dans un format que nous savons lire. JPEG, PNG ou WebP. » | choisir une autre photo |
| résolution insuffisante | « Cette photo est trop petite pour un rendu net. À partir de 800 px de côté. » | choisir une autre photo |
| photo difficile | la photo est acceptée, l'avertissement vient **après** l'analyse | — |

**Le refus n'est jamais un cul-de-sac.** Chaque message dit quoi faire
ensuite, et la zone de dépôt reste là.

**Remplacer la photo** est toujours accessible depuis le panneau gauche — et
conserve les choix de parquet, ce qui permet d'essayer la même idée sur deux
pièces.

Aucun stockage public n'est développé maintenant. La photo vit dans l'onglet.

### Étape 2 — Analyse

Trois moments nommés, dans la langue de l'utilisateur :

```
Le sol          ·  ✓
La perspective  ·  ✓
Les obstacles   ·  ✓
```

Puis : **« Votre pièce est prête »**, et le premier parquet est déjà là.

**Interdits d'affichage** : logs, noms de modèles, scores, pourcentages de
confiance, coordonnées, nombre de sommets, durées en millisecondes. Rien de
tout cela n'aide à décider, et tout cela inquiète.

La progression doit rester honnête : si l'analyse dure 4 s, on montre 4 s. On
ne fabrique pas une fausse barre pour paraître travailler, et on n'annonce pas
« Les obstacles ✓ » si le service n'a pas cette capacité ce jour-là — l'étape
correspondante n'apparaît alors pas du tout.

> **Dans le prototype, ces états sont des DEMO.** Ils sont déclenchés à la
> main par un sélecteur visible, et le prototype le dit. Aucune de ces phrases
> ne doit être écrite dans le front avant que la capacité correspondante
> existe : annoncer « perspective ajustée » sans l'avoir ajustée est un
> mensonge que l'utilisateur découvrira sur le rendu.

---

## 3. Les quatre issues de l'analyse

Le service Python produit `status` ∈ `success` · `partial` ·
`needs_manual_adjustment` · `rejected`. L'UX les traite **différemment** — et
c'est le point qui décide si le produit paraît intelligent ou fragile.

### `success` — aucun travail demandé

Le parquet est posé, l'écran principal s'ouvre. Le panneau gauche affiche trois
coches. **Aucun avertissement, aucune invitation à corriger.** « Ajuster la
détection » existe mais reste un bouton secondaire, gris, que personne ne
touche.

### `partial` — le résultat d'abord, la réserve ensuite

Le rendu est affiché comme dans `success`. Un bandeau **non bloquant** apparaît
sous l'image, et seulement s'il apporte quelque chose :

> Le coin gauche au fond est incertain — le parquet peut y déborder.
> **Ajuster** · *Ignorer*

La règle est stricte : **le rendu passe avant l'avertissement.** Un utilisateur
qui voit d'abord un avertissement croit que ça n'a pas marché. Un utilisateur
qui voit d'abord sa pièce, puis une réserve, comprend qu'on lui parle d'un
détail.

Un `partial` sans conséquence visible ne produit **aucun** bandeau.

### `needs_manual_adjustment` — une retouche, pas un polygonage

Le rendu est affiché tel qu'il est, avec une invitation claire :

> Le sol n'est pas tout à fait juste. **Ajuster la détection** — deux minutes.

L'écran de correction n'est **pas** un éditeur de sommets. Voir §7.

### `rejected` — expliquer et raccompagner

Pas de rendu. Un écran calme, la photo en grand mais atténuée, et une raison
en langage courant, tirée du `warnings` correspondant :

| cause technique | ce qu'on dit | ce qu'on conseille |
| --- | --- | --- |
| `image_too_small` | « Cette photo est trop petite pour un rendu net. » | « Reprenez-la à la résolution normale de votre appareil. » |
| `image_blurry` | « La photo est floue. » | « Appuyez-vous contre un mur, ou posez le téléphone. » |
| `image_too_dark` | « La pièce est trop sombre. » | « Ouvrez les rideaux ou allumez. » |
| aucun sol trouvé | « Nous ne trouvons pas de sol sur cette photo. » | « Reculez de deux pas et cadrez le sol au premier plan. » |

Et toujours, en bas : **« Essayer une autre photo »** et **« Choisir une pièce
d'exemple »**. Un rejet ne doit jamais renvoyer l'utilisateur nulle part.

> **Rappel** : la logique de confiance du LOT IA 7 n'est pas développée ici. On
> prépare seulement les quatre entrées de l'UX.

---

## 4. L'écran principal

```
┌───────────────────────────────────────────────────────────────────────┐
│  Pose Parquet     Photo — Analyse — Personnalisation — Résultat   ♡ ⋯ │
├──────────┬─────────────────────────────────────────┬──────────────────┤
│          │                                         │                  │
│ Votre    │                                         │  Parquet         │
│ pièce    │                                         │  Ambiances       │
│ [vignette]│           LA PIÈCE                     │  Réglages        │
│          │        (parquet appliqué)               │                  │
│ Sol ✓    │                                         │  ┌────┬────┐     │
│ Persp. ✓ │                                         │  │    │    │     │
│ Obst. ✓  │                                         │  └────┴────┘     │
│          │      [ ◑ Avant/après ]      [ ⤢ ]      │                  │
│ Ajuster  │                                         │                  │
├──────────┴─────────────────────────────────────────┴──────────────────┤
│  Suggestions pour votre pièce    ▸ ▸ ▸                                │
└───────────────────────────────────────────────────────────────────────┘
```

**La pièce domine, et cela se mesure.** Cible : la zone centrale occupe au
moins **58 % de la largeur** et **72 % de la hauteur utile** sur un écran de
1440 px. Panneau gauche 200–240 px, panneau droit 300–340 px, bande basse
120–150 px et **rétractable**.

### Ce que j'écarte de la maquette, et pourquoi

La direction validée est bonne. Trois points me paraissent devoir être
challengés, comme le lot y invite :

**Une seule bande basse, pas quatre.** La maquette prévoit
« suggestions / coups de cœur / similaires / catalogue ». Quatre rangées de
cartes noient la pièce et transforment l'écran en boutique. Je propose **une**
bande, avec un sélecteur de contenu discret (`Suggestions` · `Mes favoris` ·
`Catalogue`), et une seule rangée visible à la fois. Le catalogue complet
mérite son propre écran plein — pas une lucarne.

**Trois onglets à droite, jamais quatre.** `Parquet` · `Ambiances` ·
`Réglages`. Et `Ambiances` doit être le **même** contenu que la bande basse,
pas un second jeu de propositions : deux endroits qui suggèrent des choses
différentes obligent à comparer deux listes.

**Le panneau gauche n'est pas un diagnostic.** Trois lignes d'état maximum, une
vignette, un bouton secondaire. Pas de score, pas de détail géométrique, pas de
liste d'avertissements. Ce qui doit être dit à l'utilisateur se dit sous
l'image, où il regarde.

### Le panneau gauche

```
Votre pièce
[ vignette 16:10 ]
Salon · 1600 × 1067

Sol détecté            ✓
Perspective ajustée    ✓
Obstacles identifiés   ✓

[ Ajuster la détection ]
[ Changer de photo ]
```

Les coches sont vertes. Un état incertain devient un point ambre et une phrase
courte — jamais une croix rouge, qui ferait croire à un échec.

`Changer de pièce` avec des vignettes n'a de sens qu'une fois plusieurs photos
en session. Tant que le stockage n'existe pas, ce bloc n'apparaît pas.

### Le viewport central

Trois contrôles, et rien d'autre, en surimpression discrète :

- **Avant / après** — voir §8 ;
- **Plein écran** ;
- **Comparer** — voir §9.

Le zoom et le déplacement existent mais sans boutons : molette et glissé
suffisent, et un utilisateur qui ne zoome pas ne doit pas voir de commande de
zoom.

---

## 5. Personnalisation — le panneau de droite

Trois onglets. Le premier suffit à 90 % des visiteurs.

### `Parquet`

| contrôle | forme | ce qui le contraint |
| --- | --- | --- |
| **Essence** | pastilles texturées, 4–6 visibles, « voir tout » | le catalogue réel |
| **Teinte** | pastilles de couleur, 5–6 | la gamme réelle de l'essence |
| **Motif** | 3 grandes vignettes illustrées | ce que le moteur sait faire |
| **Largeur** | 3 à 4 crans nommés, pas un curseur libre | les largeurs réellement vendues |
| **Finition** | 3 pastilles avec un reflet visible | les finitions réellement proposées |

**Les crans, pas les curseurs.** Une largeur de lame n'est pas continue : les
produits existent en 90, 140, 190 mm. Un curseur libre laisserait choisir
120 mm et fabriquerait un rendu qu'aucun devis ne peut suivre. Les crans
portent le millimétrage réel en légende.

**Ne jamais proposer une combinaison qui n'existe pas.** Si une essence n'a pas
de version « gris », la pastille grise disparaît — elle ne se grise pas, elle
n'est pas là. Le front dispose déjà de `compatiblePatterns` par référence : un
motif non compatible ne doit pas être offert.

### `Ambiances`

Le même contenu que la bande basse, en colonne. Voir §6.

### `Réglages`

Replié par défaut, et c'est essentiel : un utilisateur qui ouvre le panneau et
voit huit curseurs referme l'onglet. Chaque réglage n'apparaît que si le moteur
le porte réellement — voir `docs/product-ai-contract.md` §5 pour le classement
exact de chacun.

```
Orientation des lames        ↺ ────●──── ↻     (existe)
Variation entre lames        ────●────         (existe)
Visibilité des joints        ──●──────         (existe)
Brillance                    ────●────         (existe)

⌄ Réinitialiser les réglages
```

**Une seule ligne de sécurité** : « Réinitialiser les réglages » ramène aux
valeurs du produit. Sans elle, un utilisateur qui a poussé un curseur trop loin
croit avoir cassé le rendu.

---

## 6. Suggestions — trois générations à ne pas confondre

La bande basse propose des directions prêtes :

| carte | ce qu'elle applique |
| --- | --- |
| **Clair et lumineux** | chêne naturel, lames larges, mat |
| **Chaleureux** | chêne miel, lames, huilé |
| **Élégant et moderne** | chêne gris, lames étroites, satiné |
| **Caractère** | chêne fumé, lames, brossé |
| **Point de Hongrie** | chêne naturel, point de Hongrie |
| **Bâton rompu** | chêne miel, bâton rompu |

Une carte = **une image** de la pièce de l'utilisateur avec ce parquet, plus
deux lignes de texte. Pas une fiche produit : on choisit une ambiance à l'œil.

### Les trois générations, et la phrase qui va avec

| génération | ce que c'est | ce qu'on peut dire |
| --- | --- | --- |
| **A · presets éditoriaux** | six combinaisons choisies à la main | « Nos ambiances » |
| **B · suggestions calculées** | filtrées par les caractéristiques mesurées de la pièce — luminosité, teinte des murs, taille | « Adapté à votre pièce » |
| **C · recommandations IA** | un modèle apprend des choix | « Recommandé pour vous » |

**Aujourd'hui : A.** Et le libellé doit le dire. Écrire « Suggestions pour
votre pièce » alors que les six cartes sont les mêmes pour tout le monde est
une promesse creuse que l'utilisateur détecte à la deuxième pièce essayée.

La génération B est atteignable **sans aucun nouveau modèle** : la luminosité
et la teinte dominante de la photo sont déjà mesurées par l'étage qualité. Un
sol sombre dans une pièce sombre est un mauvais conseil, et le savoir ne
demande pas d'IA. C'est la première évolution à faire, et la moins coûteuse.

---

## 7. Ajuster la détection — une retouche, pas un éditeur

Le bouton est **secondaire**. Quand l'analyse est bonne, personne ne le touche.

Quand on l'ouvre, l'écran de correction montre le sol détecté en surbrillance
douce et **cinq contrôles** :

```
[ + Ajouter au sol ]  [ − Retirer du sol ]     ○——● taille

[ ↶ ]  [ ↷ ]                        [ Terminé ]
```

Le geste est **le pinceau**, pas le sommet. On peint ce qui manque, on efface
ce qui dépasse, on annule si on s'est trompé. Le rendu se met à jour sous le
pinceau.

**Ce qui ne doit jamais apparaître ici** : des polygones à cinquante sommets,
des poignées de plan de perspective, le vocabulaire de `tools/annotate.html`.
Un utilisateur public ne doit pas soupçonner qu'un modèle de données
géométrique existe.

**Bonne nouvelle vérifiée** : le pinceau existe déjà dans le front —
`js/scene/mask.js` porte `beginStroke(zoneId, mode, radius, point)` avec
`mode ∈ {'add','remove'}`. Il n'y a rien à inventer, seulement à exposer
autrement. Voir `docs/product-ai-contract.md` §5.

Un ajustement de contour **ne relance pas** l'analyse Python. Voir §10.

---

## 8. Avant / après

Le contrôle le plus utilisé du produit. Il doit être atteignable **sans
réfléchir**, et trois formes coexistent bien :

- **maintien** — appuyer sur le bouton montre la photo d'origine, relâcher la
  rend. C'est le geste le plus rapide, et le plus naturel pour comparer ;
- **curseur** — une poignée verticale glissée sur l'image, pour montrer les
  deux moitiés ensemble ;
- **bascule** — un clic, pour laisser la photo d'origine affichée.

**Aucun réglage n'est perdu** en revenant à l'origine : on cache le parquet, on
ne le déconfigure pas.

---

## 9. Comparaison

Le produit doit permettre d'essayer plusieurs solutions sans perdre son
travail. Deux niveaux :

- **Comparer 2** — curseur ou côte à côte ;
- **Comparer 3** — trois vues égales sur grand écran.

Ces deux modes **existent déjà** dans le front (`js/studio/compare.js`, modes
`slider` et `grid`, deux ou trois variantes). L'UX publique n'a donc pas à les
concevoir, seulement à les rendre visibles plus tôt.

Un état conceptuel `comparisonSlots` décrit les variantes retenues :

```
comparisonSlots: [
  { id: 'a', label: 'Chêne naturel',  config: {…}, thumbnail: … },
  { id: 'b', label: 'Chêne gris',     config: {…}, thumbnail: … },
]
```

**Ce n'est pas dans `SceneData`.** Un choix de parquet n'appartient pas à la
géométrie de la pièce : la même scène supporte cent parquets. `SceneData`
décrit ce que la photo montre, `comparisonSlots` décrit ce que l'utilisateur
essaie. Mélanger les deux obligerait à revalider une scène à chaque changement
de teinte. Voir `docs/product-ai-contract.md` §6.

---

## 10. La séparation qui tient tout le produit

```
Python                            JS / WebGL
──────                            ─────────
comprend la pièce UNE FOIS   →    change le parquet INSTANTANÉMENT
produit SceneData                 lit SceneData
                                  teinte, motif, largeur, finition, réglages
```

**Un changement de parquet ne rappelle jamais Python.** C'est une règle
d'architecture, pas une optimisation : un aller-retour réseau par pastille de
teinte détruirait l'expérience, et l'utilisateur cesserait d'explorer.

Python est rappelé dans **trois cas seulement** :

1. une **nouvelle photo** ;
2. la même photo **recadrée ou remplacée** ;
3. éventuellement, un affinage explicitement demandé (« analyser plus finement »).

Un ajustement de masque au pinceau n'en fait **pas** partie : il modifie le
masque côté client, et le moteur repeint. Le front est déjà construit ainsi.

---

## 11. Favoris et enregistrement

Besoins **documentés, non développés** :

| besoin | ce que ça suppose |
| --- | --- |
| **Ajouter aux favoris** | une liste de configurations, locale à la session |
| **Enregistrer mon projet** | un identifiant, donc un stockage |
| **Retrouver mon projet** | un compte, ou un lien secret |
| **Partager** | une URL publique, donc de l'hébergement d'image |

Aucun compte, aucun backend, aucune base dans ce lot. Le cœur du produit doit
fonctionner **sans compte** : demander une inscription avant d'avoir montré un
résultat est le moyen le plus sûr de perdre le visiteur.

**Contrainte de confidentialité à ne pas perdre de vue** : une photo de
visiteur, et tout masque dérivé, restent temporaires. Ils n'entrent jamais dans
le corpus, le dataset, le banc d'essai ni les journaux — un masque de sol
décrit la géométrie d'une habitation. Voir `docs/annotation-protocol.md` §10.

---

## 12. Les dix états, un par un

| état | ce que voit l'utilisateur | actions | données nécessaires | appel Python |
| --- | --- | --- | --- | --- |
| **EMPTY** | zone de dépôt, exemples | déposer, choisir, exemple | — | non |
| **UPLOADING** | photo en fondu, barre fine | annuler | — | non |
| **ANALYZING** | trois moments nommés | annuler | — | **oui**, en cours |
| **SUCCESS** | pièce + parquet, 3 coches | tout | `sceneData` complet | terminé |
| **PARTIAL** | pièce + parquet, bandeau non bloquant | tout, + ajuster | `sceneData` + `warnings` | terminé |
| **NEEDS_MANUAL_ADJUSTMENT** | pièce + parquet imparfait, invitation | ajuster en priorité | `sceneData` partiel | terminé |
| **REJECTED** | photo atténuée, raison, conseil | autre photo, exemple | `status` + `warnings` | terminé |
| **CUSTOMIZING** | identique à SUCCESS, panneau droit actif | tous les contrôles | aucune nouvelle | **non** |
| **COMPARING** | 2 ou 3 vues, ou curseur | échanger, appliquer, fermer | aucune nouvelle | **non** |
| **SAVED** | confirmation discrète, favori marqué | continuer, partager | — | non |

La colonne de droite est la plus importante du tableau : **quatre états sur dix
ne parlent jamais à Python.** C'est là que vit la fluidité du produit.

---

## 13. Design

**Direction** : premium, calme, lumineux, éditorial. La pièce est le sujet ;
l'interface est le cadre.

| | |
| --- | --- |
| fond | blanc chaud `#fbfaf8`, gris très clair `#f2f1ee` |
| encres | graphite `#22201d`, gris moyen `#6b6660` |
| accent | brun terre `#8a6244` — bois, pas technologie |
| réussite | vert sourd `#3f7d53`, **uniquement** pour les états |
| réserve | ambre `#b07d2b`, jamais rouge pour un `partial` |

**Le bleu n'est pas la couleur du produit.** Apple est cité pour la hiérarchie,
les espaces et la finition — pas pour sa palette. Un accent brun terre dit le
bois ; un accent bleu dirait le logiciel.

**À éviter**, et c'est explicite : cartes partout, glassmorphism appuyé,
gradients décoratifs, look SaaS, grands panneaux sombres, bordures sur tout,
icônes qui n'informent pas.

**Typographie** : polices système, aucune police téléchargée. Titres en 600,
corps en 400, un seul niveau d'accent.

**Animations** : 150–250 ms, uniquement pour ce qui change d'état.
`prefers-reduced-motion` respecté.

---

## 14. Responsive

| largeur | disposition |
| --- | --- |
| ≥ 1280 px | trois colonnes, bande basse visible |
| 1024–1280 px | trois colonnes serrées, bande basse rétractée |
| 768–1024 px | pièce + panneau droit en **drawer**, panneau gauche en barre haute |
| < 768 px | pièce plein écran + **bottom sheet** de personnalisation |

Sur smartphone, on **n'essaie pas** de garder trois colonnes. Le parcours
devient : la pièce occupe l'écran, une feuille se lève depuis le bas pour la
teinte et le motif, et « avant/après » reste un bouton flottant. Ce lot ne
développe pas le mobile plus loin.

---

## 15. Le viewport immersif

La grande photo n'est pas une image posée sur la page : c'est **la vue que
l'utilisateur manipule**. On ne dit pas « voici votre pièce », on dit « votre
pièce est là, regardez-la de près ».

### Ce que c'est, et ce que ce n'est pas

C'est du **pan et zoom 2D** sur une photographie. Rien d'autre.

On ne peut donc pas : avancer dans la pièce, tourner derrière un meuble,
changer de point de vue, voir un mur sous un autre angle. L'interface ne le
propose pas et ne le suggère pas — pas de curseur d'orbite, pas de manette,
pas de vocabulaire de visite. Le jour où une vraie navigation 3D existera,
elle sera un autre lot, avec ses propres données.

L'inspiration d'interaction vient des outils cartographiques : la molette
zoome **sous le curseur**, le glisser déplace, un bouton recentre. Elle
s'arrête là. Rien n'est emprunté à leur apparence — ni contrôles, ni couleurs,
ni icônes. L'identité reste Pose Parquet.

### Un seul état pour toute la scène

```
viewport = { z, x, y }

  z       facteur de zoom, 1 = ajusté à l'écran
  x, y    translation en pixels écran du coin haut-gauche de la scène
```

Et une seule fonction écrit la **même** transformation dans chaque groupe :

```
#stage                                   le cadre, overflow caché
  [data-vp] #vpPhoto  → la photo d'origine
  [data-vp] #vpB      → le rendu de la version B
  #clipA              → découpage du séparateur, en espace ÉCRAN
    [data-vp] #vpA    → le rendu de la version A
```

C'est la règle qui compte : **jamais de transformation séparée** pour la photo,
le rendu A et le rendu B. Sinon la comparaison mentirait — deux sols décalés
d'un pixel, et on compare deux cadrages au lieu de deux parquets. Un test
vérifie que les trois groupes portent une chaîne de transformation identique.

Le découpage du séparateur vit **au-dessus** de la transformation, sur
`#clipA`. Une ligne posée sur la vitre : elle reste là où l'utilisateur l'a
laissée, quel que soit le zoom.

### 100 % veut dire « ajusté à l'écran »

Pas « taille native des pixels », qui ne veut rien dire pour l'utilisateur.
`fitToView()` fait tenir la scène entière dans le cadre, la centre, garde le
ratio — l'équivalent d'un `object-fit: contain` — et c'est ce cadrage qui vaut
**100 %**. Donc 150 % signifie « une fois et demie le cadrage de départ ».

Bornes : de 100 % (l'ajustement ; en dessous on ne verrait que du vide) à
500 %. Assez pour inspecter un joint, un chanfrein, un pied de meuble ou la
ligne mur/sol ; pas assez pour se perdre à 5 000 %.

### Ce qui conserve le cadrage, et ce qui le remet à zéro

| geste | viewport |
| --- | --- |
| changer de parquet dans la même pièce | **conservé** |
| avant / après | **conservé** |
| ouvrir ou déplacer une comparaison | **conservé**, et les deux côtés bougent ensemble |
| changer de pièce | `fitToView()` |
| importer une photo | `fitToView()` |
| entrer ou sortir du plein écran | **conservé**, position rebornée au nouveau cadre |

La ligne la plus importante est la première. L'utilisateur zoome sur une
plinthe, essaie quatre références : il reste sur sa plinthe. Un recentrage
automatique à chaque changement de produit rendrait la comparaison
impossible.

### Bornes de déplacement

L'image couvre toujours le cadre : on ne peut pas la faire sortir ni voir du
vide autour. Quand elle est plus petite que le cadre sur un axe, elle se
recentre d'elle-même sur cet axe. Le déplacement reste large — à 300 %, il
reste plus de la moitié de la largeur à explorer — mais on ne perd jamais la
pièce.

### Gestes

Une seule implémentation, en Pointer Events, sert la souris, le trackpad et le
tactile :

| geste | effet |
| --- | --- |
| molette | zoom sous le curseur |
| molette + `ctrl` (pincement trackpad) | zoom sous le curseur, plus vif |
| glisser (souris, un doigt) | déplacement |
| deux doigts | pincement, zoom autour du milieu des doigts |
| double-clic | zoom avant doux autour du point cliqué |
| `Maj` + double-clic | zoom arrière |

Le curseur passe de `grab` à `grabbing`. Les images du viewport ne sont pas
glissables : sans cela le navigateur démarre son propre glisser-déposer
d'image, et la page croit à un import — c'est arrivé, et c'est corrigé.

Clavier, parce que la gestuelle ne doit jamais être le seul chemin :
`+` / `-` zooment, `0` recentre, `F` bascule le plein écran, `Échap` en sort
ou ferme une modale. Aucun de ces raccourcis ne se déclenche dans un champ de
saisie.

### Contrôles

Une barre minuscule, en bas à droite, sur la photo :

```
[ − ]  [ 100 % ]  [ + ]  [ ⌖ ]  [ ⛶ ]
```

Blanc translucide, flou léger, ombre à peine visible. Le niveau affiché est
aussi un bouton : le toucher recentre. Chaque commande porte son `aria-label`,
et le cadre lui-même annonce « Vue de la pièce. Molette pour zoomer, glisser
pour déplacer. » Tout ce qui se fait au geste se fait aussi au bouton.

### Plein écran

Le mode immersif enlève ce qui n'aide pas à regarder : l'en-tête disparaît, la
navigation flottante disparaît, la capsule d'état disparaît. Il reste les
trois outils du haut (avant/après, comparer, sortir), une carte produit
réduite à sa vignette et son nom, et la barre de zoom.

Au bout de trois secondes sans mouvement, ce qui reste s'atténue à 32 % — et
revient au premier mouvement. Atténué, jamais supprimé : un contrôle qui
disparaît pour de bon est une frustration, pas une épure.

Le plein écran natif est demandé au navigateur ; s'il le refuse (dans un
cadre embarqué, par exemple), le mode immersif fonctionne quand même. C'est
une dégradation, pas une panne.

### Fluidité

Une seule transformation GPU (`translate3d` + `scale`), écrite sur trois
éléments, sans recalcul de mise en page. Pendant un glisser : **aucune
animation**, le déplacement suit le pointeur. Les gestes discrets — boutons,
double-clic, recentrage — sont interpolés sur 200 ms, et pas du tout si
`prefers-reduced-motion` est demandé.

Au changement de parquet, un fondu de 160 ms entre l'ancien et le nouveau
rendu : le sol change sous les yeux, sans flash blanc, et sans que le cadrage
bouge d'un pixel.

### Sur mobile

Le moteur n'est pas souris-seule et le pincement est prévu, mais ce lot ne
développe pas l'UX mobile : la disposition du §14 reste à faire.

---

## 16. Ce que ce document ne fait pas

- il ne choisit **aucun modèle d'IA** et n'en installe aucun ;
- il ne recrée **aucun moteur de rendu** — celui du front existe et fonctionne ;
- il n'invente **aucune capacité** du moteur : chaque réglage cité est classé
  dans `docs/product-ai-contract.md` §5 ;
- il ne touche **pas** au catalogue Premibel : les essences et teintes citées
  sont des exemples d'UX, et le prototype le dit ;
- il ne modifie **ni le front, ni WordPress, ni `SceneData`**.

`tools/product-concept.html` **est** le visualiseur décrit ici. Il ne dessine
pas le parquet lui-même : il pilote un moteur de rendu et recopie son résultat,
avec des captures préfabriquées en repli. Cette page n'a jamais contenu son
propre moteur, et ne doit pas en contenir — la garde de
`tools/product-concept.check.js` existe pour cela.
