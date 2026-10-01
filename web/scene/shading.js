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
 * On sépare donc trois choses :
 *
 *   basse fréquence   la lumière de la pièce — soleil, dégradé vers le fond,
 *                     grande ombre d'un meuble. En LUMINANCE seulement (voir
 *                     ci-dessous). C'est ce qui ancre le parquet dans la scène.
 *
 *   résidu clair      ce qui, à pleine résolution, est nettement plus clair que
 *                     l'éclairement local, puis **flouté** : un reflet de
 *                     fenêtre est large, une veine claire est fine et ne
 *                     survit pas au flou. Dosé selon la finition, jamais nul.
 *
 *   résidu sombre     ce qui est nettement plus sombre que l'éclairement local
 *                     ET plus large qu'un joint : l'ombre sous une chaise, le
 *                     pied d'un radiateur, le contact mur/sol. Une ouverture
 *                     morphologique retire les lignes fines (joints, veines
 *                     sombres) et garde les taches ; un seuil d'amplitude
 *                     écarte les simples différences de teinte entre lames.
 *
 * ## Luminance, pas couleur — LOT PHOTO.2
 *
 * La version précédente reportait la lumière **en couleur** : un gain par
 * canal, rapport de la couleur locale floutée à la couleur moyenne du sol.
 * L'intention était bonne (le soleil est chaud, l'ombre est bleutée) ; le
 * résultat ne l'était pas. Sur un sol d'origine coloré — un chêne brun — les
 * zones sombres ont des canaux rouge et bleu qui ne décroissent pas à la même
 * vitesse, et le rapport à la moyenne devient un virage de teinte : −40 % de
 * rouge, −17 % de bleu. Appliqué à un chêne miel, cela donne un parquet VERT
 * OLIVE. La revue l'a mesuré sur une petite pièce entière.
 *
 * Ce virage n'est pas la couleur de la lumière : c'est la couleur de l'ancien
 * revêtement, que rien ne permet de séparer de celle de la lumière sans
 * connaître l'albédo de ce qu'on remplace. On ne le connaît pas. Le gain est
 * donc une luminance, identique sur les trois canaux, et la couleur du parquet
 * vient du parquet. Reste une dominante GLOBALE de lumière — une seule couleur
 * pour toute la scène, lue sur les zones claires du sol, bornée à ±8 % par
 * canal — qui dit « cette pièce est chaude » sans redessiner l'ancien sol.
 *
 * Tout est calculé sur une image réduite (la lumière d'une pièce n'a pas besoin
 * de 1600 px) et **normalisé par le masque du sol** : sans quoi un mur clair
 * contaminerait la première rangée de lames.
 */

/** Côté maximal de la carte : au-delà, on décrit du détail, plus de la lumière. */
const MAP_MAX = 460;
/** Dominante de lumière globale : jamais plus de ±8 % par canal. */
const LIGHT_TINT_MAX = 0.08;
/** Résidu clair : au-dessus de cet excès relatif, un pixel est un reflet. */
const GLOSS_THRESHOLD = 0.06;
/** Résidu sombre : en dessous de ce déficit relatif, ce n'est qu'une lame plus
 *  foncée que sa voisine, pas une ombre. Mesuré : les lames d'un même parquet
 *  s'écartent de 5 à 15 % de leur moyenne locale, une ombre de meuble de 25 à
 *  60 %. */
const SHADOW_THRESHOLD = 0.18;

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
 * Filtre séparable par boîte sur une carte à un canal, en place logique.
 * `op` = 'blur' | 'min' | 'max'. Sert au flou des résidus et à l'ouverture
 * morphologique (min puis max) qui retire les lignes fines.
 */
