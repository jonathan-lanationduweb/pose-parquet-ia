/**
 * Rendu d'une scène — API unique, deux moteurs derrière.
 *
 *   SCÈNE + MATÉRIAUX  →  createSceneRenderer()  →  canevas peint
 *
 * L'appelant ne choisit pas le moteur et n'a pas à savoir lequel tourne :
 * WebGL 2 quand il est disponible, Canvas 2D sinon. Les deux consomment les
 * mêmes données et sont censés rendre la même image ; c'est ce qui permet de
 * garder le second comme référence.
 *
 * Tout ce qui ne dépend que de la photo — masques, éclairement, reflets — est
 * calculé une fois par scène. Changer de parquet ne recalcule que le parquet.
 * C'est aussi ce qui rend la comparaison honnête : les trois variantes
 * partagent, par construction, la même géométrie, les mêmes masques, le même
 * éclairement et la même caméra. Seul le matériau change.
 */
import { createSceneMasks } from './mask.js';
import { mark, mesure, chrono, releve } from '../utils/perf.js';
import { buildShadingMap, buildResidualMaps, habillerShading, habillerResidus } from './shading.js';
import { lightDirection } from './geometry.js';
import { materialMaps, materialMapsAsync, warmMaterial } from './material.js';
import { createCanvasRenderer } from './renderer-canvas.js';
import { createGlRenderer, glAvailable } from './renderer-gl.js';

/* ------------------------------------------------------------------ */
/* Éclairement hors du fil principal                                    */
/* ------------------------------------------------------------------ */

let workerLumiere = null;
let lumiereIndisponible = false;
let compteurLumiere = 0;
const attentesLumiere = new Map();

function obtenirWorkerLumiere() {
  if (workerLumiere || lumiereIndisponible) return workerLumiere;
  if (typeof Worker !== 'function' || typeof window === 'undefined') { lumiereIndisponible = true; return null; }
  try {
    workerLumiere = new Worker(new URL('./lighting-worker.js', import.meta.url), { type: 'module' });
  } catch {
    lumiereIndisponible = true;
    return null;
  }
  workerLumiere.onmessage = (event) => {
    const { id, shading, residual, erreur } = event.data || {};
    const a = attentesLumiere.get(id);
    if (!a) return;
    attentesLumiere.delete(id);
    if (erreur) a.reject(new Error(erreur));
    else a.resolve({ shading: habillerShading(shading), residual: habillerResidus(residual) });
  };
  workerLumiere.onerror = () => {
    attentesLumiere.forEach((a) => a.reject(new Error('worker d’éclairement indisponible')));
    attentesLumiere.clear();
    workerLumiere.terminate();
    workerLumiere = null;
    lumiereIndisponible = true;
  };
  return workerLumiere;
}

/** Calcule l'éclairement d'une photo dans le worker. `null` sans worker. */
function lumiereAsync(source, coverage, light) {
  const w = obtenirWorkerLumiere();
  if (!w) return null;
  const id = (compteurLumiere += 1);
  return new Promise((resolve, reject) => {
    attentesLumiere.set(id, { resolve, reject });
    /* Des copies : la page garde ses pixels et son masque. */
    w.postMessage({
      id,
      source: { width: source.width, height: source.height, data: new Uint8ClampedArray(source.data) },
      coverage: new Uint8Array(coverage),
      light: light ? JSON.parse(JSON.stringify(light)) : light,
    });
  });
}

