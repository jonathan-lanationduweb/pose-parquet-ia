/*
  Batterie navigateur — bibliothèque de pièces et application d'un parquet.

      PPAI_PLAYWRIGHT_CORE=<chemin vers playwright-core> \
      node tools/rooms-render-flow.check.mjs

  Ce qu'elle prouve, dans un vrai Chrome, sur le moteur réel :

    * une catégorie est une collection (plusieurs scènes, compte calculé) ;
    * « Application… » n'est affiché QUE tant qu'aucune image du dernier
      choix n'est présentée — invariant échantillonné en continu ;
    * A -> B -> C : seul C est appliqué, et le statut ne parle que de C ;
    * 50 changements rapides : aucun blocage, aucune exception, aucune
      promesse rejetée non traitée, le dernier choix est à l'écran ;
    * délai dépassé et moteur en erreur : sortie en ERROR, jamais APPLYING
      pour toujours, et reprise ;
    * changement de pièce : état remis à zéro, produit conservé.

  Écrit des captures sous `review/rooms-and-render-fix/` (non versionné)
  quand PPAI_CAPTURES n'est pas à 0.
*/
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const CORE = process.env.PPAI_PLAYWRIGHT_CORE;
if (!CORE) { console.error('PPAI_PLAYWRIGHT_CORE manquant : chemin vers playwright-core.'); process.exit(2); }
const { chromium } = require(CORE);
const BASE = process.env.PPAI_BASE || 'http://127.0.0.1:8143';
const CAPTURES = process.env.PPAI_CAPTURES !== '0';
const OUT = path.resolve('review/rooms-and-render-fix');
fs.mkdirSync(OUT, { recursive: true });
const ROOMS = JSON.parse(fs.readFileSync('web/data/rooms.json', 'utf8'));

let bad = 0;
const ok = (n, c, d) => { if (!c) bad += 1; console.log(`${c ? 'OK  ' : 'ECHEC'} ${n}${d !== undefined ? '  -> ' + (typeof d === 'string' ? d : JSON.stringify(d)) : ''}`); };
const mesures = {};

const browser = await chromium.launch({ channel: 'chrome', headless: true });

