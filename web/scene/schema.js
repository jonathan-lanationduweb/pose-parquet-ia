/**
 * Schéma d'une scène.
 *
 * Une scène, c'est tout ce qu'il faut savoir d'une photographie pour y poser
 * un parquet : où est le sol, comment il fuit vers l'horizon, ce qui doit
 * rester devant, comment la pièce est éclairée.
 *
 * Ces données arrivent aujourd'hui de deux endroits :
 *   - data/scenes/*.json  : pièces d'exemple, calibrées à la main ;
 *   - la sélection de l'utilisateur sur sa propre photo.
 *
 * Elles arriveront un jour d'un service d'analyse (voir
 * docs/future-ai-api-contract.md). Le moteur de rendu ne saura toujours pas
 * d'où elles viennent : c'est tout l'intérêt de normaliser ici, une fois.
 *
 * Toutes les coordonnées sont normalisées (0 → 1 sur l'image), jamais en
 * pixels. Les valeurs légèrement hors bornes sont volontaires : un plan de
 * sol se prolonge très souvent au-delà du cadre.
 */

export const SCHEMA = 'pose-parquet/scene@1';

const clone = (points) => points.map((p) => ({ x: p.x, y: p.y }));
const num = (value, fallback) => (Number.isFinite(value) ? value : fallback);

/**
 * Une zone de sol : un plan de perspective et un contour.
 *
 * Le plan et le contour sont deux choses différentes, et c'est ce qui permet
 * de traiter proprement une pièce vue à travers une ouverture :
 *   - `plane.quad` est un repère. Il donne la fuite et l'échelle, et peut
 *     déborder très largement de ce qui est visible ;
 *   - `mask` est la surface réellement peinte, aussi découpée qu'il faut.
 *
 * `surfaceId` est la clé de la continuité : deux zones qui la partagent sont
 * le même sol, donc le même matériau. `plane.origin`, en mètres dans le repère
 * du sol, décale la trame — c'est ce qui aligne les lames de part et d'autre
 * d'une porte.
 */
function normalizeZone(raw, index, planes) {
  // Un plan peut être partagé : deux pièces en enfilade sur la même dalle
  // sont un seul plan de sol vu à travers une ouverture. Le déclarer une fois
  // et le référencer garantit une continuité exacte, là où deux plans
  // calibrés séparément laisseraient un décalage au raccord.
  const plane = (raw.planeRef && planes[raw.planeRef]) || raw.plane || {};
  if (raw.planeRef && !planes[raw.planeRef]) {
    throw new Error(`Zone « ${raw.id || index} » : plan « ${raw.planeRef} » introuvable`);
  }
  const mask = raw.mask || {};
  const quad = Array.isArray(plane.quad) ? plane.quad : raw.quad;
  if (!Array.isArray(quad) || quad.length !== 4) {
    throw new Error(`Zone « ${raw.id || index} » : plane.quad doit compter 4 points`);
  }
  const polygon = Array.isArray(mask.polygon) ? mask.polygon : raw.mask;

  return {
    id: raw.id || `zone-${index + 1}`,
    label: raw.label || `Zone ${index + 1}`,
    surfaceId: raw.surfaceId || 'sol',
    planeRef: raw.planeRef || null,
    order: num(raw.order, index),
    confidence: Number.isFinite(raw.confidence) ? raw.confidence : null,
    plane: {
      quad: clone(quad),
      meters: {
        width: num(plane.meters && plane.meters.width, 4.2),
        depth: num(plane.meters && plane.meters.depth, 4),
      },
      // Décalage de la trame, en mètres de sol. Sert à prolonger un parquet
      // d'une zone à l'autre sans que le raccord se voie.
      origin: {
        u: num(plane.origin && plane.origin.u, 0),
        v: num(plane.origin && plane.origin.v, 0),
      },
      rotationDeg: num(plane.rotationDeg, 0),
    },
    mask: {
      polygon: Array.isArray(polygon) && polygon.length >= 3 ? clone(polygon) : clone(quad),
      holes: Array.isArray(mask.holes) ? mask.holes.filter((h) => Array.isArray(h) && h.length >= 3).map(clone) : [],
    },
    // Le contour édité par l'utilisateur, quand il en a tracé un : il prend le
    // pas sur `mask.polygon` sans l'écraser, donc « revenir au contour
    // d'origine » reste possible.
    runtimeMask: null,
  };
}

