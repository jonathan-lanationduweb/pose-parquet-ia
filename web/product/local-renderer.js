/**
 * Moteur de rendu LOCAL du visualiseur.
 *
 * Ce module remplace le pont vers `pose-parquet.com` : plus d'iframe, plus de
 * `window.__studio`, plus de second serveur. L'interface parle au moteur dans
 * la même application, avec un seul état.
 *
 * ## Ce qu'il est, et ce qu'il n'est pas
 *
 * Ce n'est **pas** un nouveau moteur. Le moteur est celui de `web/scene/`,
 * copié tel quel depuis le dépôt du front — provenance exacte dans
 * `docs/RENDERER-AUTONOMY-PLAN.md`. Ce fichier est ce qui manquait autour :
 * ouvrir une pièce, tenir une configuration, demander un rendu, prévenir
 * quand il est fini. `js/studio/app.js` faisait cela en 1 485 lignes, dont
 * une quarantaine servaient au rendu ; le reste était l'interface de
 * calibration, et elle n'entre pas ici.
 *
 * ## La forme du contrat est celle du pont, exprès
 *
 * `openRoom`, `selectMaterial`, `setPattern`, `setWidth`, `setAngle`,
 * `getCapabilities`, `onRendered`, `canvas` : les mêmes sept commandes, aux
 * mêmes signatures. Ce n'est pas une nostalgie du pont — c'est ce qui permet
 * de comparer les deux moteurs sur le même appelant, donc de prouver la
 * parité avant de basculer. Une API réinventée aurait rendu la comparaison
 * impossible à faire honnêtement.
 *
 * Ce n'est pas `window.__studio` pour autant : rien n'est posé sur `window`
 * par ce module, et l'appelant reçoit l'objet en retour de fonction.
 *
 * ## Deux caches, et pourquoi la rotation en profite
 *
 * Le moteur a son cache de **matériaux** : douze entrées, clef
 * `matière|motif|largeur`. Un angle n'entre dans aucune de ces composantes —
 * la tuile de bois est la même, c'est sa projection qui tourne. Tourner ne
 * refabrique donc jamais une texture, et c'est mesurable.
 *
 * ## Deux qualités de rendu
 *
 * `paint()` accepte un pas d'échantillonnage : `step = 2` peint un pixel sur
 * deux. Le pont ne l'exposait pas ; ici il est disponible, et c'est le seul
 * gain de capacité de l'extraction. Réserve honnête : ce pas ne change rien
 * en WebGL, où le rendu passe par le nuanceur. L'aperçu tire donc son gain
 * d'ailleurs — il ne fabrique aucune texture et ne fait pas la queue.
 */

import { analyzeScene, loadSceneIndex } from '../scene/analyzer.js';
import { loadImage } from '../scene/image-loader.js';
import { createSceneRenderer } from '../scene/renderer.js';
import { reviewGeometry } from '../scene/geometry-review.js';
import { normalizeScene, validerScene, createBlankScene } from '../scene/schema.js';
import {
  createMaterial, enCache, warmMaterial, quandCartesPretes, materialMapsAsync, fabricationAsynchrone,
} from '../scene/material.js';
import { releve } from '../utils/perf.js';

/** Version du contrat local. */
export const API_VERSION = 1;

/**
 * Charge les matières depuis `data/parquets.json`, **sans la couche produit**.
 *
 * `js/studio/catalog.js` et `js/scene/product.js` fabriquent les mêmes objets
 * en traversant les fiches commerciales : c'est le bon chemin pour le site du
 * front, et le mauvais ici — le moteur n'a pas à connaître une marque. Les
 * entrées de `parquets.json` ont déjà la forme qu'attend `createMaterial`.
 *
 * Correction d'audit : le plan d'extraction classait `product.js` et
 * `catalog.js` « inutiles au produit » sans dire d'où venaient les objets
 * matériau. Le classement était juste, l'explication incomplète.
 */