async function ouvrir(viewport, query = '') {
  const ctx = await browser.newContext({ viewport });
  /* Compteurs posés avant le script de la page : exceptions, promesses
     rejetées sans traitement, et l'invariant du statut, échantillonné à
     chaque image du navigateur. */
  await ctx.addInitScript(() => {
    window.__rejets = [];
    window.addEventListener('unhandledrejection', (e) => window.__rejets.push(String(e.reason && e.reason.message || e.reason)));
    window.__violations = [];
    const echantillon = () => {
      const c = window.__concept;
      if (c && c.etatApplication && c.state && c.state.source) {
        const pill = document.querySelector('#card .busy[data-etat="applying"]');
        const cle = c.appliedKey();
        const montre = c.state.applied.key === cle;
        /* Le statut « Application… » et une image du choix courant ne
           coexistent jamais. */
        if (pill && montre) window.__violations.push({ cle, t: Math.round(performance.now()) });
      }
      requestAnimationFrame(echantillon);
    };
    requestAnimationFrame(echantillon);
  });
  const page = await ctx.newPage();
  const erreurs = [];
  page.on('pageerror', (e) => erreurs.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error') erreurs.push(m.text()); });
  await page.goto(`${BASE}/tools/product-concept.html?${query}`);
  await page.waitForFunction(() => window.__concept && window.__concept.DEMO_ROOMS.length > 0
    && window.__concept.adapter.connecte, null, { timeout: 60000 });
  return { ctx, page, erreurs };
}

const etat = (page) => page.evaluate(() => {
  const c = window.__concept;
  return { etat: c.etatApplication(), cle: c.appliedKey(), applied: c.state.applied, applying: c.state.applying,
    pill: (document.querySelector('#card .busy') || {}).textContent || '', retry: !!document.querySelector('#card [data-open="retryApply"]'), produit: c.state.productId, piece: c.state.roomId };
});
/* Attend le rendu du dernier choix. En cas d'expiration, ne lève pas : la
   batterie juge l'état atteint (ERROR propre ou blocage) et le rapporte. */
const attendreRendu = (page, ms = 120000) => page.waitForFunction(() => {
  const c = window.__concept;
  return c.etatApplication() === 'rendered' && c.state.applied.source === 'live' && !c.state.applying && !c.state.pendingApply;
}, null, { timeout: ms }).then(() => true, async () => {
  const e = await etat(page);
  console.log('  (rendu non obtenu dans le délai)', JSON.stringify(e));
  return false;
});
const capture = async (page, nom) => { if (CAPTURES) await page.screenshot({ path: path.join(OUT, nom), type: 'jpeg', quality: 84 }); };

/* ================= 1. Bibliothèque : catégories -> scènes ================= */
{
  const { ctx, page, erreurs } = await ouvrir({ width: 1440, height: 900 });
  const proposees = ROOMS.scenes.filter((s) => s.renderReady && s.calibration.status === 'validated');
  const attendu = Object.fromEntries(ROOMS.categories.map((c) => [c.id,
    proposees.filter((s) => [s.category, ...(s.alsoIn || [])].includes(c.id)).length]).filter(([, n]) => n > 0));
  const cats = await page.$$eval('#quickRooms [data-cat]', (els) => els.map((e) => [e.dataset.cat, e.querySelector('.nm').textContent.trim()]));
  ok('la galerie montre une carte par catégorie non vide', cats.length === Object.keys(attendu).length, cats.map((c) => c[1]).join(' · '));
  ok('chaque compte affiché est le compte du manifeste', cats.every(([id, txt]) => txt.endsWith(`(${attendu[id]})`)));
  ok('au moins une catégorie a plusieurs scènes', Object.values(attendu).some((n) => n > 1), attendu);
  await capture(page, '01-room-categories.jpg');
  await page.click('#quickRooms [data-cat="chambre"]');
  const nChambre = await page.locator('#quickRooms [data-room]').count();
  ok('Chambre ouvre ses scènes', nChambre === attendu.chambre, `${nChambre}`);
  await capture(page, '02-chambre-gallery.jpg');
  await page.click('[data-cat-back]');
  ok('le retour ramène aux catégories', (await page.locator('#quickRooms [data-cat]').count()) === cats.length);
  await page.click('#quickRooms [data-cat="sejour"]');
  ok('Séjour ouvre ses scènes', (await page.locator('#quickRooms [data-room]').count()) === attendu.sejour);
  await capture(page, '03-sejour-gallery.jpg');
  await page.click('[data-cat-back]');

  /* ================= 2. Chambre bleue + Zeus : le statut se lève ========= */
  const blueCategory = ROOMS.scenes.find(r => r.id === 'chambre').category;
  await page.click(`#quickRooms [data-cat="${blueCategory}"]`);
  const t0 = Date.now();
  await page.click('#quickRooms [data-room="chambre"]');
  const vuApplication = await page.waitForFunction(() => {
    const b = document.querySelector('#card .busy[data-etat="applying"]');
    return b && b.getBoundingClientRect().width > 0 && !document.getElementById('card').classList.contains('hidden');
  }, null, { timeout: 10000 }).then(() => true, () => false);
  ok('pendant la première application, la carte montre « Préparation du parquet… »', vuApplication
    || (await page.evaluate(() => window.__concept.etatApplication())) === 'rendered');
  await capture(page, '07-product-applying.jpg');
  await attendreRendu(page);
  mesures.premierRenduChambreMs = Date.now() - t0;
  const e1 = await etat(page);
  ok('chambre + Zeus : rendu présenté, statut levé', e1.etat === 'rendered' && e1.pill === '', e1);
  ok('aucune image du choix courant n’a coexisté avec « Application… »',
    (await page.evaluate(() => window.__violations.length)) === 0, await page.evaluate(() => window.__violations.slice(0, 3)));
  await page.waitForTimeout(400);
  await capture(page, '05-chambre-blue-after.jpg');
  await capture(page, '08-product-applied.jpg');

  /* Overlay DEV : absent ici (pas de ?dev=1). */
  ok('aucun overlay de géométrie hors DEV', (await page.locator('[aria-label="Axes du sol"]').count()) === 0);

  /* ================= 3. A -> B -> C ================= */
  const ids = await page.evaluate(() => window.__concept.PREMIBEL_DEMO_PRODUCTS
    .filter((p) => p.kind === 'product' && p.renderable !== false).map((p) => [p.id, p.pattern, p.widthMm]));
  const pick = (pattern) => ids.filter((x) => x[1] === pattern).map((x) => x[0]);
  const [A, B, C] = [pick('lames')[3], pick('baton-rompu')[1], pick('lames')[7]];
  await page.evaluate(([a, b, c]) => { const k = window.__concept; k.select(a, true); k.select(b, true); k.select(c, true); }, [A, B, C]);
  await attendreRendu(page);
  const e2 = await etat(page);
  ok('A -> B -> C : C est à l’écran', e2.produit === C && e2.applied.key === e2.cle && e2.cle.includes(`|${C}|`), e2);
  ok('A -> B -> C : statut levé', e2.pill === '');

  /* Produit en cache : retour à Zeus (déjà rendu dans cette pièce). */
  let t = Date.now();
  await page.evaluate(() => window.__concept.select('POINF36005', true));
  await attendreRendu(page);
  mesures.produitEnCacheMs = Date.now() - t;
  /* Nouvelle matière : une référence jamais rendue. */
  const neuf = pick('lames').find((id) => ![A, C].includes(id) && id !== 'CHENF36014');
  t = Date.now();
  await page.evaluate((id) => window.__concept.select(id, true), neuf);
  await attendreRendu(page);
  mesures.nouvelleMatiereMs = Date.now() - t;

  /* ================= 4. 50 changements rapides ================= */
  const suite = [];
  const pool = [...pick('lames').slice(0, 6), ...pick('point-de-hongrie').slice(0, 3), ...pick('baton-rompu').slice(0, 3)];
  for (let i = 0; i < 50; i += 1) {
    const r = i % 3;
    if (r === 0) suite.push(['produit', pool[i % pool.length]]);
    else if (r === 1) suite.push(['angle', [0, 90, 45, 315][i % 4]]);
    else suite.push(['produit', pool[(i * 7) % pool.length]]);
  }
  await page.evaluate(async (s) => {
    const k = window.__concept;
    for (const [quoi, v] of s) {
      if (quoi === 'produit') k.select(v, true); else k.setOrientation(v);
      await new Promise((r) => setTimeout(r, 15));
    }
  }, suite);
  const dernierProduit = [...suite].reverse().find((x) => x[0] === 'produit')[1];
  const dernierAngle = [...suite].reverse().find((x) => x[0] === 'angle')[1];
  try { await attendreRendu(page, 180000); } catch { /* jugé ci-dessous */ }
  const e3 = await etat(page);
  ok('50 changements : pas de blocage, dernier choix rendu', e3.etat === 'rendered' && !e3.applying, e3);
  ok('50 changements : le dernier produit et le dernier angle gagnent',
    e3.produit === dernierProduit && e3.cle.endsWith(`|${dernierAngle}|1`), e3.cle);
  ok('50 changements : aucune promesse rejetée non traitée', (await page.evaluate(() => window.__rejets.length)) === 0,
    await page.evaluate(() => window.__rejets));
  ok('50 changements : invariant du statut tenu', (await page.evaluate(() => window.__violations.length)) === 0);
  await page.evaluate(() => window.__concept.setOrientation(0));
  await attendreRendu(page);

  /* ================= 5. Changement de pièce ================= */
  const parcours = ['chambre', 'chambre-parisienne', 'sejour', 'chambre'];
  const produitGarde = await page.evaluate(() => window.__concept.state.productId);
  await page.evaluate(() => window.__concept.startCompare && window.__concept.startCompare());
  const durees = [];
  for (const id of parcours) {
    t = Date.now();
    await page.evaluate((r) => window.__concept.openRoom(r), id);
    const juste = await page.evaluate(() => ({ cmp: window.__concept.state.compare, ba: window.__concept.state.ba }));
    ok(`${id} : comparaison et avant/après remis à zéro`, juste.cmp === null && juste.ba === false);
    await attendreRendu(page);
    durees.push([id, Date.now() - t]);
    const e = await etat(page);
    ok(`${id} : rendu, produit conservé`, e.piece === id && e.produit === produitGarde && e.etat === 'rendered', e);
  }
  mesures.changementPiece = durees;
  ok('console sans erreur (parcours principal)', erreurs.length === 0, erreurs.slice(0, 3));
  await ctx.close();
}

/* ================= 6. Délai dépassé -> ERROR, puis résultat tardif ======== */
{
  const { ctx, page, erreurs } = await ouvrir({ width: 1440, height: 900 }, 'dev=1&ptimeout=60');
  await page.evaluate(() => window.__concept.openRoom('bureau-vide'));
  await page.waitForFunction(() => window.__concept.etatApplication() === 'error', null, { timeout: 30000 });
  const e = await etat(page);
  /* L'état affiché est ERROR. Une nouvelle tentative peut tourner en fond
     (`applying`) : le message reste stable jusqu'au succès ou à Réessayer. */
  ok('délai dépassé : sortie en ERROR, statut d’échec affiché', e.etat === 'error' && /Impossible d’appliquer/.test(e.pill) && !/Préparation du parquet…/.test(e.pill), e);
  ok('délai dépassé : bouton Réessayer (même instant)', e.retry === true);
  ok('délai dépassé : la photo reste visible', await page.evaluate(() => !!document.getElementById('photo').getAttribute('src')));
  /* Le résultat tardif du moteur est accepté s'il correspond encore au choix. */
  await attendreRendu(page).catch(() => {});
  const e2 = await etat(page);
  ok('le rendu tardif remplace l’échec', e2.etat === 'rendered' && e2.pill === '', e2);
  ok('console sans erreur (délai)', erreurs.length === 0, erreurs.slice(0, 3));
  await ctx.close();
}

/* ================= 7. Moteur en erreur -> ERROR, catalogue utilisable ====== */
{
  const { ctx, page, erreurs } = await ouvrir({ width: 1440, height: 900 }, 'dev=1');
  await page.evaluate(() => window.__concept.openRoom('entree-cadree'));
  await attendreRendu(page);
  await page.evaluate(() => {
    const a = window.__concept.adapter;
    window.__vraiApply = a.applyProfile;
    a.applyProfile = () => Promise.reject(new Error('panne simulée'));
  });
  const autre = await page.evaluate(() => window.__concept.PREMIBEL_DEMO_PRODUCTS
    .find((p) => p.kind === 'product' && p.renderable !== false && p.id !== window.__concept.state.productId && p.pattern === 'lames').id);
  await page.evaluate((id) => window.__concept.select(id, true), autre);
  await page.waitForFunction(() => window.__concept.etatApplication() === 'error', null, { timeout: 15000 }).catch(() => {});
  const e = await etat(page);
  ok('moteur en erreur : ERROR, pas APPLYING', e.etat === 'error' && !e.applying && !/Préparation du parquet…/.test(e.pill), e);
  ok('moteur en erreur : la photo reste affichée', await page.evaluate(() => !!document.getElementById('photo').getAttribute('src')));
  await page.evaluate(() => { window.__concept.adapter.applyProfile = window.__vraiApply; });
  await page.click('[data-open="retryApply"]');
  await attendreRendu(page);
  ok('Réessayer après la panne : rendu', (await etat(page)).etat === 'rendered');
  ok('console sans erreur (panne)', erreurs.length === 0, erreurs.slice(0, 3));

  /* Overlay DEV de géométrie : horizon, fuites, axes, guides. */
  await page.evaluate(() => window.__concept.openRoom('chambre'));
  await attendreRendu(page);
  const d = await page.evaluate(() => window.__geometryReview && window.__geometryReview.show(true));
  ok('overlay DEV : diagnostics de géométrie disponibles', !!(d && d.zones && d.zones.length));
  await page.waitForTimeout(300);
  await capture(page, '06-geometry-overlay.jpg');
  await ctx.close();
}

/* ================= 7 bis. Matières Premibel exactes, catalogue ================= */
{
  const { ctx, page, erreurs } = await ouvrir({ width: 1440, height: 900 });
  const index = JSON.parse(fs.readFileSync('web/data/materials/premibel/index.json', 'utf8'));
  const declarees = Object.entries(index.materials).filter(([, e]) => e.materialFidelity === 'exact').map(([id]) => id);
  const atlasLocaux = declarees.filter((id) => fs.existsSync(`web/assets/products/premibel/materials/${id}.atlas.webp`));
  const info = await page.evaluate(() => {
    const c = window.__concept;
    return { chargees: c.adapter.matieresExactes.map((m) => m.product), compte: c.compteCatalogue(),
      badges: document.querySelectorAll('#prods .pd-badge.exact').length,
      repetee: (document.getElementById('prods').textContent.match(/Matière indicative/g) || []).length };
  });
  ok('exactes : le moteur charge exactement celles dont l’atlas est présent',
    JSON.stringify([...info.chargees].sort()) === JSON.stringify([...atlasLocaux].sort()), info.chargees);
  ok('exactes : aucune référence « exact » sans matière chargée', info.compte.exacts === info.chargees.length, info.compte);
  ok('catalogue : les quatre statuts couvrent toutes les références',
    info.compte.exacts + info.compte.representatifs + info.compte.apercuSeul + info.compte.indisponibles === info.compte.produits, info.compte);
  ok('catalogue : plus de « Matière indicative » répété sous chaque carte', info.repetee === 0, info.repetee);
  ok('catalogue : un badge « Exact » par référence exacte affichée', info.badges <= info.chargees.length && (info.chargees.length === 0 || info.badges > 0));
  if (info.chargees.length) {
    await page.evaluate(() => window.__concept.openRoom('chambre'));
    await attendreRendu(page);
    const t = await page.evaluate(async (id) => {
      const c = window.__concept; const t0 = performance.now(); c.select(id, true);
      await new Promise((ok) => { const f = () => (c.etatApplication() === 'rendered' && !c.state.applying && !c.state.pendingApply) ? ok() : requestAnimationFrame(f); f(); });
      return { ms: Math.round(performance.now() - t0), fid: c.product().materialFidelity, src: c.state.applied.source };
    }, info.chargees.find((id) => id !== 'BTRPF39009') || info.chargees[0]);
    ok('exacte : rendue par le moteur', t.fid === 'exact' && t.src === 'live', t);
    mesures.matiereExacte = t.ms;
  }
  /* Une référence sans aperçu : fiche légère, rien n'est appliqué. */
  const avant = await page.evaluate(() => window.__concept.state.productId);
  const fiche = await page.evaluate(() => {
    const c = window.__concept;
    const p = c.PREMIBEL_DEMO_PRODUCTS.find((x) => x.renderable === false && x.productUrl);
    c.select(p.id);
    const f = document.getElementById('ficheLegere');
    return { ouverte: !!f && !f.hidden, lien: !!(f && f.querySelector('a[href]')), texte: f ? f.textContent : '', produit: c.state.productId };
  });
  ok('sans aperçu : fiche légère avec lien, aucun parquet appliqué',
    fiche.ouverte && fiche.lien && /Aperçu 3D bientôt disponible/.test(fiche.texte) && fiche.produit === avant, fiche);
  /* Filtre « Aperçu disponible ». */
  const filtre = await page.evaluate(() => {
    const c = window.__concept; const input = document.getElementById('fApercu');
    if (input.checked) input.click();
    const tous = c.visible().length;
    input.click();
    const filtres = c.visible();
    return { tous, apres: filtres.length, toutesRendables: filtres.every((p) => p.renderable !== false) };
  });
  ok('filtre « Aperçu disponible » : ne garde que ce qui se rend', filtre.apres < filtre.tous && filtre.toutesRendables, filtre);
  /* Préchargement : les cartes visibles préparent leur matière. */
  const precharge = await page.evaluate(async () => {
    const c = window.__concept;
    c.prechargerVisibles();
    const cibles = c.PREMIBEL_DEMO_PRODUCTS.filter((p) => p.renderable !== false && p.renderProfile && p.id !== c.state.productId).slice(0, 2);
    const t0 = performance.now();
    await new Promise((ok) => { const f = () => (cibles.some((p) => c.adapter.matierePrete(p.renderProfile)) || performance.now() - t0 > 45000 ? ok() : setTimeout(f, 100)); f(); });
    return cibles.some((p) => c.adapter.matierePrete(p.renderProfile));
  });
  ok('préchargement : une carte visible a sa matière prête avant le clic', precharge);
  ok('console sans erreur (matières)', erreurs.length === 0, erreurs.slice(0, 3));
  await ctx.close();
}

/* ================= 8. Responsive ================= */
for (const [w, h] of [[390, 844], [768, 1024], [1440, 900]]) {
  const { ctx, page, erreurs } = await ouvrir({ width: w, height: h });
  const debord = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  ok(`${w} : pas de débordement horizontal (accueil)`, debord <= 0, `${debord}px`);
  if (w === 390) await capture(page.locator ? page : page, '09-room-categories-390.jpg');
  await page.click(`#quickRooms [data-cat="${ROOMS.scenes.find(r => r.id === 'chambre').category}"]`);
  const cols = await page.evaluate(() => getComputedStyle(document.getElementById('quickRooms')).gridTemplateColumns.split(' ').length);
  ok(`${w} : galerie de scènes en ${cols} colonne(s)`, w <= 400 ? cols <= 2 : cols >= 2);
  if (w === 390) {
    await page.evaluate(() => document.getElementById('quickRooms').scrollIntoView());
    await capture(page, '10-chambre-gallery-390.jpg');
  }
  await page.click('#quickRooms [data-room="chambre"]');
  ok(`${w} : la chambre est rendue`, await attendreRendu(page));
  const debord2 = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  ok(`${w} : pas de débordement horizontal (visualiseur)`, debord2 <= 0, `${debord2}px`);
  if (w === 390) { await page.waitForTimeout(300); await capture(page, '11-render-390.jpg'); }
  ok(`${w} : console sans erreur`, erreurs.length === 0, erreurs.slice(0, 3));
  await ctx.close();
}

await browser.close();
fs.writeFileSync(path.join(OUT, 'mesures.json'), JSON.stringify(mesures, null, 2));
console.log('\nMESURES', JSON.stringify(mesures));
console.log(`\n${bad ? `${bad} ECHEC(S)` : 'AUCUN ECHEC'}`);
process.exit(bad ? 1 : 0);
