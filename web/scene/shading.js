/**
 * Éclairement repris de la photo.
 *
 * C'est la pièce qui manquait pour que le parquet cesse d'avoir l'air collé.
 *
 * L'approche naïve — multiplier la texture par la luminance du pixel d'origine
 * — reporte tout : la lumière du soleil, mais aussi **les lames de l'ancien
 * sol**. Le résultat garde en filigrane le parquet qu'on voulait remplacer, et
 * l'œil le voit immédiatement : deux trames se superposent.
 *
 * On sépare donc les deux :
 *
 *   basse fréquence   la lumière de la pièce — soleil, ombres portées,
 *                     dégradé vers le fond, obscurcissement sous les meubles.
 *                     C'est ce qu'on garde, et c'est ce qui ancre le parquet
 *                     dans la scène.
 *
 *   haute fréquence   le détail de l'ancien revêtement : joints, veines,
 *                     nœuds. C'est ce qu'on jette — sauf sa partie claire,
 *                     réservée aux finitions brillantes, parce qu'un reflet de
 *                     fenêtre est large et clair là où un joint est fin et
 *                     sombre.
 *
 * La lumière est traitée **en couleur**, pas en niveaux de gris : le soleil de
 * fin de journée est chaud, la lumière d'une baie sur un jardin est verte, un
 * angle à l'ombre est bleuté. Un parquet éclairé par une lumière neutre alors
 * que toute la pièce baigne dans une lumière chaude se voit immédiatement, même
 * quand on ne sait pas dire pourquoi.
 *
 * S'y ajoute l'ombre de contact au pied des murs et des meubles : un sol n'est
 * jamais aussi clair contre une plinthe qu'en pleine pièce. Sans elle, le
 * parquet a l'air posé par-dessus la photo ; avec elle, il a l'air dessous.
 *
 * Tout est calculé sur une image réduite (la lumière d'une pièce n'a pas besoin
 * de 1600 px) et **normalisé par le masque du sol** : sans quoi un mur clair
 * contaminerait la première rangée de lames.
 */

/** Côté maximal de la carte : au-delà, on décrit du détail, plus de la lumière. */
const MAP_MAX = 460;

/**
 * Flou par boîte séparable, appliqué trois fois : très proche d'un gaussien.
 * Les canaux et les poids sont floutés ensemble, puis divisés — un pixel hors
 * du sol pèse zéro, il ne peut donc pas éclaircir le bord de la zone.
 */
function blurWeighted(channels, weight, width, height, radius, passes = 3) {
  const buffers = channels.map((c) => Float32Array.from(c));
  const spare = channels.map(() => new Float32Array(channels[0].length));
  let w = Float32Array.from(weight);
  let wSpare = new Float32Array(w.length);

  const line = (src, dst, count, stride, lanes, laneStride) => {
    const span = radius * 2 + 1;
    for (let lane = 0; lane < lanes; lane += 1) {
      const base = lane * laneStride;
      let sum = 0;
      for (let i = -radius; i <= radius; i += 1) {
        sum += src[base + Math.min(count - 1, Math.max(0, i)) * stride];
      }
      for (let i = 0; i < count; i += 1) {
        dst[base + i * stride] = sum / span;
        sum +=
          src[base + Math.min(count - 1, Math.max(0, i + radius + 1)) * stride] -
          src[base + Math.min(count - 1, Math.max(0, i - radius)) * stride];
      }
    }
  };

  for (let pass = 0; pass < passes; pass += 1) {
    for (let c = 0; c < buffers.length; c += 1) {
      line(buffers[c], spare[c], width, 1, height, width);
      const tmp = buffers[c];
      buffers[c] = spare[c];
      spare[c] = tmp;
    }
    line(w, wSpare, width, 1, height, width);
    [w, wSpare] = [wSpare, w];

    for (let c = 0; c < buffers.length; c += 1) {
      line(buffers[c], spare[c], height, width, width, 1);
      const tmp = buffers[c];
      buffers[c] = spare[c];
      spare[c] = tmp;
    }
    line(w, wSpare, height, width, width, 1);
    [w, wSpare] = [wSpare, w];
  }

  return { channels: buffers, weight: w };
}

