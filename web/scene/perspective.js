/**
 * Homographie 4 points (projection perspective).
 *
 * On calcule la matrice qui envoie le carré unité (0,0) (1,0) (1,1) (0,1)
 * sur le quadrilatère du sol défini par l'utilisateur, puis son inverse :
 * le rendu parcourt les pixels de l'image et remonte aux coordonnées du sol.
 * C'est ce qui donne la perspective — une lame proche paraît plus grande
 * qu'une lame au fond de la pièce.
 */

/**
 * Matrice 3×3 (carré unité → quadrilatère).
 * @param {{x:number,y:number}[]} quad 4 points, dans l'ordre :
 *        fond-gauche, fond-droite, proche-droite, proche-gauche
 * @returns {number[]} [a, b, c, d, e, f, g, h, 1]
 */
export function squareToQuad(quad) {
  const [p0, p1, p2, p3] = quad;
  const dx1 = p1.x - p2.x;
  const dx2 = p3.x - p2.x;
  const dy1 = p1.y - p2.y;
  const dy2 = p3.y - p2.y;
  const sx = p0.x - p1.x + p2.x - p3.x;
  const sy = p0.y - p1.y + p2.y - p3.y;

  let g = 0;
  let h = 0;
  const det = dx1 * dy2 - dx2 * dy1;

  if (Math.abs(sx) > 1e-9 || Math.abs(sy) > 1e-9) {
    if (Math.abs(det) < 1e-9) return null;
    g = (sx * dy2 - dx2 * sy) / det;
    h = (dx1 * sy - sx * dy1) / det;
  }

  return [
    p1.x - p0.x + g * p1.x,
    p3.x - p0.x + h * p3.x,
    p0.x,
    p1.y - p0.y + g * p1.y,
    p3.y - p0.y + h * p3.y,
    p0.y,
    g,
    h,
    1,
  ];
}

/** Inverse d'une matrice 3×3 donnée à plat. */
export function invert(m) {
  const [a, b, c, d, e, f, g, h, i] = m;
  const A = e * i - f * h;
  const B = -(d * i - f * g);
  const C = d * h - e * g;
  const det = a * A + b * B + c * C;
  if (Math.abs(det) < 1e-12) return null;
  const inv = 1 / det;
  return [
    A * inv,
    -(b * i - c * h) * inv,
    (b * f - c * e) * inv,
    B * inv,
    (a * i - c * g) * inv,
    -(a * f - c * d) * inv,
    C * inv,
    -(a * h - b * g) * inv,
    (a * e - b * d) * inv,
  ];
}

/** Applique une matrice à un point (renvoie les coordonnées déshomogénéisées). */
export function apply(m, x, y) {
  const w = m[6] * x + m[7] * y + m[8];
  return {
    x: (m[0] * x + m[1] * y + m[2]) / w,
    y: (m[3] * x + m[4] * y + m[5]) / w,
  };
}

/** Boîte englobante entière d'un quadrilatère, bornée à la taille du canevas. */
export function bounds(quad, width, height) {
  const xs = quad.map((p) => p.x);
  const ys = quad.map((p) => p.y);
  return {
    x0: Math.max(0, Math.floor(Math.min(...xs))),
    y0: Math.max(0, Math.floor(Math.min(...ys))),
    x1: Math.min(width, Math.ceil(Math.max(...xs))),
    y1: Math.min(height, Math.ceil(Math.max(...ys))),
  };
}

/** Aire d'un polygone (formule du lacet) — sert à valider une sélection. */
export function area(points) {
  let sum = 0;
  for (let i = 0; i < points.length; i += 1) {
    const a = points[i];
    const b = points[(i + 1) % points.length];
    sum += a.x * b.y - b.x * a.y;
  }
  return Math.abs(sum) / 2;
}