function filterChannel(src, width, height, radius, op) {
  const out = new Float32Array(src.length);
  const tmp = new Float32Array(src.length);
  const pass = (from, to, count, stride, lanes, laneStride) => {
    for (let lane = 0; lane < lanes; lane += 1) {
      const base = lane * laneStride;
      for (let i = 0; i < count; i += 1) {
        let acc = op === 'min' ? Infinity : op === 'max' ? -Infinity : 0;
        for (let k = -radius; k <= radius; k += 1) {
          const j = Math.min(count - 1, Math.max(0, i + k));
          const v = from[base + j * stride];
          if (op === 'min') acc = v < acc ? v : acc;
          else if (op === 'max') acc = v > acc ? v : acc;
          else acc += v;
        }
        to[base + i * stride] = op === 'blur' ? acc / (radius * 2 + 1) : acc;
      }
    }
  };
  pass(src, tmp, width, 1, height, width);
  pass(tmp, out, height, width, width, 1);
  return out;
}

/**
 * Carte d'éclairement d'une scène.
 *
 * @param {ImageData} source            photo d'origine
 * @param {Uint8ClampedArray} coverage  couverture du sol, taille image
 * @param {object} light                scene.light
 * @returns {{width:number,height:number,rgba:Float32Array,reference:number,
 *            lightTint:number[], sample:(x,y,out)=>Float32Array, luminance:(x,y)=>number}}
 *
 * `rgba` contient, par pixel de la carte réduite :
 *   0,1,2 → gain de LUMINANCE, le même dans les trois canaux (1 = éclairement
 *           moyen du sol). Trois canaux pour garder le format de texture et
 *           le contrat de `sample()` ; la couleur n'y est plus.
 *   3     → ombre de contact (1 = pleine pièce, < 1 le long des bords)
 *
 * `lightTint` est la dominante globale de la lumière, un triplet autour de 1
 * de luminance unitaire, borné à ±LIGHT_TINT_MAX.
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

  /* ---- Assemblage : un gain de luminance, pas une recoloration ---- */

  const rgba = new Float32Array(count * 4);
  const gains = new Float32Array(count);
  for (let i = 0; i < count; i += 1) {
    const p = i * 4;
    const known = blurred.weight[i] > 1e-4;
    let gain = 1;
    if (known) {
      const w = blurred.weight[i];
      const lum =
        (0.2126 * blurred.channels[0][i] + 0.7152 * blurred.channels[1][i] + 0.0722 * blurred.channels[2][i]) / w;
      gain = lum / reference;
    }
    // Les trous (aucun pixel de sol alentour) reçoivent un éclairement
    // neutre : au pire, le parquet y garde sa couleur propre.
    gains[i] = known ? gain : 0;
    rgba[p] = gain;
    rgba[p + 1] = gain;
    rgba[p + 2] = gain;
    // `contact` vaut 1 en pleine zone et décroît vers les bords ; on ne garde
    // que l'assombrissement, dosé par la scène.
    rgba[p + 3] = 1 - light.contact * (1 - Math.min(1, contact[i]));
  }

  /* ---- Dominante globale de la lumière ----
     La couleur des zones les plus éclairées du sol, rapportée à la couleur
     moyenne du sol : si le quart le plus clair est plus chaud que l'ensemble,
     la lumière est chaude. Une seule valeur pour la scène, bornée, et de
     luminance unitaire pour ne pas doubler le gain. */
  const lightTint = [1, 1, 1];
  {
    const connus = [];
    for (let i = 0; i < count; i += 1) if (gains[i] > 0) connus.push(i);
    if (connus.length >= 16) {
      connus.sort((a, b) => gains[b] - gains[a]);
      const quart = connus.slice(0, Math.max(4, Math.floor(connus.length / 4)));
      const clair = [0, 0, 0];
      let masse = 0;
      quart.forEach((i) => {
        for (let c = 0; c < 3; c += 1) clair[c] += blurred.channels[c][i];
        masse += blurred.weight[i];
      });
      if (masse > 0) {
        const ratio = clair.map((v, c) => v / masse / refRgb[c]);
        const lumRatio = 0.2126 * ratio[0] + 0.7152 * ratio[1] + 0.0722 * ratio[2];
        for (let c = 0; c < 3; c += 1) {
          const t = lumRatio > 0 ? ratio[c] / lumRatio : 1;
          lightTint[c] = Math.min(1 + LIGHT_TINT_MAX, Math.max(1 - LIGHT_TINT_MAX, t));
        }
      }
    }
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
    lightTint,
    sample,
    /** Éclairement en luminance seule : sert au repérage de la direction. */
    luminance(x, y) {
      sample(x, y, scratch);
      return 0.2126 * scratch[0] + 0.7152 * scratch[1] + 0.0722 * scratch[2];
    },
  };
}

