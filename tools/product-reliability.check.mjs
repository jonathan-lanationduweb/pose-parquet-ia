/*
  Batterie de FIABILITÉ du visualiseur — MISSION STABILISATION.

      node tools/product-reliability.check.mjs

  Pilote un vrai Chrome (playwright-core) sur le visualiseur servi par FastAPI.
  Prérequis, vérifiés au démarrage et nommés s'ils manquent :

    - le service sur PPAI_BASE (défaut http://127.0.0.1:8143), lancé avec
      PPAI_DEV_SERVE_STATIC=1 ;
    - `playwright-core` importable, ou son chemin dans PPAI_PLAYWRIGHT_CORE ;
    - Google Chrome installé (canal `chrome`).

  Deux familles de cas :

    1. SIMULÉS — la réponse d'analyse est interceptée et remplacée. C'est ce
       qui rend reproductibles la réponse périmée, la panne, le délai dépassé,
       la scène invalide et la préparation du modèle. Ils tournent partout.
    2. RÉELS — chaque photo de `datasets/private-real/` est envoyée au vrai
       service (PPAI_EXPERIMENTAL_FLOOR=1 attendu) et parcourue de bout en bout.
       Rien n'est copié : la photo est lue sur place. Absentes, ces lignes sont
       déclarées NON EXÉCUTÉES, jamais réussies.

  Sortie : la liste des contrôles, puis `review/stability/matrix.json` et
  `matrix.md` (hors Git). Code de sortie non nul au moindre échec.
*/
import { existsSync, mkdirSync, writeFileSync, readdirSync } from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';

const BASE = process.env.PPAI_BASE || 'http://127.0.0.1:8143';
const ROOT = process.cwd();
const OUT = path.join(ROOT, 'review', 'stability');
const PRIVE = path.join(ROOT, 'datasets', 'private-real');
const DEMO_PHOTO = path.join(ROOT, 'web', 'assets', 'images', 'room-sejour.jpg');
const PHOTOS_REELLES = ['chambre', 'sejour', 'entree-cadree', 'couloir', 'salon', 'appartement-ancien', 'petite-piece'];
const CAPTURES = process.env.PPAI_CAPTURES !== '0';

let echecs = 0;
const resultats = [];
const ok = (nom, cond, detail) => {
  if (!cond) echecs += 1;
  resultats.push({ nom, ok: Boolean(cond), detail });
  console.log(`${cond ? 'OK   ' : 'ECHEC'} ${nom}${detail !== undefined ? '  -> ' + detail : ''}`);
};

/* ------------------------------------------------------------ prérequis */
async function chargerPlaywright() {
  try { return await import('playwright-core'); } catch { /* suite */ }
  const chemin = process.env.PPAI_PLAYWRIGHT_CORE;
  if (chemin) { const req = createRequire(import.meta.url); return req(chemin); }
  console.error('playwright-core introuvable : installez-le, ou indiquez son chemin dans PPAI_PLAYWRIGHT_CORE.');
  process.exit(2);
}
const pw = await chargerPlaywright();
const chromium = pw.chromium || (pw.default && pw.default.chromium);
let sante;
try { sante = await (await fetch(`${BASE}/health`)).json(); } catch {
  console.error(`Service injoignable sur ${BASE} : lancez-le avec PPAI_DEV_SERVE_STATIC=1.`);
  process.exit(2);
}
const experimental = Boolean(sante && sante.experimentalFloor);
console.log(`service ${BASE} · mode expérimental ${experimental ? sante.experimentalFloor : 'éteint'}`);

const navigateur = await chromium.launch({ channel: 'chrome', headless: true });
mkdirSync(OUT, { recursive: true });

/* ------------------------------------------------------------ outils */
const PAGE = (q = '') => `${BASE}/tools/product-concept.html?dev=1${q}`;

async function nouvellePage({ largeur = 1440, hauteur = 900, sansWebGL = false } = {}) {
  const ctx = await navigateur.newContext({ viewport: { width: largeur, height: hauteur } });
  const p = await ctx.newPage();
  p.__erreurs = [];
  p.on('pageerror', (e) => p.__erreurs.push(String(e)));
  p.on('console', (m) => { if (m.type() === 'error') p.__erreurs.push(m.text()); });
  p.__analyses = 0;
  p.on('request', (r) => { if (r.url().includes('/v1/analyze-room')) p.__analyses += 1; });
  await p.addInitScript((sansGL) => {
    // Comptage des URL d'objet vivantes (fuites de photos).
    const vivantes = new Set();
    const cree = URL.createObjectURL.bind(URL);
    const revoque = URL.revokeObjectURL.bind(URL);
    URL.createObjectURL = (o) => { const u = cree(o); vivantes.add(u); return u; };
    URL.revokeObjectURL = (u) => { vivantes.delete(u); return revoque(u); };
    window.__blobsVivants = () => vivantes.size;
    // Workers créés et écouteurs posés sur window/document, pour détecter une
    // fabrique ou un abonnement qui se multiplierait à chaque import.
    const W = window.Worker; window.__workers = 0;
    window.Worker = function (...a) { window.__workers += 1; return new W(...a); };
    window.Worker.prototype = W.prototype;
    window.__ecouteurs = 0;
    for (const cible of [window, document]) {
      const ajout = cible.addEventListener.bind(cible);
      cible.addEventListener = (...a) => { window.__ecouteurs += 1; return ajout(...a); };
    }
    // Moteurs créés (pour savoir lequel tourne réellement).
    let fabrique;
    Object.defineProperty(window, '__localEngineFactory', {
      configurable: true,
      get() { return fabrique; },
      set(v) { fabrique = async (...a) => { const r = await v(...a); (window.__moteurs = window.__moteurs || []).push(r); return r; }; },
    });
    if (sansGL) {
      const orig = HTMLCanvasElement.prototype.getContext;
      HTMLCanvasElement.prototype.getContext = function (t, ...a) {
        if (/webgl/.test(t)) return null;
        return orig.call(this, t, ...a);
      };
    }
  }, sansWebGL);
  return p;
}

