/**
 * Analyse d'une pièce : le seul endroit qui sait d'où viennent les données.
 *
 *   IMAGE  →  analyzeScene()  →  SceneData  →  moteur de rendu
 *
 * Deux stratégies existent aujourd'hui, et aucune ne fait d'analyse d'image :
 *
 *   - `precalibrated` : lit data/scenes/<id>.json, calibré à la main ;
 *   - `manual`        : fabrique une scène minimale que l'utilisateur ajuste.
 *
 * Une troisième viendra un jour, sans que le reste du visualiseur change :
 *
 *   registerAnalyzer('remote', async ({ file }) => {
 *     const body = new FormData();
 *     body.append('image', file);
 *     const res = await fetch(`${API}/analyze-room`, { method: 'POST', body });
 *     return res.json(); // normalisée automatiquement ci-dessous
 *   });
 *
 * Le contrat de cette réponse est écrit dans docs/future-ai-api-contract.md.
 * Tant que cette stratégie n'est pas enregistrée, l'interface ne parle ni
 * d'analyse ni de détection : ce serait faux.
 */
import { normalizeScene, createBlankScene } from './schema.js';

const analyzers = new Map();

export function registerAnalyzer(name, fn) {
  analyzers.set(name, fn);
}
export const hasAnalyzer = (name) => analyzers.has(name);
export const availableAnalyzers = () => [...analyzers.keys()];

/**
 * @param {object} context
 * @param {string} [context.sceneId]  pièce d'exemple à charger
 * @param {number} [context.width]    dimensions de l'image, pour une photo
 * @param {number} [context.height]
 * @param {File}   [context.file]     photo d'origine (pour une future analyse)
 * @param {string} [context.base]     préfixe des chemins du site
 * @param {string} [strategy]         défaut : `precalibrated` si un id est fourni
 * @returns {Promise<object>} SceneData normalisée
 */
export async function analyzeScene(context = {}, strategy) {
  const name = strategy || (context.sceneId ? 'precalibrated' : 'manual');
  const analyzer = analyzers.get(name) || analyzers.get('manual');
  const raw = await analyzer(context);
  return raw && raw.schema && raw.floorZones && raw.surfaces ? raw : normalizeScene(raw);
}

/* ------------------------------------------------------------------ */
/* Pièces d'exemple : scènes calibrées à la main                       */
/* ------------------------------------------------------------------ */

const cache = new Map();

/** Manifeste des pièces d'exemple. */
export async function loadSceneIndex(base = '') {
  if (!cache.has('__index__')) {
    cache.set(
      '__index__',
      // `no-cache` : le navigateur peut garder le fichier, mais il le
      // revalide à chaque chargement. Sans cela, un manifeste gardé dix
      // minutes par l'hébergeur suffit à faire disparaître une scène qu'on
      // vient d'ajouter — et un lien profond vers elle tombe dans le vide.
      // La réponse est de quelques kilo-octets et revient en 304.
      fetch(`${base}data/scenes/index.json`, { cache: 'no-cache' }).then((response) => {
        if (!response.ok) throw new Error('Pièces d’exemple indisponibles');
        return response.json();
      })
    );
  }
  return cache.get('__index__');
}

/**
 * Statut d'une pièce d'exemple.
 *
 *   validated     calibrée, relue, proposée aux visiteurs ;
 *   experimental  gardée pour le contrôle qualité, pas proposée ;
 *   disabled      conservée dans le dépôt mais hors service.
 *
 * Une scène difficile a de la valeur : elle montre où le moteur plie. La
 * supprimer pour faire propre, c'est perdre le seul cas qui apprenait quelque
 * chose. Le statut permet de la garder sans l'imposer à un visiteur.
 *
 * **Le défaut est `experimental`, pas `validated`.** Une scène dont le statut
 * a été oublié n'apparaît donc pas publiquement : l'oubli fait rater une
 * scène, il ne publie pas un rendu que personne n'a regardé.
 */
export const STATUTS = ['validated', 'experimental', 'disabled'];

/**
 * DEUX statuts, parce qu'une scène peut être juste et laide.
 *
 * `geometryStatus` dit si la perspective, l'échelle et le contour sont
 * prouvés : deux directions mesurées, une focale déduite, un quadrilatère
 * orthogonal, des résidus au pixel. `visualStatus` dit si le RENDU est
 * présentable.
 *
 * Les deux ne se déduisent pas l'un de l'autre, et c'est la leçon de cette
 * passe. Trois scènes portaient `status: validated` sur la seule foi de leur
 * géométrie :
 *
 *   - piece-claire : masque qui monte sur le mur de gauche, bord en dents de
 *     scie, occulteurs en boîtes englobantes ;
 *   - appartement-ancien : une bande du MÊME sol, le long du mur droit, n'est
 *     pas couverte par le masque — le visiteur voit la moitié du couloir
 *     changer ;
 *   - contraste : ce n'est pas une pièce. Un mur, un rai de soleil, une
 *     lisière de sol. Excellente pour éprouver le report de lumière, absurde
 *     comme « pièce d'exemple » offerte au visiteur.
 *
 * Aucun chiffre géométrique ne dit cela. Il faut regarder.
 *
 * Le défaut de `visualStatus`, en cas d'oubli, est `experimental` : une
 * scène qu'on n'a pas regardée ne se publie pas.
 */
