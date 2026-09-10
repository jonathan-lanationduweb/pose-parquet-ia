/**
 * Matériau.
 *
 * Un parquet n'est pas une teinte : c'est une essence, une largeur de lame,
 * une finition, un veinage — et, à terme, un jeu de cartes physiques.
 *
 * Le modèle de données prévoit dès maintenant les trois cartes usuelles :
 *
 *   albedo     couleur du bois, sans lumière
 *   normal     relief : chanfreins, veines creusées, joints
 *   roughness  brillance locale : une veine ouverte est plus mate qu'un nœud
 *
 * Aucune n'est fournie sous forme de fichier aujourd'hui : nous n'avons pas de
 * ressources photographiques adaptées, et fabriquer de fausses normal maps
 * n'apporterait rien. L'albedo est donc dessiné par le moteur procédural
 * (js/scene/texture.js), et le relief est dérivé de sa luminance — une
 * approximation honnête, remplacée sans rien casser le jour où de vraies
 * cartes existent :
 *
 *   assets/materials/chene-naturel/
 *     albedo.webp  normal.webp  roughness.webp  thumbnail.webp
 *
 * Il suffit alors de déclarer `maps` dans data/parquets.json.
 */
import { buildTexture, buildMips, etendreMips, TILE, TILE_METERS } from './texture.js';
import { reliefFromAlbedo } from './relief.js';
import { chrono } from '../utils/perf.js';

/** Rugosité de référence par finition : ce qui distingue mat, satiné, verni. */
const FINISH = {
  brut: { roughness: 0.95, clearcoat: 0.0 },
  huile: { roughness: 0.82, clearcoat: 0.04 },
  mat: { roughness: 0.74, clearcoat: 0.08 },
  satine: { roughness: 0.5, clearcoat: 0.22 },
  vernis: { roughness: 0.34, clearcoat: 0.38 },
  cire: { roughness: 0.6, clearcoat: 0.16 },
};

/** Devine la finition à partir de son libellé — le catalogue est en français. */
function finishProfile(label = '', declared) {
  if (declared && FINISH[declared]) return { key: declared, ...FINISH[declared] };
  const text = label.toLowerCase();
  // « brossé » : la brosse creuse le grain et mate la surface. Sans ce cas, un
  // « Fumé brossé » retombait sur « mat » et recevait un reflet qu'il n'a pas.
  const key = text.includes('brut') || text.includes('bross')
    ? 'brut'
    : text.includes('satin')
      ? 'satine'
      : text.includes('vernis')
        ? text.includes('mat')
          ? 'mat'
          : 'vernis'
        : text.includes('cir')
          ? 'cire'
          : text.includes('huil')
            ? 'huile'
            : 'mat';
  return { key, ...FINISH[key] };
}

/**
 * Enrichit une entrée de data/parquets.json en matériau complet.
 * L'entrée d'origine reste accessible : le catalogue et les vignettes
 * continuent de fonctionner à l'identique.
 */
export function createMaterial(entry) {
  const finish = finishProfile(entry.finish, entry.finishKind);
  return {
    ...entry,
    plank: {
      width: entry.boardWidth,
      length: entry.boardLength || entry.boardWidth * 9,
      bevel: entry.texture.bevel,
    },
    surface: {
      roughness: Number.isFinite(entry.roughness) ? entry.roughness : finish.roughness,
      clearcoat: Number.isFinite(entry.clearcoat) ? entry.clearcoat : finish.clearcoat,
      // Amplitude du relief, en fraction de la largeur de lame. Le bois brut
      // accroche la lumière, un vernis épais l'aplanit.
      relief: Number.isFinite(entry.relief) ? entry.relief : 0.45 - finish.clearcoat * 0.6,
      finishKind: finish.key,
    },
    variation: Number.isFinite(entry.variation) ? entry.variation : entry.texture.spread / 30,
    /**
     * Cartes physiques. Vides aujourd'hui : voir assets/materials/README.md.
     * `hasMaps` dit si le moteur peut s'en servir ; sinon il retombe sur le
     * dessin procédural, qui reste la source de vérité par défaut.
     */
    maps: {
      albedo: (entry.maps && entry.maps.albedo) || null,
      normal: (entry.maps && entry.maps.normal) || null,
      roughness: (entry.maps && entry.maps.roughness) || null,
    },
    hasMaps: Boolean(entry.maps && entry.maps.albedo),
    proceduralFallback: entry.proceduralFallback !== false,
    /** Dimensions et angle propres à chaque motif. Voir js/scene/texture.js. */
    patternProfiles: entry.patternProfiles || null,
  };
}

