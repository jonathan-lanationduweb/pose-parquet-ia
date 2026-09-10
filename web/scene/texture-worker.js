/**
 * Fabrication des cartes d'un matériau, hors du fil principal.
 *
 * Le point de Hongrie émet 74 248 tracés et coûte de 1,2 à 3 secondes de
 * rastérisation ; dessiné sur le fil principal, il figeait l'interface le
 * temps du calcul — mesuré : une tâche bloquante de 1 209 ms au changement de
 * motif, 2 919 ms sur une machine plus lente. Ici le même code tourne dans un
 * Web Worker sur un OffscreenCanvas : l'interface reste vivante, le rendu
 * précédent reste affiché, et le nouveau arrive quand il est prêt.
 *
 * Le worker ne connaît ni le catalogue ni le cache : il reçoit un matériau
 * (données pures, clonables) et une configuration, et renvoie le niveau 0 de
 * l'albedo et du relief sous forme de tableaux transférés — pas copiés.
 *
 * Protocole :
 *   → { id, material, config }
 *   ← { id, albedo: {size, data}, relief: {size, data} }
 *   ← { id, erreur: string }
 */
import { buildTexture, buildMips } from './texture.js';
import { reliefFromAlbedo } from './relief.js';

self.onmessage = (event) => {
  const { id, material, config, kind } = event.data || {};
  try {
    if (kind === 'apercu') {
      // Aperçu d'un motif pour le panneau : même dessin, tuile réduite, et un
      // ImageBitmap transféré — pas de lecture de pixels, pas de copie.
      const petite = buildTexture(material, { pattern: config.pattern, size: config.size || 320 });
      const bitmap = petite.transferToImageBitmap();
      self.postMessage({ id, bitmap }, [bitmap]);
      return;
    }
    const tile = buildTexture(material, {
      pattern: config.pattern || material.defaultPattern,
      width: config.width || null,
    });
    const [albedo] = buildMips(tile, 1);
    const relief = reliefFromAlbedo(albedo, material.surface);
    self.postMessage(
      { id, albedo, relief },
      [albedo.data.buffer, relief.data.buffer],
    );
  } catch (erreur) {
    self.postMessage({ id, erreur: String(erreur && erreur.message ? erreur.message : erreur) });
  }
};
