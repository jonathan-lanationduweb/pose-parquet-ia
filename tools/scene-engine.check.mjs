/*
  Batterie du moteur de scène — LOT PHOTO.4.

      node tools/scene-engine.check.mjs        (depuis la racine du dépôt)

  Deux promesses, vérifiées sans navigateur (aucun canevas n'est nécessaire) :

  1. Bâton rompu : chaque lame du sol a une identité stable, déduite de ses
     indices ABSOLUS dans le réseau. Une lame coupée par le bord d'une tuile
     garde la même identité — donc la même apparence — des deux côtés, et
     l'apparence empruntée à une autre lame ne déplace aucun joint.

  2. Lumière : sur une scène synthétique qui contient un veinage, des joints,
     une large bande de soleil et une ombre, les cartes gardent le soleil et
     l'ombre, et éliminent le grain et les joints. C'est ce qui interdit
     d'optimiser la lumière sur la seule photo de la chambre.
*/
import { lameBaton, apparenceBaton, motifPeriode, hacheLame } from '../web/scene/texture.js';
import { buildShadingMap, buildResidualMaps } from '../web/scene/shading.js';
import { readFileSync } from 'node:fs';

let echecs = 0;
const ok = (nom, cond, detail) => {
  if (!cond) echecs += 1;
  console.log(`${cond ? 'OK   ' : 'ECHEC'} ${nom}${detail !== undefined ? '  -> ' + detail : ''}`);
};

/* ------------------------------------------------------------ bâton rompu */
const parquets = JSON.parse(readFileSync('web/data/parquets.json', 'utf8')).parquets;
const materiau = parquets.find((m) => m.id === 'chene-naturel');
const g = motifPeriode(materiau, 'baton-rompu', 0.09);
ok('le motif bâton rompu expose son réseau', g && g.type === 'baton' && g.na > 0 && g.nb > 0,
  g && `w=${g.w.toFixed(4)} l=${g.l.toFixed(4)} na=${g.na} nb=${g.nb}`);
ok('aucune autre période pour les lames droites', motifPeriode(materiau, 'lames', 0.19) === null);

// Graine déterministe : même entrée, même sortie.
ok('le hachage est déterministe', hacheLame(3, -7, 1, 2) === hacheLame(3, -7, 1, 2));

// Pavage : tout point d'une grande surface tombe dans une lame.
let trous = 0;
let echantillons = 0;
for (let u = -1.37; u < 2.4; u += 0.0173) {
  for (let v = -1.21; v < 2.3; v += 0.0191) {
    echantillons += 1;
    if (!lameBaton(u, v, g)) trous += 1;
  }
}
ok('le réseau couvre tout le sol (aucun point sans lame)', trous === 0, `${trous} / ${echantillons}`);

// Raccord : de part et d'autre d'un bord de tuile, à l'intérieur d'une même lame.
const eps = 1e-6;
let paires = 0;
let differentes = 0;
for (let v = 0.003; v < 1; v += 0.0137) {
  for (const [ua, ub] of [[1 - eps, 1 + eps], [-eps, eps], [2 - eps, 2 + eps]]) {
    const a = lameBaton(ua, v, g);
    const b = lameBaton(ub, v, g);
    if (!a || !b || a.i !== b.i || a.j !== b.j || a.t !== b.t) continue; // sur un joint : pas une même lame
    paires += 1;
    const xa = apparenceBaton(ua, v, g);
    const xb = apparenceBaton(ub, v, g);
    if (xa.du !== xb.du || xa.dv !== xb.dv || xa.expo !== xb.expo || xa.chaleur !== xb.chaleur) differentes += 1;
  }
}
for (let u = 0.003; u < 1; u += 0.0137) {
  for (const [va, vb] of [[1 - eps, 1 + eps], [-eps, eps]]) {
    const a = lameBaton(u, va, g);
    const b = lameBaton(u, vb, g);
    if (!a || !b || a.i !== b.i || a.j !== b.j || a.t !== b.t) continue;
    paires += 1;
    const xa = apparenceBaton(u, va, g);
    const xb = apparenceBaton(u, vb, g);
    if (xa.du !== xb.du || xa.dv !== xb.dv) differentes += 1;
  }
}
ok('une lame coupée par un bord de tuile garde la même apparence des deux côtés',
  paires > 50 && differentes === 0, `${paires} lames traversant un bord, ${differentes} différentes`);

