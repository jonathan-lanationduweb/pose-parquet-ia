/*
  Revue géométrique des pièces de démonstration.

      PPAI_PLAYWRIGHT_CORE=<chemin vers playwright-core> \
      node tools/scene-review.capture.mjs [id ...]

  Pour chaque scène de `web/data/rooms.json` qui a une SceneData, une
  planche de six vues sous `review/rooms-and-render-fix/scenes/<id>.jpg` :

    original | masque du sol | géométrie (horizon, fuites, axes, guides)
    lames    | point de Hongrie | bâton rompu

  et des contrôles CHIFFRÉS dans `scenes/checks.json`. Ils ne remplacent pas
  l'œil — une scène n'est validée qu'après lecture de sa planche — mais ils
  attrapent ce que l'œil rate : un plan dont les fuites ne tombent pas sur
  celles des murs, une lame dont la largeur projetée ne croît pas vers
  l'avant, un sol qui monte au-dessus de l'horizon.

  Le serveur de développement doit tourner (`python -m scripts.product_dev`),
  `PPAI_BASE` le désigne (défaut http://127.0.0.1:8143). Rien n'est écrit
  hors de `review/`, qui n'est pas versionné.
*/
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const CORE = process.env.PPAI_PLAYWRIGHT_CORE;
if (!CORE) { console.error('PPAI_PLAYWRIGHT_CORE manquant : chemin vers playwright-core.'); process.exit(2); }
const { chromium } = require(CORE);
const BASE = process.env.PPAI_BASE || 'http://127.0.0.1:8143';
const OUT = path.resolve('review/rooms-and-render-fix/scenes');
fs.mkdirSync(OUT, { recursive: true });

const rooms = JSON.parse(fs.readFileSync('web/data/rooms.json', 'utf8'));
const voulues = process.argv.slice(2);
const scenes = rooms.scenes.filter((s) => s.sceneData && (!voulues.length || voulues.includes(s.id)));

/* Trois produits, un par motif. Choisis parce qu'ils existent dans le
   catalogue de démonstration et couvrent les trois géométries du moteur. */
const PRODUITS = [['lames', 'CHENF36014'], ['pdh', 'POINF36005'], ['br', 'BTRPF39009']];

