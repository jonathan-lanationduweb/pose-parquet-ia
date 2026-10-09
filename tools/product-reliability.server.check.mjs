/*
  Batterie de fiabilité — VRAI SERVEUR (MISSION STABILISATION).

      node tools/product-reliability.server.check.mjs

  Démarre lui-même le service (port 8150, .venv du dépôt), et vérifie ce qu'aucune
  simulation ne prouve : démarrage à froid avec le modèle en chargement, panne
  réelle pendant un import, reprise par « Réessayer » sans recharger la page,
  mode expérimental éteint. Utilise `datasets/private-real/chambre.jpg` si elle
  existe, sinon la photo de démonstration du séjour. `playwright-core` comme
  pour product-reliability.check.mjs (PPAI_PLAYWRIGHT_CORE si besoin).
*/
import { spawn } from 'node:child_process';
import { existsSync, mkdirSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';
const req = createRequire(import.meta.url);
async function charger() {
  try { return await import('playwright-core'); } catch { /* suite */ }
  if (process.env.PPAI_PLAYWRIGHT_CORE) return req(process.env.PPAI_PLAYWRIGHT_CORE);
  console.error('playwright-core introuvable (PPAI_PLAYWRIGHT_CORE).'); process.exit(2);
}
const pwm = await charger();
const chromium = pwm.chromium || pwm.default.chromium;
const ROOT = process.cwd();
const PYTHON = existsSync(path.join(ROOT, '.venv/Scripts/python.exe')) ? path.join(ROOT, '.venv/Scripts/python.exe') : path.join(ROOT, '.venv/bin/python');
const PORT = 8150;
const BASE = `http://127.0.0.1:${PORT}`;
const PRIVEE = path.join(ROOT, 'datasets/private-real/chambre.jpg');
const PHOTO = existsSync(PRIVEE) ? PRIVEE : path.join(ROOT, 'web/assets/images/room-sejour.jpg');
const OUT = path.join(ROOT, 'review', 'product-rework');
mkdirSync(OUT, {recursive:true});
const res = [];
const ok = (n, c, d) => { res.push([c, n, d]); console.log(`${c ? 'OK   ' : 'ECHEC'} ${n}  -> ${d}`); };

function demarrer(experimental) {
  const env = { ...process.env, PPAI_DEV_SERVE_STATIC: '1', PPAI_EXPERIMENTAL_FLOOR: experimental ? '1' : '0', PPAI_EXPERIMENTAL_FLOOR_CANDIDATE: 'oneformer' };
  const args = experimental ? ['-m', 'scripts.product_dev', '--port', String(PORT)] : ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(PORT), '--log-level', 'warning'];
  const p = spawn(PYTHON, args, { cwd: ROOT, env, stdio: 'ignore' });
  return p;
}
async function attendreSante(etatVoulu = null, ms = 60000) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) {
    try { const j = await (await fetch(`${BASE}/health`)).json(); if (!etatVoulu || j.experimentalFloor === etatVoulu) return { j, ms: Date.now() - t0 }; } catch { /* attente */ }
    await new Promise((r) => setTimeout(r, 250));
  }
  return null;
}
async function etatFinal(p, ms = 300000) {
  const t0 = Date.now(); let dernier; let depuis = Date.now(); const vus = new Set();
  while (Date.now() - t0 < ms) {
    const e = await p.evaluate(() => window.__concept.etatProduit()); vus.add(e);
    if (e !== dernier) { dernier = e; depuis = Date.now(); }
    if (!['PHOTO_SELECTED', 'ANALYSIS_WAITING', 'ANALYZING', 'RENDER_PENDING'].includes(e) && Date.now() - depuis > 700) return { e, vus: [...vus], ms: Date.now() - t0 };
    await new Promise((r) => setTimeout(r, 200));
  }
  return { e: `STUCK:${dernier}`, vus: [...vus] };
}
const nav = await chromium.launch({ channel: 'chrome', headless: true });

// 1. Démarrage à froid : serveur neuf, navigateur neuf, import pendant le chargement du modèle.
let srv = demarrer(true);
const boot = await attendreSante();
ok('démarrage : /health répond pendant le chargement du modèle', boot && boot.j.experimentalFloor === 'loading', boot && `${boot.ms} ms, ${boot.j.experimentalFloor}`);
let ctx = await nav.newContext({ viewport: { width: 1440, height: 900 } });
let p = await ctx.newPage(); const erreurs = []; p.on('pageerror', (e) => erreurs.push(String(e)));
await p.goto(`${BASE}/tools/product-concept.html?dev=1`); await p.waitForFunction(() => window.__concept);
await p.setInputFiles('#file', PHOTO);
const f1 = await etatFinal(p);
ok('import pendant le chargement : « Préparation » puis rendu, sans recharger', f1.vus.includes('ANALYSIS_WAITING') && f1.e === 'RENDER_READY', `${f1.vus.join('>')} ${f1.e} ${Math.round(f1.ms / 1000)} s`);

