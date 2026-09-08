/*
  Batterie du concept de Visualiseur — `tools/product-concept.html`.

      node tools/product-concept.check.js       (depuis la racine du dépôt)

  Elle lit le fichier comme du texte, puis exécute son <script> sur un DOM
  minimal. Les deux niveaux servent : la lecture de texte attrape ce que
  l'exécution ne voit pas (un `width: 0` sur le porte-masques, un `<div>`
  orphelin, un z-index inversé), et l'exécution attrape ce que la lecture ne
  voit pas (un masque vide, une largeur non proposée par le produit).

  Ce que la batterie ne remplace pas : l'ouverture réelle dans un navigateur.
  Trois défauts de cette version-ci n'étaient visibles que là — le sol
  entièrement masqué, les modales enfermées dans une section masquée, et la
  version B recouvrant les deux moitiés du comparateur. Chacun a laissé ici
  un test de non-régression, mais aucun n'aurait été trouvé sans Chrome.
*/
const fs = require('fs');
const html = fs.readFileSync('tools/product-concept.html', 'utf8');
let bad = 0;
const ok = (n, c, d) => {
  if (!c) bad += 1;
  console.log(`${c ? 'OK  ' : 'ECHEC'} ${n}${d !== undefined ? '  -> ' + d : ''}`);
};

