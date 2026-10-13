/**
 * Cartes d'éclairement d'une pièce, hors du fil principal.
 *
 * Ouvrir une pièce calculait sur le fil principal la carte d'éclairement et
 * les résidus (reflets, ombres de contact, soleil) : mesuré le 13 octobre
 * 2026, 3 à 10 s de page figée à chaque première visite, selon la charge de
 * la machine. Le calcul est le même ; il se fait ici.
 *
 * Protocole :
 *   → { id, source: { width, height, data }, coverage, light }
 *   ← { id, shading: {…données}, residual: {…données} }  (tableaux transférés)
 *   ← { id, erreur }
 *
 * Seules des données voyagent : les fonctions de lecture (`sample`,
 * `fullRes`) sont refaites côté page par `habillerShading` et
 * `habillerResidus`.
 */
import { buildShadingMap, buildResidualMaps } from './shading.js';

self.onmessage = (event) => {
  const { id, source, coverage, light } = event.data || {};
  try {
    const shading = buildShadingMap(source, coverage, light);
    const residual = buildResidualMaps(source, coverage, shading);
    const s = {
      width: shading.width, height: shading.height, rgba: shading.rgba,
      reference: shading.reference, referenceRgb: shading.referenceRgb,
      lightTint: shading.lightTint, fullW: shading.fullW, fullH: shading.fullH,
    };
    const r = {
      gloss: residual.gloss, shadow: residual.shadow, light: residual.light, mid: residual.mid,
      width: residual.width, height: residual.height, fullW: residual.fullW, fullH: residual.fullH, k: residual.k,
    };
    self.postMessage({ id, shading: s, residual: r },
      [s.rgba.buffer, r.gloss.buffer, r.shadow.buffer, r.light.buffer, r.mid.buffer]);
  } catch (erreur) {
    self.postMessage({ id, erreur: String(erreur && erreur.message ? erreur.message : erreur) });
  }
};
