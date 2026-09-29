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
 *   ← { id, albedo: {size, data}, relief: {size, data}, etapes: {…} }
 *   ← { id, erreur: string }
 *
 * `etapes` porte trois durées en millisecondes — dessin, lecture des pixels,
 * relief. Elles sont mesurées ici parce qu'elles ne peuvent l'être ailleurs :
 * `perf.js` s'active sur `window.location.search`, et un worker n'a pas de
 * `window`. Trois `performance.now()` par tuile ne coûtent rien, et sans eux
 * la seule chose qu'on sait de cette seconde et demie, c'est sa durée totale.
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
    const t0 = performance.now();
    const tile = buildTexture(material, {
      pattern: config.pattern || material.defaultPattern,
      width: config.width || null,
    });
    const t1 = performance.now();
    const [albedo] = buildMips(tile, 1);
    const t2 = performance.now();
    const relief = reliefFromAlbedo(albedo, material.surface);
    const t3 = performance.now();
    self.postMessage(
      {
        id,
        albedo,
        relief,
        etapes: {
          dessin: t1 - t0,
          lecturePixels: t2 - t1,
          relief: t3 - t2,
          taille: albedo.size,
        },
      },
      [albedo.data.buffer, relief.data.buffer],
    );
  } catch (erreur) {
    self.postMessage({ id, erreur: String(erreur && erreur.message ? erreur.message : erreur) });
  }
};
