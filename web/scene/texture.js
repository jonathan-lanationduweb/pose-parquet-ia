/**
 * Albedo du bois : la tuile de parquet, dessinée.
 *
 * Une référence de parquet n'est pas « une teinte » : c'est un matériau
 * complet, décrit dans data/parquets.json. Chaque entrée pilote son propre
 * veinage, ses nœuds, ses fentes, son contraste, sa largeur de lame et sa
 * finition — deux parquets ne sont donc jamais la même image recolorée.
 *
 * La tuile produite est répétable (raccord invisible) et **mesurée en mètres
 * de sol** : c'est ce qui permet au moteur de la projeter comme une surface
 * réelle, où une lame de 18 cm mesure 18 cm au premier plan comme au fond.
 *
 * Elle tient le rôle de carte d'albedo. Voir js/scene/material.js pour le
 * relief et la rugosité qui en sont dérivés, et pour la place réservée à de
 * vraies cartes photographiques.
 */
import { seeded } from '../utils/dom.js';

export const TILE = 1280;
/**
 * Côté de la tuile, en mètres de sol.
 *
 * 4,80 m et non 2,40 : c'est ce qui permet à la tuile de contenir **plusieurs
 * longueurs de lame** — trois lames de 1,60 m par rangée, vingt-cinq rangées
 * décalées. Avec une tuile de 2,40 m, une lame de 1,80 m était étirée à la
 * taille de la tuile faute de place : les joints de bout s'alignaient tous les
 * 2,40 m en une grille parfaite et le sol prenait l'aspect de grandes dalles.
 * C'était l'un des défauts les plus visibles de l'ancien rendu.
 *
 * 1280 px pour 4,80 m, soit 3,75 mm par pixel de texture : l'ordre de grandeur
 * d'un pixel d'image au premier plan d'une photo d'intérieur.
 */
export const TILE_METERS = 4.8;

/**
 * Profil d'un motif : largeur de lame, longueur, et angle pour les motifs en
 * chevron.
 *
 * Une seule largeur de lame pour les trois motifs n'a pas de sens. On ne pose
 * pas un point de Hongrie ni un bâton rompu avec des lames de 18 ou 22 cm : la
 * pose traditionnelle emploie des éléments bien plus étroits, de l'ordre de
 * 9 cm, et c'est cette finesse qui fait le motif. Utiliser la largeur des lames
 * droites produisait des chevrons de 60 cm — géométriquement corrects, mais ce
 * n'était plus ce motif-là.
 *
 * **L'angle du point de Hongrie n'est pas figé à 45°.** C'est le plus répandu,
 * mais 30° et 60° existent et changent nettement le rendu : la pointe s'allonge
 * ou s'écrase. L'angle est donc un paramètre du motif, pas une constante du
 * moteur.
 *
 * Un matériau peut décrire ses propres profils dans data/parquets.json
 * (`patternProfiles`) ; sinon on dérive des valeurs par défaut raisonnables de
 * ses dimensions de lame droite.
 */
export const DEFAULT_PROFILES = {
  lames: { width: null, length: null },
  'point-de-hongrie': { width: 0.09, length: 0.6, angleDeg: 45 },
  'baton-rompu': { width: 0.09, length: 0.45 },
};

export function patternProfile(material, pattern, widthOverride) {
  const declared = (material.patternProfiles && material.patternProfiles[pattern]) || {};
  const fallback = DEFAULT_PROFILES[pattern] || DEFAULT_PROFILES.lames;
  const width =
    widthOverride ||
    declared.width ||
    (pattern === 'lames' ? material.boardWidth : Math.min(material.boardWidth, fallback.width));
  const length =
    declared.length ||
    (pattern === 'lames' ? material.boardLength || width * 9 : fallback.length || width * 5);
  return {
    width,
    length,
    angleDeg: declared.angleDeg || fallback.angleDeg || 45,
  };
}

const clampByte = (v) => Math.max(0, Math.min(255, Math.round(v)));

/**
 * Un canevas 2D, sur le fil principal comme dans un Web Worker.
 *
 * Le dessin d'une tuile est le même partout ; ce qui change, c'est la surface
 * sur laquelle on dessine. `document` n'existe pas dans un worker, et
 * `OffscreenCanvas` expose le même contexte 2D. La détection est faite à
 * l'appel, pas à l'import : ce module est chargé dans les deux mondes.
 */
