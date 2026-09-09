/*
  Batterie du concept de Visualiseur — `tools/product-concept.html`.

      node tools/product-concept.check.js       (depuis la racine du dépôt)

  Elle lit le fichier comme du texte, puis exécute son <script> sur un DOM
  minimal. Les deux niveaux servent : la lecture de texte attrape ce que
  l'exécution ne voit pas (un moteur de rendu qui repousse, un masque CSS, une
  requête réseau), et l'exécution attrape ce que la lecture ne voit pas (un
  rendu qui manque, une largeur non proposée par le produit).

  Le premier bloc est le plus important : il monte la garde contre le retour
  du faux moteur de rendu. Le parquet se dessine dans le front, en WebGL ;
  ici on change d'image, et rien de plus.

  Ce que la batterie ne remplace pas : l'ouverture réelle dans un navigateur.
*/
const fs = require('fs');
const html = fs.readFileSync('tools/product-concept.html', 'utf8');
let bad = 0;
const ok = (n, c, d) => {
  if (!c) bad += 1;
  console.log(`${c ? 'OK  ' : 'ECHEC'} ${n}${d !== undefined ? '  -> ' + d : ''}`);
};

/* Le code seul, commentaires retires. Les gardes ci-dessous doivent juger ce
   que le fichier FAIT, pas ce que ses commentaires racontent : l'en-tete parle
   justement de `floorZones` et de WebGL pour dire qu'ils n'y sont plus. */