async function ouvrir(p, q = '') {
  await p.goto(PAGE(q), { waitUntil: 'load' });
  await p.waitForFunction(() => window.__concept && window.__concept.state);
}

const etat = (p) => p.evaluate(() => window.__concept.etatProduit());
const TRANSITOIRES = ['PHOTO_SELECTED', 'ANALYSIS_WAITING', 'ANALYZING', 'RENDER_PENDING'];

/** Attend un état stable (hors transitoires) ; rend l'état, ou 'STUCK:<état>'. */
async function attendreEtatFinal(p, delaiMs = 240000) {
  const t0 = Date.now();
  let dernier = null;
  let stableDepuis = Date.now();
  while (Date.now() - t0 < delaiMs) {
    const e = await etat(p);
    if (e !== dernier) { dernier = e; stableDepuis = Date.now(); }
    if (!TRANSITOIRES.includes(e) && Date.now() - stableDepuis > 700) return e;
    await new Promise((r) => setTimeout(r, 150));
  }
  return `STUCK:${dernier}`;
}

async function importer(p, fichier) {
  await p.setInputFiles('#file', fichier);
}

/** Ce que voit l'utilisateur : rendu live, couche visible, barre produit. */
const lecture = (p) => p.evaluate(() => {
  const c = window.__concept;
  const q = (id) => document.getElementById(id);
  const vis = (el) => el && !el.classList.contains('hidden') && getComputedStyle(el).display !== 'none';
  return {
    etat: c.etatProduit(), applied: c.state.applied, mode: c.adapter.mode,
    coucheVisible: vis(q('clipA')) && q('after').width > 0,
    carte: vis(q('card')), barreSansParquet: vis(q('noscene')),
    texteBarre: vis(q('noscene')) ? q('noscene').textContent.replace(/\s+/g, ' ').trim() : null,
    actions: vis(q('noscene')) ? [...q('noscene').querySelectorAll('[data-open]')].map((b) => b.dataset.open) : [],
    analyse: c.state.roomAnalysis.status, texteAnalyse: c.state.roomAnalysis.texte,
    scene: c.state.photoScene ? { statut: c.state.photoScene.status, posee: c.state.photoScene.posee } : null,
    moteurs: (window.__moteurs || []).map((m) => m.backend),
  };
});

/** Les fonctions produit, sans relancer l'analyse. */
async function parcoursProduit(p) {
  const avant = p.__analyses;
  const r = await p.evaluate(async () => {
    const c = window.__concept;
    const att = async (fn) => { const t0 = performance.now(); while (!fn() && performance.now() - t0 < 30000) await new Promise((x) => setTimeout(x, 30)); return fn(); };
    const out = {};
    for (const [id, cle] of [['CHENF39031', 'lames'], ['POINF36005', 'pdh'], ['BTRPF39009', 'baton'], ['CHENF36014', 'lames150']]) {
      c.select(id, true);
      out[cle] = await att(() => c.state.applied.source === 'live' && c.state.applied.key.includes(id));
    }
    let rot = true;
    for (const deg of [37, 90, 315, 0]) {
      c.setOrientation(deg, false);
      rot = rot && await att(() => c.state.applied.source === 'live' && c.state.applied.key.endsWith(`|${deg}`));
    }
    out.rotation = rot;
    document.getElementById('baBtn').click();
    await new Promise((x) => setTimeout(x, 300));
    out.avantApres = c.state.ba && document.getElementById('clipA').style.clipPath.startsWith('inset(0px 0px 0px')
      && document.getElementById('tagA').textContent === 'Avant';
    document.getElementById('baBtn').click();
    c.startCompare(); await new Promise((x) => setTimeout(x, 200));
    c.select('CHENF39031', true);
    out.comparaison = await att(() => c.state.appliedB && c.state.appliedB.source === 'live')
      && await att(() => c.state.applied.source === 'live')
      && /^A — /.test(document.getElementById('tagA').textContent) && /^B — /.test(document.getElementById('tagB').textContent);
    c.startCompare(); await new Promise((x) => setTimeout(x, 300));
    await att(() => c.state.applied.source === 'live');
    return out;
  });
  r.analysesPendantProduit = p.__analyses - avant;
  return r;
}

