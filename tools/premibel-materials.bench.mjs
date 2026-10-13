/*
  Banc de vitesse des matières — froide, préchargée, en cache.

      PPAI_PLAYWRIGHT_CORE=<playwright-core> node tools/premibel-materials.bench.mjs [runs]

  Pour chaque run, deux pages neuves (préchargement du catalogue coupé par
  `?dev=1&prefetch=0&initialProduct=CHENF39031`, pour que « froid » veuille dire froid) :

    page A  pièce ouverte, puis chaque produit une première fois (FROID),
            puis chaque produit une seconde fois (EN CACHE : rendu déjà fait) ;
    page B  pièce ouverte, puis pour chaque produit : préchargement de sa
            matière, attente qu'elle soit prête, puis clic (PRÉCHARGÉ).

  Le temps est mesuré DANS la page, du choix à l'image du produit présentée
  (`etatApplication() === 'rendered'` avec un rendu du moteur). Écrit
  `review/premibel-materials/bench.json`. Les chiffres dépendent de la charge
  de la machine : le banc la mentionne, il ne la corrige pas.
*/
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const CORE = process.env.PPAI_PLAYWRIGHT_CORE;
if (!CORE) { console.error('PPAI_PLAYWRIGHT_CORE manquant.'); process.exit(2); }
const { chromium } = require(CORE);
const BASE = process.env.PPAI_BASE || 'http://127.0.0.1:8143';
const RUNS = Number(process.argv[2] || 5);
const PIECE = process.env.PPAI_PIECE || 'chambre';
const PRODUITS = (process.env.PPAI_PRODUITS || 'CHENF36014,CHENF36015,BTRPF39009,CHEN38163,POINF39011').split(',');
const OUT = path.resolve('review/premibel-materials');
fs.mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({ channel: 'chrome', headless: true });

async function page() {
  const p = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const erreurs = [];
  p.on('pageerror', (e) => erreurs.push(String(e)));
  p.on('console', (m) => { if (m.type() === 'error') erreurs.push(m.text()); });
  await p.goto(`${BASE}/tools/product-concept.html?dev=1&prefetch=0&initialProduct=CHENF39031`);
  await p.waitForFunction(() => window.__concept && window.__concept.DEMO_ROOMS.length > 0
    && window.__concept.adapter.connecte, null, { timeout: 90000 });
  /* Ouvrir la pièce avec le produit par défaut, puis attendre le rendu. */
  const ouverture = await p.evaluate(async (piece) => {
    const c = window.__concept;
    const rendu = () => new Promise((ok) => { const t = () => (c.etatApplication() === 'rendered' && c.state.applied.source === 'live' && !c.state.applying && !c.state.pendingApply) ? ok() : requestAnimationFrame(t); t(); });
    const t0 = performance.now(); c.openRoom(piece); await rendu(); return Math.round(performance.now() - t0);
  }, PIECE);
  return { p, erreurs, ouverture };
}

const mesurer = (p, id, avant) => p.evaluate(async ([id, avant]) => {
  const c = window.__concept;
  const prod = c.PREMIBEL_DEMO_PRODUCTS.find((x) => x.id === id);
  if (avant === 'precharger') {
    c.adapter.prechargerMatieres([prod.renderProfile]);
    await new Promise((ok) => { const t = () => (c.adapter.matierePrete(prod.renderProfile) ? ok() : setTimeout(t, 30)); t(); });
    await new Promise((r) => setTimeout(r, 100));
  }
  const rendu = () => new Promise((ok) => { const t = () => (c.etatApplication() === 'rendered' && c.state.applied.source === 'live' && c.state.applied.key === c.appliedKey() && !c.state.applying && !c.state.pendingApply) ? ok() : requestAnimationFrame(t); t(); });
  const t0 = performance.now(); c.select(id, true); await rendu();
  return { ms: Math.round(performance.now() - t0), etat: c.etatApplication(), fid: prod.materialFidelity };
}, [id, avant]);

const res = { piece: PIECE, produits: PRODUITS, runs: [], ouvertures: [] };
for (let run = 0; run < RUNS; run += 1) {
  const r = { froid: {}, cache: {}, precharge: {} };
  const a = await page();
  res.ouvertures.push(a.ouverture);
  for (const id of PRODUITS) r.froid[id] = await mesurer(a.p, id, null);
  for (const id of PRODUITS) r.cache[id] = await mesurer(a.p, id, null);
  r.erreursA = a.erreurs;
  await a.p.close();
  const b = await page();
  res.ouvertures.push(b.ouverture);
  for (const id of PRODUITS) r.precharge[id] = await mesurer(b.p, id, 'precharger');
  r.erreursB = b.erreurs;
  await b.p.close();
  res.runs.push(r);
  console.log(`run ${run + 1}`, PRODUITS.map((id) => `${id} ${r.froid[id].ms}/${r.precharge[id].ms}/${r.cache[id].ms}`).join(' | '));
}
await browser.close();

const med = (xs) => { const s = [...xs].sort((x, y) => x - y); return s[Math.floor(s.length / 2)]; };
const tableau = PRODUITS.map((id) => {
  const col = (k) => res.runs.map((r) => r[k][id].ms);
  const f = col('froid'); const p = col('precharge'); const c = col('cache');
  return { id, fidelite: res.runs[0].froid[id].fid,
    froid: { min: Math.min(...f), med: med(f), max: Math.max(...f) },
    precharge: { min: Math.min(...p), med: med(p), max: Math.max(...p) },
    cache: { min: Math.min(...c), med: med(c), max: Math.max(...c) },
    rendus: res.runs.every((r) => ['froid', 'precharge', 'cache'].every((k) => r[k][id].etat === 'rendered')) };
});
res.tableau = tableau;
res.erreurs = res.runs.flatMap((r) => [...r.erreursA, ...r.erreursB]);
fs.writeFileSync(path.join(OUT, 'bench.json'), JSON.stringify(res, null, 2));
console.log('\nproduit | fidélité | froid min/méd/max | préchargé | en cache');
for (const t of tableau) {
  console.log(`${t.id} | ${t.fidelite} | ${t.froid.min}/${t.froid.med}/${t.froid.max} | ${t.precharge.min}/${t.precharge.med}/${t.precharge.max} | ${t.cache.min}/${t.cache.med}/${t.cache.max}${t.rendus ? '' : ' | ÉCHEC DE RENDU'}`);
}
console.log('ouverture de pièce (ms)', res.ouvertures.join(', '));
console.log('erreurs console', res.erreurs.length);