function creerCanvas(largeur, hauteur) {
  if (typeof document !== 'undefined') {
    const c = document.createElement('canvas');
    c.width = largeur;
    c.height = hauteur;
    return c;
  }
  return new OffscreenCanvas(largeur, hauteur);
}
/**
 * Couleurs opaques, mémoïsées.
 *
 * Un veinage, c'est 34 000 traits en pose droite et 74 000 en point de
 * Hongrie, chacun d'une teinte légèrement différente. Écrire
 * `rgba(r,g,b,a)` et le donner à `strokeStyle` oblige le navigateur à
 * analyser une couleur CSS à chaque trait.
 *
 * Ce que ça coûte, mesuré : 100 ms pour 34 000 affectations en chaîne contre
 * 42 ms mémoïsées — 59 ms gagnées par tuile en pose droite, environ 130 en
 * point de Hongrie. C'est réel et c'est petit : 4 à 7 % du temps de la tuile.
 * Un premier micro-banc annonçait 886 ms, en comparant deux boucles qui ne
 * traçaient pas la même chose ; la mesure en situation l'a démenti. Le gros du
 * temps est dans le tracé lui-même, pas dans la couleur — voir le rapport de
 * profilage. Ce qui est gardé ici l'est parce que c'est gratuit et prouvé
 * identique, pas parce que ça règle le problème.
 *
 * L'alpha passe donc par `globalAlpha` et la couleur reste opaque. Comme
 * `globalAlpha` multiplie l'alpha de la source, le résultat composité est
 * exactement le même ; et comme les composantes ne prennent qu'une poignée de
 * valeurs — deux accents décalés d'un petit entier — la chaîne est réutilisée
 * au lieu d'être reconstruite. Vérifié : les neuf tuiles de contrôle gardent
 * la même empreinte au pixel après ce changement.
 */
const opaques = new Map();
const opaque = (r, g, b) => {
  const r8 = clampByte(r);
  const g8 = clampByte(g);
  const b8 = clampByte(b);
  const cle = (r8 << 16) | (g8 << 8) | b8;
  let v = opaques.get(cle);
  if (v === undefined) {
    v = `rgb(${r8},${g8},${b8})`;
    opaques.set(cle, v);
  }
  return v;
};

const rgb = (c, shift = 0, warm = 0) =>
  `rgb(${clampByte(c[0] + shift + warm)},${clampByte(c[1] + shift)},${clampByte(c[2] + shift - warm)})`;

/** Divise TILE en un nombre entier de pas proche de la valeur souhaitée. */
const fit = (target) => TILE / Math.max(1, Math.round(TILE / target));

/** Somme des caractères : deux matériaux différents tirent des veinages différents. */
const seedOf = (id) => {
  let n = 17;
  for (let i = 0; i < id.length; i += 1) n = (n * 31 + id.charCodeAt(i)) % 100003;
  return n;
};

/* ------------------------------------------------------------------ */
/* Éléments de bois                                                    */
/* ------------------------------------------------------------------ */

/** Trace une strie dans la longueur de la lame, avec une légère ondulation. */
function streak(ctx, x, y, w, h, horizontal, t, wobble, random) {
  const long = horizontal ? w : h;
  const across = horizontal ? h : w;
  const a = across * t;
  const w1 = across * wobble * (random() - 0.5);
  const w2 = across * wobble * (random() - 0.5);
  ctx.beginPath();
  if (horizontal) {
    ctx.moveTo(x - 4, y + a);
    ctx.bezierCurveTo(x + long * 0.28, y + a + w1, x + long * 0.66, y + a + w2, x + long + 4, y + a);
  } else {
    ctx.moveTo(x + a, y - 4);
    ctx.bezierCurveTo(x + a + w1, y + long * 0.28, x + a + w2, y + long * 0.66, x + a, y + long + 4);
  }
  ctx.stroke();
}

/**
 * Les deux accents d'un veinage : un plus sombre que le fond, un plus clair.
 *
 * `tex.grain` est toujours plus sombre que `tex.base`. Sur un chêne clair ça
 * suffit ; sur un chêne fumé, un accent sombre posé sur un fond déjà sombre ne
 * se voit pas, et la lame redevient un aplat — c'est exactement ce qui faisait
 * lire les teintes foncées comme « éteintes ».
 *
 * D'où un second accent, plus clair que le fond, dont la part augmente quand le
 * bois s'assombrit. Comme les deux accents se répartissent de part et d'autre
 * du fond, la teinte moyenne de la lame ne bouge pas : on gagne du
 * microcontraste sans éclaircir le matériau.
 */
function accents(tex) {
  const lum = (0.2126 * tex.base[0] + 0.7152 * tex.base[1] + 0.0722 * tex.base[2]) / 255;
  const partClaire = Math.min(0.68, Math.max(0.16, 0.84 - lum * 0.94));
  const ecart = 58 - lum * 30;
  /**
   * L'accent clair est un **gain**, pas une somme.
   *
   * Ajouter la même quantité aux trois canaux rapproche la couleur du gris :
   * mesuré sur les dix chênes du catalogue, l'accent additif perdait de 0,05 à
   * 0,09 de saturation et décalait la teinte de 2 à 5,6° sur les teintes
   * foncées — d'où les traînées grisâtres visibles sur le Fumé, là où un chêne
   * fumé n'a que des fibres plus claires ET toujours brunes. Sur le Craie,
   * l'écrêtage du bleu poussait même la teinte de +17°.
   *
   * Multiplier conserve les rapports entre canaux, donc la teinte et la
   * saturation exactement. Le gain est calé sur la luminance que visait la
   * version additive : à microcontraste égal (dLum identique sur les huit
   * teintes non écrêtées), on ne perd rien de ce que la passe précédente avait
   * gagné.
   *
   * Le plafond est le seul compromis : sur un chêne presque blanc le gain bute
   * sur 255 et l'accent devient plus discret qu'avant. C'est le bon sens
   * physique — une fibre éclairée sur un bois déjà crème ne peut pas être
   * beaucoup plus claire — alors que l'ancienne amplitude n'était atteinte
   * qu'en écrêtant vers un blanc bleuté.
   */
  const viseeLum = (0.2126 * (tex.base[0] + ecart)
    + 0.7152 * (tex.base[1] + ecart * 0.95)
    + 0.0722 * (tex.base[2] + ecart * 0.8)) / 255;
  const gain = Math.min(viseeLum / Math.max(lum, 0.02), 255 / Math.max(tex.base[0], tex.base[1], tex.base[2], 1));
  return {
    deep: tex.grain,
    lift: [clampByte(tex.base[0] * gain), clampByte(tex.base[1] * gain), clampByte(tex.base[2] * gain)],
    partClaire,
    // Un bois foncé demande un peu plus d'amplitude pour donner autant à voir.
    vigueur: 1 + (1 - lum) * 0.55,
  };
}