export function createSceneRenderer({ prefer = 'auto' } = {}) {
  const gl = prefer === 'canvas' || !glAvailable() ? null : createGlRenderer();
  const cpu = createCanvasRenderer();
  const backend = gl ? gl.backend : cpu.backend;

  let scene = null;
  let photo = null; // { canvas, width, height }
  let source = null; // ImageData
  let masks = null;
  let shading = null;
  let residual = null; // { gloss, shadow }
  let lightDir = null;
  const buffers = new Map(); // canevas cible → ImageData réutilisée
  /* Pièces déjà préparées : pixels, masques, éclairement. Rouvrir une pièce
     de démonstration recalculait tout — mesuré le 12 octobre 2026 : 3 à 5 s
     de fil principal à CHAQUE retour sur la chambre. Seules les pièces
     calibrées y entrent (`cleCache`), jamais une photo importée, et une
     entrée est oubliée dès que son masque est retouché. */
  const preparees = new Map();
  const PREPAREES_MAX = 6;
  let cleCourante = null;
  /* Une scène installée après une autre annule l'éclairement en vol de la
     première : son résultat tardif ne doit pas écraser celui de la seconde. */
  let generationScene = 0;

  /** Cartes d'éclairement, de reflets et d'ombres : refaites si le sol bouge.
   *
   * Les résidus sont calculés pour toute scène depuis le LOT PHOTO.2 : les
   * reflets touchent désormais toutes les finitions, et les ombres de contact
   * ne dépendent pas du matériau. Avant, la carte de reflets n'existait que
   * pour une finition brillante, fabriquée au premier clic sur l'une d'elles. */
  function prepareLighting() {
    shading = chrono('J.lumiere.shading', () => buildShadingMap(source, masks.effectiveCoverage, scene.light));
    residual = chrono('J.lumiere.residus', () => buildResidualMaps(source, masks.effectiveCoverage, shading));
    installerLumiere();
  }

  /** Pose des cartes déjà calculées (ici ou dans le worker) sur le moteur. */
  function installerLumiere() {
    lightDir = lightDirection(shading);
    if (gl) {
      chrono('I.gpu.cartes', () => {
        gl.setShading(shading);
        gl.setResidual(residual);
        gl.setMasks(masks);
      });
    }
  }

  /* Préparations en cours, par clé de pièce : un préchargement et une
     ouverture de la même pièce partagent le même calcul. */
  const enPreparation = new Map();

  function retenirPreparation(cle, prep) {
    if (!cle) return;
    if (preparees.size >= PREPAREES_MAX) preparees.delete(preparees.keys().next().value);
    preparees.set(cle, prep);
  }

  /**
   * Calcule pixels, masques et éclairement d'une scène. Rend l'objet tout de
   * suite sans worker, une promesse avec. N'installe rien.
   */
  function preparer(sc, prepared, cle) {
    const src = prepared.canvas
      .getContext('2d', { willReadFrequently: true })
      .getImageData(0, 0, prepared.width, prepared.height);
    const msk = chrono('C.masques', () => createSceneMasks(sc, prepared.width, prepared.height));
    const calcul = lumiereAsync(src, msk.effectiveCoverage, sc.light);
    const finir = (sh, re) => {
      const prep = { photo: prepared, source: src, masks: msk, shading: sh, residual: re, lightDir: lightDirection(sh) };
      retenirPreparation(cle, prep);
      return prep;
    };
    if (!calcul) {
      const sh = chrono('J.lumiere.shading', () => buildShadingMap(src, msk.effectiveCoverage, sc.light));
      const re = chrono('J.lumiere.residus', () => buildResidualMaps(src, msk.effectiveCoverage, sh));
      return finir(sh, re);
    }
    const t0 = performance.now();
    const promesse = calcul.then(({ shading: sh, residual: re }) => {
      releve('J.lumiere.worker', performance.now() - t0);
      return finir(sh, re);
    }, () => {
      /* Worker en panne : le calcul se fait ici, comme avant. */
      const sh = buildShadingMap(src, msk.effectiveCoverage, sc.light);
      return finir(sh, buildResidualMaps(src, msk.effectiveCoverage, sh));
    }).finally(() => { if (cle && enPreparation.get(cle) === entree) enPreparation.delete(cle); });
    const entree = { photo: prepared, promesse };
    if (cle) enPreparation.set(cle, entree);
    return promesse;
  }

  /** Installe une préparation sur le moteur (cartes GPU comprises). */
  function installer(prep) {
    ({ source, masks, shading, residual } = prep);
    if (gl) gl.setPhoto(source);
    installerLumiere();
  }

  return {
    backend,
    anisotropy: gl ? gl.anisotropy : 1,

    get scene() {
      return scene;
    },
    get masks() {
      return masks;
    },
    get photo() {
      return photo ? photo.canvas : null;
    },
    get size() {
      return photo ? { width: photo.width, height: photo.height } : null;
    },
    get ready() {
      return Boolean(scene && source && masks && shading);
    },

    /**
     * Installe une scène et sa photo.
     * @param {object} nextScene SceneData normalisée
     * @param {{canvas:HTMLCanvasElement,width:number,height:number}} prepared
     */
    setScene(nextScene, prepared, { cleCache = null } = {}) {
      scene = nextScene;
      photo = prepared;
      buffers.clear();
      cleCourante = cleCache;
      const jeton = (generationScene += 1);
      /* Préparée d'avance (préchargement) ou en cours de préparation : on
         la reprend au lieu de la recalculer. */
      const deja = cleCache && preparees.get(cleCache);
      if (deja && deja.photo === prepared) { installer(deja); return undefined; }
      const enVol = cleCache && enPreparation.get(cleCache);
      const calcul = enVol && enVol.photo === prepared ? enVol.promesse : preparer(nextScene, prepared, cleCache);
      if (!(calcul instanceof Promise)) { installer(calcul); return undefined; }
      /* Dans le worker : la page reste vivante. La scène n'est « prête »
         qu'avec son éclairement — `ready` reste faux d'ici là, et
         l'appelant attend la promesse. */
      shading = null;
      return calcul.then((prep) => {
        if (jeton !== generationScene) return false; // une autre scène est passée
        installer(prep);
        return true;
      });
    },

    /**
     * Prépare une pièce SANS l'installer : pixels, masques, éclairement,
     * calculés dans le worker et gardés pour la prochaine ouverture. Sert au
     * préchargement des pièces visibles de la galerie. Sans worker, ne fait
     * rien : le calcul figerait la page, ce qu'un préchargement ne doit
     * jamais faire.
     */
    precharger(nextScene, prepared, cleCache) {
      if (!cleCache || !obtenirWorkerLumiere()) return Promise.resolve(false);
      const deja = preparees.get(cleCache);
      if (deja && deja.photo === prepared) return Promise.resolve(true);
      const enVol = enPreparation.get(cleCache);
      if (enVol && enVol.photo === prepared) return enVol.promesse.then(() => true, () => false);
      const calcul = preparer(nextScene, prepared, cleCache);
      return calcul instanceof Promise ? calcul.then(() => true, () => false) : Promise.resolve(true);
    },

    /**
     * Le contour d'une zone a changé. Les masques se refont d'eux-mêmes au
     * prochain rendu ; l'éclairement, lui, coûte cher — on ne le recalcule
     * qu'à la fin du geste, via refreshLighting().
     */
    /** Oublie la préparation gardée de la pièce courante (masque retouché). */
    oublierPreparation() {
      if (cleCourante) preparees.delete(cleCourante);
    },

    invalidateMasks() {
      if (cleCourante) preparees.delete(cleCourante);
      if (masks) masks.invalidate();
    },

    /**
     * Recalcule l'éclairement après une correction du sol.
     *
     * L'éclairement dépend du masque : la moyenne de référence est prise sur
     * les pixels de sol, et une moyenne qui inclurait un mur clair décalerait
     * tout le rendu. À appeler quand la poignée est relâchée, pas pendant
     * qu'on la déplace.
     */
    refreshLighting() {
      if (cleCourante) preparees.delete(cleCourante);
      if (masks) prepareLighting();
    },

    /** Photo edits use the same worker as scene preparation. Late results cannot replace a new scene. */
    async refreshLightingAsync() {
      if (cleCourante) preparees.delete(cleCourante);
      if (!masks) return false;
      const token = generationScene, editedMasks = masks;
      const calcul = lumiereAsync(source, masks.effectiveCoverage, scene.light);
      if (!calcul) { prepareLighting(); return true; }
      try {
        const next = await calcul;
        if (token !== generationScene || editedMasks !== masks) return false;
        shading = next.shading; residual = next.residual;
        installerLumiere();
      } catch {
        if (token !== generationScene || editedMasks !== masks) return false;
        prepareLighting();
      }
      return true;
    },

    /** Prépare une texture en tâche de fond, pour que le clic soit instantané. */
    warm: warmMaterial,

    /**
     * Matériaux à appliquer, par surface.
     *
     * Une surface est un sol : toutes ses zones reçoivent le même bois, quelle
     * que soit leur perspective. C'est ce qui fait qu'un parquet choisi change
     * la pièce du fond en même temps que celle du premier plan.
     */
    /** Vrai après un `surfacesFor` dont au moins une surface attend ses cartes. */
    enAttente: false,

    /**
     * Attend que les cartes de toutes les surfaces soient prêtes.
     *
     * `paint()` est synchrone et rend `false` quand une carte se fabrique dans
     * le worker : l'application, elle, repeindra au signal. Les pages d'outil
     * qui peignent UNE fois puis lisent les pixels — revue des scènes, contrôle
     * des zones — n'ont pas ce signal ; sans cette attente elles lisaient un
     * canevas noir. Elles appellent donc `await renderer.preparer(config)`.
     */
    async preparer(config, perSurface) {
      if (!this.ready || !config || !config.material) return false;
      if (scene.floorZones.every(z => z.plane.projection?.status === 'NEEDS_MANUAL_GEOMETRY')) return false;
      await Promise.all(scene.surfaces.map((surface) => {
        const entry = (perSurface && perSurface.get(surface.id)) || config;
        return entry && entry.material ? materialMapsAsync(entry.material, entry) : null;
      }));
      return true;
    },

    surfacesFor(config, perSurface) {
      const map = new Map();
      this.enAttente = false;
      scene.surfaces.forEach((surface) => {
        const entry = (perSurface && perSurface.get(surface.id)) || config;
        if (!entry || !entry.material) return;
        const maps = materialMaps(entry.material, entry);
        // `null` : les cartes se fabriquent dans le worker. On ne peint pas
        // cette surface maintenant ; l'application sera prévenue et repeindra.
        if (!maps) { this.enAttente = true; return; }
        map.set(surface.id, { material: entry.material, config: entry, maps });
      });
      return map;
    },

    /**
     * Peint la scène dans un canevas.
     * @param {HTMLCanvasElement} target
     * @param {object} config          { material, pattern, angle, width, scale }
     * @param {Map} [perSurface]       surfaceId → config, pour les cas mixtes
     * @param {number} [step]          1 = pleine résolution, 2 = allégé (Canvas)
     */
    paint(target, config, perSurface, step = 1) {
      if (!this.ready || !config || !config.material) return false;
      if (scene.floorZones.every(z => z.plane.projection?.status === 'NEEDS_MANUAL_GEOMETRY')) return false;
      mark('paint:debut');
      const { width, height } = photo;
      if (target.width !== width || target.height !== height) {
        target.width = width;
        target.height = height;
        buffers.delete(target);
      }
      const surfaces = this.surfacesFor(config, perSurface);
      if (!surfaces.size) return false;

      // Le masque a pu changer depuis le dernier rendu (poignée déplacée,
      // pinceau) : on relit les cartes avant de peindre.
      if (gl) {
        gl.setMasks(masks);
        gl.draw({ scene, masks, surfaces, lightDir, shading });
        const ctx = target.getContext('2d');
        ctx.clearRect(0, 0, width, height);
        ctx.drawImage(gl.canvas, 0, 0);
        mark('paint:fin');
        mesure(`paint.webgl.q${step}`, 'paint:debut', 'paint:fin');
        return true;
      }

      const ctx = target.getContext('2d', { willReadFrequently: true });
      if (!buffers.has(target)) buffers.set(target, ctx.createImageData(width, height));
      const buffer = buffers.get(target);
      // Le moteur logiciel échantillonne toute la pyramide : on la complète ici,
      // une fois, plutôt que de la calculer pour tout le monde.
      surfaces.forEach((entry) => { if (entry.maps.completer) entry.maps.completer(); });
      const ok = cpu.paint({
        source, target: buffer, scene, masks, shading,
        gloss: residual && residual.fullRes().gloss, shadow: residual && residual.fullRes().shadow,
        light: residual && residual.fullRes().light,
        mid: residual && residual.fullRes().mid, mid: residual && residual.fullRes().mid, surfaces, step,
      });
      if (!ok) return false;
      ctx.putImageData(buffer, 0, 0);
      mark('paint:fin');
      mesure(`paint.canvas.q${step}`, 'paint:debut', 'paint:fin');
      return true;
    },

    /**
     * Rend la scène avec le moteur logiciel, quel que soit le moteur actif.
     * Sert au banc de comparaison des deux moteurs.
     */
    paintWithCanvas(target, config, perSurface, step = 1) {
      if (!this.ready) return false;
      const { width, height } = photo;
      target.width = width;
      target.height = height;
      const ctx = target.getContext('2d', { willReadFrequently: true });
      const buffer = ctx.createImageData(width, height);
      const surfaces = this.surfacesFor(config, perSurface);
      // Même raison que dans paint() : le moteur logiciel lit tous les niveaux.
      surfaces.forEach((entry) => { if (entry.maps.completer) entry.maps.completer(); });
      const ok = cpu.paint({
        source,
        target: buffer,
        scene,
        masks,
        shading,
        gloss: residual && residual.fullRes().gloss,
        shadow: residual && residual.fullRes().shadow,
        light: residual && residual.fullRes().light,
        surfaces,
        step,
      });
      if (ok) ctx.putImageData(buffer, 0, 0);
      return ok;
    },
  };
}