/**
 * Carte d'éclairement d'une scène.
 *
 * @param {ImageData} source            photo d'origine
 * @param {Uint8ClampedArray} coverage  couverture du sol, taille image
 * @param {object} light                scene.light
 * @returns {{width:number,height:number,rgba:Float32Array,reference:number,
 *            sample:(x,y,out)=>Float32Array, luminance:(x,y)=>number}}
 *
 * `rgba` contient, par pixel de la carte réduite :
 *   0,1,2 → gain par canal (1 = éclairement moyen du sol)
 *   3     → ombre de contact (1 = pleine pièce, < 1 le long des bords)
 */
export function buildShadingMap(source, coverage, light) {
  const fullW = source.width;
  const fullH = source.height;
  const src = source.data;

  const ratio = Math.min(1, MAP_MAX / Math.max(fullW, fullH));
  const width = Math.max(8, Math.round(fullW * ratio));
  const height = Math.max(8, Math.round(fullH * ratio));
  const stepX = fullW / width;
  const stepY = fullH / height;
  const count = width * height;

  /* Sous-échantillonnage par moyenne de bloc, pondérée par le masque. */
  const chan = [new Float32Array(count), new Float32Array(count), new Float32Array(count)];
  const weight = new Float32Array(count);
  for (let y = 0; y < height; y += 1) {
    const sy0 = Math.floor(y * stepY);
    const sy1 = Math.max(sy0 + 1, Math.floor((y + 1) * stepY));
    for (let x = 0; x < width; x += 1) {
      const sx0 = Math.floor(x * stepX);
      const sx1 = Math.max(sx0 + 1, Math.floor((x + 1) * stepX));
      let r = 0;
      let g = 0;
      let b = 0;
      let cover = 0;
      for (let sy = sy0; sy < sy1; sy += 1) {
        const row = sy * fullW;
        for (let sx = sx0; sx < sx1; sx += 1) {
          const i = row + sx;
          const c = coverage[i] / 255;
          if (c <= 0.02) continue;
          const p = i * 4;
          r += src[p] * c;
          g += src[p + 1] * c;
          b += src[p + 2] * c;
          cover += c;
        }
      }
      const index = y * width + x;
      chan[0][index] = r;
      chan[1][index] = g;
      chan[2][index] = b;
      weight[index] = cover;
    }
  }

  /* ---- Éclairement : basse fréquence, en couleur ---- */

  const radius = Math.max(2, Math.round(light.blurRadius * width));
  const blurred = blurWeighted(chan, weight, width, height, radius);

  // Référence : la couleur moyenne du sol. L'éclairement est un rapport à
  // cette moyenne, jamais une valeur absolue — le parquet garde donc sa propre
  // teinte, seule la modulation vient de la photo.
  const totals = [0, 0, 0];
  let mass = 0;
  for (let i = 0; i < count; i += 1) {
    if (blurred.weight[i] <= 1e-4) continue;
    for (let c = 0; c < 3; c += 1) totals[c] += blurred.channels[c][i];
    mass += blurred.weight[i];
  }
  const refRgb = totals.map((t) => (mass > 0 ? Math.max(12, t / mass) : 128));
  const reference = 0.2126 * refRgb[0] + 0.7152 * refRgb[1] + 0.0722 * refRgb[2];

  /* ---- Ombre de contact : la couverture du sol, floutée ---- */

  // Une plinthe, un pied de meuble : l'éclairement y est réduit sur quelques
  // centimètres. Flouter la couverture donne exactement cette décroissance,
  // et pour rien : la carte est déjà là.
  const solid = new Float32Array(count);
  for (let i = 0; i < count; i += 1) solid[i] = weight[i] > 0 ? 1 : 0;
  const ones = new Float32Array(count).fill(1);
  const contactRadius = Math.max(1, Math.round(width * 0.012));
  const contact = blurWeighted([solid], ones, width, height, contactRadius, 2).channels[0];

  /* ---- Assemblage ---- */

  const rgba = new Float32Array(count * 4);
  for (let i = 0; i < count; i += 1) {
    const p = i * 4;
    const known = blurred.weight[i] > 1e-4;
    for (let c = 0; c < 3; c += 1) {
      // Les trous (aucun pixel de sol alentour) reçoivent un éclairement
      // neutre : au pire, le parquet y garde sa couleur propre.
      rgba[p + c] = known ? blurred.channels[c][i] / blurred.weight[i] / refRgb[c] : 1;
    }
    // `contact` vaut 1 en pleine zone et décroît vers les bords ; on ne garde
    // que l'assombrissement, dosé par la scène.
    rgba[p + 3] = 1 - light.contact * (1 - Math.min(1, contact[i]));
  }

  const sample = (x, y, out) => {
    const fx = Math.min(width - 1.001, Math.max(0, (x / fullW) * width - 0.5));
    const fy = Math.min(height - 1.001, Math.max(0, (y / fullH) * height - 0.5));
    const x0 = fx | 0;
    const y0 = fy | 0;
    const tx = fx - x0;
    const ty = fy - y0;
    const i00 = (y0 * width + x0) * 4;
    const i10 = i00 + 4;
    const i01 = i00 + width * 4;
    const i11 = i01 + 4;
    const w00 = (1 - tx) * (1 - ty);
    const w10 = tx * (1 - ty);
    const w01 = (1 - tx) * ty;
    const w11 = tx * ty;
    for (let c = 0; c < 4; c += 1) {
      out[c] = rgba[i00 + c] * w00 + rgba[i10 + c] * w10 + rgba[i01 + c] * w01 + rgba[i11 + c] * w11;
    }
    return out;
  };

  const scratch = new Float32Array(4);
  return {
    width,
    height,
    rgba,
    reference,
    referenceRgb: refRgb,
    sample,
    /** Éclairement en luminance seule : sert au repérage de la direction. */
    luminance(x, y) {
      sample(x, y, scratch);
      return 0.2126 * scratch[0] + 0.7152 * scratch[1] + 0.0722 * scratch[2];
    },
  };
}

