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
import {
  createMaterial, enCache, warmMaterial, quandCartesPretes, materialMapsAsync,
} from '../scene/material.js';
import { chrono, releve } from '../utils/perf.js';

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
async function loadMaterials(base) {
  const reponse = await fetch(`${base}data/parquets.json`, { cache: 'no-cache' });
  if (!reponse.ok) throw new Error('Catalogue de matières indisponible');
  const brut = await reponse.json();
  const liste = (brut.parquets || []).map(createMaterial);
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
  const [materials, index] = await Promise.all([
    loadMaterials(base),
    loadSceneIndex(base).catch(() => ({ scenes: [] })),
  ]);

  /** Le seul état de configuration. Pas d'état d'iframe, pas d'état de Studio. */
  let config = { material: null, pattern: 'lames', width: null, angle: 0, scale: 1 };
  let sceneId = null;
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
  function demandeRendu() {
    if (demande) return;
    demande = true;
    Promise.resolve().then(() => {
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
           `false` sur une texture froide, et l'appelant croirait à un échec. */
        await renderer.preparer(config);
        const fait = peindre(1);
        if (!fait) prevenir(0);
        return fait;
      });
    });
  }

  return {
    apiVersion: API_VERSION,
    get canvas() { return canvas; },
    get scene() { return sceneId; },
    get backend() { return renderer.backend; },
    get ready() { return renderer.ready; },
    /** Les pièces calibrées disponibles localement. */
    get scenes() { return (index.scenes || []).map((s) => s.id); },
    /** Diagnostic seulement, hors contrat. */
    get config() { return { ...config, material: config.material ? config.material.id : null }; },

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
        const prete = await loadImage(`${base}assets/images/${fichier}`);
        marquer('B.photo', tPhoto);
        chrono('D.setScene', () => renderer.setScene(scene, prete));
        sceneId = id;
        return true;
      });
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
    prechauffer(materialId, pattern, width, { urgent = false } = {}) {
      const material = materialId ? materials.get(materialId) : config.material;
      if (!material) return false;
      const conf = {
        pattern: pattern || config.pattern,
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