/** Correction manuelle par de VRAIS clics : bouton de la barre, trait, Terminé. */
async function correctionManuelle(p) {
  const bouton = await p.$('#noscene [data-open="floor"], #card [data-open="floor"]');
  if (!bouton) return { possible: false };
  await bouton.click();
  await p.waitForFunction(() => window.__concept.floorEdit.actif, null, { timeout: 30000 }).catch(() => {});
  const actif = await p.evaluate(() => window.__concept.floorEdit.actif);
  if (!actif) return { possible: true, ouverte: false };
  const box = await p.$eval('#stage', (el) => { const r = el.getBoundingClientRect(); return { x: r.left, y: r.top, w: r.width, h: r.height }; });
  // Zone de sol tracée : pixels couverts de la teinte du moteur.
  const zone = () => p.evaluate(() => {
    const ov = window.__concept.adapter.pinceau.overlay(); if (!ov) return 0;
    const d = ov.canvas.getContext('2d').getImageData(0, 0, ov.width, ov.height).data;
    let n = 0; for (let i = 3; i < d.length; i += 16) if (d[i] > 0) n += 1; return n;
  });
  const z0 = await zone();
  // Un trait « ajouter au sol », vérifié, puis ANNULÉ : la preuve que l'outil
  // agit, sans laisser un trait arbitraire sur la photo de quelqu'un.
  await p.click('#floorTools [data-brush="add"]');
  await p.click('#floorTools [data-size="60"]');
  await p.mouse.move(box.x + box.w * 0.3, box.y + box.h * 0.45);
  await p.mouse.down();
  for (let k = 1; k <= 8; k += 1) await p.mouse.move(box.x + box.w * (0.3 + k * 0.05), box.y + box.h * 0.45);
  await p.mouse.up();
  const z1 = await zone();
  await p.click('#floorUndo');
  await p.click('#floorTools [data-brush="remove"]');
  await p.click('#floorTools [data-size="16"]');
  await p.mouse.move(box.x + box.w * 0.5, box.y + box.h * 0.85); await p.mouse.down(); await p.mouse.move(box.x + box.w * 0.55, box.y + box.h * 0.85); await p.mouse.up();
  const z2 = await zone();
  await p.click('#floorUndo');
  const z3 = await zone();
  const outils = { ajoute: z1 > z0, retire: z2 < z0, annule: z3 === z0 };
  await p.click('#floorDone');
  const fin = await attendreEtatFinal(p, 60000);
  return { possible: true, ouverte: true, fin, outils, ...(await lecture(p)) };
}

/* ------------------------------------------------------------ réponses simulées */
function sceneSimulee({ confiance = 0.8, statut = 'auto_render', quad = null } = {}) {
  const q = quad || [{ x: 0.3, y: 0.55 }, { x: 0.7, y: 0.55 }, { x: 1.15, y: 1.05 }, { x: -0.15, y: 1.05 }];
  return {
    schema: 'pose-parquet/analysis@2', status: 'analysis_incomplete', confidence: null, warnings: [],
    image: { width: 1600, height: 1067, aspectRatio: 1.5, megapixels: 1.7, format: 'JPEG', exifOrientationApplied: false },
    quality: {}, lens: null, sceneData: null, timings: {},
    experimental: { floor: {
      candidate: 'simulation', maskPngBase64: '', maskWidth: 1600, maskHeight: 1067, coverage: 0.3, boundary: [], timingsMs: {}, metadata: {},
      sceneData: {
        schema: 'pose-parquet/scene@1', id: 'photo', label: 'Ma pièce', source: 'ai', confidence: confiance,
        image: { width: 1600, height: 1067 }, camera: { horizon: 0.42 },
        surfaces: [{ id: 'sol', label: 'Sol', continuous: true }],
        planes: { sol: { quad: q, meters: { width: 4.2, depth: 5 } } },
        floorZones: [{ id: 'sol-1', label: 'Sol', surfaceId: 'sol', planeRef: 'sol', order: 0,
          mask: { polygon: [{ x: 0.05, y: 0.6 }, { x: 0.95, y: 0.6 }, { x: 0.99, y: 0.99 }, { x: 0.01, y: 0.99 }], holes: [] } }],
        occluders: [], light: { kind: 'photo-luma', strength: 1, blurRadius: 0.045 }, warnings: ['experimental_scene'],
      },
      sceneStatus: statut, sceneConfidence: confiance, perspective: { horizon: 0.42, marqueur: confiance }, rug: {}, sceneProvenance: {},
    } },
  };
}
async function simulerAnalyse(p, fabrique) {
  await p.route('**/v1/analyze-room', async (route) => {
    const r = await fabrique(route);
    if (r === 'abort') return route.abort('connectionrefused');
    if (r && r.http) return route.fulfill({ status: r.http, contentType: 'application/json', body: JSON.stringify(r.body || {}) });
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(r) });
  });
}
const pause = (ms) => new Promise((r) => setTimeout(r, ms));