/**
 * Résidu clair de la photo, à pleine résolution.
 *
 * `luminance du pixel − éclairement basse fréquence`, borné aux valeurs
 * positives. Ne subsiste donc que ce qui est **plus clair** que l'éclairement
 * local : les reflets de fenêtre, la traînée du soleil sur un sol verni. Les
 * joints et les veines de l'ancien parquet, qui sont plus sombres, sont
 * écartés — c'est exactement ce qu'on cherche à ne pas reproduire.
 *
 * Ce résidu n'est appliqué qu'aux finitions brillantes, et à faible dose : le
 * réalisme compte plus que l'effet.
 */
export function buildGlossMap(source, coverage, shading) {
  const width = source.width;
  const height = source.height;
  const src = source.data;
  const gloss = new Float32Array(width * height);
  const out = new Float32Array(4);
  for (let y = 0; y < height; y += 1) {
    const row = y * width;
    for (let x = 0; x < width; x += 1) {
      const i = row + x;
      if (coverage[i] <= 2) continue;
      const p = i * 4;
      const luma = 0.2126 * src[p] + 0.7152 * src[p + 1] + 0.0722 * src[p + 2];
      shading.sample(x, y, out);
      const local = (0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]) * shading.reference;
      const excess = (luma - local) / Math.max(24, local);
      gloss[i] = excess > 0.04 ? Math.min(1, excess) : 0;
    }
  }
  return gloss;
}