/**
 * Résidus de la photo à pleine résolution : reflets et ombres de contact.
 *
 * Pour chaque pixel de sol, l'écart relatif entre sa luminance et
 * l'éclairement basse fréquence local. Deux cartes en sortent :
 *
 *   gloss    l'excès clair au-delà de GLOSS_THRESHOLD, **flouté** sur ~0,5 %
 *            de la largeur. Un reflet de fenêtre ou une traînée de soleil sur
 *            un sol verni sont larges et passent ; une veine claire ou un joint
 *            clair font deux pixels, le flou les dilue sous le seuil de
 *            visibilité. Appliqué à TOUTES les finitions depuis le LOT
 *            PHOTO.2, dosé par la brillance : une finition mate garde un
 *            quart de l'éclat (la lumière de la fenêtre touche encore le sol),
 *            une finition vernie presque tout.
 *
 *   shadow   le déficit sombre au-delà de SHADOW_THRESHOLD, passé par une
 *            **ouverture morphologique** (minimum puis maximum sur ~0,4 % de la
 *            largeur). Une ligne plus fine que le noyau disparaît : joints,
 *            veines sombres, rainures de l'ancien sol. Une tache plus large
 *            reste : l'ombre sous une chaise, le pied d'un radiateur, le bas
 *            d'un mur. Le seuil d'amplitude écarte en amont les simples
 *            différences de teinte entre lames voisines.
 *
 * Ni l'une ni l'autre ne réinjecte le motif de l'ancien revêtement : c'est la
 * condition, et elle se vérifie sur un sol à lames sans meuble, où la carte
 * d'ombre doit rester presque vide.
 */
export function buildResidualMaps(source, coverage, shading) {
  /* Demi-résolution : les deux cartes sont floutées ou ouvertes sur plusieurs
     pixels, elles ne portent aucun détail fin. Mesuré à 1600 × 1067 : 1,5 s
     à pleine résolution sur le fil principal, à chaque ouverture de scène —
     environ huit fois moins ici. */
  const fullW = source.width;
  const fullH = source.height;
  const k = fullW * fullH > 600000 ? 2 : 1;
  const width = Math.ceil(fullW / k);
  const height = Math.ceil(fullH / k);
  const src = source.data;
  const gloss = new Float32Array(width * height);
  const shadow = new Float32Array(width * height);
  const sol = new Uint8Array(width * height);
  const out = new Float32Array(4);
  for (let y = 0; y < height; y += 1) {
    const sy = Math.min(fullH - 1, y * k);
    for (let x = 0; x < width; x += 1) {
      const sx = Math.min(fullW - 1, x * k);
      const j = sy * fullW + sx;
      if (coverage[j] <= 2) continue;
      const i = y * width + x;
      sol[i] = 1;
      const p = j * 4;
      const luma = 0.2126 * src[p] + 0.7152 * src[p + 1] + 0.0722 * src[p + 2];
      shading.sample(sx, sy, out);
      const local = (0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]) * shading.reference;
      const ecart = (luma - local) / Math.max(24, local);
      if (ecart > GLOSS_THRESHOLD) gloss[i] = Math.min(1, ecart - GLOSS_THRESHOLD);
      else if (-ecart > SHADOW_THRESHOLD) shadow[i] = Math.min(1, (-ecart - SHADOW_THRESHOLD) / 0.45);
    }
  }
  const rGloss = Math.max(1, Math.round((fullW * 0.005) / k));
  const glossFlou = filterChannel(gloss, width, height, rGloss, 'blur');
  // Après le flou, ce qui reste sous 0,02 est le fantôme d'une veine : zéro.
  for (let i = 0; i < glossFlou.length; i += 1) glossFlou[i] = glossFlou[i] < 0.02 ? 0 : glossFlou[i];

  const rOuv = Math.max(2, Math.round((fullW * 0.004) / k));
  const ouvert = filterChannel(filterChannel(shadow, width, height, rOuv, 'min'), width, height, rOuv, 'max');
  const shadowDoux = filterChannel(ouvert, width, height, Math.max(1, Math.round(rOuv / 2)), 'blur');
  // Hors du sol, aucune ombre : la carte ne doit pas déborder sur un mur.
  for (let i = 0; i < shadowDoux.length; i += 1) if (!sol[i]) shadowDoux[i] = 0;

  /* Le moteur Canvas lit les cartes au pixel de l'image : il reçoit une
     version agrandie, fabriquée seulement s'il la demande. */
  let pleine = null;
  const fullRes = () => {
    if (pleine) return pleine;
    if (k === 1) { pleine = { gloss: glossFlou, shadow: shadowDoux }; return pleine; }
    const g = new Float32Array(fullW * fullH);
    const o = new Float32Array(fullW * fullH);
    for (let y = 0; y < fullH; y += 1) {
      const ry = Math.min(height - 1, (y / k) | 0) * width;
      const row = y * fullW;
      for (let x = 0; x < fullW; x += 1) {
        const i = ry + Math.min(width - 1, (x / k) | 0);
        g[row + x] = glossFlou[i];
        o[row + x] = shadowDoux[i];
      }
    }
    pleine = { gloss: g, shadow: o };
    return pleine;
  };

  return { gloss: glossFlou, shadow: shadowDoux, width, height, fullRes };
}