/* ------------------------------------------------------------------ */
/* Fabrication des cartes                                              */
/* ------------------------------------------------------------------ */

const cache = new Map();
const MAX_CACHE = 12;
/** Niveaux de la pyramide attendus par le moteur logiciel. */
const NIVEAUX = 5;
const key = (material, config) =>
  `${material.id}|${config.pattern}|${config.width || 'auto'}|${config.plankLength || 'auto'}`;

/**
 * Relief dérivé de l'albedo.
 *
 * Faute de vraie normal map, on lit le relief dans la luminance de la tuile :
 * un joint sombre est un creux, un chanfrein clair une arête. C'est faux d'un
 * point de vue physique, mais visuellement juste sur du bois — et ça suffit à
 * faire accrocher la lumière sur les joints, ce qui est précisément le détail
 * qui manque quand un parquet a l'air peint.
 *
 * Sortie : une carte RG (dérivées x et y), packée dans les canaux 0 et 1, plus
 * la rugosité locale dans le canal 2. Un seul échantillonnage suffit au shader.
 */

/**
 * Cartes prêtes à échantillonner pour un matériau et une configuration.
 *
 * @returns {{albedo: {size,data}[], relief: {size,data}[], tile: HTMLCanvasElement,
 *            meters: number, surface: object}}
 */
/**
 * Assemble l'objet `maps` à partir du niveau 0 de l'albedo et du relief.
 * Commun aux deux voies de fabrication, synchrone et worker.
 */
function assemble(material, tile, albedo0, relief0) {
  const albedo = [albedo0];
  const relief = [relief0];
  const maps = {
    albedo,
    relief,
    tile,
    meters: TILE_METERS,
    size: TILE,
    surface: material.surface,
    /**
     * Complète la pyramide : à appeler avant tout échantillonnage de niveau > 0.
     *
     * Le moteur logiciel lit `maps.albedo.length - 1` comme niveau maximal ;
     * il doit donc appeler ceci d'abord, sinon il travaillera à la seule pleine
     * résolution et le moirage des lames lointaines reviendra. Idempotent.
     */
    completer() {
      if (albedo.length >= NIVEAUX) return maps;
      chrono('texture.mips+', () => etendreMips(albedo, NIVEAUX));
      chrono('texture.relief+', () => {
        for (let i = relief.length; i < albedo.length; i += 1) relief.push(reliefFromAlbedo(albedo[i], material.surface));
      });
      return maps;
    },
  };
  return maps;
}

function retenir(id, maps) {
  if (cache.size >= MAX_CACHE) cache.delete(cache.keys().next().value);
  cache.set(id, maps);
  return maps;
}

/* ------------------------------------------------------------------ */
/* Fabrication hors du fil principal                                   */
/* ------------------------------------------------------------------ */

/**
 * Le worker n'est créé qu'à la première demande, et une seule fois.
 *
 * `OffscreenCanvas` manque encore à quelques navigateurs : dans ce cas la
 * fabrication reste synchrone, comme avant — plus lente, mais juste.
 */
let worker = null;
let workerIndisponible = false;
const enCours = new Map();   // clé → { resolve, reject, material, tile }
const abonnes = new Set();
let compteur = 0;