const matrice = [];
const ligne = (cas, champs) => { matrice.push({ cas, ...champs }); };

/* ============================================================ 1. scène démo */
{
  const p = await nouvellePage();
  await ouvrir(p);
  await p.evaluate(() => window.__concept.openRoom('sejour'));
  const fin = await attendreEtatFinal(p, 90000);
  const v = await lecture(p);
  ok('scène démo : rendu live', fin === 'RENDER_READY' && v.applied.source === 'live' && v.coucheVisible, `${fin} ${v.applied.source}`);
  const prod = await parcoursProduit(p);
  ok('scène démo : produits, motifs, largeurs, rotation, avant/après, comparaison',
    prod.lames && prod.pdh && prod.baton && prod.lames150 && prod.rotation && prod.avantApres && prod.comparaison, JSON.stringify(prod));
  ligne('démo séjour', { analyse: 'n/a', sol: 'calibré', geometrie: 'calibrée', decision: 'démo', rendu: v.applied.source, manuel: 'n/a', produit: prod.lames && prod.pdh && prod.baton ? 'PASS' : 'FAIL', rotation: prod.rotation ? 'PASS' : 'FAIL', comparaison: prod.comparaison && prod.avantApres ? 'PASS' : 'FAIL', resultat: fin === 'RENDER_READY' ? 'AUTO_RENDER_SUCCESS' : `BROKEN(${fin})` });
  ok('scène démo : 0 erreur console', p.__erreurs.length === 0, p.__erreurs.join(' | '));
  await p.context().close();
}

/* ============================================================ 2. photo simulée : auto */
{
  const p = await nouvellePage();
  await simulerAnalyse(p, () => sceneSimulee());
  await ouvrir(p);
  await importer(p, DEMO_PHOTO);
  const fin = await attendreEtatFinal(p);
  const v = await lecture(p);
  ok('photo auto : rendu live posé', fin === 'RENDER_READY' && v.coucheVisible && v.carte, `${fin}`);
  ok('photo auto : une seule analyse par import', p.__analyses === 1, p.__analyses);
  const prod = await parcoursProduit(p);
  ok('photo auto : 0 analyse au changement de produit, d\'angle, à la comparaison', prod.analysesPendantProduit === 0, prod.analysesPendantProduit);
  ok('photo auto : fonctions produit', prod.lames && prod.pdh && prod.baton && prod.rotation && prod.avantApres && prod.comparaison, JSON.stringify(prod));
  ok('photo auto : 0 erreur console', p.__erreurs.length === 0, p.__erreurs.join(' | '));
  await p.context().close();
}

/* ============================================================ 3. photo simulée : manuel */
{
  const p = await nouvellePage();
  await simulerAnalyse(p, () => sceneSimulee({ confiance: 0.4, statut: 'needs_manual_adjustment' }));
  await ouvrir(p);
  await importer(p, DEMO_PHOTO);
  const fin = await attendreEtatFinal(p);
  const v = await lecture(p);
  ok('photo à ajuster : AUCUN rendu automatique', fin === 'NEEDS_MANUAL_ADJUSTMENT' && !v.coucheVisible && !v.applied.source, `${fin} couche=${v.coucheVisible}`);
  ok('photo à ajuster : message et actions', v.barreSansParquet && v.actions.includes('floor') && /approximativement/.test(v.texteBarre || ''), v.texteBarre);
  const m = await correctionManuelle(p);
  ok('photo à ajuster : « Ajuster le sol » au clic → ajouter, retirer, annuler, taille → Terminé → parquet live', m.ouverte && m.outils.ajoute && m.outils.retire && m.outils.annule && m.fin === 'RENDER_READY' && m.applied.source === 'live' && m.coucheVisible, JSON.stringify({ fin: m.fin, src: m.applied && m.applied.source, outils: m.outils }));
  const prod = await parcoursProduit(p);
  ok('photo à ajuster : toutes les fonctions après correction', prod.lames && prod.baton && prod.rotation && prod.avantApres && prod.comparaison, JSON.stringify(prod));
  ok('photo à ajuster : 0 erreur console', p.__erreurs.length === 0, p.__erreurs.join(' | '));
  await p.context().close();
}

/* ============================================================ 4. scène invalide */
{
  const p = await nouvellePage();
  const deg = [{ x: 0.5, y: 0.5 }, { x: 0.5, y: 0.5 }, { x: 0.5, y: 0.5 }, { x: 0.5, y: 0.5 }];
  await simulerAnalyse(p, () => sceneSimulee({ quad: deg }));
  await ouvrir(p);
  await importer(p, DEMO_PHOTO);
  const fin = await attendreEtatFinal(p);
  const v = await lecture(p);
  ok('scène invalide annoncée auto : AUCUN rendu, correction proposée', fin === 'NEEDS_MANUAL_ADJUSTMENT' && !v.coucheVisible && v.actions.includes('floor'), `${fin} ${v.texteBarre}`);
  const m = await correctionManuelle(p);
  ok('scène invalide : tracé manuel → parquet live', m.fin === 'RENDER_READY' && m.coucheVisible, m.fin);
  ok('scène invalide : 0 erreur console', p.__erreurs.length === 0, p.__erreurs.join(' | '));
  await p.context().close();
}