/**
 * Matières EXACTES des produits Premibel (`data/materials/premibel/`).
 *
 * Une matière exacte n'est retenue que si son atlas — dérivé de la photo du
 * produit, non versionné — est réellement servi, et si un worker peut la
 * fabriquer (le chemin synchrone ne sait pas lire un atlas). Sinon elle est
 * ignorée, et le produit reste en matière représentative : on ne déclare
 * jamais « exact » un rendu qui ne l'est pas.
 *
 * @returns {Promise<{ materials: object[], produits: object[] }>}
 */
async function loadExactMaterials(base) {
  if (!fabricationAsynchrone()) return { materials: [], produits: [] };
  try {
    const r = await fetch(`${base}data/materials/premibel/index.json`, { cache: 'no-cache' });
    if (!r.ok) return { materials: [], produits: [] };
    const index = await r.json();
    const entrees = Object.entries(index.materials || {}).filter(([, e]) => e.materialFidelity === 'exact' && e.definition);
    const resultats = await Promise.all(entrees.map(async ([produit, e]) => {
      try {
        const def = await (await fetch(`${base}${e.definition}`, { cache: 'no-cache' })).json();
        const atlasUrl = new URL(`${base}${def.atlas.url}`, globalThis.location ? globalThis.location.href : undefined);
        if (def.atlas.version) atlasUrl.searchParams.set("v", def.atlas.version);
        const url = atlasUrl.href;
        const tete = await fetch(url, { method: 'HEAD', cache: 'no-cache' });
        if (!tete.ok) return null;
        return { produit, entree: e, material: createMaterial({ ...def, atlas: { ...def.atlas, url } }) };
      } catch {
        return null;
      }
    }));
    const ok = resultats.filter(Boolean);
    return {
      materials: ok.map((x) => x.material),
      produits: ok.map((x) => ({ product: x.produit, material: x.material.id, pattern: x.entree.pattern,
        widthMm: x.entree.widthMm, lengthMm: x.entree.lengthMm })),
    };
  } catch {
    return { materials: [], produits: [] };
  }
}

async function loadMaterials(base) {
  const reponse = await fetch(`${base}data/parquets.json`, { cache: 'no-cache' });
  if (!reponse.ok) throw new Error('Catalogue de matières indisponible');
  const brut = await reponse.json();
  const liste = (brut.parquets || []).map(entry => createMaterial(entry.atlas ? { ...entry, atlas: { ...entry.atlas, url: new URL(`${base}${entry.atlas.url}`, location.href).href } } : entry));
  if (!liste.length) throw new Error('Aucune matière dans le catalogue');
  return new Map(liste.map((m) => [m.id, m]));
}

/**
 * @param {object} options
 * @param {string} options.base   préfixe des données locales, ex. `../web/`
 * @param {'auto'|'canvas'} [options.prefer]
 */