/**
 * Figure en cathédrale : les arcs emboîtés d'un débit sur dosse.
 *
 * C'est le dessin le plus reconnaissable d'un chêne, et il ne s'obtient pas
 * avec des stries longitudinales. Quand la lame est sciée à travers les
 * cernes, ceux-ci affleurent en arcs emboîtés, en ogive, qui se resserrent
 * vers l'axe de la lame. Sans eux, on peut empiler autant de stries qu'on veut
 * dans la longueur : la surface garde l'aspect régulier d'un placage.
 *
 * Une cathédrale = quelques arcs concentriques, tracés en courbes quadratiques
 * dans le repère de la lame, de plus en plus étroits et de plus en plus
 * marqués vers le centre.
 */
function cathedral(ctx, x, y, w, h, horizontal, random, poseEncre, tex, vigueur) {
  const long = horizontal ? w : h;
  const across = horizontal ? h : w;
  // Une à trois cathédrales par lame, jamais alignées d'une lame à l'autre.
  const combien = 1 + Math.round(random() * 1.6);
  for (let k = 0; k < combien; k += 1) {
    const centre = long * (0.12 + random() * 0.76);
    const cote = random() < 0.5 ? 0.34 : 0.66;   // vers un bord ou l'autre
    const base = across * cote;
    const sens = cote < 0.5 ? 1 : -1;
    const arcs = 3 + Math.round(random() * 3);
    const etendue = long * (0.1 + random() * 0.16);
    for (let a = 0; a < arcs; a += 1) {
      const t = (a + 1) / (arcs + 1);
      const demi = etendue * (1 - t * 0.62);
      const fleche = across * (0.1 + 0.3 * t) * sens;
      // Largeur et contraste calés sur le bois réel : une cathédrale de chêne
      // est une bande d'un à deux centimètres, pas un cheveu. Un arc d'un
      // pixel à 6 % d'opacité, comme au premier essai, ne survit pas à la
      // réduction — le sol reprend aussitôt son aspect de placage strié.
      poseEncre(tex.grainAlpha * vigueur * (0.7 + t * 1.1), 12);
      ctx.lineWidth = Math.max(1.2, across * (0.05 + 0.09 * t));
      ctx.beginPath();
      if (horizontal) {
        ctx.moveTo(x + centre - demi, y + base);
        ctx.quadraticCurveTo(x + centre, y + base + fleche, x + centre + demi, y + base);
      } else {
        ctx.moveTo(x + base, y + centre - demi);
        ctx.quadraticCurveTo(x + base + fleche, y + centre, x + base, y + centre + demi);
      }
      ctx.stroke();
    }
  }
}

/**
 * Veinage : figure large, cathédrales, fibre de fond, cernes marqués, nœuds.
 *
 * Le fond fibreux compte autant que les cernes. Une dizaine de traits nets
 * donne le *dessin* d'un bois ; c'est la densité de stries très pâles qui en
 * donne la *matière*. Sans elle, chaque lame reste un aplat dégradé — et une
 * fois projetée au sol, la surface se lit comme une image plaquée.
 */