/* ============================================================ 5. réponse périmée */
{
  const p = await nouvellePage();
  let n = 0;
  await simulerAnalyse(p, async () => {
    n += 1;
    const moi = n;
    if (moi === 1) await pause(2500); // A, lente
    if (moi === 2) await pause(1200); // B, moyenne
    return sceneSimulee({ confiance: [0, 0.71, 0.72, 0.73][moi] });
  });
  await ouvrir(p);
  await importer(p, DEMO_PHOTO);
  await pause(150);
  await importer(p, DEMO_PHOTO);
  await pause(150);
  await importer(p, DEMO_PHOTO);
  const fin = await attendreEtatFinal(p);
  await pause(3000); // laisser arriver les réponses de A et B
  const conf = await p.evaluate(() => window.__concept.state.photoScene && window.__concept.state.photoScene.confidence);
  ok('A puis B puis C : seul C est appliqué', fin === 'RENDER_READY' && conf === 0.73, `${fin} confiance=${conf}`);
  const blobs = await p.evaluate(() => window.__blobsVivants());
  ok('imports successifs : anciennes URL de photo révoquées', blobs <= 1, `${blobs} vivantes`);
  const avant = await p.evaluate(() => ({ w: window.__workers, e: window.__ecouteurs }));
  for (let k = 0; k < 3; k += 1) { await importer(p, DEMO_PHOTO); await attendreEtatFinal(p); }
  const apres = await p.evaluate(() => ({ w: window.__workers, e: window.__ecouteurs, blobs: window.__blobsVivants() }));
  ok('trois imports de plus : aucun worker ni écouteur global ajouté, une seule URL vivante',
    apres.w === avant.w && apres.e === avant.e && apres.blobs <= 1, `workers ${avant.w}→${apres.w} · écouteurs ${avant.e}→${apres.e} · URL ${apres.blobs}`);
  ok('réponse périmée : 0 erreur console', p.__erreurs.length === 0, p.__erreurs.join(' | '));
  await p.context().close();
}

/* ============================================================ 6. import → pièce démo → retour → nouvel import */
{
  const p = await nouvellePage();
  await simulerAnalyse(p, async () => { await pause(1500); return sceneSimulee({ confiance: 0.66 }); });
  await ouvrir(p);
  await importer(p, DEMO_PHOTO);
  await pause(300);
  await p.evaluate(() => window.__concept.openRoom('chambre'));
  const demo = await attendreEtatFinal(p, 60000);
  await pause(2000);
  const vDemo = await lecture(p);
  ok('analyse en cours puis pièce démo : la réponse ne touche pas la démo', demo === 'RENDER_READY' && !vDemo.scene && vDemo.applied.key.startsWith('chambre'), `${demo} ${vDemo.applied.key}`);
  await importer(p, DEMO_PHOTO);
  const fin = await attendreEtatFinal(p);
  ok('… puis nouvel import : rendu propre', fin === 'RENDER_READY', fin);
  await p.context().close();
}

/* ============================================================ 7. panne, reprise */
{
  const p = await nouvellePage();
  let panne = true;
  await simulerAnalyse(p, () => (panne ? 'abort' : sceneSimulee()));
  await ouvrir(p);
  await importer(p, DEMO_PHOTO);
  const fin = await attendreEtatFinal(p);
  const v = await lecture(p);
  ok('service injoignable : photo gardée, message, Réessayer et Tracer', fin === 'ANALYSIS_UNAVAILABLE' && v.actions.includes('retry') && v.actions.includes('floor') && /injoignable/.test(v.texteBarre || ''), `${fin} ${v.texteBarre}`);
  if (CAPTURES) await p.screenshot({ path: path.join(OUT, 'backend-down.jpg'), type: 'jpeg', quality: 88 });
  panne = false;
  await p.click('#noscene [data-open="retry"]');
  const fin2 = await attendreEtatFinal(p);
  ok('service revenu : « Réessayer » → parquet, sans recharger la page', fin2 === 'RENDER_READY', fin2);
  await p.context().close();
}

/* ============================================================ 8. délai dépassé, erreur serveur, refus */
{
  const p = await nouvellePage();
  await simulerAnalyse(p, async () => { await pause(4000); return sceneSimulee(); });
  await ouvrir(p, '&atimeout=1500');
  await importer(p, DEMO_PHOTO);
  const fin = await attendreEtatFinal(p, 20000);
  const v = await lecture(p);
  ok('délai dépassé : état distinct, message, pas de spinner', fin === 'ANALYSIS_UNAVAILABLE' && v.analyse === 'timeout' && /trop de temps/.test(v.texteBarre || ''), `${fin} ${v.analyse}`);
  await p.context().close();
}
for (const [code, attendu, motif] of [[500, 'error', /échoué/], [422, 'rejected', /décodée|analysée/]]) {
  const p = await nouvellePage();
  await simulerAnalyse(p, () => ({ http: code, body: { detail: { code: 'x', message: 'x' } } }));
  await ouvrir(p);
  await importer(p, DEMO_PHOTO);
  const fin = await attendreEtatFinal(p);
  const v = await lecture(p);
  ok(`HTTP ${code} : état ${attendu}, photo gardée, tracé possible`, fin === 'ANALYSIS_ERROR' && v.analyse === attendu && motif.test(v.texteBarre || '') && v.actions.includes('floor'), `${fin} ${v.analyse} ${v.texteBarre}`);
  await p.context().close();
}