// Emprunt d'apparence : la position de lecture tombe dans une lame du MÊME
// type, à la même place relative — la géométrie ne bouge pas.
const origine = (u, v, lame) => {
  const s = Math.SQRT2 * (v - 0.5);
  const d = Math.SQRT2 * (u - 0.5);
  return [s - 2 * lame.i * g.l, d - 2 * lame.j * g.w];
};
let mauvais = 0;
let total = 0;
for (let u = 0.01; u < 3; u += 0.0311) {
  for (let v = 0.01; v < 3; v += 0.0293) {
    const lame = lameBaton(u, v, g);
    const app = apparenceBaton(u, v, g);
    const cible = lameBaton(u + app.du, v + app.dv, g);
    total += 1;
    if (!lame || !cible || cible.t !== lame.t) { mauvais += 1; continue; }
    const [sa, da] = origine(u, v, lame);
    const [sb, db] = origine(u + app.du, v + app.dv, cible);
    if (Math.abs(sa - sb) > 1e-9 || Math.abs(da - db) > 1e-9) mauvais += 1;
  }
}
ok('l\'apparence empruntée tombe à la même place dans une lame du même type', mauvais === 0, `${mauvais} / ${total}`);

// Diversité : combien de lames distinctes de la tuile sont réellement lues.
const choix = new Set();
for (let u = 0; u < 4; u += 0.011) for (let v = 0; v < 4; v += 0.013) {
  const app = apparenceBaton(u, v, g);
  const lame = lameBaton(u, v, g);
  choix.add(`${lame.t}|${Math.round(app.du / (g.w * Math.SQRT2))}|${Math.round(app.dv / (g.l * Math.SQRT2))}`);
}
ok('les lames du sol puisent dans une large part de la tuile', choix.size > 0.8 * 2 * g.na * g.nb,
  `${choix.size} apparences distinctes sur ${2 * g.na * g.nb} possibles`);

// Variation par lame : légère, jamais une teinte aléatoire forte.
let maxExpo = 0;
let maxChaleur = 0;
for (let u = 0; u < 2; u += 0.017) for (let v = 0; v < 2; v += 0.019) {
  const a = apparenceBaton(u, v, g);
  maxExpo = Math.max(maxExpo, Math.abs(a.expo - 1));
  maxChaleur = Math.max(maxChaleur, Math.abs(a.chaleur));
}
ok('variation d\'exposition par lame bornée à 3,5 %', maxExpo <= 0.035 + 1e-9, maxExpo.toFixed(4));
ok('variation de chaleur par lame bornée à 2 %', maxChaleur <= 0.02 + 1e-9, maxChaleur.toFixed(4));

/* ------------------------------------------------------------ lumière */
const W = 640;
const H = 400;
const data = new Uint8ClampedArray(W * H * 4);
const couverture = new Uint8ClampedArray(W * H).fill(255);
let graine = 12345;
const alea = () => { graine = (graine * 16807) % 2147483647; return graine / 2147483647; };
const dansSoleil = (x, y) => Math.abs((x - y * 0.6) - 300) < 70; // bande oblique de 140 px
const dansOmbre = (x, y) => x > 40 && x < 160 && y > 250 && y < 360;
for (let y = 0; y < H; y += 1) {
  for (let x = 0; x < W; x += 1) {
    let v = 120 * (1 + 0.18 * (alea() - 0.5)); // veinage : bruit fin
    if (y % 28 === 0) v *= 0.55; // joints
    if (dansSoleil(x, y)) v *= 1.6;
    if (dansOmbre(x, y)) v *= 0.5;
    const i = (y * W + x) * 4;
    data[i] = v * 1.25; data[i + 1] = v; data[i + 2] = v * 0.7; data[i + 3] = 255;
  }
}
const source = { width: W, height: H, data };
const ombrage = buildShadingMap(source, couverture, { blurRadius: 0.045, contact: 0.35 });
const cartes = buildResidualMaps(source, couverture, ombrage).fullRes();
const moyenne = (carte, filtre) => {
  let s = 0; let n = 0;
  for (let y = 0; y < H; y += 1) for (let x = 0; x < W; x += 1) if (filtre(x, y)) { s += carte[y * W + x]; n += 1; }
  return s / Math.max(1, n);
};
const coeurSoleil = (x, y) => Math.abs((x - y * 0.6) - 300) < 40 && y > 30 && y < H - 30;
const solOrdinaire = (x, y) => !dansSoleil(x, y) && Math.abs((x - y * 0.6) - 300) > 140 && !dansOmbre(x, y)
  && !(x > 0 && x < 220 && y > 200) && x > 20 && x < W - 20 && y > 20 && y < H - 20;
