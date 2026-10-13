/*
  Captures des matières Premibel — représentative contre exacte, en pièce.

      PPAI_PLAYWRIGHT_CORE=<playwright-core> node tools/premibel-materials.capture.mjs

  Écrit sous `review/premibel-materials/renders/` (non versionné) :

    <piece>-<id>-exact.jpg           la matière exacte, dans chaque pièce ;
    piece-claire-<id>-representative.jpg  l'ancienne matière représentative,
                                      même pièce, même cadrage ;
    renders.json                     ce qui a été rendu, et en combien de temps.

  Les planches finales sont assemblées par
  `python -m scripts.premibel_material_review`.
*/
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const CORE = process.env.PPAI_PLAYWRIGHT_CORE;
if (!CORE) { console.error('PPAI_PLAYWRIGHT_CORE manquant.'); process.exit(2); }
const { chromium } = require(CORE);
const BASE = process.env.PPAI_BASE || 'http://127.0.0.1:8143';
const OUT = path.resolve('review/premibel-materials/renders');
fs.mkdirSync(OUT, { recursive: true });
const PIECES = ['piece-claire', 'chambre', 'sejour', 'couloir-enfilade'];

const browser = await chromium.launch({ channel: 'chrome', headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const erreurs = [];
page.on('pageerror', (e) => erreurs.push(String(e)));
page.on('console', (m) => { if (m.type() === 'error') erreurs.push(m.text()); });
await page.goto(`${BASE}/tools/product-concept.html?dev=1`);
await page.waitForFunction(() => window.__concept && window.__concept.DEMO_ROOMS.length > 0
  && window.__concept.adapter.connecte, null, { timeout: 90000 });

const exactes = await page.evaluate(() => window.__concept.adapter.matieresExactes.map((m) => m.product));
console.log('matières exactes chargées', exactes.join(', '));

/* Rend un produit (ou un profil représentatif, via un produit témoin
   temporaire) dans une pièce, et rend l'image et la durée. */
const rendre = (piece, id, representatif) => page.evaluate(async ([piece, id, representatif]) => {
  const c = window.__concept;
  const vrai = c.PREMIBEL_DEMO_PRODUCTS.find((p) => p.id === id);
  let cible = id;
  if (representatif) {
    if (!vrai.representativeProfile) return { absent: true };
    cible = `${id}--representatif`;
    if (!c.PREMIBEL_DEMO_PRODUCTS.some((p) => p.id === cible)) {
      c.PREMIBEL_DEMO_PRODUCTS.push({ ...vrai, id: cible, kind: 'temoin', materialFidelity: 'representative', renderProfile: vrai.representativeProfile });
    }
  }
  const rendu = () => new Promise((ok) => { const t = () => (c.etatApplication() === 'rendered' && c.state.applied.source === 'live' && c.state.applied.key === c.appliedKey() && !c.state.applying && !c.state.pendingApply) ? ok() : requestAnimationFrame(t); t(); });
  const t0 = performance.now();
  c.select(cible, true);
  if (c.state.roomId !== piece || c.state.source !== 'demo') c.openRoom(piece);
  await rendu();
  const a = document.getElementById('after');
  return { ms: Math.round(performance.now() - t0), etat: c.etatApplication(), img: a.toDataURL('image/jpeg', 0.9) };
}, [piece, id, representatif]);

const journal = [];
for (const piece of PIECES) {
  for (const id of [...exactes, 'POINF39011']) {
    const r = await rendre(piece, id, false);
    const fidelity = exactes.includes(id) ? 'exact' : 'representative';
    fs.writeFileSync(path.join(OUT, `${piece}-${id}-${fidelity}.jpg`), Buffer.from(r.img.split(',')[1], 'base64'));
    journal.push({ piece, id, kind: fidelity, ms: r.ms, etat: r.etat });
    console.log(piece, id, fidelity, r.etat, r.ms);
    if (piece === 'piece-claire' && exactes.includes(id)) {
      const rep = await rendre(piece, id, true);
      if (!rep.absent) {
        fs.writeFileSync(path.join(OUT, `${piece}-${id}-representative.jpg`), Buffer.from(rep.img.split(',')[1], 'base64'));
        journal.push({ piece, id, kind: 'representative', ms: rep.ms, etat: rep.etat });
        console.log(piece, id, 'representative', rep.etat, rep.ms);
      }
    }
  }
}
fs.writeFileSync(path.join(OUT, 'renders.json'), JSON.stringify({ exactes, journal, erreurs }, null, 2));
console.log('erreurs console', erreurs.length ? erreurs : 0);
await browser.close();

if (erreurs.length) process.exitCode = 1;