function obtenirWorker() {
  if (worker || workerIndisponible) return worker;
  if (typeof Worker !== 'function' || typeof OffscreenCanvas !== 'function') {
    workerIndisponible = true;
    return null;
  }
  try {
    worker = new Worker(new URL('./texture-worker.js', import.meta.url), { type: 'module' });
  } catch {
    workerIndisponible = true;
    return null;
  }
  worker.onmessage = (event) => {
    const { id, albedo, relief, erreur, bitmap } = event.data || {};
    const attente = enCours.get(id);
    if (!attente) return;
    enCours.delete(id);
    if (erreur) {
      attente.reject(new Error(erreur));
      return;
    }
    if (bitmap) {
      // Aperçu : rien à mettre en cache de cartes, on livre l'image.
      apercus.set(attente.cle, bitmap);
      attente.resolve(bitmap);
      return;
    }
    // Les tableaux arrivent transférés : `Uint8ClampedArray` reconstruite sur
    // le tampon reçu, sans copie.
    const a0 = { size: albedo.size, data: new Uint8ClampedArray(albedo.data.buffer || albedo.data) };
    const r0 = { size: relief.size, data: new Uint8ClampedArray(relief.data.buffer || relief.data) };
    const maps = retenir(attente.cle, assemble(attente.material, null, a0, r0));
    attente.resolve(maps);
    abonnes.forEach((cb) => { try { cb(attente.cle, maps); } catch { /* un abonné défaillant n'arrête pas les autres */ } });
  };
  worker.onerror = () => {
    // Le worker est hors d'usage : on rejette ce qui attend et on repasse en
    // synchrone pour la suite de la session.
    enCours.forEach((att) => att.reject(new Error('worker de texture indisponible')));
    enCours.clear();
    worker.terminate();
    worker = null;
    workerIndisponible = true;
    abonnes.forEach((cb) => { try { cb(null, null); } catch { /* idem */ } });
  };
  return worker;
}

/**
 * Prévenu quand des cartes demandées en asynchrone sont prêtes.
 * Le rendu qui a dû s'abstenir se replanifie sur ce signal.
 */
export function quandCartesPretes(cb) {
  abonnes.add(cb);
  return () => abonnes.delete(cb);
}

/** Les cartes sont-elles en train d'être fabriquées ailleurs ? */
export function enFabrication(material, config) {
  return [...enCours.values()].some((a) => a.cle === key(material, config));
}

/**
 * Demande les cartes au worker. Résout avec l'objet `maps`, déjà en cache.
 * Deux demandes identiques ne lancent qu'un calcul.
 */
export function materialMapsAsync(material, config = {}) {
  const cle = key(material, config);
  if (cache.has(cle)) return Promise.resolve(cache.get(cle));
  const deja = [...enCours.values()].find((a) => a.cle === cle);
  if (deja) return deja.promesse;
  const w = obtenirWorker();
  if (!w) return Promise.resolve(materialMaps(material, config));
  let resolve; let reject;
  const promesse = new Promise((res, rej) => { resolve = res; reject = rej; });
  const id = (compteur += 1);
  enCours.set(id, { cle, material, resolve, reject, promesse });
  // Le matériau part en copie structurée : données pures uniquement.
  w.postMessage({
    id,
    material: JSON.parse(JSON.stringify(material)),
    config: { pattern: config.pattern || material.defaultPattern, width: config.width || null },
  });
  return promesse;
}

/* ------------------------------------------------------------------ */
/* Aperçus de motif                                                    */
/* ------------------------------------------------------------------ */

const apercus = new Map();
const MAX_APERCUS = 24;

/**
 * Aperçu d'un motif pour un matériau, hors du fil principal.
 *
 * Le panneau des motifs redessinait trois tuiles de 320 px à chaque
 * ouverture et à chaque changement de motif — sur le fil principal, via
 * `requestIdleCallback`. Or le coût d'une tuile ne dépend presque pas de sa
 * taille (il est dans l'émission des tracés) : mesuré, l'ouverture du panneau
 * bloquait le fil jusqu'à 726 ms, et le point de Hongrie, dont les cartes
 * étaient pourtant déjà fabriquées ailleurs, gardait ce blocage.
 *
 * Résout avec un `ImageBitmap` prêt à dessiner. Mémoïsé par matériau, motif
 * et taille ; repli synchrone sans worker.
 */
