/**
 * Chargement des images du visualiseur : pièces d'exemple et photos importées.
 *
 * Les photos importées ne quittent jamais le navigateur : elles sont lues via
 * URL.createObjectURL, redimensionnées si nécessaire, puis dessinées dans un
 * canevas local. Aucun envoi réseau.
 */

/** Largeur maximale traitée : au-delà, le rendu coûte cher pour rien. */
const MAX_WIDTH = 1600;
const MAX_HEIGHT = 1200;
export const ACCEPTED = ['image/jpeg', 'image/png', 'image/webp'];

/** Charge une image et renvoie un canevas déjà redimensionné. */
export function loadImage(src) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.decoding = 'async';
    img.onload = () => resolve(prepare(img));
    img.onerror = () => reject(new Error('Image illisible'));
    img.src = src;
  });
}

/** Redimensionne si besoin et renvoie { canvas, width, height }. */
export function prepare(img) {
  // Sur un petit écran, on travaille sur une image plus légère : le rendu est
  // recalculé à chaque réglage, et deux fois moins de pixels, c'est deux fois
  // moins d'attente. La qualité perçue reste identique à l'affichage.
  const small = typeof window !== 'undefined' && window.innerWidth < 600;
  const maxWidth = small ? 1100 : MAX_WIDTH;
  const maxHeight = small ? 825 : MAX_HEIGHT;
  const ratio = Math.min(1, maxWidth / img.naturalWidth, maxHeight / img.naturalHeight);
  const width = Math.round(img.naturalWidth * ratio);
  const height = Math.round(img.naturalHeight * ratio);
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  ctx.imageSmoothingQuality = 'high';
  ctx.drawImage(img, 0, 0, width, height);
  return { canvas, width, height };
}

/**
 * Lit un fichier choisi par l'utilisateur.
 * @param {File} file
 * @returns {Promise<{canvas:HTMLCanvasElement,width:number,height:number,name:string}>}
 */
export async function loadFile(file) {
  if (!file) throw new Error('Aucun fichier');
  const type = (file.type || '').toLowerCase();
  if (!ACCEPTED.includes(type)) {
    throw new Error('Format non pris en charge. Utilisez un JPG, un PNG ou un WebP.');
  }
  if (file.size > 20 * 1024 * 1024) {
    throw new Error('Photo trop lourde (20 Mo maximum).');
  }

  const url = URL.createObjectURL(file);
  try {
    const prepared = await loadImage(url);
    return { ...prepared, name: file.name };
  } finally {
    URL.revokeObjectURL(url);
  }
}
