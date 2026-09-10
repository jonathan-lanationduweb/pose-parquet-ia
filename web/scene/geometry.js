/**
 * Géométrie d'une zone de sol, partagée par les deux moteurs de rendu.
 *
 * Les deux ont besoin exactement des mêmes nombres — c'est la condition pour
 * qu'ils donnent la même image, et donc pour que le moteur Canvas reste une
 * référence utilisable.
 */
import { squareToQuad, invert } from './perspective.js';

/**
 * Repère de perspective d'une zone, en pixels image.
 *
 * `jac` est le jacobien du plan au centre du quadrilatère : de combien de
 * pixels l'image se déplace quand on avance d'un mètre sur le sol. Il varie
 * lentement, une seule évaluation au centre suffit largement pour orienter
 * la lumière.
 *
 * @returns {{H:number[], M:number[], jac:number[], center:{x,y}}|null}
 */
export function zoneTransform(zone, width, height) {
  const quad = zone.plane.quad.map((p) => ({ x: p.x * width, y: p.y * height }));
  const H = squareToQuad(quad);
  if (!H) return null;
  const M = invert(H);
  if (!M) return null;

  const at = (u, v) => {
    const w = H[6] * u + H[7] * v + H[8];
    return { x: (H[0] * u + H[1] * v + H[2]) / w, y: (H[3] * u + H[4] * v + H[5]) / w };
  };
  const center = at(0.5, 0.5);
  const du = at(0.52, 0.5);
  const dv = at(0.5, 0.52);
  const stepU = 0.02 * zone.plane.meters.width;
  const stepV = 0.02 * zone.plane.meters.depth;

  return {
    H,
    M,
    center,
    jac: [(du.x - center.x) / stepU, (dv.x - center.x) / stepV, (du.y - center.y) / stepU, (dv.y - center.y) / stepV],
  };
}

/**
 * D'où vient la lumière, lu dans la carte d'éclairement.
 *
 * Le gradient dominant de la lumière pointe vers sa source : une fenêtre à
 * gauche laisse un dégradé qui décroît vers la droite. Aucun modèle, aucune
 * estimation savante — juste la photo, moyennée.
 *
 * @returns {{x:number,y:number}} direction unitaire, en repère image
 */
export function lightDirection(shading) {
  const { width, height, rgba } = shading;
  const lum = (index) => {
    const p = index * 4;
    return 0.2126 * rgba[p] + 0.7152 * rgba[p + 1] + 0.0722 * rgba[p + 2];
  };
  let gx = 0;
  let gy = 0;
  for (let y = 1; y < height - 1; y += 1) {
    const row = y * width;
    for (let x = 1; x < width - 1; x += 1) {
      gx += lum(row + x + 1) - lum(row + x - 1);
      gy += lum(row + width + x) - lum(row - width + x);
    }
  }
  const length = Math.hypot(gx, gy);
  // Éclairage diffus, pas de direction franche : lumière d'en haut à gauche,
  // la convention qui trahit le moins.
  if (length < 1e-3) return { x: -0.55, y: -0.83 };
  return { x: gx / length, y: gy / length };
}

/**
 * Direction de la lumière ramenée dans le repère de la tuile.
 *
 * Le relief est décrit dans la tuile, la lumière est mesurée dans l'image :
 * sans ce passage, les chanfreins d'une zone vue de biais seraient éclairés du
 * mauvais côté.
 *
 * @param {number[]} jac      jacobien de la zone
 * @param {{x,y}} dir         direction de la lumière, repère image
 * @param {number} angleRad   orientation du motif
 */
export function tileLight(jac, dir, angleRad) {
  const det = jac[0] * jac[3] - jac[1] * jac[2];
  const inv = Math.abs(det) > 1e-9 ? 1 / det : 0;
  const lu = inv * (jac[3] * dir.x - jac[1] * dir.y);
  const lv = inv * (-jac[2] * dir.x + jac[0] * dir.y);
  const norm = Math.hypot(lu, lv) || 1;
  const cos = Math.cos(angleRad);
  const sin = Math.sin(angleRad);
  return {
    u: (lu / norm) * cos + (lv / norm) * sin,
    v: -(lu / norm) * sin + (lv / norm) * cos,
  };
}