/**
 * Un objet qui doit rester devant le parquet.
 *
 * Ce n'est volontairement pas un trou de masque : un occulteur vaut pour
 * toutes les zones et survit à une correction du contour. Le rendu y restaure
 * les pixels de la photo — un canapé n'est donc jamais repeint, quelle que
 * soit la zone sur laquelle il se trouve.
 */
function normalizeOccluder(raw, index) {
  if (!Array.isArray(raw.polygon) || raw.polygon.length < 3) return null;
  return {
    id: raw.id || `occ-${index + 1}`,
    label: raw.label || 'Objet',
    kind: raw.kind || 'furniture',
    polygon: clone(raw.polygon),
    contact: Array.isArray(raw.contact) ? clone(raw.contact) : null,
    depth: num(raw.depth, 0.5),
    castsShadow: raw.castsShadow !== false,
    feather: num(raw.feather, 0.0015),
  };
}

/**
 * Normalise une scène, d'où qu'elle vienne.
 * Lève si la scène est inutilisable : mieux vaut un message qu'un rendu faux.
 * @returns {object} SceneData
 */
export function normalizeScene(raw) {
  if (!raw || typeof raw !== 'object') throw new Error('Scène vide');
  if (raw.schema && raw.schema.split('@')[0] !== SCHEMA.split('@')[0]) {
    throw new Error(`Schéma de scène inconnu : ${raw.schema}`);
  }

  const image = raw.image || {};
  const planes = raw.planes || {};
  const zones = (Array.isArray(raw.floorZones) ? raw.floorZones : [])
    .map((zone, index) => normalizeZone(zone, index, planes))
    .sort((a, b) => a.order - b.order);
  if (!zones.length) throw new Error('Une scène doit compter au moins une zone de sol');

  // Les surfaces sont déduites des zones si elles ne sont pas déclarées : une
  // scène minimale (photo importée) n'a pas à les écrire.
  const declared = new Map((raw.surfaces || []).map((s) => [s.id, s]));
  const surfaces = [...new Set(zones.map((z) => z.surfaceId))].map((id) => ({
    id,
    label: (declared.get(id) || {}).label || 'Sol',
    continuous: (declared.get(id) || {}).continuous !== false,
  }));

  const light = raw.light || {};

  return {
    schema: SCHEMA,
    id: raw.id || raw.sceneId || 'scene',
    label: raw.label || 'Ma pièce',
    source: raw.source || 'manual', // manual | precalibrated | ai
    confidence: Number.isFinite(raw.confidence) ? raw.confidence : null,

    image: {
      file: image.file || null,
      width: num(image.width, 0),
      height: num(image.height, 0),
      alt: image.alt || '',
      credit: image.credit || null,
    },

    camera: {
      horizon: num(raw.camera && raw.camera.horizon, null),
      vanishingPoints: Array.isArray(raw.camera && raw.camera.vanishingPoints)
        ? clone(raw.camera.vanishingPoints)
        : [],
      fovDeg: num(raw.camera && raw.camera.fovDeg, null),
      tiltDeg: num(raw.camera && raw.camera.tiltDeg, null),
      heightM: num(raw.camera && raw.camera.heightM, null),
    },

    surfaces,
    floorZones: zones,
    occluders: (Array.isArray(raw.occluders) ? raw.occluders : []).map(normalizeOccluder).filter(Boolean),

    /**
     * Profondeur. `plane` = calculée depuis le plan du sol, ce qui est exact
     * pour les pixels de sol et suffit à faire varier la netteté et l'échelle
     * avec l'éloignement. Une carte d'image (`kind: 'image'`) viendra plus
     * tard décrire aussi ce qui n'est pas le sol, pour trier les occlusions.
     */
    depth: {
      kind: (raw.depth && raw.depth.kind) || (raw.depthMap ? 'image' : 'plane'),
      file: (raw.depth && raw.depth.file) || (raw.depthMap && raw.depthMap.file) || null,
      near: num(raw.depth && raw.depth.near, null),
      far: num(raw.depth && raw.depth.far, null),
    },

    /**
     * Éclairement. `photo-luma` : on relit la lumière dans la photo elle-même.
     * `blurRadius`, en fraction de la largeur d'image, sépare l'éclairement du
     * détail — c'est ce qui empêche les lames de l'ancien sol de réapparaître
     * en fantôme sous le nouveau parquet.
     */
    light: {
      kind: light.kind || 'photo-luma',
      strength: num(light.strength, 1),
      blurRadius: num(light.blurRadius, 0.035),
      // Lumière d'ambiance : la part de l'éclairement qui ne vient pas
      // directement de la fenêtre mais du rebond sur les murs et le plafond.
      //
      // Sans elle, le gain appliqué au bois descend aussi bas que la photo,
      // et un parquet foncé dans une zone peu éclairée s'effondre vers le
      // noir : on ne lit plus un sol sombre, on lit un trou. Aucune pièce
      // réelle ne se comporte comme ça — un sol foncé reçoit toujours de la
      // lumière indirecte, et c'est elle qui le rattache à la pièce.
      //
      // Le gain devient `ambient + (1 - ambient) · gain` : les ombres se
      // relèvent, les tons moyens et les hautes lumières ne bougent pas.
      ambient: num(light.ambient, 0.22),
      // Part de la **couleur** de la lumière reportée sur le parquet, en plus
      // de son intensité. 0 : éclairement en niveaux de gris, le bois garde
      // une teinte neutre au milieu d'une pièce dorée — et ça se voit.
      // 1 : le bois prend toute la dominante de la photo, y compris ses
      // défauts de balance des blancs. La moitié tient le juste milieu.
      tint: num(light.tint, 0.5),
      // Assombrissement au pied des murs et des meubles.
      contact: num(light.contact, 0.35),
    },

    warnings: Array.isArray(raw.warnings) ? raw.warnings.slice() : [],
  };
}

