/**
 * Carte de relief dérivée de l'albedo : pentes du bois (R, G) et rugosité (B).
 *
 * Module sans DOM, volontairement : il est appelé par `material.js` sur le fil
 * principal ET par `texture-worker.js` dans un Web Worker. Tout ce dont il a
 * besoin est un tableau de pixels et deux nombres.
 */

/**
 * @param {{size:number,data:Uint8ClampedArray}} mip niveau d'albedo
 * @param {{relief:number,roughness:number}} surface réglages du matériau
 * @returns {{size:number,data:Uint8ClampedArray}}
 */
export function reliefFromAlbedo(mip, { relief, roughness }) {
  const size = mip.size;
  const src = mip.data;
  const out = new Uint8ClampedArray(size * size * 4);
  const luma = new Float32Array(size * size);
  for (let i = 0, p = 0; i < luma.length; i += 1, p += 4) {
    luma[i] = (0.2126 * src[p] + 0.7152 * src[p + 1] + 0.0722 * src[p + 2]) / 255;
  }
  const amp = relief * 160;
  for (let y = 0; y < size; y += 1) {
    const up = ((y - 1 + size) % size) * size;
    const down = ((y + 1) % size) * size;
    const row = y * size;
    for (let x = 0; x < size; x += 1) {
      const left = (x - 1 + size) % size;
      const right = (x + 1) % size;
      const dx = luma[row + right] - luma[row + left];
      const dy = luma[down + x] - luma[up + x];
      const p = (row + x) * 4;
      out[p] = 128 + dx * amp;
      out[p + 1] = 128 + dy * amp;
      // Une zone sombre (joint, veine ouverte) est plus mate qu'une zone claire
      out[p + 2] = Math.round(255 * Math.min(1, roughness * (1.25 - luma[row + x] * 0.45)));
      out[p + 3] = 255;
    }
  }
  return { size, data: out };
}