const joints = (x, y) => y % 28 === 0 && solOrdinaire(x, y);
/* Le gain d'éclairage FINAL, toutes couches combinées, comme dans le moteur :
   base basse fréquence × ombres de contact × lumière (hautes lumières et
   échelle moyenne, bornées ensemble). Une large bande de soleil vit surtout
   dans la base ; ce que les autres couches ajoutent ne doit jamais dessiner le
   grain ni les joints. */
const lumiere = { contactShadow: 0.6, highlight: 1.2, midLight: 1.5, lightMax: 1.7 };
const echant = new Float32Array(4);
const gain = (x, y) => {
  ombrage.sample(x, y, echant);
  const base = 0.2126 * echant[0] + 0.7152 * echant[1] + 0.0722 * echant[2];
  const i = y * W + x;
  return base * (1 - lumiere.contactShadow * cartes.shadow[i])
    * Math.min(lumiere.lightMax, (1 + lumiere.highlight * cartes.light[i]) * (1 + lumiere.midLight * cartes.mid[i]));
};
const moyenneGain = (filtre) => {
  let s = 0; let n = 0;
  for (let y = 0; y < H; y += 1) for (let x = 0; x < W; x += 1) if (filtre(x, y)) { s += gain(x, y); n += 1; }
  return s / Math.max(1, n);
};
const gSol = moyenneGain(solOrdinaire);
const gSoleil = moyenneGain(coeurSoleil);
const gOmbre = moyenneGain((x, y) => x > 70 && x < 130 && y > 280 && y < 330);
ok('le soleil reste nettement plus clair que le sol ordinaire', gSoleil / gSol > 1.35, (gSoleil / gSol).toFixed(2));
ok("l'ombre reste nettement plus sombre", gOmbre / gSol < 0.75, (gOmbre / gSol).toFixed(2));
// Grain : l'éclairage ne doit pas varier d'un pixel à l'autre comme le bruit.
let ecartMax = 0;
for (let y = 60; y < 180; y += 1) for (let x = 440; x < 600; x += 1) {
  if (!solOrdinaire(x, y) || !solOrdinaire(x + 1, y)) continue;
  ecartMax = Math.max(ecartMax, Math.abs(gain(x + 1, y) - gain(x, y)));
}
ok("le grain n'entre pas dans l'éclairage (écart entre pixels voisins)", ecartMax < 0.01, ecartMax.toFixed(4));
// Joints : la rangée de joint ne doit pas être plus sombre que ses voisines.
let joint = 0; let voisin = 0; let nj = 0;
for (let y = 56; y < 200; y += 28) for (let x = 440; x < 600; x += 1) {
  if (!solOrdinaire(x, y)) continue;
  joint += gain(x, y); voisin += (gain(x, y - 4) + gain(x, y + 4)) / 2; nj += 1;
}
ok("les joints n'entrent pas dans l'éclairage", Math.abs(joint - voisin) / nj < 0.01, (Math.abs(joint - voisin) / nj).toFixed(4));
const lumSol = moyenne(cartes.mid, solOrdinaire) + moyenne(cartes.light, solOrdinaire);
const lumJoints = moyenne(cartes.mid, joints) + moyenne(cartes.light, joints);
ok('couches lumière nulles sur le sol ordinaire', lumSol < 0.02, lumSol.toFixed(4));
ok('couches lumière nulles sur les joints', lumJoints < 0.02, lumJoints.toFixed(4));
ok('les joints ne deviennent pas des ombres', moyenne(cartes.shadow, joints) < 0.02, moyenne(cartes.shadow, joints).toFixed(4));

console.log(echecs ? `\n${echecs} ECHEC(S)` : '\nAUCUN ECHEC');
process.exit(echecs ? 1 : 0);