export function apercuAsync(material, pattern, size = 320) {
  const cle = `apercu|${material.id}|${pattern}|${size}`;
  if (apercus.has(cle)) return Promise.resolve(apercus.get(cle));
  const deja = [...enCours.values()].find((a) => a.cle === cle);
  if (deja) return deja.promesse;
  const wk = obtenirWorker();
  if (!wk) return Promise.resolve(buildTexture(material, { pattern, size }));
  if (apercus.size >= MAX_APERCUS) {
    const premier = apercus.keys().next().value;
    const vieux = apercus.get(premier);
    if (vieux && vieux.close) vieux.close();
    apercus.delete(premier);
  }
  let resolve; let reject;
  const promesse = new Promise((res, rej) => { resolve = res; reject = rej; });
  const id = (compteur += 1);
  enCours.set(id, { cle, material, resolve, reject, promesse });
  wk.postMessage({ id, kind: 'apercu', material: JSON.parse(JSON.stringify(material)), config: { pattern, size } });
  return promesse;
}

/** Le worker existe-t-il ? Décide si `materialMaps` peut renvoyer null. */
export const fabricationAsynchrone = () => Boolean(obtenirWorker());

/**
 * Cartes d'un matériau, depuis le cache.
 *
 * Si elles n'y sont pas ET qu'un worker est disponible, la fabrication est
 * lancée là-bas et cette fonction renvoie `null` : le moteur peint ce qu'il
 * peut (rien pour cette surface) et l'application est prévenue par
 * `quandCartesPretes`. Sans worker, on fabrique ici, comme avant.
 */
export function materialMaps(material, config = {}) {
  const id = key(material, config);
  if (cache.has(id)) return cache.get(id);
  if (obtenirWorker()) {
    materialMapsAsync(material, config);
    return null;
  }

  // `width` n'est transmis que si l'utilisateur l'a explicitement réglé : sans
  // quoi on court-circuiterait le choix de largeur propre au motif (une lame
  // droite de 18 cm, un chevron de 9 cm).
  const tile = chrono('texture.tuile', () => buildTexture(material, {
    pattern: config.pattern || material.defaultPattern,
    width: config.width || null,
  }));
  // Niveau 0 seulement : les réductions ne servent qu'au moteur logiciel, et
  // `completer()` les fabrique le jour où il les demande. Voir etendreMips().
  const albedo0 = chrono('texture.mips0', () => buildMips(tile, 1))[0];
  const relief0 = chrono('texture.relief0', () => reliefFromAlbedo(albedo0, material.surface));
  return retenir(id, assemble(material, tile, albedo0, relief0));
}

/** Prépare des cartes sans bloquer : sert à précharger les références voisines. */
/**
 * Les cartes de ce matériau sont-elles déjà prêtes ?
 *
 * Sert à l'interface, pas au moteur : construire une tuile coûte de 0,8 à
 * 3 secondes de fil principal, et un clic qui déclenche cette construction
 * doit pouvoir le dire au lieu de laisser croire à un blocage.
 */
export function enCache(material, config) {
  return cache.has(key(material, config));
}

/**
 * Prépare les cartes d'un matériau pendant une période d'inactivité.
 *
 * Sans délai de garde, volontairement. La version précédente passait
 * `{ timeout: 1200 }` à `requestIdleCallback`, ce qui garantit l'exécution
 * au bout d'une seconde et demie même si le fil principal est occupé — donc
 * exactement au moment où il ne faut pas, une tuile coûtant jusqu'à trois
 * secondes. Sans garde, si le navigateur ne trouve jamais de répit, la tuile
 * ne se construit pas d'avance : elle se construira à la demande, ce qui est
 * le comportement correct.
 */
export function warmMaterial(material, config) {
  if (cache.has(key(material, config))) return;
  const run = () => { materialMapsAsync(material, config).catch(() => {}); };
  if (typeof window.requestIdleCallback === 'function') window.requestIdleCallback(run);
  else window.setTimeout(run, 400);
}

export const clearMaterialCache = () => cache.clear();
