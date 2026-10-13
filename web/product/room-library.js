/**
 * Bibliothèque des pièces de démonstration — `web/data/rooms.json`.
 *
 * Une catégorie est une COLLECTION de scènes, pas une image. Tout ce que la
 * galerie affiche se calcule ici depuis le manifeste : la liste des
 * catégories, le nombre entre parenthèses, la vignette de couverture, les
 * scènes d'une catégorie. Ajouter une pièce, c'est ajouter une entrée au
 * manifeste ; aucune fonction de la page n'a à changer.
 *
 * Deux portes, et elles ne se confondent pas :
 *
 *   availableForGallery  la photo a le droit d'être montrée ;
 *   renderReady          sa géométrie a été relue, un parquet peut s'y poser.
 *
 * Seules les scènes qui ont les deux sont proposées. Une scène dont la
 * calibration n'est pas validée ne peut pas être `renderReady` : la règle est
 * vérifiée ici (`problemesBibliotheque`) et non laissée à la discipline de qui
 * édite le JSON.
 *
 * Fonctions pures, sans DOM : la batterie Node les exécute telles quelles.
 */

export const ROOMS_SCHEMA = 'pose-parquet/rooms@1';

/** Une scène est proposée aux visiteurs si et seulement si ceci est vrai. */
export const proposable = (s) => Boolean(s && s.availableForGallery && s.renderReady
  && s.calibration && s.calibration.status === 'validated' && s.sceneData);

/** Toutes les catégories d'une scène : la principale, puis les secondaires. */
export const categoriesDe = (s) => [s.category, ...(Array.isArray(s.alsoIn) ? s.alsoIn : [])]
  .filter((c, i, a) => c && a.indexOf(c) === i);

/** Les incohérences d'un manifeste. Vide = utilisable. */
export function problemesBibliotheque(m) {
  const p = [];
  if (!m || m.schema !== ROOMS_SCHEMA) return ['schema'];
  const cats = new Set((m.categories || []).map((c) => c.id));
  const ids = new Set();
  for (const s of m.scenes || []) {
    if (!s.id) { p.push('scene_sans_id'); continue; }
    if (ids.has(s.id)) p.push(`${s.id}:doublon`);
    ids.add(s.id);
    if (!s.name) p.push(`${s.id}:nom`);
    if (!s.image) p.push(`${s.id}:image`);
    if (!s.thumbnail) p.push(`${s.id}:vignette`);
    categoriesDe(s).forEach((c) => { if (!cats.has(c)) p.push(`${s.id}:categorie_inconnue:${c}`); });
    if (s.renderReady && !(s.calibration && s.calibration.status === 'validated')) {
      p.push(`${s.id}:renderReady_sans_calibration_validee`);
    }
    if (s.renderReady && !s.sceneData) p.push(`${s.id}:renderReady_sans_sceneData`);
  }
  return p;
}

/** Les scènes proposées d'une catégorie, dans l'ordre du manifeste. */
export const scenesDe = (m, categorie) => (m && m.scenes ? m.scenes : [])
  .filter((s) => proposable(s) && categoriesDe(s).includes(categorie));

/**
 * Les catégories à montrer, avec leur compte RÉEL et une couverture.
 * Une catégorie sans scène proposée n'apparaît pas : pas de fausse catégorie.
 */
export function categoriesGalerie(m) {
  /* Une couverture par catégorie, et autant que possible une DIFFÉRENTE
     pour chacune : deux catégories illustrées par la même photo se
     ressemblent au point qu'on les croirait dupliquées. Les catégories les
     plus petites choisissent d'abord — elles ont le moins de choix ;
     l'affichage, lui, garde l'ordre du manifeste. */
  const liste = (m && m.categories ? m.categories : [])
    .map((c) => ({ id: c.id, label: c.label, scenes: scenesDe(m, c.id) }))
    .filter((c) => c.scenes.length > 0);
  const prises = new Set();
  const couverture = new Map();
  [...liste].sort((a, b) => a.scenes.length - b.scenes.length).forEach((c) => {
    const cover = c.scenes.find((s) => !prises.has(s.id)) || c.scenes[0];
    prises.add(cover.id);
    couverture.set(c.id, cover);
  });
  return liste.map((c) => ({ id: c.id, label: c.label, count: c.scenes.length, cover: couverture.get(c.id) }));
}

/** Toutes les scènes proposées, sans doublon. */
export const scenesProposees = (m) => (m && m.scenes ? m.scenes : []).filter(proposable);

/** Une scène par identifiant (proposée ou non : le moteur la cherche aussi). */
export const sceneParId = (m, id) => (m && m.scenes ? m.scenes : []).find((s) => s.id === id) || null;

/** Charge le manifeste. Lève si le fichier manque ou se contredit. */
export async function chargerBibliotheque(base = '') {
  const r = await fetch(`${base}data/rooms.json`, { cache: 'no-cache' });
  if (!r.ok) throw new Error('Bibliothèque de pièces indisponible');
  const m = await r.json();
  const p = problemesBibliotheque(m);
  if (p.length) throw new Error(`Bibliothèque de pièces incohérente : ${p.join(', ')}`);
  return m;
}