export async function createLocalRenderer({ base = '', prefer = 'auto' } = {}) {
  const renderer = createSceneRenderer({ prefer });
  /* Deux requêtes indépendantes : le catalogue de matières ne dit rien des
     scènes, et l'index des scènes ne dit rien des matières. Elles étaient
     enchaînées par deux `await` successifs — un aller-retour réseau de plus,
     payé à chaque démarrage pour rien. */
  const [materials, exactes, index] = await Promise.all([
    loadMaterials(base),
    loadExactMaterials(base),
    loadSceneIndex(base).catch(() => ({ scenes: [] })),
  ]);
  exactes.materials.forEach((m) => materials.set(m.id, m));

  /** Le seul état de configuration. Pas d'état d'iframe, pas d'état de Studio. */
  let config = { material: null, pattern: 'lames', width: null, plankLength: null, angle: 0, scale: 1 };
  let sceneId = null;
  let coveragePreview = null;
  /** Photos décodées des pièces de démonstration, par fichier. */
  const photosPieces = new Map();
  const abonnes = new Set();
  const canvas = document.createElement('canvas');

  /* Une opération lourde à la fois. Deux `openRoom` concurrents
     installeraient deux scènes dans le même moteur, et la seconde gagnerait
     au hasard. Même raison que la file de l'adaptateur qui précédait. */
  let file = Promise.resolve();
  const enFile = (travail) => {
    const tour = file.then(travail, travail);
    file = tour.catch(() => {});
    return tour;
  };

  /** Releve une duree deja ecoulee, sans envelopper l'appel. */
  function marquer(nom, depuis) {
    releve(nom, performance.now() - depuis);
  }

  function prevenir(quality) {
    [...abonnes].forEach((cb) => {
      try { cb(quality); } catch { /* un abonné qui jette n'arrête pas les autres */ }
    });
  }

  function peindre(step) {
    if (!renderer.ready || !config.material) return false;
    const fait = renderer.paint(canvas, config, undefined, step);
    if (fait) prevenir(step === 1 ? 1 : 0.5);
    return fait;
  }

  /* ---------------- Demande de rendu ----------------

     Les setters ne peignent pas : ils écrivent l'état et **demandent** un
     rendu. Plusieurs écritures d'affilée — le motif ET la largeur ET l'angle,
     ce que fait l'adaptateur pour chaque produit — ne doivent produire qu'un
     rendu, celui de l'état final. La demande est donc coalescée sur une
     microtâche, et la file garantit qu'un rendu en cours n'est pas doublé. */
  let demande = false;
  /* ---------------- Préchargement des matières ----------------

     Les matières des cartes VISIBLES du catalogue se préparent pendant les
     temps morts, une à la fois. Deux règles :
       * le produit demandé passe toujours devant : tant qu'un rendu attend
         sa matière (`renduEnAttente`), le préchargement se suspend ;
       * on ne prépare que ce qu'on montre — une liste courte, remplacée à
         chaque défilement, jamais les 394 références. */
  let fileMatieres = [];
  let pompeMatieres = false;
  let renduEnAttente = 0;
  /* Ouvertures de pièce en cours : leur éclairement passe avant. */
  let ouvertures = 0;
  const auRepos = (f) => (typeof requestIdleCallback === 'function' ? requestIdleCallback(f, { timeout: 1000 }) : setTimeout(f, 150));
  function pomperMatieres() {
    const prochain = fileMatieres.shift();
    if (!prochain) { pompeMatieres = false; return; }
    pompeMatieres = true;
    auRepos(() => {
      if (renduEnAttente > 0 || ouvertures > 0) {
        fileMatieres.unshift(prochain);
        setTimeout(pomperMatieres, 250);
        return;
      }
      const m = materials.get(prochain.materialFamily);
      const conf = { pattern: prochain.pattern, width: prochain.widthM || null, plankLength: prochain.lengthM || null };
      if (!m || enCache(m, conf)) { pomperMatieres(); return; }
      materialMapsAsync(m, conf, {priority:'background'}).catch(() => {}).finally(pomperMatieres);
    });
  }

  function demandeRendu() {
    if (demande) return;
    demande = true;
    Promise.resolve().then(() => {
      if (!demande) return;
      demande = false;
      enFile(async () => {
        if (!renderer.ready || !config.material) {
          /* On prévient MÊME quand on ne peint pas.
             Un abonné qui attend un rendu doit apprendre qu'il n'y en aura
             pas ; sans cela il attend son délai de garde entier. Mesuré :
             `applyProfile` appelé avant toute ouverture de pièce rendait la
             main au bout de 20 006 ms. Le zéro dit « rien n'a été peint »,
             et se distingue de 1 (rendu complet) et 0,5 (brouillon). */
          prevenir(0);
          return false;
        }
        /* `preparer` attend les cartes du worker : sans cela `paint` rend
           `false` sur une texture froide, et l'appelant croirait à un échec.
           Pendant cette attente, le préchargement du catalogue se tait. */
        /* Une fabrication de tuile qui échoue (worker hors d'usage, délai
           dépassé) doit aussi prévenir : sinon l'abonné attend son délai de
           garde entier pour apprendre qu'il n'y aura rien. */
        renduEnAttente += 1;
        try {
          await renderer.preparer(config);
        } catch {
          prevenir(0);
          return false;
        } finally {
          renduEnAttente -= 1;
        }
        const fait = peindre(1);
        if (!fait) prevenir(0);
        return fait;
      });
    });
  }

  function floorViewportFocus() {
    const m = renderer.masks;
    if (!m) return null;
    const coverage = m.coverage, occlusion = m.occlusion;
    let best = null;
    for (const fy of [.72, .82, .92]) {
      const y = Math.min(m.height - 1, Math.round(m.height * fy));
      let start = -1;
      for (let x = 0; x <= m.width; x++) {
        const i = y * m.width + x;
        const visible = x < m.width && coverage[i] > 127 && (!occlusion || occlusion[i] < 127);
        if (visible && start < 0) start = x;
        if (!visible && start >= 0) {
          if (!best || x - start > best.length) best = { x: (start + x) / (2 * m.width), y: fy, length: x - start };
          start = -1;
        }
      }
    }
    return best;
  }

  return {
    apiVersion: API_VERSION,
    get geometryKey() { const s=renderer.scene; return s ? `${s.id}|${s.geometryVersion || 'legacy'}|${s.image.width}x${s.image.height}` : 'none'; },
    get canvas() { return canvas; },
    get scene() { return sceneId; },
    get backend() { return renderer.backend; },
    get ready() { return renderer.ready; },
    visitSnapshot() { return renderer.ready ? { scene: structuredClone(renderer.scene), floorFocus: floorViewportFocus(), masks: renderer.masks, size: renderer.size, canvas } : null; },
    geometryDiagnostics(profile = null, angle = null) {
      const current = profile ? { ...config, material: materials.get(profile.materialFamily) || config.material,
        pattern: profile.pattern, width: profile.widthM, plankLength: profile.lengthM,
        scale: profile.scale || 1, angle: angle || 0 } : config;
      return reviewGeometry(renderer.scene, renderer.masks, renderer.size, current);
    },
    /** Les pièces calibrées disponibles localement. */
    get scenes() { return (index.scenes || []).map((s) => s.id); },
    /** Produits Premibel dont la matière EXACTE est réellement disponible. */
    get matieresExactes() { return exactes.produits.map((p) => ({ ...p })); },
    /** Diagnostic seulement, hors contrat. */
    get config() { return { ...config, material: config.material ? config.material.id : null }; },

    /**
     * Prépare une pièce sans l'ouvrir : SceneData, photo décodée, masques et
     * éclairement (dans le worker). Hors de la file : un préchargement ne
     * retarde jamais une ouverture demandée. Rend `true` si la pièce est
     * prête pour une ouverture rapide.
     */
    async prechargerPiece(id) {
      const entree = (index.scenes || []).find((s) => s.id === id);
      if (!entree || sceneId === id) return false;
      try {
        const scene = await analyzeScene({ sceneId: id, base }, 'precalibrated');
        const fichier = entree.file || (scene.image && scene.image.file);
        if (!fichier) return false;
        let prete = photosPieces.get(fichier);
        if (!prete) {
          prete = await loadImage(`${base}assets/images/${fichier}`);
          if (photosPieces.size >= 6) photosPieces.delete(photosPieces.keys().next().value);
          photosPieces.set(fichier, prete);
        }
        return await renderer.precharger(scene, prete, `piece:${id}:${JSON.stringify(scene)}`);
      } catch {
        return false;
      }
    },

    /** Ouvre une pièce : scène calibrée, photo, masques, cartes de lumière. */
    openRoom(id) {
      return enFile(async () => {
        if (sceneId === id && renderer.ready) return true;
        const entree = (index.scenes || []).find((s) => s.id === id);
        const tScene = performance.now();
        const scene = await analyzeScene({ sceneId: id, base }, 'precalibrated');
        marquer('C.sceneData', tScene);
        const fichier = (entree && entree.file) || (scene.image && scene.image.file);
        if (!fichier) throw new Error(`Scène « ${id} » sans photo déclarée`);
        /* `loadImage` prend une URL et rend { canvas, width, height }, déjà
           redimensionné pour l'écran s'il le faut : exactement ce qu'attend
           `setScene`, et le même chemin que le front. */
        const tPhoto = performance.now();
        /* La photo décodée est gardée : c'est elle qui identifie la
           préparation mise en cache par le moteur (masques, lumière). */
        let prete = photosPieces.get(fichier);
        if (!prete) {
          prete = await loadImage(`${base}assets/images/${fichier}`);
          if (photosPieces.size >= 6) photosPieces.delete(photosPieces.keys().next().value);
          photosPieces.set(fichier, prete);
        }
        marquer('B.photo', tPhoto);
        { const tS = performance.now(); ouvertures += 1; try { await renderer.setScene(scene, prete, { cleCache: `piece:${id}:${JSON.stringify(scene)}` }); } finally { ouvertures -= 1; } marquer('D.setScene', tS); }
        sceneId = id;
        return true;
      });
    },

    /**
     * Ouvre une scène fournie telle quelle — la photo de l'utilisateur et la
     * scène EXPÉRIMENTALE que Python en a tirée.
     *
     * Même chemin que `openRoom` à une différence près : la scène ne vient
     * pas de `data/scenes/`, elle arrive déjà construite, et la photo est une
     * URL d'objet locale — jamais envoyée, jamais écrite. `normalizeScene`
     * lève si la scène est inutilisable : mieux vaut un message qu'un
     * parquet posé sur une géométrie fausse.
     *
     * @param {object} raw     SceneData brute (`pose-parquet/scene@1`)
     * @param {string} imageUrl URL de la photo (object URL)
     * @param {string} [id]    identifiant d'état, `photo` par défaut
     */
    openScene(raw, imageUrl, id = 'photo') {
      return enFile(async () => {
        /* Une scène invalide ne touche pas le moteur : la scène précédente
           reste en place, et l'appelant reçoit une erreur qui la nomme. */
        const problemes = validerScene(raw);
        if (problemes.length) {
          const e = new Error(`Scène refusée : ${problemes.join(', ')}`);
          e.problemes = problemes;
          throw e;
        }
        const scene = normalizeScene(raw);
        const tPhoto = performance.now();
        const prete = await loadImage(imageUrl);
        marquer('B.photo', tPhoto);
        { const tS = performance.now(); ouvertures += 1; try { await renderer.setScene(scene, prete); } finally { ouvertures -= 1; } marquer('D.setScene', tS); }
        sceneId = id;
        return true;
      });
    },

    /**
     * Scène MANUELLE : la photo, un plan de sol par défaut, une zone à tracer
     * au pinceau. Le filet de sécurité quand l'analyse n'a rien proposé —
     * aucun sol trouvé, scène refusée, service muet. La perspective par
     * défaut est une hypothèse, et le parquet posé dessus le dira.
     */
    openManualScene(imageUrl, width, height, id = 'photo') {
      return enFile(async () => {
        const scene = createBlankScene({ width, height, label: 'Ma pièce (sol tracé à la main)' });
        const prete = await loadImage(imageUrl);
        { const tS = performance.now(); ouvertures += 1; try { await renderer.setScene(scene, prete); } finally { ouvertures -= 1; } marquer('D.setScene', tS); }
        sceneId = id;
        return true;
      });
    },

    /* ---------------- Correction du sol au pinceau ----------------

       Les masques du moteur savent déjà recevoir des coups de pinceau
       (`beginStroke` / `extendStroke` / `undo`) : c'est l'outil de la
       sélection manuelle du front, jamais branché ici. On l'expose pour le
       Mode Photo — ajouter au sol, retirer du sol — sans rien inventer.

       Un trait se peint dans la première zone : les zones d'une scène IA
       partagent toutes le même plan, donc un pixel ajouté y reçoit la même
       perspective que ses voisins. */
    beginStroke(mode, radius, point) {
      if (typeof renderer.oublierPreparation === 'function') renderer.oublierPreparation();
      const masks = renderer.masks;
      const zone = renderer.scene && renderer.scene.floorZones[0];
      if (!masks || !zone) return false;
      masks.beginStroke(zone.id, mode === 'remove' ? 'remove' : 'add', radius, point);
      return true;
    },
    extendStroke(point) {
      if (!renderer.masks) return false;
      renderer.masks.extendStroke(point);
      return true;
    },
    /** Fin de geste : masques refaits au prochain rendu, lumière recalculée. */
    endStroke({ deferRender = false } = {}) {
      if (!renderer.ready) return false;
      renderer.invalidateMasks();
      if (!deferRender) { renderer.refreshLighting(); demandeRendu(); }
      return true;
    },
    /** Photo brush: keep the mask overlay responsive, rebuild lighting once on Done. */
    commitStrokeEdits() {
      return enFile(async () => {
        if (!renderer.ready) return false;
        return renderer.refreshLightingAsync();
      });
    },
    undoStroke({ deferRender = false } = {}) {
      if (!renderer.masks) return false;
      const fait = renderer.masks.undo();
      if (fait) { renderer.invalidateMasks(); if (!deferRender) { renderer.refreshLighting(); demandeRendu(); } }
      return fait;
    },
    /**
     * La zone de sol courante, dessinée en teinte translucide, pour la montrer
     * pendant la correction.
     *
     * C'est le MOTEUR qui écrit ces pixels, pas la page : la page ne compose
     * rien, elle copie un canevas — c'est la règle qui interdit qu'un
     * troisième moteur de rendu renaisse dans le HTML, et sa batterie de
     * contrôle la vérifie à la lettre (`putImageData` y est banni).
     *
     * @returns {{canvas:HTMLCanvasElement|OffscreenCanvas,width:number,height:number}|null}
     */
    coverageOverlay() {
      const masks = renderer.masks;
      if (!masks) return null;
      const { width, height } = masks;
      const coverage = masks.effectiveCoverage;
      if (!coveragePreview || coveragePreview.width !== width || coveragePreview.height !== height) {
        const canvas = document.createElement('canvas'); canvas.width = width; canvas.height = height;
        coveragePreview = { canvas, image: new ImageData(width, height), width, height };
      }
      const image = coveragePreview.image;
      const d = image.data;
      d.fill(0);
      for (let i = 0, p = 0; i < coverage.length; i += 1, p += 4) {
        const a = coverage[i];
        if (!a) continue;
        d[p] = 60; d[p + 1] = 130; d[p + 2] = 255; d[p + 3] = Math.round(a * 0.42);
      }
      const teinte = coveragePreview.canvas;
      teinte.getContext('2d').putImageData(image, 0, 0);
      return { canvas: teinte, width, height };
    },

    /** La matière, par son identifiant de matière — jamais par une référence produit. */
    selectMaterial(id) {
      const material = materials.get(id);
      if (!material) return false;
      config = { ...config, material };
      demandeRendu();
      return true;
    },

    setPattern(pattern) {
      config = { ...config, pattern };
      demandeRendu();
      return true;
    },

    setAngle(deg) {
      config = { ...config, angle: Number(deg) || 0 };
      demandeRendu();
      return true;
    },

    /**
     * Largeur de lame en mètres, `null` pour laisser le motif décider.
     * Bornes identiques à celles du pont : on ne change pas le comportement
     * en même temps que le moteur.
     */
    setWidth(metres) {
      if (metres !== null && !(Number.isFinite(metres) && metres >= 0.02 && metres <= 0.5)) return false;
      config = { ...config, width: metres };
      demandeRendu();
      return true;
    },

    setScale(value) {
      if (!(Number.isFinite(value) && value >= 0.5 && value <= 2)) return false;
      config = { ...config, scale: value };
      demandeRendu();
      return true;
    },

    /** Longueur commerciale, indépendante de la largeur et du matériau. */
    setPlankLength(metres) {
      if (metres !== null && !(Number.isFinite(metres) && metres >= 0.1 && metres <= 4)) return false;
      config = { ...config, plankLength: metres };
      demandeRendu();
      return true;
    },

    /**
     * Ce qui est réellement pilotable. `finish`, `grain` et `joints` restent
     * faux : ils sont cuits dans la famille de texture, aucun réglage ne les
     * change — mentir ici donnerait des curseurs sans effet.
     */
    getCapabilities() {
      return {
        pattern: true, width: true, orientation: true,
        finish: false, grain: false, joints: false,
      };
    },

    onRendered(cb) {
      if (typeof cb !== 'function') return () => {};
      abonnes.add(cb);
      return () => abonnes.delete(cb);
    },

    /* ---------------- Ce que le pont ne pouvait pas offrir ---------------- */

    /** Vrai si la tuile de l'état courant est déjà fabriquée. */
    tuilePrete() {
      return Boolean(config.material) && enCache(config.material, config);
    },

    /**
     * Prépare une tuile d'avance.
     *
     * Deux régimes, et la différence compte :
     *
     *   opportuniste (défaut)  `requestIdleCallback` sans délai de garde. Si
     *                          le navigateur ne trouve jamais de répit, la
     *                          tuile ne se fabrique pas — c'est le
     *                          comportement voulu pour des références
     *                          voisines, dont personne n'attend rien.
     *
     *   `urgent: true`         la demande part tout de suite au worker. À
     *                          réserver à la tuile que l'on SAIT être sur le
     *                          chemin critique : celle du produit
     *                          sélectionné, qu'il faudra de toute façon
     *                          fabriquer dès que l'utilisateur ouvrira une
     *                          pièce. La fabriquer pendant que la photo se
     *                          décode ne coûte rien au fil principal — le
     *                          travail est dans le worker — et retire une à
     *                          trois secondes de l'attente visible.
     *
     * Mesuré : sans cela, ouvrir une pièce coûtait 355 ms de scène PUIS
     * 1 534 à 3 357 ms de tuile, en série. Les deux ne dépendent pas l'un de
     * l'autre : une tuile de bois ne sait rien de la pièce où elle sera posée.
     */
    /**
     * Prépare en tâche de fond les matières d'une liste de profils (les cartes
     * visibles du catalogue). Remplace la liste précédente. Rend le nombre de
     * profils retenus.
     */
    prechargerMatieres(profils) {
      fileMatieres = (profils || []).filter((p) => p && materials.has(p.materialFamily)).slice(0, 8);
      if (!pompeMatieres) pomperMatieres();
      return fileMatieres.length;
    },

    /** La matière de ce profil est-elle déjà prête ? */
    matierePrete(profil) {
      const m = profil && materials.get(profil.materialFamily);
      return Boolean(m && enCache(m, { pattern: profil.pattern, width: profil.widthM || null, plankLength: profil.lengthM || null }));
    },

    prechauffer(materialId, pattern, width, { urgent = false, plankLength = null } = {}) {
      const material = materialId ? materials.get(materialId) : config.material;
      if (!material) return false;
      const conf = {
        pattern: pattern || config.pattern,
        plankLength,
        width: width === undefined ? config.width : width,
      };
      if (enCache(material, conf)) return true;
      if (urgent) {
        materialMapsAsync(material, conf).catch(() => { /* la demande normale refera */ });
        return true;
      }
      warmMaterial(material, conf);
      return true;
    },

    /** Prévient quand une tuile fabriquée en tâche de fond arrive. */
    surCartesPretes(cb) { return quandCartesPretes(cb); },

    /**
     * Aperçu pendant un geste : un angle, tout de suite, ou rien.
     *
     * Trois refus délibérés — ce sont eux qui rendent l'aperçu sûr :
     * il ne passe **pas** par la file, il ne fabrique **aucune** texture, et
     * il abandonne si la tuile n'est pas déjà prête. Un aperçu qui
     * attendrait une texture ne serait plus un aperçu, et un aperçu qui
     * ferait la queue arriverait après le rendu final.
     *
     * @returns {boolean} vrai si quelque chose a été peint
     */
    apercuAngle(deg) {
      if (!renderer.ready || !config.material) return false;
      config = { ...config, angle: Number(deg) || 0 };
      if (!enCache(config.material, config)) return false;
      return peindre(2);
    },

    /** Rendu final, pleine qualité, texture fabriquée si nécessaire. */
    rendre() {
      // Le rendu explicite remplace la demande coalescée des setters.
      demande = false;
      return enFile(async () => {
        if (!renderer.ready || !config.material) return false;
        await renderer.preparer(config);
        return peindre(1);
      });
    },

    /** L'état courant, pour une clef de cache ou un diagnostic. */
    etat() {
      return {
        scene: sceneId,
        material: config.material ? config.material.id : null,
        pattern: config.pattern,
        width: config.width,
        angle: config.angle,
      };
    },
  };
}