/* ============================================================ 9. préparation du modèle */
{
  const p = await nouvellePage();
  let healthCalls = 0;
  await p.route('**/health', (r) => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ status: 'ok', service: 'pose-parquet-ai', experimentalFloor: ++healthCalls < 3 ? 'loading' : 'ready' }) }));
  await simulerAnalyse(p, async () => { await pause(2500); return sceneSimulee(); });
  await ouvrir(p);
  await importer(p, DEMO_PHOTO);
  await pause(800);
  const pendant = await lecture(p);
  ok('modèle en préparation : « Préparation de l’analyse… », photo visible', pendant.etat === 'ANALYSIS_WAITING' && /Préparation/.test(pendant.texteBarre || ''), `${pendant.etat} ${pendant.texteBarre}`);
  ok('aucune photo envoyée pendant le chargement', p.__analyses === 0);
  await p.evaluate(() => { const c = window.__concept; c.select('CHENF39031', true); c.setOrientation(37, false); });
  const fin = await attendreEtatFinal(p);
  ok('… puis rendu une fois prêt', fin === 'RENDER_READY', fin);
  ok('choisir et tourner pendant la préparation conserve l’analyse', await p.evaluate(() => window.__concept.state.applied.key.includes('CHENF39031') && window.__concept.state.orientationDeg === 37));
  await p.context().close();
}

/* ============================================================ 10. mode expérimental éteint (réponse sans bloc) */
{
  const p = await nouvellePage();
  await simulerAnalyse(p, () => { const r = sceneSimulee(); delete r.experimental; return r; });
  await ouvrir(p);
  await importer(p, DEMO_PHOTO);
  const fin = await attendreEtatFinal(p);
  const v = await lecture(p);
  ok('sans détection expérimentale : pas de parquet inventé, tracé proposé', fin === 'NEEDS_MANUAL_ADJUSTMENT' && !v.coucheVisible && /pas active/.test(v.texteBarre || ''), `${fin} ${v.texteBarre}`);
  await p.context().close();
}

/* ============================================================ 11. moteur Canvas (WebGL indisponible) */
{
  const p = await nouvellePage({ sansWebGL: true });
  await simulerAnalyse(p, () => sceneSimulee());
  await ouvrir(p);
  await p.evaluate(() => window.__concept.openRoom('sejour'));
  const demo = await attendreEtatFinal(p, 120000);
  await importer(p, DEMO_PHOTO);
  const fin = await attendreEtatFinal(p, 120000);
  const v = await lecture(p);
  ok('WebGL indisponible : bascule réelle sur Canvas', v.moteurs.length > 0 && v.moteurs.every((m) => m === 'canvas'), v.moteurs.join(','));
  ok('Canvas : démo et photo rendues', demo === 'RENDER_READY' && fin === 'RENDER_READY' && v.coucheVisible, `${demo} ${fin}`);
  const r = await p.evaluate(async () => {
    const c = window.__concept; c.select('BTRPF39009', true);
    const t0 = performance.now(); while (!(c.state.applied.source === 'live' && c.state.applied.key.includes('BTRPF39009')) && performance.now() - t0 < 60000) await new Promise((x) => setTimeout(x, 50));
    return c.state.applied.source;
  });
  ok('Canvas : bâton rompu rendu', r === 'live', r);
  if (CAPTURES) await p.screenshot({ path: path.join(OUT, 'canvas-fallback.jpg'), type: 'jpeg', quality: 88 });
  ok('Canvas : 0 erreur console', p.__erreurs.length === 0, p.__erreurs.join(' | '));
  await p.context().close();
}

/* ============================================================ 12. rechargement */
{
  const p = await nouvellePage();
  await simulerAnalyse(p, () => sceneSimulee());
  await ouvrir(p);
  await importer(p, DEMO_PHOTO);
  await attendreEtatFinal(p);
  await p.evaluate(() => { const c = window.__concept; if (!c.state.favourites.has('CHENF39031')) c.toggleFav('CHENF39031'); });
  await p.reload({ waitUntil: 'load' });
  await p.waitForFunction(() => window.__concept);
  const r = await p.evaluate(() => ({ fav: window.__concept.state.favourites.has('CHENF39031'), source: window.__concept.state.source, etat: window.__concept.etatProduit() }));
  ok('rechargement : favoris gardés, aucune photo restaurée, état neuf', r.fav && r.source === null && r.etat === 'IDLE', JSON.stringify(r));
  ok('rechargement : 0 erreur console', p.__erreurs.length === 0, p.__erreurs.join(' | '));
  await p.context().close();
}