/* ================= Autonomie et confidentialite ================= */
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
  ['WebGL', /getContext\(\s*['"]webgl/i],
  ['data URI', /;base64,/i],
  ['FileReader', /FileReader/],
]) ok(`aucun ${label}`, !re.test(html));
ok('un seul <script>', (html.match(/<script/g) || []).length === 1);
ok('polices systeme uniquement', /-apple-system/.test(html) && /Georgia/.test(html));
ok('prefers-reduced-motion', /prefers-reduced-motion/.test(html));
ok('aucun asset concurrent',
  !/quick-?step/i.test(html.replace(/quick-step and karndean/i, '')) || !/logo|\.svg"|\.png"/i.test(html));
ok('aucune donnee privee embarquee', !/datasets\/private-real\/[a-z-]+\.jpg["']/.test(
  html.replace(/PHOTOS \+/g, '')) || /const PHOTOS = '\.\.\/datasets\/private-real\/';/.test(html));

/* ================= 1. Plus aucun assistant, plus aucun panneau ================= */
ok('aucun stepper', !/class="steps"/.test(html) && !/data-state="now"/.test(html));
ok('aucune etape numerotee', !/Étape [1-4]/.test(html) && !/étape 1/i.test(html));
ok('« Voir le résultat » absent', !/Voir le résultat/.test(html));
ok('aucune colonne de gauche permanente', !/id="left"/.test(html) && !/class="left"/.test(html));
ok('aucun configurateur permanent', !/id="panel"/.test(html) && !/id="config"/.test(html));
ok('la piece occupe tout sous l en-tete', /#stage \{ flex: 1;/.test(html));
ok('en-tete de 54 px', /height: 54px/.test(html));
ok('en-tete minimal : 4 actions',
  (html.match(/class="hbtn/g) || []).length === 4, `${(html.match(/class="hbtn/g) || []).length} boutons`);

/* ================= 2. Navigation en trois entrees portant leur valeur ========= */
ok('trois entrees de navigation',
  /id="navRoom"/.test(html) && /id="navFloor"/.test(html) && /id="navCustom"/.test(html));
ok('chaque entree affiche sa valeur',
  /id="navRoomVal"/.test(html) && /id="navFloorVal"/.test(html) && /id="navCustomVal"/.test(html));
ok('barre centrale a trois outils',
  /id="baBtn"/.test(html) && /id="cmpBtn"/.test(html) && /id="fsBtn"/.test(html));

/* ================= 3. Deux entrees dans le visualiseur ================= */
ok('porte « Importer ma photo »', /id="doorImport"/.test(html));
ok('porte « Choisir une pièce »', /id="doorRooms"/.test(html));
ok('import present DANS le selecteur de piece', /id="sheetImport"/.test(html));
ok('input fichier JPEG/PNG/WebP', /accept="image\/jpeg,image\/png,image\/webp"/.test(html));
ok('lecture locale par ObjectURL', /URL\.createObjectURL/.test(html));
ok('URL d objet revoquee', /revokeObjectURL/.test(html));
ok('glisser-deposer', /dataTransfer/.test(html));
ok('analyse simulee, pas calculee', /Analyse de votre pièce…/.test(html));
ok('repli si photo absente', /fallbackPhoto/.test(html) && /photo indisponible/.test(html));

/* ================= 4. Le sol vient des vraies calibrations ================= */
ok('source des calibrations documentee',
  /data\/scenes\/<id>\.json/.test(html) && /commit lu\s*:\s*124b553/.test(html)
  && /lu le\s*:\s*8 septembre 2026/.test(html));
/* Et l'etat du front au moment ou on l'ecrit : sans ca, « commit lu »
   laisse croire que c'est la derniere version. */
ok('la fraicheur de la lecture est dite', /encore à jour\s*:/.test(html));
ok('filtre de selection documente', /contour de 8 points au moins/.test(html));
ok('scenes ecartees nommees', /entree-cadree/.test(html) && /salon/.test(html));
ok('aucun polygone generique de repli',
  !/DEFAULT_FLOOR/.test(html) && !/FALLBACK_FLOOR/.test(html)
  && /calibrated\(\) gates|Peignable seulement si/.test(html));
ok('masques SVG, pas clip-path', /<mask id="floorMask"/.test(html) && /<mask id="occlMask"/.test(html));
ok('les trous sont soustraits', /zone\.holes/.test(html));
ok('occulteurs restaurant la photo', /id="occl"/.test(html) && /entry\.occluders/.test(html));
ok('le recadrage cover est pris en compte', /Math\.max\(box\.width \/ entry\.w/.test(html));
/* Regression : un SVG porte-masques en 0x0 empeche Chrome de resoudre
   `mask: url(#floorMask)`, et le sol disparait tout entier. */
ok('le SVG porte-masques occupe la scene',
  /#masks \{[^}]*inset: 0[^}]*\}/.test(html) && !/#masks \{[^}]*width: 0/.test(html));

/* Regression : les modales vivaient dans #stage, masque sur l'ecran
   d'entree — « Choisir une piece » n'ouvrait rien depuis l'accueil. */
const bodyMarkup = html.split('</style>')[1].split('<script>')[0];
ok('les modales sont hors de la scene',
  bodyMarkup.indexOf('id="roomSheet"') > bodyMarkup.indexOf('</section>')
  && bodyMarkup.indexOf('id="catSheet"') > bodyMarkup.indexOf('</section>')
  && bodyMarkup.indexOf('id="cusSheet"') > bodyMarkup.indexOf('</section>'));
ok('les modales sont ancrees a la page', /\.scrim \{ position: fixed/.test(html)
  && /\.sheetp \{\s*position: fixed/.test(html));
/* Et le balisage doit rester equilibre : un <div> orphelin casserait la
   superposition du sol sans qu'aucun test de chaine ne le voie. */
(() => {
  const stack = [];
  let extra = 0;
  for (const tok of bodyMarkup.match(/<\/?div[^>]*>/g) || []) {
    if (tok.startsWith('</')) { if (stack.length) stack.pop(); else extra += 1; }
    else stack.push(tok);
  }
  ok('balisage equilibre', stack.length === 0 && extra === 0,
    `${stack.length} non ferme(s), ${extra} en trop`);
})();

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
    attrs: {}, classList: classList(), children: [], files: [], kids: [],
    style: { setProperty() {} }, parentElement: null,
    firstChild: { addEventListener() {}, style: {} },
    get innerHTML() { return this._h; },
    set innerHTML(v) { this._h = String(v); this.children = parseKids(String(v)); this.kids = []; },
    addEventListener(t, f) { (listeners[key] ??= {})[t] = f; },
    setAttribute(n, v) { this.attrs[n] = String(v); },
    getAttribute(n) { return this.attrs[n] ?? null; },
    appendChild(c) { this.kids.push(c); },
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
  createElementNS: (ns, t) => {
    const n = make(t);
    n.ns = ns;
    n.tagName = t;
    return n;
  },
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

/* ================= 5. Les huit pieces calibrees ================= */
ok('cinq pieces retenues', api.DEMO_ROOMS.length === 5, `${api.DEMO_ROOMS.length}`);
ok('chaque piece a au moins une zone reelle',
  api.DEMO_ROOMS.every((r) => r.zones.length >= 1));
ok('aucun contour grossier',
  api.DEMO_ROOMS.every((r) => r.zones.reduce((n, z) => n + z.poly.length, 0) >= 8),
  `min = ${Math.min(...api.DEMO_ROOMS.map((r) => r.zones.reduce((n, z) => n + z.poly.length, 0)))} points`);
ok('le sejour porte bien ses DEUX zones',
  api.DEMO_ROOMS.find((r) => r.id === 'sejour').zones.length === 2);
const totalZones = api.DEMO_ROOMS.reduce((n, r) => n + r.zones.length, 0);
ok('six zones de sol au total', totalZones === 6, `${totalZones}`);
const totalOccl = api.DEMO_ROOMS.reduce((n, r) => n + r.occluders.length, 0);
ok('occulteurs issus des donnees reelles', totalOccl === 3, `${totalOccl}`);
ok('coordonnees normalisees',
  api.DEMO_ROOMS.every((r) => r.zones.every((z) => z.poly.every(([x, y]) =>
    x >= 0 && x <= 1 && y >= 0 && y <= 1))));
/* Ecartees a l extraction : brouillon ou contour trop grossier.
   Ecartees a la revue visuelle : ancien sol encore visible, sol reduit a une
   bande, ou sol d origine carrele que la recoloration ne rend pas en bois. */
const ECARTEES = ['salon', 'entree-cadree', 'appartement-ancien', 'petite-piece', 'couloir'];
ok('les pieces ecartees sont absentes',
  !api.DEMO_ROOMS.some((r) => ECARTEES.includes(r.id)));
ok('chaque exclusion est motivee dans le fichier',
  ECARTEES.every((id) => html.includes(id)));
ok('la revue visuelle est chiffree', /dernière rangée visible du cadre/.test(html));
ok('la limite de rendu est assumee', /pas pour juger un RENDU/.test(html));

/* Le sol doit descendre jusqu au bas du cadre : sinon l ancien sol reste
   visible au premier plan, ce qui a fait refuser la V4. */
const deep = api.DEMO_ROOMS.map((r) => Math.max(...r.zones.flatMap((z) => z.poly.map(([, y]) => y))));
ok('chaque sol atteint le bas du cadre', Math.min(...deep) >= 0.97,
  `plus haut = ${Math.min(...deep).toFixed(3)}`);
const wide = api.DEMO_ROOMS.map((r) => {
  const xs = r.zones.flatMap((z) => z.poly.map(([x]) => x));
  return Math.max(...xs) - Math.min(...xs);
});
ok('chaque sol couvre une large part de la largeur', Math.min(...wide) >= 0.45,
  `plus etroit = ${Math.min(...wide).toFixed(2)}`);
/* Et il ne doit PAS remonter dans les murs. */
const high = api.DEMO_ROOMS.map((r) => Math.min(...r.zones.flatMap((z) => z.poly.map(([, y]) => y))));
ok('aucun sommet dans le tiers haut', Math.min(...high) >= 0.33,
  `plus haut = ${Math.min(...high).toFixed(3)}`);

/* ================= 6. Les masques ================= */
api.openRoom('sejour');
ok('choisir une piece ouvre le visualiseur', el('stage').classList.contains('hidden') === false);
ok('la source est demo', api.state.source === 'demo', api.state.source);
ok('la photo affichee est celle choisie', String(el('photo').src).includes('sejour.jpg'), el('photo').src);
const zones = api.buildMasks();
ok('le masque reprend les deux zones du sejour', zones === 2, `${zones}`);
ok('les polygones sont poses dans le masque', el('floorShapes').kids.length === 2);
ok('les polygones du masque sont blancs',
  el('floorShapes').kids.every((k) => k.attrs.fill === '#fff'));
const pts = el('floorShapes').kids[0].attrs.points.split(' ').map((p) => p.split(',').map(Number));
ok('les points sont en pixels ecran',
  pts.every(([x, y]) => x >= -600 && x <= 1800 && y >= -400 && y <= 1100),
  `${pts.length} points`);
ok('le sol descend jusqu au bord bas a l ecran',
  Math.max(...el('floorShapes').kids.flatMap((k) => k.attrs.points.split(' ').map((p) => Number(p.split(',')[1])))) >= 700 * 0.97);
ok('les couches de sol portent le masque',
  el('floor').style.mask === 'url(#floorMask)' && el('joints').style.mask === 'url(#floorMask)');
ok('la couche occulteur porte son propre masque', el('occl').style.mask === 'url(#occlMask)');
ok('le masque est dimensionne', el('masks').attrs.width === '1200' && el('masks').attrs.height === '700');

/* Une piece a occulteurs : ils doivent etre poses, sinon un meuble serait
   repeint en parquet. */
api.openRoom('piece-claire');
api.buildMasks();
ok('les occulteurs de la grande piece claire sont poses', el('occlShapes').kids.length === 2,
  `${el('occlShapes').kids.length}`);
api.openRoom('chambre');
api.buildMasks();
ok('la chambre restaure sa grille encastree', el('occlShapes').kids.length === 1);
api.openRoom('sejour');
api.buildMasks();
ok('une piece sans occulteur n en pose aucun', el('occlShapes').kids.length === 0);

/* ================= 7. Une photo inconnue n est PAS masquee ================= */
api.loadUpload({ type: 'image/jpeg', name: 'ma-piece.jpg' });
ok('la source devient uploaded', api.state.source === 'uploaded', api.state.source);
ok('la photo importee devient la scene', String(el('photo').src).includes('blob:local-only'));
ok('ses dimensions reelles sont relevees', api.room().w === 1920 && api.room().h === 1280);
ok('elle n est PAS consideree calibree', api.calibrated() === false);
ok('aucun polygone fabrique', api.buildMasks() === 0);
ok('les couches de parquet sont masquees', el('after').classList.contains('hidden') === true);
ok('le message d honnetete est affiche', /Analyse automatique non connectée/.test(html));
ok('une sortie est proposee', /id="unkRooms"/.test(html) && /id="unkOther"/.test(html));
/* Et la photo doit rester visible derriere le message, sinon « votre photo
   s'affiche » est faux : voile translucide, carte opaque. */
ok('la photo reste visible sous le voile',
  /\.veil \{[^}]*background: rgba\(30, 28, 24, 0\.34\)/.test(html)
  && /\.veil \.box \{[^}]*background: var\(--surface\)/.test(html));
api.loadUpload({ type: 'image/gif', name: 'anim.gif' });
ok('un format refuse ne remplace pas la scene', api.state.uploaded.name === 'ma-piece.jpg',
  api.state.uploaded.name);

/* ================= 8. Rien n est conserve ================= */
api.openRoom('chambre');
ok('changer de piece libere la photo importee', api.state.uploaded === null);
ok("l'URL d'objet est revoquee", revoked.includes('blob:local-only'));
ok('aucune persistance', !/localStorage|sessionStorage|indexedDB/.test(html));

/* ================= 9. Le catalogue, coeur du parcours ================= */
ok('onze produits demo', api.DEMO_PRODUCTS.length === 11, `${api.DEMO_PRODUCTS.length}`);
ok('chaque produit a une reference', api.DEMO_PRODUCTS.every((p) => /DEMO · /.test(p.ref)));
ok('chaque produit a une future fiche', api.DEMO_PRODUCTS.every((p) => /^#fiche\//.test(p.url)));
ok('seuls les trois motifs du moteur du front',
  api.DEMO_PRODUCTS.every((p) => ['straight', 'chevron', 'herringbone'].includes(p.pattern)));
ok('les trois motifs du front sont connus',
  Object.keys(api.PATTERNS).length === 3 && /point-de-hongrie|Point de Hongrie/.test(html));
api.openCat();
ok('la grille montre tous les produits', count('prods', /class="pd"/g) === 11);
ok('les vignettes sont des textures, pas du texte', count('prods', /class="tex"/g) === 11);
ok('le compte figure dans le titre', el('catCount').textContent === '(11)', el('catCount').textContent);
/* Les deux seules occurrences de « Appliquer » sont des commentaires qui
   rappellent qu'il n'y en a pas : ce test cherche un vrai bouton. */
ok('aucun bouton « Appliquer »',
  !/<button[^>]*>[^<]*Appliquer/.test(html) && !/>Appliquer</.test(html));
ok('filtre motif', count('fPattern', /class="chip"/g) === 3);
ok('teintes en pastilles', count('fTone', /class="dot-b"/g) >= 6);
ok('filtre essence', count('fSpecies', /class="chip"/g) === 3);
ok('inspirations = filtres du catalogue', count('moods', /class="mood"/g) === 6);

const before = api.visible().length;
api.toggleFilter('pattern', 'herringbone');
ok('un filtre reduit la grille', api.visible().length === 2, `${before} -> ${api.visible().length}`);
ok('le compte suit le filtre', el('catCount').textContent === '(2)', el('catCount').textContent);
api.toggleFilter('pattern', 'herringbone');
ok('le meme filtre se retire', api.visible().length === before);
api.toggleFilter('mood', 'hongrie');
ok('une inspiration filtre aussi', api.visible().length === 2, `${api.visible().length}`);
api.toggleFilter('mood', 'hongrie');

/* ================= 10. Le clic EST l action ================= */
api.select('demo-oak-smoked');
ok('choisir un parquet le pose immediatement', api.state.productId === 'demo-oak-smoked');
ok('la largeur retombe sur une largeur reelle',
  api.product().availableWidths.includes(api.state.width), `${api.state.width} mm`);
ok('la finition retombe sur une finition reelle',
  api.product().availableFinishes.includes(api.state.finish), api.state.finish);
ok('la navigation affiche le parquet pose',
  el('navFloorVal').textContent === 'Chêne fumé', el('navFloorVal').textContent);
ok('la carte produit est petite et flottante',
  /#card, #cardB \{[\s\S]*?width: 196px/.test(html));
ok('la carte porte la reference', /class="ref"/.test(h('card')));
ok('la carte propose la fiche', /VOIR LA FICHE/.test(h('card')));
ok('la carte porte precedent / favori / suivant',
  /data-step="prevA"/.test(h('card')) && /data-fav=/.test(h('card')) && /data-step="nextA"/.test(h('card')));

const current = api.state.productId;
api.stepProduct(1, 'A');
ok('la fleche suivant change de parquet', api.state.productId !== current, api.state.productId);
api.stepProduct(-1, 'A');
ok('la fleche precedent revient', api.state.productId === current, api.state.productId);

/* ================= 11. Personnaliser : capacites reelles seulement ========= */
api.select('demo-oak-natural');
api.paintCustom();
ok('deux motifs pour le chene naturel', count('patterns', /class="pt"/g) === 2,
  `${count('patterns', /class="pt"/g)}`);
ok('les motifs absents sont annonces', /indisponible/.test(el('patternNote').textContent),
  el('patternNote').textContent);
ok('trois largeurs pour le chene naturel', count('widths', /class="chip"/g) === 3);
api.select('demo-oak-smoked');
api.paintCustom();
ok('deux largeurs pour le chene fume', count('widths', /class="chip"/g) === 2);
ok('une seule finition pour le chene fume', count('finishes', /class="chip"/g) === 1);
ok('la restriction est expliquee', /Finitions proposées/.test(el('finishNote').textContent));
ok('deux sens de pose', count('orient', /class="or"/g) === 2);
ok('reglages avances replies', /<div id="adv" class="hidden"/.test(html));
ok('quatre reglages avances', (html.match(/class="slide"/g) || []).length === 4);

/* ================= 12. Favoris, comparaison, avant/apres ================= */
ok('aucun favori au depart', api.state.favourites.size === 0);
api.toggleFav('demo-walnut');
ok('un favori se pose', api.state.favourites.has('demo-walnut'));
ok('le compteur d en-tete suit', el('favCount').textContent === '1');
api.toggleFav('demo-walnut');
ok('un favori se retire', api.state.favourites.size === 0);

api.state.compare = { b: 'demo-walnut' };
api.paint();
ok('la comparaison affiche deux cartes', el('cardB').classList.contains('hidden') === false);
ok('les versions sont etiquetees', el('tagA').classList.contains('hidden') === false
  && el('tagB').classList.contains('hidden') === false);
ok('la navigation s efface pendant la comparaison', el('nav').classList.contains('hidden') === true);
ok('la comparaison est UNE photo scindee', /id="split"/.test(html) && !/grid-template-columns: repeat\(3/.test(
  (html.match(/#cmp[\s\S]{0,200}/) || [''])[0]));
ok('le second parquet est rendu', /url\('/.test(String(el('cmpFloor').style.backgroundImage)));
/* Regression : #cmpLayer (z-index 1) peignait au-dessus de #after sans
   z-index, et la version B recouvrait les DEUX moities du separateur.
   Les deux couches ne se declarent pas au meme endroit : #cmpLayer porte son
   z-index en attribut style, #after dans la feuille. */
const zOf = (id) => {
  const inline = html.match(new RegExp('id="' + id + '"[^>]*style="[^"]*z-index:[ ]*([0-9]+)'));
  if (inline) return Number(inline[1]);
  const sheet = html.match(new RegExp('#' + id + '[^{]*[{][^}]*z-index:[ ]*([0-9]+)'));
  return sheet ? Number(sheet[1]) : null;
};
ok('la version A est au-dessus de la version B',
  zOf('cmpLayer') !== null && zOf('after') !== null && zOf('cmpLayer') < zOf('after'),
  `cmpLayer ${zOf('cmpLayer')} < after ${zOf('after')}`);
ok('les occulteurs restent au-dessus des deux',
  zOf('occl') > zOf('after'), `occl ${zOf('occl')} > after ${zOf('after')}`);
api.stepProduct(1, 'B');
ok('le cote B change seul', api.state.compare.b !== 'demo-walnut' && api.state.productId === 'demo-oak-smoked',
  `${api.state.compare.b} / ${api.state.productId}`);
api.state.compare = null;
api.paint();
ok('fermer la comparaison rend la navigation', el('nav').classList.contains('hidden') === false);

api.state.ba = true;
api.state.split = 0.4;
api.paint();
ok('avant/apres decoupe le parquet', el('after').style.clipPath === 'inset(0 60.00% 0 0)',
  el('after').style.clipPath);
ok('le separateur est visible', el('split').classList.contains('hidden') === false);
api.state.ba = false;
api.paint();
ok('avant/apres se desactive', el('after').style.clipPath === 'none');
ok('le separateur disparait', el('split').classList.contains('hidden') === true);

/* ================= 13. Changer de piece conserve le parquet ================= */
const kept = api.state.productId;
api.openRoom('bureau-vide');
ok('le parquet survit au changement de piece', api.state.productId === kept, api.state.productId);
ok('la nouvelle piece est peinte', String(el('photo').src).includes('bureau-vide.jpg'));
ok('le masque est reconstruit', el('floorShapes').kids.length === 1);

/* ================= 14. Etats d analyse ================= */
api.setDemo('success', true);
ok('« Pièce prête » est une petite capsule',
  /Pièce prête/.test(h('status')) && /#status \{[\s\S]*?border-radius: var\(--r-pill\)/.test(html));
ok('aucun bandeau plein cadre pour un succes', el('rejected').classList.contains('hidden') === true);
api.setDemo('partial', true);
ok('partial propose un ajustement', /Ajuster/.test(h('status')));
api.setDemo('manual', true);
ok('manual insiste visuellement', el('status').classList.contains('urge') === true);
api.setDemo('rejected', true);
ok('rejected explique et propose une reprise', el('rejected').classList.contains('hidden') === false);
ok('le conseil de reprise est concret', /appuyez-vous contre un mur/.test(html));
api.setDemo('success', true);
ok('la retouche au pinceau existe', /id="brush"/.test(html) && /Ajouter/.test(html) && /Retirer/.test(html));

/* ================= 15. Le selecteur de piece ================= */
api.openRooms();
ok('les categories sont listees', count('roomCats', /data-cat=/g) === 4,
  `${count('roomCats', /data-cat=/g)} categories`);
ok('le compte des pieces est affiche', /5 pièces calibrées/.test(el('roomCount').textContent),
  el('roomCount').textContent);
ok('la grille montre de vraies photos', count('roomGrid', /<img/g) >= 1);
ok('la piece courante est cochee', /class="tick"/.test(h('roomGrid')));
ok('le nombre de zones est annonce', /zone/.test(h('roomGrid')));

/* ================= 15 bis. La couverture du sol, mesuree =================
   Point-dans-polygone sur la derniere rangee visible du cadre : au premier
   plan, une photo d interieur prise debout montre du sol sur presque toute
   la largeur. Un score faible signifie que de l ancien sol reste affiche —
   le defaut qui a fait refuser la V4. */
const STAGE = { left: 0, top: 0, width: 1200, height: 700 };
function inside(pt, poly) {
  let c = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i]; const [xj, yj] = poly[j];
    if (((yi > pt[1]) !== (yj > pt[1])) && (pt[0] < (xj - xi) * (pt[1] - yi) / (yj - yi) + xi)) c = !c;
  }
  return c;
}
const coverage = api.DEMO_ROOMS.map((r) => {
  const to = api.mapper(STAGE, r);
  const polys = r.zones.map((z) => z.poly.map(to));
  const y = STAGE.height - 3;
  let on = 0;
  for (let i = 0; i < 200; i++) {
    const x = (i + 0.5) * STAGE.width / 200;
    if (polys.some((p) => inside([x, y], p))) on += 1;
  }
  return { id: r.id, pct: on / 2 };
});
ok('aucune piece ne laisse un pan d ancien sol au premier plan',
  coverage.every((c) => c.pct >= 80),
  coverage.map((c) => `${c.id} ${c.pct.toFixed(0)}%`).join(', '));

/* ================= 16. Le motif, pas une grille ================= */
const wood = api.woodCss('straight', { joint: 100, grain: 100, variation: 100, width: 190 });
const alphas = [...wood.matchAll(/rgba\(52, 33, 18, ([\d.]+)\)/g)].map((m) => Number(m[1]));
ok('joints doux meme au maximum', Math.max(...alphas) <= 0.2, `alpha max = ${Math.max(...alphas)}`);
ok('aucun noir pur dans le motif', !/rgba\(0, 0, 0, [1-9]/.test(wood) && !/#000/.test(wood));
ok('le motif porte un veinage', wood.split('repeating-linear-gradient').length - 1 >= 3);
ok('le point de Hongrie est a 45 deg', /45deg/.test(api.woodCss('chevron', api.opts())));
ok('le sens de pose fait tourner le motif',
  api.woodCss('straight', api.opts()) !== (() => {
    api.state.orient = 'cross';
    const c = api.woodCss('straight', api.opts());
    api.state.orient = 'long';
    return c;
  })());

/* ================= 17. Textures de produit lisibles ================= */
const tex = api.texture(api.product('demo-walnut'), 1.5);
ok('la texture produit est procedurale', /linear-gradient/.test(tex) && !/url\(/.test(tex));
ok('la texture ne depend pas de la photo', !/blob:|\.jpg/.test(tex));
ok('aucune apostrophe double dans un attribut style', !/style="[^"]*url\("/.test(html));
ok('les pastilles ne sont pas en display inline',
  /\.pd \.tex \{[\s\S]*?display: block/.test(html) && /#card \.sw[\s\S]*?display: block/.test(html));

console.log(bad ? `\n${bad} ECHEC(S)` : '\nAUCUN ECHEC');
process.exit(bad ? 1 : 0);