/** Quadrilatère de départ pour une photo dont on ne sait rien. */
export const DEFAULT_QUAD = [
  { x: 0.18, y: 0.62 },
  { x: 0.82, y: 0.62 },
  { x: 1.02, y: 1.0 },
  { x: -0.02, y: 1.0 },
];

/**
 * Scène minimale : une photo, une zone, un plan approximatif.
 * C'est le point de départ de la correction manuelle — et exactement ce qu'un
 * service d'analyse renverra en mieux.
 */
export function createBlankScene({ width, height, quad = DEFAULT_QUAD, meters, label = 'Ma pièce' } = {}) {
  return normalizeScene({
    id: `upload-${Date.now().toString(36)}`,
    label,
    source: 'manual',
    image: { width, height, alt: 'Votre pièce' },
    floorZones: [
      {
        id: 'zone-1',
        label: 'Sol',
        surfaceId: 'sol',
        plane: { quad, meters: meters || { width: 4.2, depth: 4 } },
        mask: { polygon: quad },
      },
    ],
  });
}

/**
 * Ajoute une zone de sol à une scène existante.
 *
 * Sert quand l'utilisateur déclare un second sol sur sa photo — une pièce
 * aperçue derrière une porte, un couloir. Par défaut la nouvelle zone rejoint
 * la **même surface** que la première : c'est le cas courant, un seul parquet
 * pour tout l'étage, et cela évite de demander à l'utilisateur de comprendre la
 * notion de surface pour obtenir le résultat attendu.
 *
 * @returns {object} la zone créée, déjà présente dans scene.floorZones
 */
export function addZone(scene, { label, quad, surfaceId, meters } = {}) {
  const index = scene.floorZones.length;
  const zone = normalizeZone(
    {
      id: `zone-${index + 1}-${Date.now().toString(36)}`,
      label: label || `Sol ${index + 1}`,
      surfaceId: surfaceId || scene.surfaces[0].id,
      order: index,
      plane: {
        quad: quad || DEFAULT_QUAD,
        meters: meters || scene.floorZones[0].plane.meters,
      },
      mask: { polygon: quad || DEFAULT_QUAD },
    },
    index,
    {}
  );
  scene.floorZones.push(zone);
  return zone;
}

/** Retire une zone. La scène doit toujours en garder au moins une. */
export function removeZone(scene, zoneId) {
  if (scene.floorZones.length <= 1) return false;
  const index = scene.floorZones.findIndex((zone) => zone.id === zoneId);
  if (index < 0) return false;
  scene.floorZones.splice(index, 1);
  scene.floorZones.forEach((zone, i) => {
    zone.order = i;
  });
  return true;
}

/** Zones d'une même surface, de la plus lointaine à la plus proche. */
export const zonesOfSurface = (scene, surfaceId) =>
  scene.floorZones.filter((zone) => zone.surfaceId === surfaceId);

/** Contour effectivement peint pour une zone (édition de l'utilisateur incluse). */
export const zonePolygon = (zone) => zone.runtimeMask || zone.mask.polygon;
