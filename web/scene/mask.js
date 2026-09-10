/**
 * Masques d'une scène.
 *
 * Une scène peut compter plusieurs zones de sol : la pièce du premier plan,
 * celle que l'on aperçoit derrière une ouverture, un couloir. Chacune a son
 * propre plan de perspective, mais elles ne se recouvrent pas — ce sont des
 * morceaux de sol distincts.
 *
 * On en tire donc deux cartes seulement, quel que soit le nombre de zones :
 *
 *   labels    quelle zone possède ce pixel (0 = aucune, 1..n = index + 1)
 *   coverage  couverture antialiasée du sol (0 → 255)
 *
 * et une troisième pour ce qui doit rester devant :
 *
 *   occlusion  255 = restituer la photo d'origine (meuble, tapis, plinthe)
 *
 * Deux cartes plutôt qu'un masque par zone : la mémoire ne dépend plus du
 * nombre de zones, et le moteur de rendu fait un seul passage sur l'image.
 *
 * Le tracé se fait sur un canevas hors écran, en une passe par zone puis une
 * lecture unique — lire un canevas est de loin l'opération la plus coûteuse.
 */
import { zonePolygon } from './schema.js';

const MAX_HISTORY = 60;

const trace = (ctx, points, width, height) => {
  points.forEach((p, i) => {
    const x = p.x * width;
    const y = p.y * height;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.closePath();
};

export function createSceneMasks(scene, width, height) {
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d', { willReadFrequently: true });

  const labels = new Uint8Array(width * height);
  const coverage = new Uint8ClampedArray(width * height);
  const occlusion = new Uint8ClampedArray(width * height);

  /** Contours courants, par zone : l'édition ne touche pas la scène d'origine. */
  const polygons = new Map(scene.floorZones.map((zone) => [zone.id, zonePolygon(zone).map((p) => ({ ...p }))]));
  /** @type {{zoneId:string, mode:'add'|'remove', radius:number, points:{x:number,y:number}[]}[]} */
  let strokes = [];
  let redoStack = [];

  let boxes = new Map();
  let unionBox = null;
  let hasOcclusion = false;
  let dirty = true;

  /* ---------------- Tracé ---------------- */

  const paintStroke = (stroke, only) => {
    ctx.save();
    ctx.globalCompositeOperation = stroke.mode === 'remove' ? 'destination-out' : 'source-over';
    ctx.strokeStyle = '#fff';
    ctx.fillStyle = '#fff';
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.lineWidth = stroke.radius * 2;
    const points = only || stroke.points;
    if (points.length === 1) {
      ctx.beginPath();
      ctx.arc(points[0].x * width, points[0].y * height, stroke.radius, 0, Math.PI * 2);
      ctx.fill();
    } else {
      ctx.beginPath();
      points.forEach((p, i) => {
        const x = p.x * width;
        const y = p.y * height;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
    }
    ctx.restore();
  };

  /**
   * Dessine une zone : contour, moins ses trous, plus ses retouches.
   * Renvoie la boîte englobante lue sur le canevas, pour que le rendu ne
   * parcoure jamais l'image entière.
   */
  function drawZone(zone) {
    ctx.clearRect(0, 0, width, height);
    const polygon = polygons.get(zone.id);
    if (!polygon || polygon.length < 3) return null;

    ctx.fillStyle = '#fff';
    ctx.beginPath();
    trace(ctx, polygon, width, height);
    zone.mask.holes.forEach((hole) => trace(ctx, hole, width, height));
    ctx.fill('evenodd');

    strokes.filter((stroke) => stroke.zoneId === zone.id).forEach((stroke) => paintStroke(stroke));
    return true;
  }

  function rebuild() {
    labels.fill(0);
    coverage.fill(0);
    boxes = new Map();

    scene.floorZones.forEach((zone, index) => {
      if (!drawZone(zone)) return;
      const data = ctx.getImageData(0, 0, width, height).data;
      const label = index + 1;
      let x0 = width;
      let y0 = height;
      let x1 = 0;
      let y1 = 0;
      for (let i = 0, p = 3; i < labels.length; i += 1, p += 4) {
        const a = data[p];
        if (a <= 2) continue;
        // Les zones ne se recouvrent pas ; en cas de chevauchement résiduel,
        // la plus proche (index le plus élevé) gagne — c'est ce que l'œil
        // attend d'un sol vu par-dessus un autre.
        labels[i] = label;
        if (a > coverage[i]) coverage[i] = a;
        const x = i % width;
        const y = (i - x) / width;
        if (x < x0) x0 = x;
        if (x > x1) x1 = x;
        if (y < y0) y0 = y;
        if (y > y1) y1 = y;
      }
      if (x1 > x0 && y1 > y0) {
        boxes.set(zone.id, {
          x0: Math.max(0, x0 - 1),
          y0: Math.max(0, y0 - 1),
          x1: Math.min(width, x1 + 2),
          y1: Math.min(height, y1 + 2),
        });
      }
    });

    unionBox = null;
    boxes.forEach((box) => {
      unionBox = unionBox
        ? {
            x0: Math.min(unionBox.x0, box.x0),
            y0: Math.min(unionBox.y0, box.y0),
            x1: Math.max(unionBox.x1, box.x1),
            y1: Math.max(unionBox.y1, box.y1),
          }
        : { ...box };
    });

    /* Occlusions : données de scène, valables pour toutes les zones. */
    occlusion.fill(0);
    hasOcclusion = false;
    if (scene.occluders.length) {
      ctx.clearRect(0, 0, width, height);
      ctx.fillStyle = '#fff';
      scene.occluders.forEach((occluder) => {
        // Un liseré adouci évite l'arête de découpe, qui trahit tout de suite
        // un montage. Le flou est exprimé en fraction de largeur d'image.
        const blur = Math.max(0, occluder.feather * width);
        ctx.save();
        if (blur > 0.4) ctx.filter = `blur(${blur.toFixed(2)}px)`;
        ctx.beginPath();
        trace(ctx, occluder.polygon, width, height);
        ctx.fill();
        ctx.restore();
      });
      const data = ctx.getImageData(0, 0, width, height).data;
      for (let i = 0, p = 3; i < occlusion.length; i += 1, p += 4) {
        if (data[p] > 2) {
          occlusion[i] = data[p];
          hasOcclusion = true;
        }
      }
    }

    dirty = false;
  }

  const ensure = () => {
    if (dirty) rebuild();
  };

  return {
    width,
    height,

    get labels() {
      ensure();
      return labels;
    },
    get coverage() {
      ensure();
      return coverage;
    },
    get occlusion() {
      ensure();
      return hasOcclusion ? occlusion : null;
    },
    /** Boîte englobante d'une zone, ou de toutes si aucun id n'est donné. */
    box(zoneId) {
      ensure();
      return zoneId ? boxes.get(zoneId) || null : unionBox;
    },

    /**
     * Déclare une zone apparue après coup — l'utilisateur qui ajoute un second
     * sol sur sa photo, ou un service d'analyse qui en renvoie un de plus.
     * Sans cela la zone existerait dans la scène mais n'aurait aucun contour.
     */
    registerZone(zone) {
      if (polygons.has(zone.id)) return;
      polygons.set(zone.id, zonePolygon(zone).map((p) => ({ ...p })));
      dirty = true;
    },
    removeZone(zoneId) {
      polygons.delete(zoneId);
      strokes = strokes.filter((stroke) => stroke.zoneId !== zoneId);
      dirty = true;
    },

    getPolygon(zoneId) {
      const polygon = polygons.get(zoneId);
      return polygon ? polygon.map((p) => ({ ...p })) : [];
    },
    setPolygon(zoneId, points) {
      polygons.set(zoneId, points.map((p) => ({ ...p })));
      dirty = true;
    },
    /** Ajoute un point sur le segment le plus proche du clic. */
    insertPointNear(zoneId, point) {
      const polygon = polygons.get(zoneId);
      if (!polygon || polygon.length < 2) return -1;
      let best = 0;
      let bestDist = Infinity;
      for (let i = 0; i < polygon.length; i += 1) {
        const a = polygon[i];
        const b = polygon[(i + 1) % polygon.length];
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const len2 = dx * dx + dy * dy;
        const t = len2 ? Math.max(0, Math.min(1, ((point.x - a.x) * dx + (point.y - a.y) * dy) / len2)) : 0;
        const d = Math.hypot(point.x - (a.x + t * dx), point.y - (a.y + t * dy));
        if (d < bestDist) {
          bestDist = d;
          best = i;
        }
      }
      polygon.splice(best + 1, 0, { ...point });
      dirty = true;
      return best + 1;
    },
    removePoint(zoneId, index) {
      const polygon = polygons.get(zoneId);
      if (!polygon || polygon.length <= 3 || !polygon[index]) return false;
      polygon.splice(index, 1);
      dirty = true;
      return true;
    },
    movePoint(zoneId, index, point) {
      const polygon = polygons.get(zoneId);
      if (!polygon || !polygon[index]) return;
      polygon[index] = { ...point };
      dirty = true;
    },

    /* Retouches au pinceau : elles appartiennent à une zone, puisqu'un pixel
       de sol a besoin d'un plan de perspective pour être peint. */
    beginStroke(zoneId, mode, radius, point) {
      redoStack = [];
      strokes.push({ zoneId, mode, radius, points: [point] });
      if (strokes.length > MAX_HISTORY) strokes = strokes.slice(-MAX_HISTORY);
      dirty = true;
    },
    extendStroke(point) {
      const stroke = strokes[strokes.length - 1];
      if (!stroke) return;
      stroke.points.push(point);
      dirty = true;
    },
    undo() {
      if (!strokes.length) return false;
      redoStack.push(strokes.pop());
      dirty = true;
      return true;
    },
    redo() {
      if (!redoStack.length) return false;
      strokes.push(redoStack.pop());
      dirty = true;
      return true;
    },
    clearStrokes() {
      strokes = [];
      redoStack = [];
      dirty = true;
    },
    canUndo: () => strokes.length > 0,
    canRedo: () => redoStack.length > 0,
    hasStrokes: () => strokes.length > 0,

    invalidate() {
      dirty = true;
    },
  };
}
