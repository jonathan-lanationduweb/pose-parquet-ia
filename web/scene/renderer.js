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
import { mark, mesure } from '../utils/perf.js';
import { buildShadingMap, buildGlossMap } from './shading.js';
import { lightDirection } from './geometry.js';
import { materialMaps, materialMapsAsync, warmMaterial } from './material.js';
import { createCanvasRenderer } from './renderer-canvas.js';
import { createGlRenderer, glAvailable } from './renderer-gl.js';

/** Une finition sous ce seuil ne réfléchit rien qui se voie : carte inutile. */
const GLOSS_THRESHOLD = 0.06;

export function createSceneRenderer({ prefer = 'auto' } = {}) {
  const gl = prefer === 'canvas' || !glAvailable() ? null : createGlRenderer();
  const cpu = createCanvasRenderer();
  const backend = gl ? gl.backend : cpu.backend;

  let scene = null;
  let photo = null; // { canvas, width, height }
  let source = null; // ImageData
  let masks = null;
  let shading = null;
  let gloss = null;
  let lightDir = null;
  let glossWanted = false;
  const buffers = new Map(); // canevas cible → ImageData réutilisée

  /** Cartes d'éclairement et de reflets : refaites seulement si le sol bouge. */
  function prepareLighting() {
    shading = buildShadingMap(source, masks.coverage, scene.light);
    lightDir = lightDirection(shading);
    gloss = glossWanted ? buildGlossMap(source, masks.coverage, shading) : null;
    if (gl) {
      gl.setShading(shading);
      gl.setGloss(gloss);
      gl.setMasks(masks);
    }
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
      return Boolean(scene && source && masks);
    },

    /**
     * Installe une scène et sa photo.
     * @param {object} nextScene SceneData normalisée
     * @param {{canvas:HTMLCanvasElement,width:number,height:number}} prepared
     */
    setScene(nextScene, prepared) {
      scene = nextScene;
      photo = prepared;
      source = prepared.canvas
        .getContext('2d', { willReadFrequently: true })
        .getImageData(0, 0, prepared.width, prepared.height);
      masks = createSceneMasks(scene, prepared.width, prepared.height);
      buffers.clear();
      if (gl) gl.setPhoto(source);
      prepareLighting();
    },

    /**
     * Le contour d'une zone a changé. Les masques se refont d'eux-mêmes au
     * prochain rendu ; l'éclairement, lui, coûte cher — on ne le recalcule
     * qu'à la fin du geste, via refreshLighting().
     */
    invalidateMasks() {
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
      if (masks) prepareLighting();
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
        if (maps.surface.clearcoat > GLOSS_THRESHOLD && !glossWanted) {
          // Première finition brillante rencontrée : la carte de reflets n'a
          // pas été calculée, on la fabrique maintenant plutôt qu'à l'avance.
          glossWanted = true;
          gloss = buildGlossMap(source, masks.coverage, shading);
          if (gl) gl.setGloss(gloss);
        }
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
        gl.draw({ scene, masks, surfaces, lightDir });
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
      const ok = cpu.paint({ source, target: buffer, scene, masks, shading, gloss, surfaces, step });
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
        gloss,
        surfaces,
        step,
      });
      if (ok) ctx.putImageData(buffer, 0, 0);
      return ok;
    },
  };
}