await p.screenshot({path:path.join(OUT,'desktop-1440-upload-result.jpg'),type:'jpeg',quality:88});

// Explicit model failure stays distinct from an offline backend and offers recovery.
let analysisRequests=0;
p.on('request',r=>{if(r.url().includes('/v1/analyze-room'))analysisRequests+=1;});
await p.route('**/health',r=>r.fulfill({status:200,contentType:'application/json',body:JSON.stringify({status:'ok',service:'pose-parquet-ai',experimentalFloor:'error'})}));
await p.setInputFiles('#file',PHOTO);const modelError=await etatFinal(p,30000);
const backendState=await p.evaluate(()=>window.__concept.state.roomAnalysis.backendState);
ok('MODEL_ERROR : état distinct et aucune photo envoyée au modèle défaillant',backendState==='MODEL_ERROR'&&analysisRequests===0,backendState);
await p.unroute('**/health');

// 2. Panne réelle : le serveur s'arrête, nouvel import.
srv.kill(); await new Promise((r) => setTimeout(r, 1500));
await p.setInputFiles('#file', PHOTO);
const f2 = await etatFinal(p, 30000);
const t2 = await p.evaluate(() => document.getElementById('noscene').textContent.replace(/\s+/g, ' '));
ok('serveur arrêté : photo gardée, message, pas de spinner', f2.e === 'ANALYSIS_UNAVAILABLE' && /indisponible|injoignable/.test(t2), `${f2.e} · ${t2.slice(0, 90)}`);

// 3. Reprise : le serveur revient, « Réessayer » sans recharger la page.
srv = demarrer(true);
await attendreSante('ready', 400000);
await p.click('#noscene [data-open="retry"]');
const f3 = await etatFinal(p);
ok('serveur relancé : « Réessayer » → parquet, sans rechargement', f3.e === 'RENDER_READY', f3.e);
ok('0 erreur de page', erreurs.length === 0, erreurs.join(' | '));
await ctx.close();

// Real mobile photo and an actual manual brush stroke, while the model is warm.
ctx = await nav.newContext({viewport:{width:390,height:844}});
p = await ctx.newPage();
await p.goto(`${BASE}/tools/product-concept.html`);await p.waitForFunction(()=>window.__concept);
const couloir = path.join(ROOT,'datasets/private-real/couloir.jpg');
await p.setInputFiles('#file',existsSync(couloir)?couloir:PHOTO);
await p.waitForFunction(()=>window.__concept.state.source==='uploaded');
await p.screenshot({path:path.join(OUT,'mobile-390-upload.jpg'),type:'jpeg',quality:88});
await etatFinal(p);
await p.evaluate(()=>window.__concept.floorEditStart());
await p.waitForFunction(()=>window.__concept.floorEdit.actif);
const st=await p.locator('#stage').boundingBox();
await p.mouse.move(st.x+st.width*.45,st.y+st.height*.7);await p.mouse.down();
await p.mouse.move(st.x+st.width*.6,st.y+st.height*.74,{steps:8});await p.mouse.up();
await p.screenshot({path:path.join(OUT,'mobile-390-manual.jpg'),type:'jpeg',quality:88});
await p.click('#floorDone');const mobile=await etatFinal(p);
ok('mobile réel : pinceau puis Terminé produit le parquet',mobile.e==='RENDER_READY',mobile.e);
await p.screenshot({path:path.join(OUT,'mobile-390-upload-result.jpg'),type:'jpeg',quality:88});
await ctx.close();srv.kill();await new Promise(r=>setTimeout(r,1500));

// 4. Mode expérimental éteint, vraie photo.
srv = demarrer(false);
await attendreSante();
ctx = await nav.newContext({ viewport: { width: 1440, height: 900 } });
p = await ctx.newPage();
await p.goto(`${BASE}/tools/product-concept.html?dev=1`); await p.waitForFunction(() => window.__concept);
await p.setInputFiles('#file', PHOTO);
const f4 = await etatFinal(p, 60000);
const v4 = await p.evaluate(() => ({ couche: document.getElementById('after').width, texte: document.getElementById('noscene').textContent.replace(/\s+/g, ' ') }));
ok('mode expérimental éteint : aucun parquet inventé, tracé proposé', f4.e === 'NEEDS_MANUAL_ADJUSTMENT' && /pas active/.test(v4.texte), `${f4.e} · ${v4.texte.slice(0, 90)}`);
await p.click('#noscene [data-open="floor"]');
await p.waitForFunction(() => window.__concept.floorEdit.actif, null, { timeout: 30000 });
await p.click('#floorDone');
const f5 = await etatFinal(p, 60000);
ok('… tracé manuel → parquet live', f5.e === 'RENDER_READY', f5.e);
await ctx.close(); srv.kill();
await nav.close();
writeFileSync(path.join(OUT,'cold-start.json'),JSON.stringify(res,null,2));
console.log(res.every((r) => r[0]) ? 'AUCUN ECHEC' : `${res.filter((r) => !r[0]).length} ECHEC(S)`);
process.exit(res.every((r) => r[0]) ? 0 : 1);