const code = html
  .replace(/<!--[\s\S]*?-->/g, '')
  .replace(/\/\*[\s\S]*?\*\//g, '')
  .replace(/^\s*\/\/.*$/gm, '');

/* ================= 1. Aucun moteur de rendu ici =================
   La liste vient des versions precedentes : chaque entree a reellement
   existe dans ce fichier, et a du en sortir. */
for (const [quoi, re] of [
  ['<mask> SVG', /<mask\b/i],
  ['masque CSS', /(^|[^-\w])mask\s*:|webkitMask|-webkit-mask/],
  ['clip-path polygonal', /clip-path:\s*polygon/i],
  ['floorZones', /floorZones/],
  ['occulteurs', /occluder|occlShapes/i],
  ['demoFloorMask', /demoFloorMask|DEMO_MASK_FIX|applyMaskFix/],
  ['recoloration du sol', /floorFilter|hue-rotate|saturate\(/],
  ['generation de joints', /woodCss|jointCss|repeating-linear-gradient/],
  ['texture calculee', /function texture\b/],
  ['canevas', /createElement\(\s*['"]canvas|getContext\(/],
  ['WebGL', /webgl/i],
  ['perspective calculee', /perspective\(|function mapper|buildMasks/],
  ['calibration du front recopiee', /data\/scenes|runtimeMask|planeRef/],
]) ok(`aucun ${quoi}`, !re.test(code));

/* Un seul usage legitime du decoupage : le separateur avant/apres, et il
   est rectangulaire. */
const clips = code.match(/clipPath|clip-path/g) || [];
ok('decoupage uniquement pour le separateur',
  clips.length === 1 && /inset\(0 \$\{/.test(code) && !/polygon\(/.test(code),
  `${clips.length} occurrence(s)`);

/* ================= 2. Autonomie et confidentialite ================= */
for (const [label, re] of [
  ['<script src', /<script\s+[^>]*src=/i],
  ['<link', /<link\s/i],
  ['fetch(', /\bfetch\s*\(/],
  ['XMLHttpRequest', /XMLHttpRequest/],
  ['WebSocket', /WebSocket/],
  ['sendBeacon', /sendBeacon/],
  ['FormData', /FormData/],
  ['@font-face', /@font-face/],
  ['@import', /@import/],
  ['url(http)', /url\(\s*['"]?https?:/i],
  ['src distant', /src=["']https?:/i],
  ['localStorage', /localStorage/],
  ['sessionStorage', /sessionStorage/],
  ['indexedDB', /indexedDB/i],
  ['data URI', /;base64,/i],
  ['FileReader', /FileReader/],
]) ok(`aucun ${label}`, !re.test(html));
ok('un seul <script>', (html.match(/<script/g) || []).length === 1);
ok('polices systeme uniquement', /-apple-system/.test(html) && /Georgia/.test(html));
ok('prefers-reduced-motion', /prefers-reduced-motion/.test(html));
ok('aucune photo privee en dur',
  /const PHOTOS = '\.\.\/datasets\/private-real\/';/.test(html)
  && !/datasets\/private-real\/[a-z-]+\.jpg["']/.test(html));

/* ================= 2 bis. Premibel : source, pas dependance ================= */
ok('aucune image Premibel en hotlink',
  !/src=["']https:\/\/www\.premibel\.fr/.test(html)
  && !/url\(['"]?https:\/\/www\.premibel/.test(html));
ok('les images produit viennent du cache local',
  /const PREMIBEL = 'local-demo-assets\/premibel\/';/.test(html));
ok('aucun prix, remise, promo ni stock',
  !/\d[\d ,.]*\s*€/.test(html) && !/\bprix\b/i.test(code)
  && !/remise|promotion|\bpromo\b|en stock/i.test(code));
ok('aucun scraper',
  !/for\s*\([^)]*of\s*(pages|urls|refs)\b/i.test(code)
  && !/crawl|scrap/i.test(code));
ok('aucun asset concurrent',
  !/quick-?step|karndean/i.test(code));

/* ================= 3. L'UX V5, conservee ================= */
ok('aucun stepper', !/class="steps"/.test(html) && !/data-state="now"/.test(html));
ok('« Voir le résultat » absent', !/Voir le résultat/.test(html));
ok('aucune sidebar permanente', !/id="left"/.test(html) && !/id="panel"/.test(html));
ok('la piece occupe tout sous l en-tete', /#stage \{ flex: 1;/.test(html));
ok('en-tete de 54 px', /height: 54px/.test(html));
ok('en-tete minimal : 4 actions',
  (html.match(/class="hbtn/g) || []).length === 4, `${(html.match(/class="hbtn/g) || []).length} boutons`);
ok('trois entrees de navigation',
  /id="navRoom"/.test(html) && /id="navFloor"/.test(html) && /id="navCustom"/.test(html));
ok('chaque entree affiche sa valeur',
  /id="navRoomVal"/.test(html) && /id="navFloorVal"/.test(html) && /id="navCustomVal"/.test(html));
ok('barre centrale a trois outils',
  /id="baBtn"/.test(html) && /id="cmpBtn"/.test(html) && /id="fsBtn"/.test(html));
ok('petite carte produit flottante', /#card, #cardB \{[\s\S]*?width: 196px/.test(html));
ok('aucun bouton « Appliquer »', !/>Appliquer</.test(html) && !/<button[^>]*>[^<]*Appliquer/.test(html));

/* ================= 4. Trois images, et c'est tout ================= */
ok('trois couches d image', /<img id="photo"/.test(html) && /<img id="cmpB"/.test(html)
  && /<img id="after"/.test(html));
ok('elles sont en object-fit cover', /#photo, #cmpB, #after \{[\s\S]*?object-fit: cover/.test(html));
ok('la version A est au-dessus de la version B',
  /#cmpB \{ z-index: 1; \}/.test(html) && /#after \{ z-index: 2; \}/.test(html));
ok('la provenance des rendus est documentee',
  /window\.__studio/.test(html) && /\?perf=1/.test(html) && /preserveDrawingBuffer/.test(html));
ok('le front est dit lu et lance seulement', /Aucune écriture, aucun commit/.test(html));
ok('les rendus sont dits hors de Git', /hors de Git/.test(html));
ok('l empreinte du moteur qui a dessine est notee',
  /assets\/dist\/9685ef637e/.test(html) && /empreinte du RENDERER/.test(html));

/* ================= DOM minimal ================= */
const nodes = {};
const listeners = {};

function classList() {
  const set = new Set();
  return {
    add: (c) => set.add(c),
    remove: (c) => set.delete(c),
    contains: (c) => set.has(c),
    toggle: (c, force) => {
      const next = force === undefined ? !set.has(c) : !!force;
      if (next) set.add(c); else set.delete(c);
      return next;
    },
  };
}

function parseKids(markup) {
  return [...markup.matchAll(/<(button|span|div)[^>]*class="([^"]*)"[^>]*>([\s\S]*?)<\/\1>/g)].map((m) => {
    const classes = m[2].split(/\s+/);
    const dataset = {};
    for (const a of m[0].matchAll(/data-([a-z]+)="([^"]*)"/g)) dataset[a[1]] = a[2];
    const node = {
      tagName: m[1].toUpperCase(), dataset, outer: m[0],
      textContent: m[3].replace(/<[^>]+>/g, '').trim(),
      attrs: {}, classList: classList(), style: {},
      children: [], firstChild: { addEventListener() {}, style: {} },
      setAttribute(n, v) { this.attrs[n] = String(v); },
      getAttribute(n) { return this.attrs[n] ?? null; },
      querySelectorAll: () => [],
      _m: (sel) => classes.includes(sel.replace('.', '')),
    };
    node.closest = (sel) => (node._m(sel) ? node : null);
    return node;
  });
}

function make(key) {
  return {
    id: key, tagName: 'DIV', dataset: {}, value: '', textContent: '', _h: '',
    attrs: {}, classList: classList(), children: [], files: [],
    style: { setProperty() {} }, parentElement: null,
    get innerHTML() { return this._h; },
    set innerHTML(v) { this._h = String(v); this.children = parseKids(String(v)); },
    get src() { return this.attrs.src || ''; },
    set src(v) { this.attrs.src = String(v); },
    addEventListener(t, f) { (listeners[key] ??= {})[t] = f; },
    setAttribute(n, v) { this.attrs[n] = String(v); },
    getAttribute(n) { return this.attrs[n] ?? null; },
    focus() {}, setPointerCapture() {}, click() { this._clicked = true; },
    querySelectorAll(sel) {
      if (sel === 'img') {
        return (String(this._h).match(/<img[^>]*>/g) || []).map(() => {
          const img = make('img');
          img.parentElement = make('ph');
          return img;
        });
      }
      return this.children.filter((c) => c._m && c._m(sel));
    },
    closest: () => null,
    getBoundingClientRect: () => ({ left: 0, top: 0, width: 1200, height: 700 }),
  };
}

global.document = {
  getElementById: (id) => (nodes[id] ??= make(id)),
  querySelector: (s) => (nodes[s] ??= make(s)),
  querySelectorAll: () => [],
  createElement: (t) => make(t),
  addEventListener() {},
  body: make('body'),
};
global.window = { addEventListener() {}, devicePixelRatio: 1, location: { search: '' } };
global.setTimeout = (fn) => { void fn; return 1; };
global.clearTimeout = () => {};
const revoked = [];
global.URL = {
  createObjectURL: () => 'blob:local-only',
  revokeObjectURL: (u) => revoked.push(u),
};
/* Les Image() du prechargement ne doivent jamais echouer ici, sinon tous les
   rendus seraient marques manquants. */
class FakeImage {
  set src(v) { this._src = v; this.naturalWidth = 1920; this.naturalHeight = 1280; if (this.onload) this.onload(); }
  get src() { return this._src; }
}
global.Image = FakeImage;

const script = html.match(/<script>([\s\S]*)<\/script>/)[1];
try {
  new Function(script)();
  ok("le prototype s'execute sans exception", true);
} catch (error) {
  ok("le prototype s'execute sans exception", false, error.message);
}

const api = global.window.__concept;
ok('internes exposes', !!(api && api.state));
if (!api) { console.log('\nARRET : le script ne s est pas execute'); process.exit(1); }

const el = (id) => global.document.getElementById(id);
const h = (id) => el(id).innerHTML || '';
const count = (id, re) => (h(id).match(re) || []).length;
const R = 'local-demo-assets/renderings/';
const REFS = ['POINF36005', 'BTRPF39009', 'CHENF39031', 'CHENF36014', 'CHENF36015'];

/* ================= 5. Le mini-catalogue Premibel ================= */
ok('cinq scenes', api.DEMO_ROOMS.length === 5, `${api.DEMO_ROOMS.length}`);
const P = api.PREMIBEL_DEMO_PRODUCTS;
ok('cinq produits Premibel', P.length === 5, `${P.length}`);
ok('les cinq references attendues',
  P.map((x) => x.ref).sort().join(',') === REFS.slice().sort().join(','),
  P.map((x) => x.ref).join(','));
ok('references uniques', new Set(P.map((x) => x.ref)).size === 5);
ok('chaque produit se dit Premibel', P.every((x) => x.source === 'premibel'));
ok('chaque produit a une URL de fiche reelle',
  P.every((x) => /^https:\/\/www\.premibel\.fr\/parquet-flottant-chene-verni\/[A-Z0-9_]+\/$/.test(x.productUrl)));
ok('l URL contient la reference du produit',
  P.every((x) => x.productUrl.includes(x.ref)));
ok('chaque produit garde son image source',
  P.every((x) => /^https:\/\/www\.premibel\.fr\/wp-content\/uploads\//.test(x.imageSourceUrl)));
ok('chaque produit garde sa date de releve',
  P.every((x) => /^2026-09-\d\d$/.test(x.checkedAt)));
ok('chaque image pointe le cache local',
  P.every((x) => x.image.startsWith('local-demo-assets/premibel/')));
ok('proprietes reelles renseignees',
  P.every((x) => x.species && x.widthMm > 0 && x.lengthMm > 0 && x.thicknessMm > 0
    && x.finish && x.aspect && x.premibelFamily));
ok('aucun prix sur les produits',
  P.every((x) => !('price' in x) && !('prix' in x) && !('stock' in x)));
ok('la substitution de Piccadilly est declaree',
  P.find((x) => x.ref === 'BTRPF39009').substituteFor.includes('BTRPF39008'));
ok('l incoherence de longueur de Houston est consignee',
  /non arbitr/.test(P.find((x) => x.ref === 'CHENF39031').lengthNote));

/* ================= 5 bis. Mappage renderer, explicite ================= */
ok('chaque produit porte son mappage',
  P.every((x) => x.rendererMapping && x.rendererMapping.familyId && x.rendererMapping.pattern));
ok('aucun mappage ne se pretend exact',
  P.every((x) => x.rendererMapping.status === 'approximate'
    && x.visualAccuracy === 'approximate'),
  P.map((x) => x.rendererMapping.status).join(','));
ok('le mappage dit ce qui est exact et ce qui ne l est pas',
  P.every((x) => x.rendererMapping.exact.includes('pattern')
    && x.rendererMapping.approximate.includes('tone')
    && x.rendererMapping.unavailable.includes('albedo')));
ok('la largeur du mappage est celle du produit',
  P.every((x) => Math.round(x.rendererMapping.widthM * 1000) === x.widthMm));
ok('le motif du mappage est celui du produit',
  P.every((x) => x.rendererMapping.pattern === x.pattern));
ok('l origine de chaque famille est dite',
  P.every((x) => /pilote du front|le n/.test(x.rendererMapping.familySource)));
ok('la famille non validee est signalee',
  /non valid/.test(P.find((x) => x.ref === 'CHENF39031').rendererMapping.familySource));
ok('les documents de provenance existent',
  require('fs').existsSync('docs/premibel-demo-catalog.md'));
ok('les scenes n ont aucune geometrie',
  api.DEMO_ROOMS.every((r) => !('zones' in r) && !('occluders' in r) && !('w' in r)));
ok('un jeu de rendus par scene', api.DEMO_ROOMS.every((r) => api.DEMO_RENDERINGS[r.id]));
ok('trois scenes portent les rendus Premibel',
  api.RENDERED_ROOMS.length === 3
  && api.RENDERED_ROOMS.every((id) => Object.keys(api.DEMO_RENDERINGS[id]).length === 6),
  api.RENDERED_ROOMS.join(','));
ok('les deux autres scenes n ont que leur original',
  api.DEMO_ROOMS.filter((r) => !api.RENDERED_ROOMS.includes(r.id))
    .every((r) => Object.keys(api.DEMO_RENDERINGS[r.id]).join(',') === 'original'));
ok('un rendu par reference dans les scenes couvertes',
  api.RENDERED_ROOMS.every((id) => REFS.every((ref) => api.DEMO_RENDERINGS[id][ref])));
ok('les rendus vivent hors de Git',
  Object.values(api.DEMO_RENDERINGS).every((set) =>
    Object.values(set).every((u) => u.startsWith(R))));
ok('seuls les trois motifs du moteur du front',
  P.every((p) => ['lames', 'point-de-hongrie', 'baton-rompu'].includes(p.pattern))
  && Object.keys(api.PATTERNS).length === 3);
ok('un produit ne porte aucune recette de rendu',
  P.every((p) => !('filter' in p) && !('wood' in p) && !('tint' in p)));
/* La couche du sol ne peut recevoir QUE l'URL d'un rendu : une seule
   affectation dans tout le fichier, et sa source est `renderUrl`. Une photo
   produit Premibel ne peut donc pas se retrouver plaquee au sol. */
const afterAssigns = code.match(/\$\('after'\)\.src = [^;]+;/g) || [];
ok('la couche du sol ne recoit que le rendu',
  afterAssigns.length === 1 && afterAssigns[0].indexOf('= url;') > 0,
  afterAssigns.join(' | '));
ok('le role de la photo produit est ecrit', /JAMAIS de texture[\s\S]{0,12}de sol/.test(html));

/* ================= 6. Ouvrir une piece ================= */
ok('aucune piece au depart', api.state.source === null);
api.openRoom('sejour');
ok('choisir une piece ouvre le visualiseur', el('stage').classList.contains('hidden') === false);
ok('la source est demo', api.state.source === 'demo', api.state.source);
ok("l'image de fond est le rendu original",
  el('photo').getAttribute('src') === `${R}sejour.original.jpg`, el('photo').getAttribute('src'));
ok('la couche du parquet porte le rendu de la reference',
  el('after').getAttribute('src') === `${R}sejour.POINF36005.jpg`, el('after').getAttribute('src'));
ok('elle est visible', el('after').classList.contains('hidden') === false);
ok('aucun decoupage hors avant/apres', el('after').style.clipPath === 'none');

/* ================= 7. Selection produit : le clic change l image ========= */
api.select('CHENF36015');
ok('choisir une reference change l image',
  el('after').getAttribute('src') === `${R}sejour.CHENF36015.jpg`, el('after').getAttribute('src'));
ok('la navigation suit', el('navFloorVal').textContent === 'Chêne Invisible Pivoine',
  el('navFloorVal').textContent);
ok('la fiche produit affiche motif, largeur et reference',
  /Lames · 150 mm/.test(h('card')) && /Réf\. CHENF36015/.test(h('card')));
ok('le lien de fiche est un vrai lien, en nouvel onglet',
  /<a class="sheet" href="https:\/\/www\.premibel\.fr\/[^"]*CHENF36015\/"/.test(h('card'))
  && /target="_blank"/.test(h('card')) && /rel="noopener noreferrer"/.test(h('card')));
ok('la carte porte Personnaliser et Comparer',
  /data-open="cus"/.test(h('card')) && /data-open="cmpA"/.test(h('card')));
const before = api.state.productId;
api.stepProduct(1, 'A');
ok('la fleche suivant change de parquet', api.state.productId !== before, api.state.productId);
api.stepProduct(-1, 'A');
ok('la fleche precedent revient', api.state.productId === before);

/* ================= 8. Avant / apres : deux images de la meme scene ======= */
api.state.ba = true;
api.state.split = 0.4;
api.paint();
ok('avant/apres decoupe la couche du parquet',
  el('after').style.clipPath === 'inset(0 60.00% 0 0)', el('after').style.clipPath);
ok('le fond reste la scene d origine',
  el('photo').getAttribute('src').endsWith('sejour.original.jpg'));
ok('le separateur est visible', el('split').classList.contains('hidden') === false);
api.state.ba = false;
api.paint();
ok('avant/apres se desactive', el('after').style.clipPath === 'none');

/* ================= 9. Comparaison : deux rendus, une seule photo ========= */
api.state.compare = { b: 'CHENF36014' };
api.state.split = 0.5;
api.paint();
ok('la version B est chargee',
  el('cmpB').getAttribute('src') === `${R}sejour.CHENF36014.jpg`, el('cmpB').getAttribute('src'));
ok('les deux cartes portent de vraies references',
  /Réf\. CHENF36015/.test(h('card')) && /Réf\. CHENF36014/.test(h('cardB')));
ok('la version B est visible', el('cmpB').classList.contains('hidden') === false);
ok('la version A reste decoupee', el('after').style.clipPath === 'inset(0 50.00% 0 0)');
ok('deux cartes produit', el('cardB').classList.contains('hidden') === false);
ok('les versions sont etiquetees',
  el('tagA').classList.contains('hidden') === false && el('tagB').classList.contains('hidden') === false);
ok('la navigation s efface pendant la comparaison', el('nav').classList.contains('hidden') === true);
api.stepProduct(1, 'B');
ok('le cote B change seul',
  api.state.compare.b !== 'CHENF36014' && api.state.productId === before,
  `${api.state.compare.b} / ${api.state.productId}`);
api.state.compare = null;
api.paint();
ok('fermer la comparaison masque la version B', el('cmpB').classList.contains('hidden') === true);
ok('fermer la comparaison rend la navigation', el('nav').classList.contains('hidden') === false);

/* ================= 10. Changer de piece ================= */
const kept = api.state.productId;
api.openRoom('chambre');
ok('la reference survit au changement de piece', api.state.productId === kept, api.state.productId);
ok('la nouvelle scene est chargee',
  el('photo').getAttribute('src').endsWith('chambre.original.jpg'));
ok('le rendu de la nouvelle scene est charge',
  el('after').getAttribute('src') === `${R}chambre.${kept}.jpg`, el('after').getAttribute('src'));
ok('aucun rendu n est reutilise d une piece a l autre',
  api.renderUrl('sejour', kept) !== api.renderUrl('chambre', kept));
/* Une scene sans rendu Premibel doit retomber, pas inventer. */
api.openRoom('piece-arcades');
ok('une scene non couverte n a aucun rendu', api.renderUrl('piece-arcades', kept) === null);
ok('elle montre la photo, sans parquet',
  el('after').classList.contains('hidden') === true
  && el('photo').getAttribute('src').endsWith('piece-arcades.original.jpg'));
api.openRoom('sejour');

/* ================= 11. Repli quand un rendu manque ================= */
api.openRoom('piece-claire');
api.state.missing.add(`${R}piece-claire.CHENF36014.jpg`);
api.select('CHENF36014', true);
ok('un rendu manquant masque la couche du parquet',
  el('after').classList.contains('hidden') === true);
ok('la photo d origine reste affichee',
  el('photo').getAttribute('src').endsWith('piece-claire.original.jpg'));
ok('aucun faux parquet en repli', el('after').style.clipPath === 'none');
ok('la mention de repli est reservee au mode dev',
  api.DEV === false && el('devnote').classList.contains('hidden') === true);
ok('le texte de repli existe dans le fichier', /Rendu demo indisponible/.test(html));
api.state.missing.clear();
api.select('CHENF36014', true);
ok('le rendu revient une fois disponible', el('after').classList.contains('hidden') === false);

/* Si meme l original manque, on retombe sur la photo brute. */
api.state.missing.add(`${R}piece-claire.original.jpg`);
api.paint();
ok('sans original, la photo brute prend le relais',
  el('photo').getAttribute('src') === '../datasets/private-real/piece-claire.jpg',
  el('photo').getAttribute('src'));
api.state.missing.clear();
/* Et sans image produit locale, la vignette prend un cadre, pas un vide. */
api.state.missingImg.add(api.product('CHENF36014').image);
api.paintCard();
ok('une image produit absente donne un cadre', /class="sw noimg"/.test(h('card')));
ok('le cadre est explicite', /image produit absente/.test(html));
api.state.missingImg.clear();
api.paintCard();

/* ================= 12. Photo importee inconnue ================= */
api.loadUpload({ type: 'image/jpeg', name: 'ma-piece.jpg' });
ok('la source devient uploaded', api.state.source === 'uploaded', api.state.source);
ok('la photo importee devient la scene',
  el('photo').getAttribute('src') === 'blob:local-only', el('photo').getAttribute('src'));
ok('aucun parquet pose dessus', el('after').classList.contains('hidden') === true);
ok('ni carte produit ni outils quand rien n est pose',
  el('card').classList.contains('hidden') === true
  && el('tools').classList.contains('hidden') === true);
ok('aucun rendu inconnu invente', api.renderUrl('uploaded', 'POINF36005') === null);
ok('le message d honnetete est present', /moteur IA n'est pas connecté/.test(html));
ok('la limite est dite temporaire', /cette limite[\s\S]{0,20}dispara/.test(html));
ok('deux sorties sont proposees', /id="unkRooms"/.test(html) && /id="unkOther"/.test(html));
api.loadUpload({ type: 'image/gif', name: 'anim.gif' });
ok('un format refuse ne remplace pas la scene', api.state.uploaded.name === 'ma-piece.jpg',
  api.state.uploaded.name);

/* ================= 13. Rien n est conserve ================= */
api.openRoom('chambre');
ok('changer de piece libere la photo importee', api.state.uploaded === null);
ok("l'URL d'objet est revoquee", revoked.includes('blob:local-only'));
ok('aucune persistance de la photo', !/localStorage|sessionStorage|indexedDB/.test(html));

/* ================= 14. Catalogue ================= */
api.openCat();
ok('la grille montre les cinq references', count('prods', /class="pd"/g) === 5);
ok('les vignettes sont les photos produit',
  count('prods', /local-demo-assets\/premibel\//g) === 5);
ok('chaque carte porte nom, motif, largeur et reference',
  /Point de Hongrie Zeus Naturel/.test(h('prods'))
  && /Point de Hongrie · 92 mm — Réf\. POINF36005/.test(h('prods')));
ok('aucun prix sur les cartes', !/€/.test(h('prods')));
ok('le compte figure dans le titre', el('catCount').textContent === '(5)', el('catCount').textContent);
ok('filtre motif limite aux motifs presents',
  count('fPattern', /class="chip"/g) === api.presentPatterns().length
  && api.presentPatterns().length === 3);
ok('filtre teinte limite aux teintes presentes',
  count('fTone', /class="chip"/g) === api.presentTones().length
  && api.presentTones().length === 3, api.presentTones().join(','));
ok('filtre largeur derive du catalogue',
  api.presentWidths().join(',') === '90,92,150,190', api.presentWidths().join(','));
ok('aucune largeur absente proposee',
  api.presentWidths().every((mm) => P.some((x) => x.widthMm === mm)));
api.toggleFilter('pattern', 'baton-rompu');
ok('un filtre reduit la grille', api.visible().length === 1, `${api.visible().length}`);
ok('le compte suit le filtre', el('catCount').textContent === '(1)');
api.toggleFilter('pattern', 'baton-rompu');
ok('le meme filtre se retire', api.visible().length === 5);
api.toggleFilter('widthMm', 150);
ok('la largeur filtre aussi', api.visible().length === 2, `${api.visible().length}`);
api.toggleFilter('widthMm', 150);

/* Inspirations : editoriales, et dites comme telles. */
ok('trois inspirations', api.MOODS.length === 3);
ok('elles pointent de vraies references',
  api.MOODS.every((m) => m.refs.every((r) => REFS.includes(r))));
ok('elles sont annoncees comme editoriales',
  /sélection éditoriale, écrite à la main/.test(h('moods')));
ok('aucune pretention d IA', !/recommand|intelligence artificielle/i.test(h('moods')));
api.toggleFilter('mood', 'graphique');
ok('une inspiration filtre le catalogue',
  api.visible().map((x) => x.ref).sort().join(',') === 'BTRPF39009,POINF36005',
  api.visible().map((x) => x.ref).join(','));
api.toggleFilter('mood', 'graphique');

/* ================= 15. Personnaliser : chercher une variante ==============
   Un vrai produit n'est pas configurable. Changer un critere doit conduire a
   une AUTRE reference, jamais transformer celle-ci. */
api.openRoom('sejour');
api.select('POINF36005', true);
api.paintCustom();
ok('le panneau nomme la reference active',
  /Réf\. POINF36005/.test(el('cusName').textContent), el('cusName').textContent);
ok('il explique qu une reference est definie',
  /une référence\s*\n?\s*définie/.test(el('cusIntro').innerHTML));
ok('les trois motifs sont proposes', count('patterns', /class="pt"/g) === 3);
ok('chaque motif mene a une reference', count('patterns', /data-variant="[A-Z]/g) === 3);
ok('les quatre largeurs du catalogue', count('widths', /class="chip"/g) === 4);
ok('les trois teintes du catalogue', count('tones', /class="chip"/g) === 3);
ok('la finition est unique et non modifiable',
  count('finishes', /class="chip"/g) === 1 && /Verni/.test(h('finishes')));
ok('la note dit pourquoi', /pas de/.test(el('finishNote').textContent));

/* Zeus est un point de Hongrie 92 mm : demander des lames doit donner une
   AUTRE reference, pas un Zeus en lames. */
const vLames = api.findVariant({ pattern: 'lames' });
ok('demander des lames renvoie une autre reference',
  vLames && vLames.ref !== 'POINF36005' && vLames.pattern === 'lames', vLames && vLames.ref);
const v190 = api.findVariant({ widthMm: 190 });
ok('demander 190 mm renvoie Houston', v190 && v190.ref === 'CHENF39031', v190 && v190.ref);
const vChaud = api.findVariant({ tone: 'chaud' });
ok('demander la teinte chaude renvoie Pivoine',
  vChaud && vChaud.ref === 'CHENF36015', vChaud && vChaud.ref);
ok('un critere absent du catalogue ne renvoie rien',
  api.findVariant({ widthMm: 220 }) === null);
ok('la variante ne transforme jamais le produit actif',
  api.product('POINF36005').widthMm === 92
  && api.product('POINF36005').pattern === 'point-de-hongrie');

/* Le sens de pose reste un reglage du rendu, pas une autre reference. */
ok('deux sens de pose', count('orient', /class="or"/g) === 2);
ok('le sens de pose est dit reglage de rendu',
  /pas une autre\s*\n?\s*référence/.test(html));

/* ================= 16. Favoris ================= */
ok('aucun favori au depart', api.state.favourites.size === 0);
api.toggleFav('POINF36005');
ok('un favori memorise la vraie reference', api.state.favourites.has('POINF36005'));
ok('le compteur d en-tete suit', el('favCount').textContent === '1');
api.toggleFav('POINF36005');
ok('un favori se retire', api.state.favourites.size === 0);

/* ================= 17. Etats d analyse ================= */
api.setDemo('success', true);
ok('« Pièce prête » est une petite capsule',
  /Pièce prête/.test(h('status')) && /#status \{[\s\S]*?border-radius: var\(--r-pill\)/.test(html));
ok('aucun bandeau plein cadre pour un succes', el('rejected').classList.contains('hidden') === true);
api.setDemo('partial', true);
ok('partial reste une capsule, sans action a inventer',
  /incertain/.test(h('status')) && !/Ajuster/.test(h('status')));
api.setDemo('rejected', true);
ok('rejected explique et propose une reprise', el('rejected').classList.contains('hidden') === false);
ok('le conseil de reprise est concret', /appuyez-vous contre un mur/.test(html));
api.setDemo('success', true);
ok('aucun pinceau de retouche de masque', !/id="brush"/.test(html) && !/brAdd|brDel/.test(html));

/* ================= 18. Selecteur de piece ================= */
api.openRooms();
ok('les categories sont listees', count('roomCats', /data-cat=/g) === 4,
  `${count('roomCats', /data-cat=/g)}`);
ok('le compte des pieces est affiche', /5 pièces/.test(el('roomCount').textContent),
  el('roomCount').textContent);
ok('la grille montre les scenes', count('roomGrid', /<img/g) >= 1);
ok('la piece courante est cochee', /class="tick"/.test(h('roomGrid')));
ok('l import est dans le selecteur', /id="sheetImport"/.test(html));
ok('repli si image absente', /markFallbacks/.test(html) && /photo indisponible/.test(html));

/* ================= 19. Modales hors de la scene =================
   Regression : elles vivaient dans #stage, masque sur l'ecran d'entree, et
   « Choisir une piece » n'ouvrait rien depuis l'accueil. */
const body = html.split('</style>')[1].split('<script>')[0];
ok('les modales sont hors de la scene',
  ['roomSheet', 'catSheet', 'cusSheet'].every((id) =>
    body.indexOf(`id="${id}"`) > body.indexOf('</section>')));
ok('les modales sont ancrees a la page',
  /\.scrim \{ position: fixed/.test(html) && /\.sheetp \{\s*position: fixed/.test(html));
(() => {
  const stack = [];
  let extra = 0;
  for (const tok of body.match(/<\/?div[^>]*>/g) || []) {
    if (tok.startsWith('</')) { if (stack.length) stack.pop(); else extra += 1; }
    else stack.push(tok);
  }
  ok('balisage equilibre', stack.length === 0 && extra === 0,
    `${stack.length} non ferme(s), ${extra} en trop`);
})();

/* ================= Inventaire des rendus attendus ================= */
console.log('');
console.log('Mini-catalogue Premibel (metadonnees versionnees, binaires non)');
console.log('  reference     motif              largeur  famille de rendu   mappage');
P.forEach((x) => {
  console.log(`  ${x.ref.padEnd(13)} ${api.PATTERNS[x.pattern].padEnd(18)}`
    + ` ${String(x.widthMm + ' mm').padStart(7)}  ${x.rendererMapping.familyId.padEnd(18)}`
    + ` ${x.rendererMapping.status}`);
});
console.log('');
console.log('Rendus attendus (hors de Git, produits par le Visualiseur du front)');
api.DEMO_ROOMS.forEach((r) => {
  const n = Object.keys(api.DEMO_RENDERINGS[r.id]).length;
  console.log(`  ${r.id.padEnd(16)} ${n} fichier(s)`
    + `${api.RENDERED_ROOMS.includes(r.id) ? '' : '  — original seul, repli exerce'}`);
});
console.log(`  total ${api.RENDERED_ROOMS.length * P.length} rendus`
  + ` + ${api.DEMO_ROOMS.length} originaux + ${P.length} images produit`);

console.log(bad ? `\n${bad} ECHEC(S)` : '\nAUCUN ECHEC');
process.exit(bad ? 1 : 0);