function grain(ctx, x, y, w, h, tex, random) {
  const long = Math.max(w, h);
  const across = Math.min(w, h);
  const horizontal = w >= h;
  const acc = accents(tex);
  // Vigueur propre à la lame : deux planches du même lot n'ont pas le même
  // dessin. Faire varier la *force* du veinage, et pas seulement la teinte,
  // distingue les lames sans créer le patchwork d'un décalage de couleur.
  const vigueurLame = acc.vigueur * (0.72 + random() * 0.62);
  /**
   * Pose l'accent — sombre ou clair — comme style de trait courant.
   *
   * Ne rend plus une chaîne `rgba()` : voir `opaque()`. L'alpha est
   * arrondi à trois décimales comme le faisait `toFixed(3)`, pour que le
   * résultat reste identique au pixel, et borné à [0, 1] parce que CSS
   * bornait la chaîne alors qu'une affectation hors bornes de
   * `globalAlpha` serait ignorée.
   */
  const poseEncre = (alpha, ecartTeinte) => {
    const c = random() < acc.partClaire ? acc.lift : acc.deep;
    const t = Math.round((random() - 0.5) * ecartTeinte);
    ctx.strokeStyle = opaque(c[0] + t, c[1] + t, c[2] + t);
    ctx.globalAlpha = Math.min(1, Math.max(0, Math.round(alpha * 1000) / 1000));
  };

  ctx.save();
  ctx.beginPath();
  ctx.rect(x, y, w, h);
  ctx.clip();

  // 1. Figure : quelques bandes larges et floues. C’est l’échelle qui manque
  //    le plus à un veinage synthétique — un chêne montre des zones sombres
  //    de plusieurs centimètres, pas seulement des cheveux d’un pixel, et ce
  //    sont elles qui survivent à la réduction quand la lame s’éloigne.
  const bandes = 2 + Math.round(random() * 2);
  for (let i = 0; i < bandes; i += 1) {
    poseEncre(tex.grainAlpha * vigueurLame * (0.5 + random() * 0.5), 10);
    ctx.lineWidth = across * (0.14 + random() * 0.2);
    streak(ctx, x, y, w, h, horizontal, 0.1 + random() * 0.8, 0.3, random);
  }

  // 2. Cathédrales : le dessin propre au chêne débité sur dosse. Posées avant
  //    la fibre, pour que celle-ci les traverse comme sur une planche réelle.
  cathedral(ctx, x, y, w, h, horizontal, random, poseEncre, tex, vigueurLame);

  // 3. Fibre de fond : une strie tous les pixels environ, presque invisible
  //    une à une. C'est ce qui casse l'aplat.
  const fibres = Math.max(26, Math.round(across * 1.15));
  for (let i = 0; i < fibres; i += 1) {
    poseEncre(tex.grainAlpha * vigueurLame * 0.62 * (0.3 + random()), 11);
    ctx.lineWidth = Math.max(0.5, across * 0.0065 * (0.6 + random()));
    streak(ctx, x, y, w, h, horizontal, 0.015 + random() * 0.97, 0.05, random);
  }

  // 4. Cernes marqués : le dessin propre au matériau, peu nombreux.
  //    La puissance 0,45 rend la distribution inégale — quelques traits francs
  //    et beaucoup de faibles, comme sur une planche réelle. Des cernes tous
  //    de la même force donnent une rayure régulière, donc une fausse texture.
  const lines = Math.max(2, Math.round(tex.grainLines * (0.7 + random() * 0.6)));
  for (let i = 0; i < lines; i += 1) {
    poseEncre(tex.grainAlpha * vigueurLame * (0.3 + Math.pow(random(), 0.45) * 0.95), 16);
    ctx.lineWidth = Math.max(0.6, across * tex.grainWidth * (0.5 + random()));
    streak(ctx, x, y, w, h, horizontal, 0.05 + random() * 0.9, 0.14, random);
  }

  // Les boucles ci-dessus ont réglé globalAlpha ; tout ce qui suit donne son
  // alpha dans la couleur, comme avant. Le save/restore de la lame le
  // rétablirait de toute façon, mais pas avant la fin de cette fonction.
  ctx.globalAlpha = 1;

  // Nœuds : cercles sombres cernés d'un halo, fréquence propre au matériau
  if (random() < tex.knots) {
    const kx = x + w * (0.15 + random() * 0.7);
    const ky = y + h * (0.2 + random() * 0.6);
    // Discrets : un nœud trop marqué se lit comme une tache posée sur la lame,
    // et se répète visiblement d'une tuile à l'autre.
    const kr = across * tex.knotSize * (0.58 + random() * 0.6);
    const halo = ctx.createRadialGradient(kx, ky, kr * 0.2, kx, ky, kr * 2.4);
    halo.addColorStop(0, `rgba(${tex.grain[0]},${tex.grain[1]},${tex.grain[2]},0.3)`);
    halo.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = halo;
    ctx.beginPath();
    ctx.arc(kx, ky, kr * 2.4, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = `rgba(${clampByte(tex.grain[0] - 26)},${clampByte(tex.grain[1] - 24)},${clampByte(
      tex.grain[2] - 20
    )},0.5)`;
    ctx.beginPath();
    ctx.ellipse(kx, ky, kr, kr * 0.72, random() * Math.PI, 0, Math.PI * 2);
    ctx.fill();
  }

  // Fentes et gerces : la signature des bois rustiques
  if (tex.cracks && random() < tex.cracks) {
    const cx = x + w * (0.1 + random() * 0.8);
    const cy = y + h * (0.15 + random() * 0.7);
    const len = long * (0.08 + random() * 0.22);
    ctx.strokeStyle = `rgba(${clampByte(tex.grain[0] - 40)},${clampByte(tex.grain[1] - 38)},${clampByte(
      tex.grain[2] - 34
    )},0.5)`;
    ctx.lineWidth = Math.max(0.6, across * 0.012);
    ctx.beginPath();
    if (horizontal) {
      ctx.moveTo(cx, cy);
      ctx.lineTo(cx + len, cy + across * 0.04 * (random() - 0.5));
    } else {
      ctx.moveTo(cx, cy);
      ctx.lineTo(cx + across * 0.04 * (random() - 0.5), cy + len);
    }
    ctx.stroke();
  }

  ctx.restore();
}

/**
 * Une lame : teinte propre, dégradé longitudinal, veinage, chanfrein, joints.
 *
 * Deux réglages comptent plus que les autres pour l'aspect final :
 *
 * - la **dispersion de teinte** entre lames voisines. Trop forte, le sol se
 *   lit en patchwork : on voit des cases claires et sombres avant de voir un
 *   parquet. Un vrai lot de pose est bien plus homogène que ça.
 * - la **différence entre joint latéral et joint de bout**. Les traiter à
 *   égalité dessine une grille régulière, et c'est le défaut qui trahit le
 *   plus sûrement une texture synthétique : sur un parquet posé, les joints
 *   de bout se remarquent à peine.
 */
function board(ctx, x, y, w, h, tex, random) {
  const horizontal = w >= h;

  // Dispersion de teinte proportionnée à la taille de l'élément.
  //
  // Une lame de 1,80 m peut varier franchement d'une voisine : c'est ce qu'on
  // voit sur un vrai lot, et sans cette variation le sol se lit comme un
  // placage. Un tasseau de bâton rompu de 45 cm, non : à cette taille la même
  // amplitude donne une mosaïque de cases claires et sombres. On indexe donc
  // l'amplitude sur la longueur de l'élément plutôt que d'imposer un compromis
  // unique qui trahit l'un ou l'autre.
  const varLame = Math.min(1.5, 0.6 + (Math.max(w, h) / TILE) * 4);
  const shift = Math.round((random() - 0.5) * tex.spread * varLame);
  const warm = Math.round((random() - 0.5) * tex.warm * varLame);

  ctx.save();
  const gradient = horizontal
    ? ctx.createLinearGradient(x, y, x + w, y)
    : ctx.createLinearGradient(x, y, x, y + h);
  const amp = 5 * tex.contrast;
  gradient.addColorStop(0, rgb(tex.base, shift - amp, warm));
  gradient.addColorStop(0.45, rgb(tex.base, shift + amp * 0.55, warm));
  gradient.addColorStop(1, rgb(tex.base, shift - amp * 0.7, warm));
  ctx.fillStyle = gradient;
  ctx.fillRect(x, y, w, h);

  grain(ctx, x, y, w, h, tex, random);

  // Reflet de finition : léger, dans la longueur de la lame
  if (tex.sheen > 0.01) {
    const sheen = horizontal
      ? ctx.createLinearGradient(x, y, x, y + h)
      : ctx.createLinearGradient(x, y, x + w, y);
    sheen.addColorStop(0, `rgba(255,255,255,${(tex.sheen * 0.9).toFixed(3)})`);
    sheen.addColorStop(0.5, 'rgba(255,255,255,0)');
    sheen.addColorStop(1, `rgba(0,0,0,${(tex.sheen * 0.35).toFixed(3)})`);
    ctx.fillStyle = sheen;
    ctx.fillRect(x, y, w, h);
  }

  // Chanfrein : seulement sur les longs côtés, là où il existe vraiment
  const bevel = Math.max(0.7, Math.min(w, h) * tex.bevel);
  ctx.fillStyle = 'rgba(255,255,255,0.05)';
  if (horizontal) ctx.fillRect(x, y, w, bevel);
  else ctx.fillRect(x, y, bevel, h);
  ctx.fillStyle = 'rgba(34,23,14,0.17)';
  if (horizontal) ctx.fillRect(x, y + h - bevel, w, bevel);
  else ctx.fillRect(x + w - bevel, y, bevel, h);

  // Joints : les longs côtés se voient, les joints de bout beaucoup moins.
  // Le facteur 0,6 vient de la comparaison avec les photos : un joint de
  // parquet posé est une ombre fine, pas un trait dessiné.
  const lw = Math.max(0.7, Math.min(w, h) * 0.016);
  ctx.lineWidth = lw;
  const longSides = () => {
    ctx.beginPath();
    if (horizontal) {
      ctx.moveTo(x, y + 0.4); ctx.lineTo(x + w, y + 0.4);
      ctx.moveTo(x, y + h - 0.4); ctx.lineTo(x + w, y + h - 0.4);
    } else {
      ctx.moveTo(x + 0.4, y); ctx.lineTo(x + 0.4, y + h);
      ctx.moveTo(x + w - 0.4, y); ctx.lineTo(x + w - 0.4, y + h);
    }
    ctx.stroke();
  };
  const buttSides = () => {
    ctx.beginPath();
    if (horizontal) {
      ctx.moveTo(x + 0.4, y); ctx.lineTo(x + 0.4, y + h);
      ctx.moveTo(x + w - 0.4, y); ctx.lineTo(x + w - 0.4, y + h);
    } else {
      ctx.moveTo(x, y + 0.4); ctx.lineTo(x + w, y + 0.4);
      ctx.moveTo(x, y + h - 0.4); ctx.lineTo(x + w, y + h - 0.4);
    }
    ctx.stroke();
  };
  ctx.strokeStyle = `rgba(38,26,16,${(tex.joint * 0.6).toFixed(3)})`;
  longSides();
  // Les joints de bout restent nettement plus discrets que les joints
  // lateraux — sinon on dessine une grille — mais les effacer donne des lames
  // infinies, ce qui est un aussi mauvais signal. 0,32 est le dosage ou ils se
  // devinent sans structurer l image.
  ctx.strokeStyle = `rgba(38,26,16,${(tex.joint * 0.32).toFixed(3)})`;
  buttSides();
  ctx.restore();
}

/**
 * Dessine une forme et ses répliques décalées d'une tuile (raccord).
 * La boîte englobante permet d'ignorer les huit copies invisibles : seules
 * les formes qui touchent un bord en ont réellement besoin.
 */
function wrapped(ctx, draw, box) {
  for (let dx = -1; dx <= 1; dx += 1) {
    for (let dy = -1; dy <= 1; dy += 1) {
      if (box) {
        const x = box.x + dx * TILE;
        const y = box.y + dy * TILE;
        if (x + box.w <= 0 || x >= TILE || y + box.h <= 0 || y >= TILE) continue;
      }
      ctx.save();
      ctx.translate(dx * TILE, dy * TILE);
      draw();
      ctx.restore();
    }
  }
}

/* ------------------------------------------------------------------ */
/* Motifs                                                              */
/* ------------------------------------------------------------------ */

function drawStraight(ctx, tex, profile, random) {
  const h = fit((profile.width / TILE_METERS) * TILE);
  const w = fit(Math.min(TILE, (profile.length / TILE_METERS) * TILE));
  const rows = Math.round(TILE / h);
  const cols = Math.round(TILE / w);

  for (let r = 0; r < rows; r += 1) {
    // Décalage variable : évite l'effet d'escalier trop régulier
    const offset = (((r % 3) + (r % 5) * 0.13) * w) / 3;
    for (let c = -1; c <= cols; c += 1) {
      const x = c * w + offset;
      const y = r * h;
      wrapped(ctx, () => board(ctx, x, y, w, h, tex, random), { x, y, w, h });
    }
  }
}

function drawHerringbone(ctx, tex, profile, random) {
  const w = fit((profile.width / TILE_METERS) * TILE);
  // Longueur réelle de l'élément, arrondie à un multiple de la largeur : c'est
  // la condition pour que le motif se referme sur lui-même.
  const l = w * Math.max(2, Math.round(profile.length / profile.width));
  const steps = Math.ceil((TILE * 1.6) / w) + 2;
  /**
   * Marge de couverture, calculée sur la géométrie et non au doigt mouillé.
   *
   * Le réseau est dessiné dans un repère tourné de 45°. Dans ce repère, le
   * carré de la tuile déborde de ses propres bords de (√2 − 1)·TILE/2 ≈ 265 px
   * aux quatre coins. L'ancienne marge valait 1,5·l, soit 180 px pour une lame
   * de 120 px : les coins n'étaient donc **jamais** couverts, et la tuile
   * gardait 2,13 % de fond uni (34 882 px sur 1280²) — des plaques sans lame
   * qui réapparaissaient au sol tous les 4,80 m. Mesuré sur le séjour en chêne
   * miel, où deux de ces plaques tombaient en plein milieu de la pièce.
   *
   * La marge couvre maintenant le débord de la rotation plus une lame entière,
   * quelle que soit la largeur de lame.
   */
  const marge = (Math.SQRT2 - 1) * (TILE / 2) + l + w;

  ctx.save();
  ctx.translate(TILE / 2, TILE / 2);
  ctx.rotate(Math.PI / 4);
  ctx.translate(-TILE / 2, -TILE / 2);
  for (let i = -steps; i <= steps; i += 1) {
    for (let j = -steps; j <= steps; j += 1) {
      const ox = TILE / 2 + i * l + j * w;
      const oy = TILE / 2 + i * l - j * w;
      if (ox < -marge || ox > TILE + marge || oy < -marge || oy > TILE + marge) continue;
      board(ctx, ox, oy, l, w, tex, random);
      board(ctx, ox + l, oy, w, l, tex, random);
    }
  }
  ctx.restore();
}

/**
 * Point de Hongrie : deux arêtes de lames coupées en biais qui se rejoignent en
 * pointe, colonne après colonne.
 *
 * L'angle est un **paramètre**, pas une constante. Il se mesure entre la lame
 * et l'axe de la pose : 45° donne la pointe droite classique, 30° une pointe
 * allongée et nervurée, 60° une pointe écrasée et large. Les trois existent
 * dans le commerce, et le rendu n'a rien à voir.
 *
 * Géométrie : pour une lame de longueur L inclinée de θ par rapport à l'axe
 * vertical, son emprise vaut L·sin θ en largeur et L·cos θ en hauteur ; deux
 * lames voisines d'une même arête sont décalées de w / sin θ le long de l'axe.
 * On arrondit ensuite le pas à un diviseur entier de la tuile, sans quoi le
 * motif ne se refermerait pas sur lui-même.
 */
function drawChevron(ctx, tex, profile, random) {
  const w = fit((profile.width / TILE_METERS) * TILE);
  const rad = (Math.min(75, Math.max(15, profile.angleDeg)) * Math.PI) / 180;
  const length = (profile.length / TILE_METERS) * TILE;
  const armX = length * Math.sin(rad);
  const armY = length * Math.cos(rad);
  // Décalage vertical entre deux lames d'une même arête, ajusté pour que la
  // tuile se referme.
  const step = fit(w / Math.sin(rad));
  const cols = Math.ceil(TILE / (armX * 2)) + 2;
  const rows = Math.ceil((TILE + armY) / step) + 2;

  /**
   * Une lame, en parallélogramme : le biais est porté par armX / armY, les deux
   * bouts restent verticaux — c'est la coupe d'onglet qui fait la couture entre
   * deux colonnes, donc la bonne forme pour un point de Hongrie.
   *
   * Le bois est peint **dans le repère de la lame**, pas dans celui de l'écran.
   *
   * Le chemin précédent étalait le veinage dans une boîte horizontale de
   * `armX * 2,2` : les stries et les cathédrales traversaient donc la lame en
   * biais au lieu de la suivre, et leur densité était calée sur 2,2 longueurs
   * d'arête au lieu d'une. Le point de Hongrie ressortait presque lisse — figure
   * absente, nœuds absents — quand la pose droite et le bâton rompu gardaient
   * la leur à la même distance. C'était le défaut le plus visible de cette
   * passe.
   *
   * La matrice ci-dessous envoie (s, t) — s le long de la lame, t en travers —
   * sur l'écran. `u` et `n` étant orthonormés, la lame n'est ni étirée ni
   * cisaillée dans ce repère : on peut y appeler `board()`, exactement comme
   * pour une lame droite. Le point de Hongrie hérite alors de tout ce dont il
   * était privé — veinage dans le fil, dispersion de teinte indexée sur la
   * taille de l'élément, reflet de finition, chanfrein proportionné.
   *
   * `drawChevron` ne sert qu'au point de Hongrie : aucune pose droite ni aucun
   * bâton rompu déjà validé ne passe par ici.
   */
  const plank = (x0, y0, dir) => {
    ctx.save();
    // Contour du parallélogramme : il sert de découpe, puis de joint.
    ctx.beginPath();
    ctx.moveTo(x0, y0);
    ctx.lineTo(x0 + dir * armX, y0 + armY);
    ctx.lineTo(x0 + dir * armX, y0 + armY + step);
    ctx.lineTo(x0, y0 + step);
    ctx.closePath();

    ctx.save();
    ctx.clip();
    const ux = (dir * armX) / length;
    const uy = armY / length;
    // Normale unitaire orientée du long côté A→B vers le long côté D→C.
    const nx = -uy * dir;
    const ny = ux * dir;
    ctx.transform(ux, uy, nx, ny, x0, y0);
    // Dans ce repère le parallélogramme va de s = 0 à length + step·cos θ ;
    // on couvre un peu plus large, la découpe fait le reste.
    const debord = step * Math.cos(rad);
    board(ctx, -1, 0, length + debord + 2, w, tex, random);
    ctx.restore();

    /**
     * Joint appuyé, par-dessus celui de `board()`.
     *
     * Le joint d'une lame droite fait 0,7 px de large, et un trait de moins
     * d'un pixel disparaît dès que la tuile est réduite : le chevron s'effaçait
     * alors en un champ uni parcouru de quelques traits. On repasse donc le
     * contour avec une largeur plancher, qui survit à la moyenne des mipmaps.
     */
    ctx.strokeStyle = `rgba(38,26,16,${(tex.joint * 0.6).toFixed(3)})`;
    ctx.lineWidth = Math.max(1.1, w * 0.05);
    ctx.stroke();
    ctx.restore();
  };

  for (let c = -1; c <= cols; c += 1) {
    for (let r = -2; r <= rows; r += 1) {
      const x0 = c * armX * 2;
      const y0 = r * step - armY;
      wrapped(
        ctx,
        () => {
          plank(x0, y0, 1);
          plank(x0 + armX * 2, y0, -1);
        },
        { x: x0 - armX, y: y0, w: armX * 3, h: armY + step }
      );
    }
  }
}

/**
 * Grain fin appliqué à toute la tuile : casse l'aspect « image de synthèse ».
 * On dessine une petite nappe de bruit fabriquée une seule fois, répétée en
 * mosaïque — cent fois plus rapide qu'un parcours pixel par pixel, pour un
 * résultat visuellement identique à cette échelle.
 */
let noiseTile = null;
function noise() {
  if (noiseTile) return noiseTile;
  const size = 128;
  noiseTile = creerCanvas(size, size);
  const ctx = noiseTile.getContext('2d');
  const image = ctx.createImageData(size, size);
  const data = image.data;
  const random = seeded(9173);
  for (let i = 0; i < data.length; i += 4) {
    const value = random() < 0.5 ? 0 : 255;
    data[i] = value;
    data[i + 1] = value;
    data[i + 2] = value;
    data[i + 3] = Math.round(random() * 26);
  }
  ctx.putImageData(image, 0, 0);
  return noiseTile;
}

function filmGrain(ctx, w, h, amount) {
  const tile = noise();
  ctx.save();
  ctx.globalAlpha = Math.min(0.5, amount / 12);
  ctx.globalCompositeOperation = 'overlay';
  const pattern = ctx.createPattern(tile, 'repeat');
  ctx.fillStyle = pattern;
  ctx.fillRect(0, 0, w, h);
  ctx.restore();
}

/* ------------------------------------------------------------------ */
/* API                                                                 */
/* ------------------------------------------------------------------ */

/**
 * Tuile répétable pour un matériau et un motif donnés.
 * @param {object} material entrée de data/parquets.json
 * @param {object} o
 * @param {string} o.pattern    lames | point-de-hongrie | baton-rompu
 * @param {number} [o.width]    largeur de lame en m (défaut : celle du matériau)
 * @returns {HTMLCanvasElement}
 */
export function buildTexture(material, { pattern = 'lames', width, size = TILE } = {}) {
  const tex = material.texture;
  const profile = patternProfile(material, pattern, width);
  const canvas = creerCanvas(size, size);
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  const random = seeded(seedOf(material.id) + Math.round(profile.width * 1000));

  // Tout est dessiné dans le repère de la tuile pleine : une taille réduite
  // sert aux aperçus (16 fois moins de pixels, même dessin).
  if (size !== TILE) ctx.scale(size / TILE, size / TILE);
  ctx.fillStyle = rgb(tex.grain, -14);
  ctx.fillRect(0, 0, TILE, TILE);

  if (pattern === 'point-de-hongrie') drawChevron(ctx, tex, profile, random);
  else if (pattern === 'baton-rompu') drawHerringbone(ctx, tex, profile, random);
  else drawStraight(ctx, tex, profile, random);

  ctx.setTransform(1, 0, 0, 1, 0, 0);
  filmGrain(ctx, size, size, 6);
  return canvas;
}

/**
 * Pyramide de réductions : supprime le moirage sur les lames lointaines.
 *
 * Un seul getImageData (le niveau 0), puis des moyennes de quatre pixels en
 * tableaux typés. Lire le canevas est de loin l'opération la plus coûteuse :
 * on ne la fait qu'une fois.
 */
export function buildMips(base, levels = 5) {
  const size0 = base.width;
  const data0 = base.getContext('2d', { willReadFrequently: true }).getImageData(0, 0, size0, size0).data;
  return etendreMips([{ size: size0, data: data0 }], levels);
}

/**
 * Complète une pyramide déjà commencée jusqu'à `levels` niveaux.
 *
 * Séparé de `buildMips` parce que les deux moteurs n'ont pas les mêmes
 * besoins : le moteur WebGL n'utilise que le niveau 0 et laisse le GPU faire
 * ses mipmaps (`gl.generateMipmap`), tandis que le moteur logiciel échantillonne
 * tous les niveaux. Calculer les quatre réductions puis les jeter coûtait, mesuré,
 * 870 ms de fil principal par matériau sur le chemin GPU — plus que le dessin de
 * la tuile en pose droite, qui n'en coûte que 135.
 *
 * Reprend là où la pyramide s'arrête, et ne recalcule rien.
 */
export function etendreMips(mips, levels = 5) {
  let previous = mips[mips.length - 1].data;
  let previousSize = mips[mips.length - 1].size;
  for (let level = mips.length; level < levels; level += 1) {
    const size = previousSize >> 1;
    if (size < 8) break;
    const data = new Uint8ClampedArray(size * size * 4);
    for (let y = 0; y < size; y += 1) {
      const row0 = (y * 2) * previousSize;
      const row1 = (y * 2 + 1) * previousSize;
      for (let x = 0; x < size; x += 1) {
        const a = (row0 + x * 2) * 4;
        const b = a + 4;
        const c = (row1 + x * 2) * 4;
        const d = c + 4;
        const out = (y * size + x) * 4;
        data[out] = (previous[a] + previous[b] + previous[c] + previous[d]) >> 2;
        data[out + 1] = (previous[a + 1] + previous[b + 1] + previous[c + 1] + previous[d + 1]) >> 2;
        data[out + 2] = (previous[a + 2] + previous[b + 2] + previous[c + 2] + previous[d + 2]) >> 2;
        data[out + 3] = 255;
      }
    }
    mips.push({ size, data });
    previous = data;
    previousSize = size;
  }
  return mips;
}

/**
 * Échantillon de catalogue : quelques lames vues de dessus, à l'échelle d'une
 * vignette. C'est le même moteur que le rendu, donc ce que l'on voit dans la
 * carte est bien ce que l'on obtient au sol.
 */
export function buildSwatch(material, { width = 260, height = 320, boards = 4 } = {}) {
  const tex = material.texture;
  const canvas = creerCanvas(width, height);
  const ctx = canvas.getContext('2d');
  const random = seeded(seedOf(material.id) + 7);

  ctx.fillStyle = rgb(tex.grain, -14);
  ctx.fillRect(0, 0, width, height);

  // La largeur de lame réelle se lit dans la vignette : une lame de 22 cm
  // occupe visiblement plus de place qu'une lame de 14 cm.
  const reference = 0.18;
  const count = Math.max(2, Math.round(boards * (reference / material.boardWidth)));
  const bw = width / count;
  // Deux lames et demie dans la hauteur : assez pour lire le veinage, les
  // joints et les têtes de lame sans que la vignette devienne une mosaïque.
  const bh = height / 2.4;

  for (let c = -1; c <= count; c += 1) {
    const offset = ((c % 3) * bh) / 2.6;
    for (let r = -1; r * bh < height + bh; r += 1) {
      board(ctx, c * bw, r * bh + offset, bw, bh, tex, random);
    }
  }
  filmGrain(ctx, width, height, 5);
  return canvas;
}