/* ============================================================ 13. mobile et desktop */
for (const [l, h] of [[320, 640], [360, 780], [375, 812], [390, 844], [430, 932], [1280, 800], [1440, 900], [1920, 1080]]) {
  const p = await nouvellePage({ largeur: l, hauteur: h });
  await simulerAnalyse(p, () => sceneSimulee({ confiance: 0.4, statut: 'needs_manual_adjustment' }));
  await ouvrir(p);
  await importer(p, DEMO_PHOTO);
  const etatManuel = await attendreEtatFinal(p);
  const m = await correctionManuelle(p);
  const r = await p.evaluate(async () => {
    const c = window.__concept;
    const deborde = () => document.documentElement.scrollWidth > innerWidth + 1;
    const recouverts = (sel) => [...document.querySelectorAll(sel)].filter((b) => b.offsetParent).filter((b) => {
      const x = b.getBoundingClientRect(); if (x.right < 0 || x.left > innerWidth || x.bottom < 0 || x.top > innerHeight) return false;
      const e = document.elementFromPoint(x.left + x.width / 2, x.top + x.height / 2); return !(e === b || b.contains(e));
    }).map((b) => b.dataset.open || b.id || b.textContent.trim().slice(0, 12));
    const out = { debordeRepos: deborde(), recouvertsRepos: recouverts('#card button, #zoombar button, #tools button') };
    c.openCus(); await new Promise((x) => setTimeout(x, 900));
    // Part de la scène (sous le bandeau) où la photo est visible au-dessus du tiroir.
    const st = document.getElementById('stage').getBoundingClientRect();
    const dw = document.querySelector('.dw').getBoundingClientRect();
    const photo = document.getElementById('after').getBoundingClientRect();
    const hautVisible = Math.max(st.top, photo.top); const basVisible = Math.min(innerWidth >= 1024 ? st.bottom : dw.top, photo.bottom);
    out.sceneVisiblePersonnaliser = Math.max(0, basVisible - hautVisible) / st.height;
    out.solVisiblePersonnaliser = innerWidth >= 1024 ? 'à côté du panneau' : (photo.bottom > dw.top ? 'sous le tiroir' : 'au-dessus du tiroir');
    out.debordePersonnaliser = deborde();
    out.tiroirFermable = Boolean(document.querySelector('.dw:not(.hidden) .close'));
    c.closeAll(); await new Promise((x) => setTimeout(x, 500));
    out.etat = c.etatProduit();
    return out;
  });
  const okMobile = etatManuel === 'NEEDS_MANUAL_ADJUSTMENT' && m.fin === 'RENDER_READY' && !r.debordeRepos && !r.debordePersonnaliser
    && r.recouvertsRepos.length === 0 && r.tiroirFermable && (l > 700 || r.sceneVisiblePersonnaliser >= 0.3);
  ok(`${l} × ${h} : manuel → tracé → rendu, Personnaliser, aucun débordement ni contrôle recouvert`, okMobile,
    `scène visible en Personnaliser ${(100 * r.sceneVisiblePersonnaliser).toFixed(0)} % · recouverts ${r.recouvertsRepos.join(',') || 0}`);
  if (CAPTURES && l === 390) {
    await p.screenshot({ path: path.join(OUT, 'manual-corrected-mobile.jpg'), type: 'jpeg', quality: 88 });
  }
  await p.context().close();
}