/**
 * Compatibilité : la carte de reflets seule. Les appelants nouveaux lisent
 * `buildResidualMaps`, qui rend aussi les ombres de contact.
 */
export function buildGlossMap(source, coverage, shading) {
  return buildResidualMaps(source, coverage, shading).fullRes().gloss;
}


/**
 * Luminance moyenne d'une tuile de bois, 0 a 1. Memoisee sur les cartes.
 *
 * Sert a l'ancrage d'exposition : pour savoir de combien deplacer le rendu
 * vers la lumiere de la piece, il faut d'abord savoir ou la matiere se situe
 * d'elle-meme. Calcule sur les octets reels de la tuile, pas sur la couleur
 * declaree du catalogue : le veinage, les joints et le degrade de lame
 * assombrissent sensiblement une lame par rapport a son `base`.
 *
 * Le cout est celui d'un parcours de 1024x1024 pixels, une fois par materiau
 * et par motif, a cote des 0,8 a 3 secondes que coute la tuile elle-meme.
 */
export function albedoMeanLuma(maps) {
  if (typeof maps.albedoMean === 'number') return maps.albedoMean;
  const { data } = maps.albedo[0];
  let somme = 0;
  for (let i = 0; i < data.length; i += 4) {
    somme += 0.2126 * data[i] + 0.7152 * data[i + 1] + 0.0722 * data[i + 2];
  }
  maps.albedoMean = somme / (data.length / 4) / 255;
  return maps.albedoMean;
}

/**
 * Facteur d'exposition : de combien le rendu doit se rapprocher du niveau
 * lumineux reel du sol photographie.
 *
 * `shading.reference` est la luminance moyenne du sol d'origine — la seule
 * mesure de la piece que nous ayons, et elle est deja calculee. Le rapport
 * `piece / matiere` vaut 1 quand le parquet choisi a par chance la clarte de
 * ce qu'il remplace, moins de 1 quand il est plus clair que la piece.
 *
 * Les bornes ne sont pas decoratives : sans plancher, un chene blanchi pose
 * dans un couloir sombre deviendrait gris souris et ne serait plus le produit
 * qu'on a clique. Le plafond evite symetriquement qu'un bois fonce pose sur un
 * carrelage blanc parte en surexposition.
 */
export function exposureScale(shading, albedoMean, exposure) {
  if (!(exposure > 0) || !(albedoMean > 0.02)) return 1;
  const piece = shading.reference / 255;
  const vise = piece / albedoMean;
  return Math.min(1.25, Math.max(0.6, 1 + exposure * (vise - 1)));
}
