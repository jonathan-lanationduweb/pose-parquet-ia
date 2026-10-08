/**
 * Client de l'analyse de pièce — le seul endroit qui parle à Python.
 *
 * Le visualiseur ne fait aucun `fetch` lui-même : il appelle `analyzeRoom` et
 * reçoit soit un résultat, soit une raison. Une requête réseau dispersée dans
 * trois mille lignes d'interface est une requête qu'on ne retrouve plus le
 * jour où elle échoue.
 *
 * ## Ce que le backend sait faire aujourd'hui, et ce qu'il ne sait pas
 *
 * `POST /v1/analyze-room` rend un `pose-parquet/analysis@2` :
 * dimensions après redressement EXIF, netteté, exposition, écrêtage,
 * courbure des arêtes, avertissements, et un `sceneData` qui vaut **`null`**.
 *
 * Il n'y a donc **aucune segmentation du sol**, et ce client ne fabrique rien
 * pour compenser. Il transporte ce que Python dit, y compris quand Python dit
 * « je n'ai pas de scène ». Traduire `quality` en `sceneData` serait inventer
 * une détection — exactement ce que le protocole d'annotation refuse.
 *
 * ## La dernière photo gagne
 *
 * Deux imports rapprochés lancent deux analyses. Celle d'avant est **annulée**
 * (`AbortController`) et, si sa réponse arrive quand même, elle est jetée : le
 * jeton de génération ne correspond plus. Sans cela, une photo A analysée
 * lentement viendrait écraser l'état de la photo B, et l'interface décrirait
 * une image que personne ne regarde.
 *
 * ## Vie privée
 *
 * La photo part en `multipart/form-data`, telle quelle, une fois. Aucune
 * copie, aucune base64, aucun enregistrement, aucun journal du contenu. C'est
 * une photo de domicile : elle traverse, elle ne séjourne pas.
 */

/** Contrat de réponse que ce client sait lire. */
export const ANALYSIS_SCHEMA_FAMILY = 'pose-parquet/analysis';

/**
 * Origine de l'API.
 *
 * Trois cas, dans cet ordre : `?api=` en développement, la même origine que
 * la page (cas du serveur unique, voir `PPAI_DEV_SERVE_STATIC`), puis le
 * défaut local. Une seule fonction décide, et personne d'autre.
 */
export function apiBase({ search = '', origin = '', dev = false } = {}) {
  if (dev) {
    try {
      const demande = new URLSearchParams(search).get('api');
      /* Uniquement une origine http(s) explicite : un chemin relatif ou un
         `javascript:` n'ont rien à faire ici. */
      if (demande && /^https?:\/\/[^/]+$/.test(demande)) return demande.replace(/\/$/, '');
    } catch { /* pas de recherche exploitable : on continue */ }
  }
  /* La page est servie par FastAPI lui-même : même origine, pas de CORS. */
  if (/^https?:/.test(origin)) return origin.replace(/\/$/, '');
  return 'http://127.0.0.1:8000';
}

/** Raisons d'échec, distinctes parce qu'elles ne se corrigent pas pareil. */
export const RAISONS = {
  RESEAU: 'network',
  ANNULEE: 'aborted',
  /* Le delai de garde a expire. Distinct de `aborted` : une annulation vient
     d'un geste de l'utilisateur (nouvelle photo) et ne doit rien afficher ;
     un delai depasse est un echec qu'il faut DIRE. Les confondre laissait la
     capsule sur « Analyse de la piece… » pour toujours — vu en situation,
     avec un modele qui mettait quatre-vingt-dix secondes a se charger. */
  DELAI: 'timeout',
  REFUSEE: 'rejected',
  SERVEUR: 'server',
  CONTRAT: 'contract',
};

const MESSAGES = {
  400: 'Cette photo n’a pas pu être lue.',
  413: 'Cette photo est trop lourde.',
  415: 'Format non pris en charge : utilisez un JPEG, un PNG ou un WebP.',
  422: 'Cette photo n’a pas pu être décodée.',
  500: 'L’analyse a échoué.',
};

/**
 * Crée le client.
 * @param {object} options
 * @param {string} options.base   origine de l'API, de `apiBase()`
 * @param {number} [options.timeoutMs]
 */
/*
 * 120 s de garde, et non 30. L'analyse de qualite seule tient en une
 * seconde ; la segmentation experimentale, quand le service la porte, charge
 * un modele a la premiere requete (mesure : 20 a 95 s) puis infere en 8 a
 * 12 s. Un delai de 30 s coupait systematiquement la premiere analyse d'un
 * service frais, et l'interface ne le disait pas.
 */
