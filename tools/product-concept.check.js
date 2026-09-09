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
  ['WebGL', /webgl/i],
  ['perspective calculee', /perspective\(|function mapper|buildMasks/],
  ['calibration du front recopiee', /data\/scenes|runtimeMask|planeRef/],
]) ok(`aucun ${quoi}`, !re.test(code));

/* Un canevas est desormais present — mais uniquement pour RECOPIER des
   pixels, jamais pour composer un sol. Le seul dessin autorise est
   `drawImage` (copie) et `getImageData` (empreinte). Tout ce qui servirait a
   peindre un parquet reste interdit. */
for (const [quoi, re] of [
  ['remplissage', /fillStyle|fillRect|\.fill\(/],
  ['trace de chemin', /moveTo|lineTo|\.arc\(|beginPath/],
  ['motif de canevas', /createPattern|createLinearGradient|createRadialGradient/],
  ['ecriture de pixels', /putImageData|createImageData/],
]) ok(`aucun ${quoi} sur canevas`, !re.test(code));
const dessins = (code.match(/getContext\('2d'[^)]*\)[\s\S]{0,40}?\.\w+\(/g) || []);
ok('le canevas ne sert qu a copier',
  /drawImage/.test(code) && !/\.fill/.test(code), `${dessins.length} appels`);

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
ok('la piece occupe tout sous l en-tete', /#stage \{\s*\n\s*flex: 1;/.test(html));
ok('en-tete de 54 px', /height: 54px/.test(html));
/* « Enregistrer » a ete retire : il n'avait pas de comportement, seulement
   un message disant qu'il n'en avait pas. Un bouton visible doit agir. */
ok('en-tete minimal : 3 actions',
  (html.match(/class="hbtn/g) || []).length === 3, `${(html.match(/class="hbtn/g) || []).length} boutons`);
ok('aucun bouton placebo dans l en-tete ni le menu',
  !/id="hSave"/.test(html) && !/id="menuShare"/.test(html)
  && !/besoin documenté, pas développé ici/.test(code));
ok('trois entrees de navigation',
  /id="navRoom"/.test(html) && /id="navFloor"/.test(html) && /id="navCustom"/.test(html));
ok('chaque entree affiche sa valeur',
  /id="navRoomVal"/.test(html) && /id="navFloorVal"/.test(html) && /id="navCustomVal"/.test(html));
ok('barre centrale a trois outils',
  /id="baBtn"/.test(html) && /id="cmpBtn"/.test(html) && /id="fsBtn"/.test(html));
ok('petite carte produit flottante', /#card, #cardB \{[\s\S]*?width: 196px/.test(html));
ok('aucun bouton « Appliquer »', !/>Appliquer</.test(html) && !/<button[^>]*>[^<]*Appliquer/.test(html));

/* ================= 4. Trois images, et c'est tout ================= */
ok('la photo est une image, les rendus des canevas',
  /<img id="photo"/.test(html) && /<canvas id="cmpB">/.test(html)
  && /<canvas id="after">/.test(html) && /<canvas id="afterPrev">/.test(html));
ok('le moteur est charge hors ecran, sans etre affiche',
  /<iframe id="engine"/.test(html) && /#engine \{[\s\S]*?left: -20000px/.test(html)
  && /aria-hidden="true"/.test(html));
ok('la version A est au-dessus de la version B',
  /#vpB \{ z-index: 1; \}/.test(html) && /#clipA \{[^}]*z-index: 2/.test(html));
ok('le decoupage du separateur est hors de la transformation',
  /#clipA \{ position: absolute;/.test(html)
  && /\$\('clipA'\)\.style\.clipPath/.test(code)
  && !/\$\('after'\)\.style\.clipPath/.test(code));
ok('la provenance des rendus est documentee',
  /window\.__studio/.test(html) && /\?perf=1/.test(html) && /preserveDrawingBuffer/.test(html));
ok('le front est dit lu et lance seulement', /Aucune écriture, aucun commit/.test(html));
ok('les rendus sont dits hors de Git', /hors de Git/.test(html));
ok('l empreinte du moteur qui a dessine est notee',
  /assets\/dist\/9685ef637e/.test(html) && /empreinte du RENDERER/.test(html));

/* ================= DOM minimal ================= */
const nodes = {};
const listeners = {};
/* Les trois groupes du viewport, ceux que `applyTransform()` doit ecrire a
   l'identique. */
const vpGroups = [];

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
    width: 0, height: 0, naturalWidth: 0, naturalHeight: 0, complete: true,
    getContext: () => ({
      drawImage() {},
      getImageData: () => ({ data: new Uint8Array(24 * 16 * 4) }),
    }),
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
    disabled: false,
    getBoundingClientRect: () => ({ left: 0, top: 0, width: 1200, height: 700 }),
  };
}

global.document = {
  getElementById: (id) => (nodes[id] ??= make(id)),
  querySelector: (s) => (nodes[s] ??= make(s)),
  querySelectorAll: (sel) => (sel === '[data-vp]' ? vpGroups : []),
  createElement: (t) => make(t),
  addEventListener() {},
  body: make('body'),
};
global.window = {
  addEventListener() {}, devicePixelRatio: 1, location: { search: '' },
  matchMedia: () => ({ matches: false }),
};
/* Un `setTimeout(fn, 0)` porte un report d'etat (ajustement differe,
   reclamp) : il doit s'executer. Les delais plus longs sont de l'UI temporisee
   (voile d'analyse, toast) et restent ignores, sinon les sequences testees
   sauteraient des etapes. */
global.setTimeout = (fn, ms) => { if (!ms) fn(); return 1; };
global.clearTimeout = () => {};
/* Pas d'animation dans la batterie : les rAF sont ignores, donc `setVp` est
   toujours lu dans son etat final. Les tests d'animation portent sur le code,
   et le vrai comportement est verifie dans Chrome. */
/* rAF synchrone : la batterie lit donc l'etat FINAL, comme apres animation.
   L'horloge avance a chaque appel pour que l'interpolation se termine du
   premier coup au lieu de boucler. */
global.requestAnimationFrame = (fn) => { fn(global.performance.now()); return 0; };
global.cancelAnimationFrame = () => {};
let horloge = 0;
global.performance = { now: () => (horloge += 500) };
const revoked = [];
global.URL = {
  createObjectURL: () => 'blob:local-only',
  revokeObjectURL: (u) => revoked.push(u),
};
/* Les Image() du prechargement ne doivent jamais echouer ici, sinon tous les
   rendus seraient marques manquants. */
class FakeImage {
  constructor() { this.complete = false; }
  set src(v) {
    this._src = v;
    /* Les captures sont toutes au meme cadrage ; une photo importee a le
       sien. Deux tailles distinctes, pour que le test de dimension de scene
       puisse encore distinguer les deux cas. */
    const blob = String(v).startsWith('blob:');
    this.naturalWidth = blob ? 1920 : 1200;
    this.naturalHeight = blob ? 1280 : 800;
    this.complete = true;
    if (this.onload) this.onload();
  }
  get src() { return this._src; }
}
global.Image = FakeImage;

['vpPhoto', 'vpB', 'vpA'].forEach((id) => vpGroups.push(make(id)));
nodes.vpPhoto = vpGroups[0];
nodes.vpB = vpGroups[1];
nodes.vpA = vpGroups[2];

const script = html.match(/<script>([\s\S]*)<\/script>/)[1];
try {
  new Function(script)();
  ok("le prototype s'execute sans exception", true);
} catch (error) {
  ok("le prototype s'execute sans exception", false, error.message);
}

const api = global.window.__concept;
ok('internes exposes', !!(api && api.state));
if (api) {
  /* Sous Node il n'y a pas d'iframe : l'adaptateur reste en `static`, et
     c'est justement le chemin de repli qu'on veut eprouver ici. Le mode live
     se verifie dans Chrome. */
  api.state.applied = { key: null, source: null };
}
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
  P.every((x) => x.heroImage.startsWith('local-demo-assets/premibel/')
    && x.catalogThumbnail.startsWith('local-demo-assets/premibel/')));

/* ================= 5 ter. Vignettes matiere =================
   La carte doit montrer le bois, pas un salon. Aucune fiche n'a de vignette
   matiere dediee : la provenance de chaque decoupage est donc ecrite. */
ok('chaque produit a une vignette matiere distincte de la photo d ambiance',
  P.every((x) => x.catalogThumbnail !== x.heroImage
    && /thumb\.[A-Z0-9_]+\.jpg$/.test(x.catalogThumbnail)));
ok('la provenance de chaque vignette est declaree',
  P.every((x) => ['premibel_photo_crop', 'renderer_crop'].includes(x.catalogThumbnailSource)),
  P.map((x) => x.catalogThumbnailSource).join(','));
const parSource = P.reduce((m, x) => {
  m[x.catalogThumbnailSource] = (m[x.catalogThumbnailSource] || 0) + 1;
  return m;
}, {});
ok('quatre decoupages de photo Premibel, un de notre rendu',
  parSource.premibel_photo_crop === 4 && parSource.renderer_crop === 1,
  JSON.stringify(parSource));
ok('le repli est celui de Houston, dont la fiche ne montre pas le sol de pres',
  P.find((x) => x.catalogThumbnailSource === 'renderer_crop').ref === 'CHENF39031');
ok('aucune vignette n est fabriquee de toutes pieces',
  /Rien n'est fabriqué/.test(html) && /vignette matière dédiée/.test(html));
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
/* Une seule fonction ecrit dans les couches visibles — `paintLayer` — et
   toutes les ecritures sur canevas du fichier, la sienne comme celle du cache
   de captures, ne font que COPIER des pixels. Une photo produit Premibel n'a
   donc aucun chemin jusqu'au sol, et rien ici ne compose un parquet. */
ok('une seule fonction ecrit dans les couches visibles',
  (code.match(/function paintLayer\(/g) || []).length === 1);
const ecritures = code.match(/getContext\('2d'\)\.\w+/g) || [];
ok('toutes les ecritures sur canevas sont des copies',
  ecritures.length > 0 && ecritures.every((e) => e.endsWith('.drawImage')),
  ecritures.join(' '));
ok('les sources des couches sont le moteur ou une capture',
  /paintLayer\('after', canvas\)/.test(code) && /paintLayer\(layer, img\)/.test(code)
  && !/paintLayer\([^)]*(catalogThumbnail|heroImage)/.test(code));
ok('le role de la photo produit est ecrit', /JAMAIS de texture[\s\S]{0,12}de sol/.test(html));

/* ================= 6. Ouvrir une piece ================= */
ok('aucune piece au depart', api.state.source === null);
api.openRoom('sejour');
ok('choisir une piece ouvre le visualiseur', el('stage').classList.contains('hidden') === false);
ok('la source est demo', api.state.source === 'demo', api.state.source);
ok("l'image de fond est le rendu original",
  el('photo').getAttribute('src') === `${R}sejour.original.jpg`, el('photo').getAttribute('src'));
ok('la couche du parquet porte le rendu de la reference',
  api.state.applied.key === 'sejour|POINF36005|0', api.state.applied.key);
ok('en repli, la source est la capture', api.state.applied.source === 'static',
  String(api.state.applied.source));
ok('elle est visible', el('clipA').classList.contains('hidden') === false);
ok('aucun decoupage hors avant/apres', el('clipA').style.clipPath === 'none');

/* ================= 7. Selection produit : le clic change l image ========= */
api.select('CHENF36015');
ok('choisir une reference change le sol applique',
  api.state.applied.key === 'sejour|CHENF36015|0', api.state.applied.key);
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
  el('clipA').style.clipPath === 'inset(0 60.00% 0 0)', el('clipA').style.clipPath);
ok('le fond reste la scene d origine',
  el('photo').getAttribute('src').endsWith('sejour.original.jpg'));
ok('le separateur est visible', el('split').classList.contains('hidden') === false);
ok('le fond reste la photo, pas un rendu', el('photo').getAttribute('src').includes('original'));
api.state.ba = false;
api.paint();
ok('avant/apres se desactive', el('clipA').style.clipPath === 'none');

/* ================= 9. Comparaison : deux rendus, une seule photo ========= */
api.state.compare = { b: 'CHENF36014' };
api.state.split = 0.5;
api.paint();
ok('la version B est preparee dans son propre etat',
  api.state.appliedB.key === 'sejour|CHENF36014|0', api.state.appliedB.key);
ok('A et B ne sont pas le meme etat',
  api.state.applied.key !== api.state.appliedB.key,
  `${api.state.applied.key} vs ${api.state.appliedB.key}`);
ok('les deux cartes portent de vraies references',
  /Réf\. CHENF36015/.test(h('card')) && /Réf\. CHENF36014/.test(h('cardB')));
ok('la version B est visible', el('vpB').classList.contains('hidden') === false);
ok('la version A reste decoupee', el('clipA').style.clipPath === 'inset(0 50.00% 0 0)');
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
ok('fermer la comparaison masque la version B', el('vpB').classList.contains('hidden') === true);
ok('fermer la comparaison rend la navigation', el('nav').classList.contains('hidden') === false);

/* ================= 10. Changer de piece ================= */
const kept = api.state.productId;
api.openRoom('chambre');
ok('la reference survit au changement de piece', api.state.productId === kept, api.state.productId);
ok('la nouvelle scene est chargee',
  el('photo').getAttribute('src').endsWith('chambre.original.jpg'));
ok('le rendu de la nouvelle scene est applique',
  api.state.applied.key === `chambre|${kept}|0`, api.state.applied.key);
ok('aucun rendu n est reutilise d une piece a l autre',
  api.renderUrl('sejour', kept) !== api.renderUrl('chambre', kept));
/* Une scene sans rendu Premibel doit retomber, pas inventer. */
api.openRoom('piece-arcades');
ok('une scene non couverte n a aucun rendu', api.renderUrl('piece-arcades', kept) === null);
ok('elle montre la photo, sans parquet',
  el('clipA').classList.contains('hidden') === true
  && el('photo').getAttribute('src').endsWith('piece-arcades.original.jpg'));
api.openRoom('sejour');

/* ================= 11. Repli quand un rendu manque ================= */
api.openRoom('piece-claire');
api.state.missing.add(`${R}piece-claire.CHENF36014.jpg`);
api.select('CHENF36014', true);
ok('un rendu manquant masque la couche du parquet',
  el('clipA').classList.contains('hidden') === true);
ok('la photo d origine reste affichee',
  el('photo').getAttribute('src').endsWith('piece-claire.original.jpg'));
ok('aucun faux parquet en repli', el('clipA').style.clipPath === 'none');
ok('la mention de repli est reservee au mode dev',
  api.DEV === false && el('devnote').classList.contains('hidden') === true);
ok('le mode du moteur est dit en dev', /moteur \$\{adapter\.mode\}/.test(code)
  && /rendu live/.test(code) && /capture de repli/.test(code));
api.state.missing.clear();
api.select('CHENF36014', true);
ok('le rendu revient une fois disponible',
  el('clipA').classList.contains('hidden') === false
  && api.state.applied.key === 'piece-claire|CHENF36014|0', api.state.applied.key);

/* Si meme l original manque, on retombe sur la photo brute. */
api.state.missing.add(`${R}piece-claire.original.jpg`);
api.paint();
ok('sans original, la photo brute prend le relais',
  el('photo').getAttribute('src') === '../datasets/private-real/piece-claire.jpg',
  el('photo').getAttribute('src'));
api.state.missing.clear();
/* Et sans image produit locale, la vignette prend un cadre, pas un vide. */
api.state.missingImg.add(api.product('CHENF36014').catalogThumbnail);
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
ok('aucun parquet pose dessus', el('clipA').classList.contains('hidden') === true);
ok('ni carte produit ni outils quand rien n est pose',
  el('card').classList.contains('hidden') === true
  && el('tools').classList.contains('hidden') === true);
ok('aucun rendu inconnu invente', api.renderUrl('uploaded', 'POINF36005') === null);
ok('le message d honnetete est present', /moteur IA n'est pas connecté/.test(html));
ok('la limite est dite temporaire', /cette limite[\s\S]{0,20}dispara/.test(html));
ok('deux sorties sont proposees', /id="unkRooms"/.test(html) && /id="unkOther"/.test(html));
/* Et une troisieme, discrete : sans parquet il reste la photo, et elle se
   manipule deja — sinon le voile bloquerait le viewport. */
ok('on peut explorer sa photo malgre tout', /id="unkExplore"/.test(html)
  && /Explorer ma photo quand même/.test(html));
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
ok('les vignettes du catalogue sont les matieres',
  count('prods', /thumb\.[A-Z0-9_]+\.jpg/g) === 5);
ok('aucune photo d ambiance dans la grille',
  !/premibel\/(POINF|BTRPF|CHENF)[0-9_]+\.(jpg|png)/.test(h('prods')));
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
/* La finition, le veinage et les joints ne sont pas reglables par le moteur :
   il n'y a donc AUCUN controle, seulement une phrase qui le dit. */
ok('aucun controle de finition, de veinage ni de joints',
  !/id="finishes"/.test(html) && !/id="grain"/.test(html) && !/id="joint"/.test(html)
  && !/type="range"/.test(html));
ok('et la raison est ecrite', /un réglage sans effet vaut moins que son absence/.test(html));

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
/* Le sens de pose n'apparait que si le moteur sait le rendre. En repli
   statique il n'y a pas d'orientation a offrir : la section est masquee. */
ok('le sens de pose suit la capacite du moteur',
  el('sectOrient').classList.contains('hidden') === !api.adapter.getCapabilities().orientation);
ok('trois orientations sont prevues, toutes rendues par le moteur',
  api.ORIENTATIONS.length === 3
  && api.ORIENTATIONS.map(([d]) => d).join(',') === '0,90,45');
ok('le sens de pose est dit reglage de rendu',
  /pas une\s*\n?\s*.?\s*autre référence/.test(code) || /réglage du rendu, pas une/.test(code));

/* ================= 15 bis. Le viewport : pan et zoom =================
   Un seul etat pilote toute la scene. Les tests d'etat sont ici ; la
   fluidite, elle, se juge dans Chrome. */
api.openRoom('sejour');
api.select('POINF36005', true);
const B = { w: 1200, h: 700 };          /* le cadre du DOM minimal */
const SC = api.sceneSize();
ok('la scene a la taille des rendus', SC.w === 1200 && SC.h === 800, `${SC.w}x${SC.h}`);
/* 100 % = la photo COUVRE le cadre. Avant : elle y TENAIT, et un ecran plus
   large que la photo montrait deux bandes sombres de 190 px — la piece dans
   une vignette. */
ok('100 % couvre le cadre',
  Math.abs(api.fitScale() - Math.max(B.w / SC.w, B.h / SC.h)) < 1e-9,
  api.fitScale().toFixed(4));
ok('« Ajuster » tient la scene entiere dans le cadre',
  Math.abs(api.containScale() - Math.min(B.w / SC.w, B.h / SC.h)) < 1e-9
  && api.zContain() <= 1, `${api.containScale().toFixed(4)} / z ${api.zContain().toFixed(3)}`);

/* fitToView : centre, ratio garde, zoom a 1 — donc « 100 % ». */
api.fitToView();
ok('fitToView remet le zoom a 1', api.state.vp.z === 1);
ok('a 100 %, aucun vide autour de la photo',
  SC.w * api.cssScale() >= B.w - 0.01 && SC.h * api.cssScale() >= B.h - 0.01
  && api.state.vp.x <= 0.01 && api.state.vp.y <= 0.01
  && api.state.vp.x + SC.w * api.cssScale() >= B.w - 0.01
  && api.state.vp.y + SC.h * api.cssScale() >= B.h - 0.01,
  `${api.state.vp.x.toFixed(1)},${api.state.vp.y.toFixed(1)} ${(SC.w * api.cssScale()).toFixed(0)}x${(SC.h * api.cssScale()).toFixed(0)}`);
ok('fitToView centre la scene',
  Math.abs(api.state.vp.x - (B.w - SC.w * api.fitScale()) / 2) < 0.6
  && Math.abs(api.state.vp.y - (B.h - SC.h * api.fitScale()) / 2) < 0.6,
  `${api.state.vp.x.toFixed(1)},${api.state.vp.y.toFixed(1)}`);
ok('100 % correspond a l ajustement', el('zLevel').textContent === '100 %',
  el('zLevel').textContent);

/* Une seule transformation, ecrite a l'identique partout. */
const transforms = [el('vpPhoto'), el('vpB'), el('vpA')].map((n) => n.style.transform);
ok('les trois groupes portent la MEME transformation',
  transforms.every((t) => t && t === transforms[0]), transforms.join(' || '));
ok('elle est GPU-friendly', /translate3d\(/.test(transforms[0]) && /scale\(/.test(transforms[0]),
  transforms[0]);
ok('aucune translation separee des couches',
  !el('photo').style.transform && !el('cmpB').style.transform && !el('after').style.transform);

/* Zoom : bornes. */
api.zoomAt(100, null, null, false);
ok('le zoom est borne en haut', api.state.vp.z === api.ZOOM_MAX, `${api.state.vp.z}`);
api.zoomAt(0.001, null, null, false);
ok('un geste ne descend jamais sous la couverture', api.state.vp.z === api.ZOOM_MIN, `${api.state.vp.z}`);
ok('les bornes laissent inspecter sans absurdite',
  api.ZOOM_MAX >= 4 && api.ZOOM_MAX <= 6 && api.ZOOM_MIN === 1,
  `${api.ZOOM_MIN}..${api.ZOOM_MAX}`);

/* « Ajuster » est la seule porte vers les bandes ; depuis la, zoomer en
   arriere ne fait rien — et surtout ne saute pas a 100 %. */
api.fitAll();
const zAj = api.state.vp.z;
ok('Ajuster passe sous 100 % pour montrer toute la photo', zAj < 1 && Math.abs(zAj - api.zContain()) < 1e-9, `${zAj.toFixed(3)}`);
ok('la photo entiere est visible',
  SC.w * api.cssScale() <= B.w + 0.01 && SC.h * api.cssScale() <= B.h + 0.01);
ok('et elle est centree dans le cadre',
  Math.abs(api.state.vp.x - (B.w - SC.w * api.cssScale()) / 2) < 0.6
  && Math.abs(api.state.vp.y - (B.h - SC.h * api.cssScale()) / 2) < 0.6);
ok('le bouton Ajuster se desactive une fois ajuste', el('zFit').disabled === true);
api.zoomAt(1 / 1.5, null, null, false);
ok('zoomer en arriere depuis Ajuster ne saute pas a 100 %', Math.abs(api.state.vp.z - zAj) < 1e-9, `${api.state.vp.z.toFixed(3)}`);
ok('le bouton moins est alors desactive', el('zOut').disabled === true);
api.zoomAt(1.5, null, null, false);
ok('zoomer en avant depuis Ajuster remonte', api.state.vp.z > zAj);
api.zoomAt(1 / 1.5, null, null, false);
api.zoomAt(1 / 1.5, null, null, false);
ok('et revenir en arriere s arrete a la couverture, pas aux bandes',
  Math.abs(api.state.vp.z - 1) < 1e-9, `${api.state.vp.z.toFixed(3)}`);
ok('le libelle dit le vrai niveau', el('zLevel').textContent === '100 %', el('zLevel').textContent);

/* Zoom sous le curseur : le point vise ne doit pas glisser. */
api.fitToView();
const s0 = api.cssScale();
const px = 300;
const py = 220;
const uAvant = (px - api.state.vp.x) / s0;
const vAvant = (py - api.state.vp.y) / s0;
api.zoomAt(2, px, py, false);
const s1 = api.cssScale();
const uApres = (px - api.state.vp.x) / s1;
const vApres = (py - api.state.vp.y) / s1;
ok('le point sous le curseur reste sous le curseur',
  Math.abs(uAvant - uApres) < 1.5 && Math.abs(vAvant - vApres) < 1.5,
  `${(uAvant - uApres).toFixed(2)}, ${(vAvant - vApres).toFixed(2)}`);
ok('zoomer autour du curseur ne revient pas au centre',
  Math.abs(api.state.vp.x - (B.w - SC.w * s1) / 2) > 1,
  api.state.vp.x.toFixed(1));

/* Deplacement, puis bornes : l'image couvre toujours le cadre. */
api.setVp({ z: 2, x: 99999, y: 99999 }, false);
ok('le pan ne laisse jamais sortir l image', api.state.vp.x <= 0.01 && api.state.vp.y <= 0.01,
  `${api.state.vp.x.toFixed(1)},${api.state.vp.y.toFixed(1)}`);
api.setVp({ z: 2, x: -99999, y: -99999 }, false);
const s2 = api.cssScale();
ok('ni de l autre cote',
  api.state.vp.x >= B.w - SC.w * s2 - 0.01 && api.state.vp.y >= B.h - SC.h * s2 - 0.01);
api.setVp({ z: 1, x: 400, y: 400 }, false);
ok('a 100 %, un deplacement hors cadre est ramene sans laisser de vide',
  api.state.vp.x <= 0.01 && api.state.vp.y <= 0.01
  && api.state.vp.x + SC.w * api.cssScale() >= B.w - 0.01
  && api.state.vp.y + SC.h * api.cssScale() >= B.h - 0.01,
  `${api.state.vp.x.toFixed(1)},${api.state.vp.y.toFixed(1)}`);

/* Le deplacement doit rester possible : un clamp trop dur bloquerait tout. */
api.setVp({ z: 3, x: 0, y: 0 }, false);
const marge = SC.w * api.cssScale() - B.w;
ok('a 300 %, il reste de la marge a explorer', marge > 400, `${Math.round(marge)} px`);

/* ---- Conservation du cadrage ---- */
api.setVp({ z: 2.5, x: -420, y: -260 }, false);
const garde = { ...api.state.vp };
api.select('CHENF36014', true);
ok('changer de reference conserve le cadrage',
  api.state.vp.z === garde.z && api.state.vp.x === garde.x && api.state.vp.y === garde.y,
  `${api.state.vp.z} ${api.state.vp.x} ${api.state.vp.y}`);
ok('et applique bien le nouveau sol',
  api.state.applied.key === 'sejour|CHENF36014|0', api.state.applied.key);

api.state.ba = true;
api.paint();
ok('avant/apres conserve le cadrage',
  api.state.vp.z === garde.z && api.state.vp.x === garde.x && api.state.vp.y === garde.y);
api.state.ba = false;
api.state.compare = { b: 'POINF36005' };
api.paint();
ok('la comparaison conserve le cadrage',
  api.state.vp.z === garde.z && api.state.vp.x === garde.x && api.state.vp.y === garde.y);
const tCmp = [el('vpPhoto'), el('vpB'), el('vpA')].map((n) => n.style.transform);
ok('A et B restent synchronises pendant la comparaison',
  tCmp.every((t) => t === tCmp[0]), tCmp.join(' || '));
api.setVp({ z: 2.5, x: -300, y: -200 }, false);
const tApres = [el('vpPhoto'), el('vpB'), el('vpA')].map((n) => n.style.transform);
ok('un deplacement pendant la comparaison bouge les deux cotes ensemble',
  tApres.every((t) => t === tApres[0]) && tApres[0] !== tCmp[0]);
api.state.compare = null;
api.paint();

/* Changer de piece, en revanche, recentre. */
api.setVp({ z: 3, x: -500, y: -300 }, false);
api.openRoom('chambre');
ok('changer de piece recentre', api.state.vp.z === 1, `${api.state.vp.z}`);
/* Mais un geste fait avant que le recentrage differe ne s'applique doit
   gagner : sinon l'initialisation ecraserait une action deliberee. */
ok('le recentrage differe cede a un geste',
  code.includes('if (pendingFit) fitToView(false)')
  && /rAF sert a peindre, pas a porter de l'etat/.test(html)
  && /function zoomAt[^{]*[{][^}]*pendingFit = false;/.test(code)
  && /function onMove[^{]*[{][\s\S]{0,90}pendingFit = false;/.test(code));

/* Importer une photo recentre aussi, et le viewport reste manipulable meme
   sans parquet applique. */
api.setVp({ z: 2, x: -200, y: -100 }, false);
api.loadUpload({ type: 'image/jpeg', name: 'ma-piece.jpg' });
ok('importer une photo recentre', api.state.vp.z === 1);
ok('la scene prend les dimensions de la photo importee',
  api.sceneSize().w === 1920 && api.sceneSize().h === 1280,
  `${api.sceneSize().w}x${api.sceneSize().h}`);
api.zoomAt(2, 400, 300, false);
ok('on peut zoomer une photo sans rendu', api.state.vp.z > 1, `${api.state.vp.z}`);
ok('et toujours aucun parquet dessus', el('clipA').classList.contains('hidden') === true);
api.openRoom('sejour');

/* ---- Mode immersif ---- */
ok('la barre de zoom existe et est discrete',
  /id="zoombar"/.test(html) && /#zoombar \{[\s\S]*?backdrop-filter: blur/.test(html));
ok('elle porte les cinq commandes',
  ['zOut', 'zLevel', 'zIn', 'zFit', 'zFull'].every((id) => new RegExp(`id="${id}"`).test(html)));
const barMarkup = (html.match(/<div id="zoombar">[\s\S]*?<[/]div>/) || [''])[0];
ok('chaque commande a son libelle accessible',
  barMarkup.split('aria-label').length - 1 === 5,
  `${barMarkup.split('aria-label').length - 1} libelle(s)`);
ok('le viewport a une description accessible',
  /role="group"/.test(html) && /Molette pour zoomer/.test(html));
api.setImmersive(true);
ok('le mode immersif s active', api.state.immersive === true);
ok("l'en-tete et la navigation s effacent",
  /body\.immersive header,[\s\S]*?display: none/.test(html)
  && /body\.immersive #nav/.test(html));
ok('les outils et le zoom restent',
  !/body\.immersive #tools \{[^}]*display: none/.test(html)
  && !/body\.immersive #zoombar \{[^}]*display: none/.test(html));
ok('le chrome s atténue au repos, sans disparaitre',
  /body\.immersive\.calm[\s\S]*?opacity: 0\.32/.test(html));
api.setImmersive(false);
ok('on en sort', api.state.immersive === false);
/* Regression : requestFullscreen renvoie une promesse. Sans .catch, un refus
   (cadre embarque) remplit la console de rejets non geres. */
ok('le refus du plein ecran natif est rattrape',
  /Promise\.resolve\(root\.requestFullscreen\(\)\)\.catch\(nop\)/.test(code)
  && /Promise\.resolve\(document\.exitFullscreen\(\)\)\.catch\(nop\)/.test(code));

/* ================= Stabilisation V1 : defauts trouves en usage =================
   Chaque garde ci-dessous correspond a un bug reproduit dans Chrome. */

/* Le moteur est unique : deux applications en parallele copiaient chacune le
   canevas de l'autre et le retenaient sous LEUR clef. */
ok('les operations moteur passent par une file',
  /let file = Promise\.resolve\(\);/.test(code) && /const enFile = /.test(code)
  && /return enFile\(\(\) => this\.applyProfileMaintenant\(profile, orientationDeg\)\)/.test(code)
  && /return enFile\(async \(\) => \{[\s\S]{0,80}engineScene === sceneId/.test(code));
ok('la file survit a un echec', /file = tour\.catch\(\(\) => \{\}\);/.test(code));
ok('la version B ouvre la piece par la meme file',
  /const canvasB = await adapter\.applyProfile/.test(code)
  && /if \(adapter\.scene !== entry\.id\) await adapter\.openRoom\(entry\.id\);[\s\S]{0,120}const canvasB/.test(code));

/* Un resultat perime ne s'affiche jamais : jeton d'intention. */
ok('chaque geste incremente l intention',
  (code.match(/state\.intent \+= 1;/g) || []).length >= 7,
  `${(code.match(/state\.intent \+= 1;/g) || []).length} incrementations`);
ok('le rendu live de A verifie la clef ET le jeton',
  /appliedKey\(\) === key && state\.intent === intent/.test(code));
ok('le rendu live de B verifie que la comparaison est toujours la',
  /state\.compare && state\.compare\.b === b\.id && room\(\)\.id === entry\.id/.test(code)
  && /state\.intent === intent;/.test(code));

/* picking : fermer le catalogue annule le choix de B. Reproduit : Comparer,
   fermer, puis Choisir un parquet posait une comparaison a la place. */
api.state.compare = null; api.state.ba = false; api.paint();
api.select('POINF36005', true);
api.startCompare();
ok('Comparer ouvre le catalogue en mode choix de B', api.state.picking === true
  && el('catSheet').classList.contains('hidden') === false);
api.closeAll();
ok('fermer le catalogue annule le choix de B', api.state.picking === false);
api.select('CHENF39031', true);
ok('le clic suivant change bien de sol, il ne compare pas',
  api.state.productId === 'CHENF39031' && api.state.compare === null);

/* A = B : refuse. */
api.startCompare();
api.select('CHENF39031', true);
ok('comparer une reference a elle-meme est refuse',
  api.state.compare === null && api.state.picking === true);
api.select('CHENF36014', true);
ok('une autre reference est acceptee comme B',
  api.state.compare && api.state.compare.b === 'CHENF36014' && api.state.picking === false);
ok('la carte B propose de CHANGER B, la carte A de fermer',
  /\$\{side === 'B' \? 'Changer' : 'Comparer'\}/.test(code)
  && /open\.dataset\.open === 'cmpB'\) pickB\(\)/.test(code));
api.startCompare();
ok('Comparer referme la comparaison et oublie B',
  api.state.compare === null && api.state.appliedB.key === null);

/* Changer de piece est une intention et annule un choix de B en cours. */
api.startCompare();
api.openRoom('chambre');
ok('changer de piece annule un choix de B en cours', api.state.picking === false);
api.openRoom('sejour');

/* Import : un jeton, une URL revoquee, un champ reutilisable. */
ok('un import perime est ignore et son URL liberee',
  /if \(state\.intent !== intent\) \{ URL\.revokeObjectURL\(url\); return; \}/.test(code));
ok('une erreur de lecture libere l URL', /probe\.onerror = \(\) => \{[\s\S]{0,40}URL\.revokeObjectURL\(url\);/.test(code));
ok('le champ fichier est remis a zero apres lecture', /e\.target\.value = '';/.test(code));

/* Separateur : la capture du pointeur peut echouer (NotFoundError vue dans la
   console pendant la revue) ; le relachement doit aussi etre ecoute sur le
   stage, sinon le separateur suit la souris pour toujours. */
ok('la capture du separateur est protegee',
  /try \{ if \(\$\('split'\)\.setPointerCapture\)/.test(code));
ok('le separateur se lache aussi sur le stage',
  /\$\('stage'\)\.addEventListener\('pointerup', lacherSeparateur\)/.test(code)
  && /\$\('stage'\)\.addEventListener\('pointercancel', lacherSeparateur\)/.test(code));

/* Favoris : retirer un favori depuis la liste des favoris ne doit pas
   remplacer la liste par le catalogue entier. */
api.state.favourites.clear(); api.toggleFav('POINF36005'); api.toggleFav('CHENF39031');
el('hFav').onclick();
ok('la vue favoris montre les favoris',
  api.state.catalogueView === 'favourites'
  && (h('prods').match(/data-id="/g) || []).length === 2, h('prods').match(/data-id="[A-Z0-9]+"/g));
api.toggleFav('CHENF39031');
ok('retirer un favori garde la vue favoris',
  api.state.catalogueView === 'favourites'
  && (h('prods').match(/data-id="/g) || []).length === 1, `${(h('prods').match(/data-id="/g) || []).length} carte(s)`);
api.toggleFav('POINF36005');
ok('plus aucun favori : retour au catalogue entier, sans liste vide',
  api.state.catalogueView === 'all' && (h('prods').match(/data-id="/g) || []).length === 5);
api.closeAll(); api.openCat();
ok('ouvrir le catalogue remet la vue a tout', api.state.catalogueView === 'all');
api.closeAll();

/* Le viewport se reborne quand le CADRE change, pas seulement la fenetre. */
ok('le stage est observe en taille',
  /new ResizeObserver\(reborner\)\.observe\(\$\('stage'\)\)/.test(code)
  && /window\.addEventListener\('resize', reborner\)/.test(code)
  && /visibilitychange[^;]*\{ if \(!document\.hidden\) reborner\(\); \}/.test(code));

/* ---- Raccourcis ---- */
ok('les raccourcis + - 0 f Escape existent',
  /e\.key === '\+' \|\| e\.key === '='/.test(code) && /e\.key === '0'/.test(code)
  && /e\.key === 'f'/.test(code) && /e\.key === 'Escape'/.test(code));
ok('ils ne se declenchent pas dans un champ',
  /t\.tagName === 'INPUT'/.test(code) && /isContentEditable/.test(code));

/* ---- Animation ---- */
ok('un glisser n est jamais anime',
  /setVp\(\{ z: state\.vp\.z, x: state\.vp\.x \+ \(e\.clientX - prev\.x\)[\s\S]{0,80}, false\)/.test(code));
ok('les gestes discrets sont interpoles', /const dur = 200;/.test(code));
ok('prefers-reduced-motion est respecte',
  /const REDUCED = /.test(code) && /if \(!moved \|\| !animate \|\| REDUCED\)/.test(code));

/* Reproduit dans Chrome : rAF ne se declenchait pas, et le double-clic, + , -,
   Ajuster, 100 % et le clavier ne faisaient RIEN. L'etat doit etre commis
   tout de suite ; seule l'image est interpolee, par minuteur. */
{
  const rafAvant = global.requestAnimationFrame;
  const stAvant = global.setTimeout;
  global.requestAnimationFrame = () => 0;          /* jamais appele */
  global.setTimeout = () => 0;                      /* jamais appele non plus */
  api.fitToView();
  api.zoomAt(1.5, null, null, true);
  ok('un zoom anime commet son etat sans attendre une frame',
    Math.abs(api.state.vp.z - 1.5) < 1e-9, `${api.state.vp.z}`);
  api.fitAll(true);
  ok('Ajuster anime commet son etat sans attendre une frame',
    Math.abs(api.state.vp.z - api.zContain()) < 1e-9, `${api.state.vp.z}`);
  api.fitToView(true);
  ok('100 % anime commet son etat sans attendre une frame', api.state.vp.z === 1);
  global.requestAnimationFrame = rafAvant;
  global.setTimeout = stAvant;
  /* Meme classe de defaut : `.fading` restait collee au sol quand rAF ne se
     declenchait pas. */
  ok('le fondu du sol ne depend pas de rAF',
    !/requestAnimationFrame\(\(\) => requestAnimationFrame/.test(code)
    && /fadeTimer = setTimeout\(\(\) => \$\('after'\)\.classList\.remove\('fading'\)/.test(code));
  ok('aucun etat n est porte par requestAnimationFrame',
    !/requestAnimationFrame\([^)]*state\./.test(code));
  ok('l animation ne fait plus avancer l etat frame par frame',
    !/state\.vp = \{\s*z: from\.z \+ \(c\.z - from\.z\) \* e/.test(code)
    && /shown = \{ z: from\.z \+ \(c\.z - from\.z\) \* e/.test(code));
}

/* ---- Gestes ---- */
ok('Pointer Events, pas souris seule',
  /pointerdown/.test(code) && /pointermove/.test(code) && /pointercancel/.test(code));
ok('deux doigts font un pincement', /pointers\.size === 2/.test(code) && /pinch/.test(code));
ok('la molette est traitee sans bloquer les modales',
  /\{ passive: false \}/.test(code) && /closest\('\.sheetp, \.veil, #menu'\)/.test(code));
ok('le double-clic zoome, avec Shift pour l inverse',
  /dblclick/.test(code) && /e\.shiftKey \? 1 \/ 1\.8 : 1\.8/.test(code));
ok('le curseur passe de grab a grabbing',
  /cursor: grab/.test(html) && /#stage\.grabbing \{ cursor: grabbing/.test(html));
/* Regression : sans ces deux garde-fous, glisser la piece declenchait le
   glisser-deposer natif de l'image et la page croyait a un import. */
ok('les images du viewport ne sont pas glissables',
  /-webkit-user-drag: none/.test(html) && /pointer-events: none/.test(html)
  && /user-select: none/.test(html));
ok('le pointerdown coupe le drag natif', /function onDown\(e\) \{[\s\S]{0,220}e\.preventDefault\(\)/.test(code));
ok('un depot interne n est pas pris pour un import',
  /includes\('Files'\)/.test(code));
ok('la 3D n est pas promise',
  /Ce n'est PAS de la 3D/.test(html) && !/navigation 3D possible/.test(html));

/* ================= 15 ter. Le moteur pilote la piece =================
   Les tests d'etat sont ici ; que le sol change vraiment se verifie dans
   Chrome, empreinte de canevas a l'appui. */
ok('chaque produit porte un profil de rendu',
  P.every((x) => x.renderProfile && x.renderProfile.materialFamily
    && x.renderProfile.pattern && Number.isFinite(x.renderProfile.widthM)));
ok('le profil ne contient que des proprietes honorees par le moteur',
  P.every((x) => Object.keys(x.renderProfile).sort().join(',')
    === 'lengthM,materialFamily,orientationDeg,pattern,widthM'),
  Object.keys(P[0].renderProfile).sort().join(','));
ok('la largeur du profil est celle du produit',
  P.every((x) => Math.round(x.renderProfile.widthM * 1000) === x.widthMm));
ok('le motif du profil est celui du produit',
  P.every((x) => x.renderProfile.pattern === x.pattern));
ok('les cinq profils sont distincts',
  new Set(P.map((x) => `${x.renderProfile.materialFamily}|${x.renderProfile.pattern}`
    + `|${x.renderProfile.widthM}`)).size === 5);

/* L'exactitude est decomposee : la geometrie est juste, la matiere non. */
ok('l exactitude est donnee attribut par attribut',
  P.every((x) => x.renderAccuracy
    && x.renderAccuracy.pattern === 'exact' && x.renderAccuracy.width === 'exact'
    && x.renderAccuracy.orientation === 'exact'
    && x.renderAccuracy.tone === 'approximate' && x.renderAccuracy.finish === 'approximate'));
ok('aucun attribut ne se pretend exact sur la matiere',
  P.every((x) => ['tone', 'grain', 'finish'].every((k) => x.renderAccuracy[k] !== 'exact')));

/* L'adaptateur */
ok('l adaptateur expose un contrat independant de l interface',
  ['mode', 'getCapabilities', 'connect', 'openRoom', 'applyProfile']
    .every((k) => k in api.adapter));
ok('il annonce son mode', ['live', 'static'].includes(api.adapter.mode), api.adapter.mode);
ok('sous Node il retombe en statique', api.adapter.mode === 'static');
ok('les capacites sont un objet complet',
  ['pattern', 'width', 'orientation', 'finish', 'grain', 'joints']
    .every((k) => k in api.adapter.getCapabilities()));
/* Les capacites ne sont plus devinees de l'exterieur : le moteur les
   annonce, et il les deduit lui-meme de la presence de ses commandes. Le pont
   ne fait que retenir celles qu'il sait utiliser. */
ok('les capacites viennent du moteur',
  /const dites = st\.getCapabilities\(\)/.test(code)
  && /pattern: dites\.pattern === true/.test(code)
  && /width: dites\.width === true/.test(code)
  && /orientation: dites\.orientation === true/.test(code));
ok('un moteur sans aucune capacite est refuse',
  /n annonce aucune capacite pilotable/.test(code));
ok('la finition, le veinage et les joints sont dits non reglables',
  /finish: false/.test(code) && /grain: false/.test(code) && /joints: false/.test(code));
ok('le moteur est pilote par le point d accroche du front, pas par son DOM',
  /window\.__studio|w\.__studio/.test(code) && !/contentDocument/.test(code)
  && !/querySelector\('#\w+', frame/.test(code));
/* Le point sale a disparu. La largeur passe par `setWidth`, et il ne reste
   AUCUNE ecriture dans l'etat interne du moteur — la lecture `studio.config`
   elle-meme n'existe plus dans ce fichier. */
ok('aucune mutation de la configuration du moteur',
  !/studio\.config\s*(\.\w+\s*)?=[^=]/.test(code) && !/studio\.config/.test(code));

/* Garde automatique : TOUT ce que le pont touche sur le moteur doit figurer
   dans le contrat documente. Une garde nominative (« pas de config ») ne
   protege que de ce qu'on a pense a interdire ; celle-ci protege de ce qu'on
   n'a pas pense a interdire. */
const CONTRAT_V1 = ['apiVersion', 'openRoom', 'selectMaterial', 'setPattern',
  'setAngle', 'setWidth', 'getCapabilities', 'onRendered', 'canvas'];
/* `studio` est le moteur negocie, `st` le candidat qu'examine `connect()`.
   Le nom doit etre entier, d'ou la classe ecrite en clair : les raccourcis
   comme la sequence mot-frontiere ne survivent pas aux couches
   d'echappement de cet outillage. */
/* Le `/` exclu evite de prendre `outils/studio.html` — un chemin, pas un
   acces membre. Un acces JS n'est jamais precede d'une barre oblique ici. */
const acces = (nom) => (code.match(new RegExp(`[^A-Za-z0-9_$./]${nom}[.][A-Za-z0-9_$]+`, 'g')) || [])
  .map((a) => a.split('.')[1]);
const touches = [...new Set([...acces('studio'), ...acces('st')])].sort();
const horsContrat = touches.filter((m) => !CONTRAT_V1.includes(m));
/* Un ensemble vide signifierait que la garde ne regarde rien. On l'exige
   donc non vide : sinon elle passerait sans rien prouver — c'est exactement
   comme cela qu'elle est passee la premiere fois. */
ok('le pont ne touche que le contrat documente',
  touches.length >= 8 && horsContrat.length === 0,
  horsContrat.length ? `hors contrat : ${horsContrat.join(', ')}` : touches.join(' '));

/* La clef du cache decrit un ETAT DE RENDU, pas une reference produit. */
ok('la clef d etat existe et est nommee',
  /function getRenderStateKey\(profile, orientationDeg\)/.test(code));
ok('elle enumere ce qui change les pixels',
  /`api\$\{ENGINE_API_VERSION\}`/.test(code) && /engineScene/.test(code)
  && /profile\.materialFamily/.test(code) && /profile\.pattern/.test(code)
  && /profile\.widthM/.test(code) && /Number\(orientationDeg\)/.test(code));
ok('la reference produit n entre pas dans la clef',
  !/getRenderStateKey[\s\S]{0,900}productId/.test(code));
ok('la clef est calculee dans l adaptateur, pas fournie par l appelant',
  /applyProfile\(profile, orientationDeg\)/.test(code)
  && /const key = getRenderStateKey\(profile, orientationDeg\);/.test(code)
  && !/applyProfile\([^)]*, key\)/.test(code));
ok('une seule verite pour la piece ouverte dans le moteur',
  /adapter\.scene !== entry\.id/.test(code) && !/engineRoom/.test(code));
ok('les exclusions de la clef sont justifiees dans le fichier',
  /lengthM/.test(html) && /aucune commande, capacite/.test(html)
  && /meurt avec la page/.test(html));
ok('la largeur passe par la commande du moteur',
  /studio\.setWidth\(/.test(code));
ok('chaque reglage passe par une commande, jamais par l etat',
  ['selectMaterial', 'setPattern', 'setWidth', 'setAngle']
    .every((m) => code.includes(`studio.${m}(`)));

/* La version du contrat est negociee, pas supposee. */
ok('la version attendue est nommee', /const ENGINE_API_VERSION = 1;/.test(code));
ok('une version differente fait echouer la connexion',
  /apiVersion !== ENGINE_API_VERSION/.test(code) && /ce pont conduit la v/.test(code));
ok('les commandes indispensables sont listees et verifiees',
  /const ENGINE_REQUIRED = \[/.test(code)
  && /ENGINE_REQUIRED\.filter\(\(m\) => typeof st\[m\] !== 'function'\)/.test(code));
ok('un canevas vide fait echouer la connexion',
  /canevas du moteur est absent ou vide/.test(code));
ok('le repli est muet dans l interface et explicite en dev',
  /adapter\.mode !== 'live' && adapter\.reason/.test(code));
/* Chacun des cinq refus possibles dit ce qui manque, en clair. Verifie en
   Chrome contre cinq faux moteurs ; ici on garde les phrases. */
for (const [quoi, re] of [
  ['point d accroche', /point d accroche __studio absent/],
  ['version', /ce pont conduit la v/],
  ['commandes', /commandes manquantes/],
  ['canevas', /canevas du moteur est absent ou vide/],
  ['capacites', /n annonce aucune capacite pilotable/],
]) ok(`le refus « ${quoi} » a sa raison`, re.test(code));

/* Une demande arrivee pendant un rendu ne se perd pas. Le defaut mesure :
   trois clics rapides sur le sens de pose laissaient la capture de repli a
   l'ecran, definitivement. */
ok('une demande concurrente est retenue, pas jetee',
  /state\.pendingApply = true; return;/.test(code)
  && /if \(state\.pendingApply\) \{ state\.pendingApply = false; applyFloor\(\); \}/.test(code));
ok('le rejeu ne peut pas s emballer',
  code.indexOf('state.pendingApply = false;') < code.indexOf('if (state.pendingApply) {'));

/* Plus de sondage : le moteur previent. */
ok('l attente repose sur le signal du moteur',
  /studio\.onRendered\(/.test(code) && !/function settle\(/.test(code)
  && !/same >= 2/.test(code));
ok('l abonnement est pris avant la premiere commande',
  /nextRender\(20000\);[\s\S]{0,120}studio\.selectMaterial/.test(code));
ok('un rendu brouillon laisse sa chance a la passe fine',
  /quality > 1/.test(code) && /affine/.test(code));
/* Une commande refusee par le moteur interrompt l'application : rendre puis
   retenir sous une clef qui annonce autre chose serait un mensonge durable. */
ok('un refus du moteur abandonne l application',
  /studio\.setWidth\(voulue\) !== true/.test(code)
  && /refus = `largeur refusee par le moteur/.test(code)
  && /return null;/.test(code));
/* Dans le corps d'`applyProfile` seulement : `openRoom` s'abonne aussi, et
   comparer des positions a travers tout le fichier ne prouverait rien. */
const corpsApply = code.slice(code.indexOf('async applyProfileMaintenant(profile, orientationDeg)'));
ok('le corps de l application existe hors file', corpsApply.length > 200);
ok('le refus est verifie avant tout abonnement',
  corpsApply.indexOf('studio.setWidth(voulue) !== true') > 0
  && corpsApply.indexOf('studio.setWidth(voulue) !== true')
     < corpsApply.indexOf('const attente = nextRender(20000);'));
ok('le refus est dit en dev', /adapter\.refus/.test(code));

/* Un moteur recharge est un moteur neuf : rien d'ouvert, rien de valable. */
ok('un rechargement du moteur est renegocie',
  /engineScene = null;/.test(code) && /renderCache\.clear\(\);/.test(code)
  && /L'ecouteur `load` reste attache/.test(html));
ok('la promesse de connexion ne se resout qu une fois',
  /if \(resolu\) return;/.test(code) && /resolu = true;/.test(code));
ok('un refus tardif peut degrader le mode',
  code.indexOf('mode = m;') < code.indexOf('if (resolu) return;'));

ok('un brouillon n est jamais retenu',
  /if \(abouti !== 'fin'\) return studio\.canvas;/.test(code));

/* Le cache de captures : clef, borne, eviction, invalidation. */
/* La clef est verifiee plus haut : voir « la clef d etat existe ». Ici on
   garde seulement que le cache est bien indexe par elle. */
ok('le cache est indexe par la clef d etat',
  /cacheGet\(key\)/.test(code) && /cachePut\(key, studio\.canvas\)/.test(code));
ok('le cache est borne', /const RENDER_CACHE_MAX = 8;/.test(code)
  && /renderCache\.size >= RENDER_CACHE_MAX/.test(code));
ok('l eviction sort la moins recemment utilisee',
  /renderCache\.delete\(renderCache\.keys\(\)\.next\(\)\.value\)/.test(code)
  && /renderCache\.delete\(key\);[\s\S]{0,40}renderCache\.set\(key, c\)/.test(code));
ok('le cache est vide quand les pixels changeraient sans que la clef bouge',
  /adapter\.forget\(\)/.test(code) && /renderCache\.clear\(\)/.test(code));
ok('le cout du cache est chiffre dans le fichier',
  /octets/.test(html) && /Mo/.test(html));
ok('le document d integration existe',
  require('fs').existsSync('docs/product-renderer-integration.md'));

/* Priorite des sources : le live prime, la capture amorce et rattrape. */
ok('la capture amorce, le moteur remplace',
  /amorce immediate par la capture/.test(html) && /puis le vrai moteur/.test(html));
ok('le mode live est prioritaire quand il est disponible',
  /if \(adapter\.mode !== 'live'[^)]*\) return;/.test(code));

/* La comparaison doit porter deux VRAIS etats. */
ok('la version B est rendue dans son propre etat puis A restaure',
  /applyProfile\(b\.renderProfile/.test(code)
  && /await applyFloor\(\);/.test(code)
  && /Sans ce retour, les deux cotes montreraient le meme etat/.test(html));

/* findMatchingProduct : on cherche une reference, on n'invente rien. */
ok('le chercheur de variante porte le nom du contrat',
  typeof api.findMatchingProduct === 'function');
ok('il ne renvoie que des references existantes',
  [{ pattern: 'lames' }, { widthMm: 90 }, { tone: 'chaud' }]
    .every((c) => { const r = api.findMatchingProduct(c); return !r || P.includes(r); }));
ok('une combinaison inexistante ne renvoie rien',
  api.findMatchingProduct({ widthMm: 220 }) === null
  && api.findMatchingProduct({ tone: 'fonce' }) === null);

/* Aucune commande decorative : la liste est fermee. */
ok('aucun curseur',
  !/type="range"/.test(html) && !/id="grain"|id="contrast"|id="joint"|id="variation"/.test(html));
ok('le retrait des placebos est explique dans le fichier',
  /n'avaient pas de comportement, seulement un message/.test(html));
/* Chaque entree du menu doit mener quelque part : soit un id cable dans le
   script, soit un etat de demo. Un bouton muet est un mensonge, meme
   discret — « Partager le projet » n'en avait aucun. */
(() => {
  const boutons = html.match(/<button class="mi"[^>]*>/g) || [];
  const muets = boutons.filter((b) => {
    const id = (b.match(/id="([^"]+)"/) || [])[1];
    if (b.includes('data-demo=')) return false;
    /* Cable par $('id') ou par une liste d'ids : dans les deux cas l'id
       apparait dans le script. Un id absent ne peut etre cable. */
    return !id || !code.includes(`'${id}'`);
  });
  ok('aucune entree de menu muette', muets.length === 0, muets.join(' | '));
})();

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
