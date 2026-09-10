/**
 * Mesures de performance du Visualiseur — éteintes par défaut.
 *
 * Le lag a été signalé en ces termes : « le Visualiseur lag ». Un ressenti ne
 * dit pas où, et deviner coûte plus cher que mesurer : on a déjà optimisé un
 * chemin de rendu qui n'était pas le goulot. Ce module pose donc des repères
 * nommés autour des étapes réelles — génération de texture, mips, peinture,
 * changement de produit — et n'existe qu'à la demande.
 *
 * `?perf=1` dans l'URL, ou `window.__perf = true` avant le démarrage, active
 * les mesures. Sinon `mark()` et `mesure()` sont deux fonctions vides : pas de
 * `performance.mark`, pas de tableau qui grossit, pas de branche dans le
 * chemin chaud au-delà d'un test booléen.
 *
 * Les mesures s'appuient sur l'API Performance du navigateur plutôt que sur un
 * chronomètre maison : elles apparaissent dans l'onglet Performance des
 * devtools au même endroit que les tâches longues, ce qui permet de relire une
 * trace sans rejouer la session.
 */

const actif = (() => {
  if (typeof window === 'undefined') return false;
  if (window.__perf === true) return true;
  try {
    return new URLSearchParams(window.location.search).get('perf') === '1';
  } catch {
    return false;
  }
})();

const releves = [];
/** Tâches longues du fil principal : c'est ce qui se ressent comme un blocage. */
const taches = [];

if (actif && typeof PerformanceObserver === 'function') {
  try {
    new PerformanceObserver((list) => {
      list.getEntries().forEach((e) => taches.push({ debut: Math.round(e.startTime), duree: Math.round(e.duration) }));
    }).observe({ entryTypes: ['longtask'] });
  } catch {
    /* longtask non pris en charge : les mesures nommées suffisent. */
  }
}

export const perfActif = actif;

export const mark = actif
  ? (nom) => { try { performance.mark(nom); } catch { /* budget de repères plein */ } }
  : () => {};

/**
 * Referme un intervalle et le retient.
 * @returns {number|null} durée en ms, ou null si le repère de départ manque.
 */
export const mesure = actif
  ? (nom, debut, fin) => {
    try {
      const e = performance.measure(nom, debut, fin);
      const duree = Math.round(e.duration * 100) / 100;
      releves.push({ nom, duree });
      // On vide derrière soi.
      //
      // Le tampon d'entrées de performance du navigateur est borné : au bout
      // de quelques milliers de repères il cesse silencieusement d'en
      // enregistrer, et `measure()` ne trouve plus son repère de départ. Une
      // session de mesure un peu longue rendait donc un rapport VIDE, ce qui
      // se lit comme « rien ne s'est passé » alors que tout s'était passé.
      performance.clearMeasures(nom);
      performance.clearMarks(fin);
      return duree;
    } catch {
      return null;
    }
  }
  : () => null;

/** Chronomètre direct, pour ce qui n'a pas besoin de deux repères. */
export const chrono = actif
  ? (nom, fn) => {
    const t0 = performance.now();
    const r = fn();
    releves.push({ nom, duree: Math.round((performance.now() - t0) * 100) / 100 });
    return r;
  }
  : (nom, fn) => fn();

/**
 * Résumé par nom : nombre d'appels, médiane, maximum, total.
 *
 * La médiane plutôt que la moyenne : le premier rendu d'un matériau coûte dix
 * fois le suivant, et une moyenne mélangerait les deux régimes en un chiffre
 * qui ne décrit ni l'un ni l'autre.
 */
export function rapport() {
  const parNom = new Map();
  releves.forEach(({ nom, duree }) => {
    if (!parNom.has(nom)) parNom.set(nom, []);
    parNom.get(nom).push(duree);
  });
  const lignes = [...parNom.entries()].map(([nom, v]) => {
    const tri = [...v].sort((a, b) => a - b);
    return {
      nom,
      n: v.length,
      mediane: tri[tri.length >> 1],
      min: tri[0],
      max: tri[tri.length - 1],
      total: Math.round(v.reduce((s, x) => s + x, 0) * 10) / 10,
    };
  });
  return {
    lignes: lignes.sort((a, b) => b.total - a.total),
    tachesLongues: { n: taches.length, max: taches.length ? Math.max(...taches.map((t) => t.duree)) : 0, liste: taches.slice(-12) },
  };
}

/** Vide les relevés : sert à isoler une interaction précise. */
export function raz() {
  releves.length = 0;
  taches.length = 0;
  try {
    performance.clearMarks();
    performance.clearMeasures();
  } catch {
    /* rien à vider */
  }
}

if (actif && typeof window !== 'undefined') {
  window.__perfRapport = rapport;
  window.__perfRaz = raz;
}