const lire = (liste, valeur, defaut) => (liste.includes(valeur) ? valeur : defaut);

/**
 * Le vocabulaire du visuel a un mot de plus : `failed`.
 *
 * `experimental` veut dire « pas encore regardé, ou gardé comme cas de test ».
 * `failed` veut dire « regardé, et rejeté pour une raison écrite ». Les deux
 * excluent du public, mais pas pour la même raison, et confondre les deux
 * revient à perdre la trace du travail de revue : on ne saurait plus si une
 * scène attend un regard ou si elle a déjà été jugée.
 */
export const STATUTS_VISUELS = ['validated', 'experimental', 'failed', 'disabled'];

/** Géométrie prouvée ? `status` est encore lu pour les manifestes anciens. */
export const geometrieDe = (entry) => lire(STATUTS, entry && entry.geometryStatus, lire(STATUTS, entry && entry.status, 'experimental'));

/** Rendu regardé et jugé présentable ? */
export const visuelDe = (entry) => lire(STATUTS_VISUELS, entry && entry.visualStatus, 'experimental');

/**
 * Statut d'ensemble, pour l'affichage : le moins avancé des deux.
 * `disabled` d'un côté ferme la scène ; sinon il faut deux `validated`.
 */
export const statutDe = (entry) => {
  const g = geometrieDe(entry);
  const v = visuelDe(entry);
  if (g === 'disabled' || v === 'disabled') return 'disabled';
  if (v === 'failed') return 'failed';
  return g === 'validated' && v === 'validated' ? 'validated' : 'experimental';
};

/** Les pièces proposées au visiteur : géométrie ET rendu validés. */
export const scenesPubliques = (index) =>
  (index && Array.isArray(index.scenes) ? index.scenes : [])
    .filter((e) => geometrieDe(e) === 'validated' && visuelDe(e) === 'validated');

/**
 * Les pièces listées dans « Changer de pièce ».
 *
 * Publiable et proposée dans la bibliothèque sont deux choses différentes.
 * Une scène calibrée pour une carte d'inspiration est essayable par son lien
 * sans devoir figurer dans la liste principale : les huit inspirations
 * calibrées, la bibliothèque doublerait et le choix deviendrait un catalogue
 * à faire défiler.
 *
 * `showInRoomLibrary: false` retire une scène de la liste sans la déclasser.
 * Le défaut est VRAI : une scène validée se propose, sauf décision contraire
 * écrite dans le manifeste. Un oubli garde donc le comportement d'avant.
 */
export const scenesBibliotheque = (index) =>
  scenesPubliques(index).filter((e) => e.showInRoomLibrary !== false);

/**
 * Les pièces qu'on accepte d'ouvrir sur demande explicite (lien direct).
 * Une scène expérimentale reste atteignable pour la relecture ; une scène
 * `disabled` ne s'ouvre pas.
 */
export const sceneOuvrable = (index, id) => {
  const entry = (index && Array.isArray(index.scenes) ? index.scenes : []).find((e) => e.id === id);
  return entry && geometrieDe(entry) !== 'disabled' ? entry : null;
};

registerAnalyzer('precalibrated', async ({ sceneId, base = '' }) => {
  const key = `${base}|${sceneId}`;
  if (!cache.has(key)) {
    cache.set(
      key,
      fetch(`${base}data/scenes/${sceneId}.json`).then(async (response) => {
        if (!response.ok) throw new Error(`Pièce « ${sceneId} » introuvable`);
        return normalizeScene({ ...(await response.json()), source: 'precalibrated' });
      })
    );
  }
  try {
    return await cache.get(key);
  } catch (error) {
    cache.delete(key); // une panne réseau ne doit pas être mise en cache
    throw error;
  }
});

/* ------------------------------------------------------------------ */
/* Photo importée : sélection manuelle                                 */
/* ------------------------------------------------------------------ */

/**
 * Aucune analyse : on renvoie un plan de départ plausible pour un intérieur
 * photographié debout, que l'utilisateur déplace ensuite. Le seul indice
 * exploité est le format de l'image, qui décale un peu la ligne d'horizon.
 */
registerAnalyzer('manual', ({ width = 0, height = 0, label, quad, meters } = {}) => {
  const ratio = width && height ? width / height : 1.5;
  const horizon = ratio > 1.6 ? 0.6 : 0.64;
  return createBlankScene({
    width,
    height,
    label,
    meters,
    quad:
      quad ||
      [
        { x: 0.18, y: horizon },
        { x: 0.82, y: horizon },
        { x: 1.03, y: 1.0 },
        { x: -0.03, y: 1.0 },
      ],
  });
});