const browser = await chromium.launch({ channel: 'chrome', headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const erreurs = [];
page.on('pageerror', (e) => erreurs.push(String(e)));
page.on('console', (m) => { if (m.type() === 'error') erreurs.push(m.text()); });
await page.goto(`${BASE}/tools/product-concept.html?dev=1&revue=1`);
await page.waitForFunction(() => window.__concept && window.__concept.DEMO_ROOMS.length > 0
  && window.__concept.adapter.connecte, null, { timeout: 60000 });

const attendreLive = () => page.waitForFunction(() => {
  const c = window.__concept;
  return !c.state.applying && c.state.applied.source === 'live' && c.state.applied.key === c.appliedKey();
}, null, { timeout: 120000 });

const tous = {};
for (const sc of scenes) {
  const t0 = Date.now();
  const rendus = {};
  for (const [nom, id] of PRODUITS) {
    await page.evaluate(([room, prod]) => {
      const c = window.__concept;
      c.select(prod, true);
      if (c.state.roomId !== room || c.state.source !== 'demo') c.openRoom(room);
    }, [sc.id, id]);
    try {
      await attendreLive();
      rendus[nom] = await page.evaluate(() => document.getElementById('after').toDataURL('image/jpeg', 0.85));
    } catch {
      rendus[nom] = null;
    }
  }
  const res = await page.evaluate(async (rendusIn) => {
    const { zoneTransform } = await import('/web/scene/geometry.js');
    const { apply } = await import('/web/scene/perspective.js');
    const c = window.__concept;
    const snap = c.adapter.visitSnapshot && c.adapter.visitSnapshot();
    const diag = c.adapter.geometryDiagnostics();
    if (!snap || !diag) return { erreur: 'scene_non_ouverte' };
    const { scene, masks, size } = snap;
    const W = size.width; const H = size.height;
    const photo = document.getElementById('photo');
    const charger = (src) => new Promise((ok) => { const im = new Image(); im.onload = () => ok(im); im.onerror = () => ok(null); im.src = src; });

    /* Panneau 2 : le masque, teinté sur la photo. */
    const m = document.createElement('canvas'); m.width = W; m.height = H;
    const mx = m.getContext('2d');
    mx.drawImage(photo, 0, 0, W, H);
    const img = mx.getImageData(0, 0, W, H);
    for (let i = 0; i < W * H; i += 1) {
      const a = masks.coverage[i] / 255;
      if (a <= 0) continue;
      img.data[i * 4] = img.data[i * 4] * (1 - 0.55 * a) + 40 * 0.55 * a;
      img.data[i * 4 + 1] = img.data[i * 4 + 1] * (1 - 0.55 * a) + 220 * 0.55 * a;
      img.data[i * 4 + 2] = img.data[i * 4 + 2] * (1 - 0.55 * a) + 120 * 0.55 * a;
    }
    mx.putImageData(img, 0, 0);

    /* Panneau 3 : la géométrie. */
    const g = document.createElement('canvas'); g.width = W; g.height = H;
    const gx = g.getContext('2d');
    gx.drawImage(photo, 0, 0, W, H);
    gx.fillStyle = 'rgba(0,0,0,0.25)'; gx.fillRect(0, 0, W, H);
    const lw = Math.max(2, W / 500);
    const trait = (a, b, col, dash = []) => {
      if (![a.x, a.y, b.x, b.y].every(Number.isFinite)) return;
      gx.strokeStyle = col; gx.lineWidth = lw; gx.setLineDash(dash);
      gx.beginPath(); gx.moveTo(a.x, a.y); gx.lineTo(b.x, b.y); gx.stroke();
    };
    const hz = scene.camera && Number.isFinite(scene.camera.horizon) ? scene.camera.horizon * H : null;
    if (hz !== null) trait({ x: 0, y: hz }, { x: W, y: hz }, '#ffd400', [14, 8]);
    const vpsCamera = ((scene.camera && scene.camera.vanishingPoints) || []).map((v) => ({ x: v.x * W, y: v.y * H, role: v.role }));
    for (const v of vpsCamera) {
      gx.fillStyle = '#ffd400'; gx.beginPath(); gx.arc(Math.min(Math.max(v.x, 8), W - 8), v.y, lw * 3, 0, Math.PI * 2); gx.fill();
    }
    const zones = [];
    for (const zone of scene.floorZones) {
      const t = zoneTransform(zone, W, H);
      if (!t) { zones.push({ id: zone.id, valide: false }); continue; }
      const mw = zone.plane.meters.width; const md = zone.plane.meters.depth;
      const proj = (u, v) => apply(t.H, u / mw, v / md);
      /* Contour réellement peint. */
      const poly = masks.getPolygon(zone.id).map((p) => ({ x: p.x * W, y: p.y * H }));
      for (let i = 0; i < poly.length; i += 1) trait(poly[i], poly[(i + 1) % poly.length], '#ff6b6b');
      /* Guides de lames : une ligne tous les 50 cm dans les deux sens,
         bornée à l'étendue du plan, découpée au masque par la lecture. */
      gx.save();
      gx.beginPath(); poly.forEach((p, i) => (i ? gx.lineTo(p.x, p.y) : gx.moveTo(p.x, p.y))); gx.closePath(); gx.clip();
      /* Tracé par petits segments, seulement du côté visible du plan : une
         droite du sol qui passe derrière la caméra se retourne au-delà de
         l'horizon, et la tracer d'un trait barrerait toute l'image. */
      const Hm0 = t.H;
      const w = (u, v) => Hm0[6] * (u / mw) + Hm0[7] * (v / md) + Hm0[8];
      const signe = Math.sign(w(mw / 2, md / 2));
      const segment = (pts, col) => {
        for (let i = 1; i < pts.length; i += 1) {
          const [a, b] = [pts[i - 1], pts[i]];
          if (Math.sign(w(a[0], a[1])) !== signe || Math.sign(w(b[0], b[1])) !== signe) continue;
          trait(proj(a[0], a[1]), proj(b[0], b[1]), col);
        }
      };
      const L = 12; const pas = 0.5;
      for (let k = -L; k <= L; k += pas) {
        const lu = []; const lv = [];
        for (let q = -L; q <= L; q += 0.1) { lu.push([k, q]); lv.push([q, k]); }
        segment(lu, 'rgba(101,227,211,0.9)');
        segment(lv, 'rgba(255,255,255,0.6)');
      }
      gx.restore();
      const Hm = t.H;
      const fuite = (i) => (Math.abs(Hm[6 + i]) > 1e-12 ? { x: Hm[i] / Hm[6 + i], y: Hm[3 + i] / Hm[6 + i] } : null);
      const fu = fuite(0); const fv = fuite(1);
      for (const f of [fu, fv]) if (f) { gx.strokeStyle = '#65e3d3'; gx.setLineDash([]); gx.lineWidth = lw; gx.beginPath(); gx.arc(Math.min(Math.max(f.x, 10), W - 10), Math.min(Math.max(f.y, 10), H - 10), lw * 5, 0, Math.PI * 2); gx.stroke(); }
      const dz = diag.zones.find((z) => z.id === zone.id) || {};
      zones.push({ id: zone.id, valide: true, fu, fv, meters: { mw, md }, samples: (dz.samples || []).map((s) => ({ position: s.position, px: s.valid ? +s.plankWidthPx.toFixed(1) : null })) });
    }

    /* Contrôles chiffrés. Tolérances en fraction de la hauteur d'image. */
    const ctl = {};
    const topMasque = (() => { for (let y = 0; y < H; y += 1) for (let x = 0; x < W; x += 4) if (masks.coverage[y * W + x] > 128) return y; return H; })();
    ctl.solSousHorizon = hz === null ? null : topMasque >= hz - 0.01 * H;
    ctl.fuitesSurHorizon = hz === null ? null : zones.filter((z) => z.valide).every((z) => [z.fu, z.fv].filter(Boolean)
      .filter((f) => Math.abs(f.x) < 20 * W).every((f) => Math.abs(f.y - hz) < 0.02 * H));
    /* Les fuites du PLAN tombent-elles sur celles mesurées sur les MURS ? */
    const distMin = (f) => (vpsCamera.length ? Math.min(...vpsCamera.map((v) => Math.hypot(v.x - f.x, v.y - f.y))) : null);
    ctl.fuitesAlignees = vpsCamera.length ? zones.filter((z) => z.valide).every((z) => [z.fu, z.fv].filter((f) => f && Math.abs(f.x) < 4 * W)
      .every((f) => distMin(f) < 0.03 * W)) : null;
    ctl.lamesCroissentVersAvant = zones.filter((z) => z.valide).every((z) => {
      const v = z.samples.map((s) => s.px).filter((x) => x !== null);
      return v.length < 2 || v.every((x, i) => i === 0 || x >= v[i - 1] - 0.5);
    });
    const near = zones.flatMap((z) => (z.samples || []).filter((s) => s.position === 'near').map((s) => s.px)).filter(Boolean);
    /* Une lame de 15 cm au premier plan d'une photo de pièce couvre en
       pratique 1,5 à 8 % de la largeur d'image. Hors de cette plage, l'échelle
       est suspecte (mètres déclarés, ou hauteur d'œil). */
    ctl.echelleProchePlausible = near.length ? near.every((px) => px / W > 0.012 && px / W < 0.09) : null;

    /* Planche 3 x 2. */
    const PW = 800; const PH = Math.round(PW * H / W);
    const board = document.createElement('canvas'); board.width = PW * 3; board.height = (PH + 30) * 2;
    const bx = board.getContext('2d');
    bx.fillStyle = '#fff'; bx.fillRect(0, 0, board.width, board.height);
    const panneaux = [['original', photo], ['masque du sol', m], ['géométrie', g]];
    for (const [nom, src] of Object.entries(rendusIn)) panneaux.push([nom, src ? await charger(src) : null]);
    panneaux.forEach(([nom, src], i) => {
      const x = (i % 3) * PW; const y = Math.floor(i / 3) * (PH + 30);
      bx.fillStyle = '#111'; bx.font = '18px sans-serif'; bx.fillText(nom, x + 8, y + 21);
      if (src) bx.drawImage(src, x, y + 30, PW, PH);
      else { bx.fillStyle = '#c00'; bx.fillText('rendu absent', x + 20, y + 80); }
    });
    return { board: board.toDataURL('image/jpeg', 0.84), geometrie: g.toDataURL('image/jpeg', 0.88), zones, ctl, horizon: scene.camera && scene.camera.horizon, size: { W, H } };
  }, { lames: rendus.lames, 'point de Hongrie': rendus.pdh, 'bâton rompu': rendus.br });
  if (res.erreur) { tous[sc.id] = res; console.log(sc.id, res.erreur); continue; }
  fs.writeFileSync(path.join(OUT, `${sc.id}.jpg`), Buffer.from(res.board.split(',')[1], 'base64'));
  /* Les rendus en pleine résolution, pour lire les bords de près. */
  fs.mkdirSync(path.join(OUT, sc.id), { recursive: true });
  for (const [nom, url] of Object.entries(rendus)) {
    if (url) fs.writeFileSync(path.join(OUT, sc.id, `${nom}.jpg`), Buffer.from(url.split(',')[1], 'base64'));
  }
  if (res.geometrie) fs.writeFileSync(path.join(OUT, sc.id, 'geometrie.jpg'), Buffer.from(res.geometrie.split(',')[1], 'base64'));
  delete res.geometrie;
  delete res.board;
  res.renderus = Object.fromEntries(Object.entries(rendus).map(([k, v]) => [k, Boolean(v)]));
  res.ms = Date.now() - t0;
  tous[sc.id] = res;
  console.log(sc.id, JSON.stringify(res.ctl), res.zones.map((z) => z.samples ? z.samples.map((s) => s.px).join('/') : '').join(' | '), `${res.ms} ms`);
}
fs.writeFileSync(path.join(OUT, 'checks.json'), JSON.stringify(tous, null, 2));
console.log('console', erreurs.length ? erreurs : 'aucune erreur');
await browser.close();