export function createRoomAnalysisClient({ base, timeoutMs = 120000 } = {}) {
  let generation = 0;
  let enCours = null;

  /** Annule l'analyse en cours, s'il y en a une. */
  function cancel() {
    if (enCours) {
      enCours.abort();
      enCours = null;
    }
  }

  /**
   * Analyse une photo.
   *
   * @param {File} file
   * @returns {Promise<{ok: boolean, generation: number, perime: boolean,
   *   analysis?: object, raison?: string, status?: number, message?: string,
   *   networkMs?: number}>}
   *
   * Ne jette jamais : un appelant qui doit envelopper chaque appel dans un
   * `try` finit par en oublier un, et l'interface meurt avec le backend.
   */
  async function analyzeRoom(file) {
    cancel();
    generation += 1;
    const mien = generation;
    const controleur = new AbortController();
    enCours = controleur;
    let delaiDepasse = false;
    const minuteur = setTimeout(() => { delaiDepasse = true; controleur.abort(); }, timeoutMs);
    const t0 = performance.now();

    const corps = new FormData();
    /* Le nom du champ est celui de la signature FastAPI : `image`. */
    corps.append('image', file, file.name || 'photo.jpg');

    try {
      const reponse = await fetch(`${base}/v1/analyze-room`, {
        method: 'POST',
        body: corps,
        signal: controleur.signal,
      });
      const networkMs = Math.round(performance.now() - t0);
      /* Périmée : une autre photo est passée entre-temps. On le dit, et
         l'appelant n'applique rien. */
      const perime = mien !== generation;

      if (!reponse.ok) {
        let detail = null;
        try { detail = await reponse.json(); } catch { /* corps non JSON */ }
        return {
          ok: false, generation: mien, perime, networkMs,
          raison: reponse.status >= 500 ? RAISONS.SERVEUR : RAISONS.REFUSEE,
          status: reponse.status,
          message: MESSAGES[reponse.status] || 'L’analyse a échoué.',
          detail: detail && detail.detail ? detail.detail : null,
        };
      }

      const analysis = await reponse.json();
      if (typeof analysis !== 'object' || !analysis || typeof analysis.schema !== 'string'
          || !analysis.schema.startsWith(ANALYSIS_SCHEMA_FAMILY)) {
        return {
          ok: false, generation: mien, perime, networkMs,
          raison: RAISONS.CONTRAT, status: reponse.status,
          message: 'Réponse d’analyse inattendue.',
        };
      }
      return { ok: true, generation: mien, perime, networkMs, analysis };
    } catch (e) {
      const networkMs = Math.round(performance.now() - t0);
      const abandon = e && (e.name === 'AbortError');
      const raison = abandon ? (delaiDepasse ? RAISONS.DELAI : RAISONS.ANNULEE) : RAISONS.RESEAU;
      return {
        ok: false, generation: mien, perime: mien !== generation, networkMs,
        raison,
        message: raison === RAISONS.ANNULEE ? null
          : raison === RAISONS.DELAI ? 'L’analyse a pris trop de temps.'
            : 'Analyse indisponible pour le moment.',
      };
    } finally {
      clearTimeout(minuteur);
      if (enCours === controleur) enCours = null;
    }
  }

  /**
   * État du service. Appelé **à la demande**, jamais en boucle : un service
   * qu'on interroge chaque seconde coûte plus que ce qu'il apprend.
   */
  async function health() {
    try {
      const r = await fetch(`${base}/health`, { method: 'GET' });
      if (!r.ok) return { ok: false, status: r.status };
      const corps = await r.json();
      return {
        ok: corps && corps.status === 'ok', status: r.status, service: corps && corps.service,
        /* `loading` | `ready` | `error` | `idle`, ou absent quand le service
           tourne sans le mode expérimental. */
        experimentalFloor: corps && corps.experimentalFloor ? corps.experimentalFloor : null,
      };
    } catch {
      return { ok: false, status: 0 };
    }
  }

  return {
    get base() { return base; },
    get generation() { return generation; },
    analyzeRoom,
    health,
    cancel,
  };
}

/**
 * Ce que l'interface doit dire d'un résultat réel.
 *
 * La règle tient en une phrase : **ne jamais annoncer une brique qui
 * n'existe pas.** Tant que `sceneData` est nul, il n'y a ni sol détecté, ni
 * perspective, ni objets — et l'écrire serait laisser croire que notre
 * détection fonctionne mal alors qu'elle n'existe pas encore.
 *
 * Le jour où `analysis@3` apportera une scène, ce sont ces deux lignes qui
 * changeront, et rien d'autre.
 */
/**
 * La scène EXPÉRIMENTALE, si Python en a produit une.
 *
 * Elle vit dans `experimental.floor.sceneData`, jamais dans `sceneData` : ce
 * client ne confond pas les deux, et rend un objet qui dit son statut. Le
 * front décide ensuite — poser, proposer d'ajuster, ou ne rien faire — et il
 * le décide sur `status` et `confidence`, pas sur la seule présence d'une
 * scène.
 *
 * @returns {{scene:object|null, status:string, confidence:number|null,
 *            perspective:object, rug:object, provenance:object}|null}
 */
export function sceneExperimentale(analysis) {
  const sol = analysis && analysis.experimental && analysis.experimental.floor;
  if (!sol) return null;
  return {
    scene: sol.sceneData || null,
    status: sol.sceneStatus || 'no_floor',
    confidence: Number.isFinite(sol.sceneConfidence) ? sol.sceneConfidence : null,
    perspective: sol.perspective || {},
    rug: sol.rug || {},
    provenance: sol.sceneProvenance || {},
  };
}

export function resumerAnalyse(analysis) {
  if (!analysis) return { etat: 'unavailable', texte: 'Analyse indisponible pour le moment' };
  if (analysis.status === 'rejected') {
    return { etat: 'rejected', texte: 'Cette photo n’est pas exploitable' };
  }
  /* La scène expérimentale a ses propres mots, et ils disent « expérimental ».
     « Sol détecté » tout court laisserait croire à une brique validée. */
  const xp = sceneExperimentale(analysis);
  if (xp && xp.scene && xp.status === 'auto_render') {
    return { etat: 'experimental_scene', texte: 'Sol détecté (expérimental)' };
  }
  if (xp && xp.scene && xp.status === 'needs_manual_adjustment') {
    return { etat: 'experimental_adjust', texte: 'Sol détecté approximativement' };
  }
  if (analysis.sceneData) {
    /* Chemin encore jamais emprunte : aucun backend ne renvoie de scene
       aujourd'hui. Il est ecrit pour que le jour ou cela arrive, le client
       n'ait pas a etre reecrit — pas pour faire croire que cela arrive. */
    return { etat: 'complete', texte: 'Pièce analysée' };
  }
  return { etat: 'partial', texte: 'Analyse initiale terminée' };
}