/* ============================================================ 14. photos réelles */
const reelles = existsSync(PRIVE) ? readdirSync(PRIVE) : [];
for (const nom of PHOTOS_REELLES) {
  const fichier = path.join(PRIVE, `${nom}.jpg`);
  if (!reelles.includes(`${nom}.jpg`) || !experimental || process.env.PPAI_REELLES === '0') {
    ligne(nom, { analyse: 'NON EXÉCUTÉE', sol: '—', geometrie: '—', decision: '—', rendu: '—', manuel: '—', produit: '—', rotation: '—', comparaison: '—', resultat: experimental ? 'photo absente' : 'mode expérimental éteint' });
    continue;
  }
  const p = await nouvellePage();
  await ouvrir(p);
  const t0 = Date.now();
  await importer(p, fichier);
  const fin = await attendreEtatFinal(p);
  const ms = Date.now() - t0;
  const info = await p.evaluate(() => {
    const c = window.__concept; const a = c.state.roomAnalysis.analysis;
    const f = a && a.experimental && a.experimental.floor;
    const pr = f && f.perspective;
    return f ? { couverture: f.coverage, statut: f.sceneStatus, confiance: f.sceneConfidence,
      decision: f.sceneProvenance && f.sceneProvenance.decision ? f.sceneProvenance.decision.reasons : null,
      horizon: pr && pr.horizon, metres: pr && `${pr.metersWidth}×${pr.metersDepth}`, plausible: pr && pr.plausibility ? pr.plausibility.ok : null,
      lameProche: pr && pr.plausibility ? pr.plausibility.projectedPlankWidthPx.near : null } : null;
  });
  const v = await lecture(p);
  let manuel = 'non requis';
  let finale = fin;
  if (fin === 'NEEDS_MANUAL_ADJUSTMENT' || fin === 'ANALYSIS_ERROR' || fin === 'ANALYSIS_UNAVAILABLE') {
    ok(`${nom} : aucun rendu automatique tant qu'à ajuster`, !v.coucheVisible && !v.applied.source, v.applied.source);
    if (CAPTURES && nom === 'couloir') await p.screenshot({ path: path.join(OUT, 'manual-adjustment-desktop.jpg'), type: 'jpeg', quality: 88 });
    const m = await correctionManuelle(p);
    manuel = m.fin === 'RENDER_READY' ? 'PASS' : `FAIL(${m.fin})`;
    finale = m.fin;
    if (CAPTURES && nom === 'couloir') await p.screenshot({ path: path.join(OUT, 'manual-corrected-desktop.jpg'), type: 'jpeg', quality: 88 });
  } else if (CAPTURES && nom === 'chambre') {
    await p.screenshot({ path: path.join(OUT, 'auto-success-desktop.jpg'), type: 'jpeg', quality: 88 });
  }
  const prod = finale === 'RENDER_READY' ? await parcoursProduit(p) : null;
  const resultat = fin === 'RENDER_READY' && prod ? 'AUTO_RENDER_SUCCESS'
    : manuel === 'PASS' && prod ? 'NEEDS_MANUAL_ADJUSTMENT'
      : fin === 'ANALYSIS_ERROR' || fin === 'ANALYSIS_UNAVAILABLE' ? 'ANALYSIS_FAILED_GRACEFULLY' : `BROKEN(${fin})`;
  ok(`${nom} : état produit valide`, !resultat.startsWith('BROKEN') && p.__erreurs.length === 0, `${resultat} · ${ms} ms${p.__erreurs.length ? ' · ' + p.__erreurs.join(' | ') : ''}`);
  if (prod) ok(`${nom} : fonctions produit sans réanalyse`, prod.lames && prod.pdh && prod.baton && prod.rotation && prod.avantApres && prod.comparaison && prod.analysesPendantProduit === 0, JSON.stringify(prod));
  ligne(nom, {
    analyse: `${info ? info.statut : v.analyse} (conf ${info ? info.confiance : '—'}) · ${Math.round(ms / 1000)} s`,
    sol: info ? `couverture ${(100 * info.couverture).toFixed(0)} %` : '—',
    geometrie: info ? `horizon ${info.horizon} · ${info.metres} m · lame proche ${info.lameProche} px · plausible ${info.plausible}` : '—',
    decision: info ? (info.decision && info.decision.length ? info.decision.join(', ') : 'tous contrôles OK') : '—',
    rendu: fin === 'RENDER_READY' ? 'live auto' : (manuel === 'PASS' ? 'live après tracé' : 'aucun'),
    manuel,
    produit: prod ? (prod.lames && prod.pdh && prod.baton ? 'PASS' : 'FAIL') : '—',
    rotation: prod ? (prod.rotation ? 'PASS' : 'FAIL') : '—',
    comparaison: prod ? (prod.comparaison && prod.avantApres ? 'PASS' : 'FAIL') : '—',
    resultat,
  });
  await p.context().close();
}
if (experimental && reelles.includes('chambre.jpg') && reelles.includes('couloir.jpg') && CAPTURES) {
  for (const [nom, fichierSortie] of [['chambre', 'auto-success-mobile.jpg'], ['couloir', 'manual-adjustment-mobile.jpg']]) {
    const p = await nouvellePage({ largeur: 390, hauteur: 844 });
    await ouvrir(p);
    await importer(p, path.join(PRIVE, `${nom}.jpg`));
    await attendreEtatFinal(p);
    await p.screenshot({ path: path.join(OUT, fichierSortie), type: 'jpeg', quality: 88 });
    await p.context().close();
  }
}

await navigateur.close();

/* ------------------------------------------------------------ matrice */
const colonnes = ['cas', 'analyse', 'sol', 'geometrie', 'decision', 'rendu', 'manuel', 'produit', 'rotation', 'comparaison', 'resultat'];
const md = [`| ${colonnes.join(' | ')} |`, `|${colonnes.map(() => '---').join('|')}|`,
  ...matrice.map((l) => `| ${colonnes.map((c) => String(l[c] ?? '—').replace(/\|/g, '/')).join(' | ')} |`)].join('\n');
writeFileSync(path.join(OUT, 'matrix.json'), JSON.stringify({ base: BASE, experimental: sante.experimentalFloor || null, resultats, matrice }, null, 1));
writeFileSync(path.join(OUT, 'matrix.md'), md + '\n');
console.log('\n' + md);
console.log(echecs ? `\n${echecs} ECHEC(S)` : '\nAUCUN ECHEC');
process.exit(echecs ? 1 : 0);
