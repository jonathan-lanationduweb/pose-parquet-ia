/**
 * Le tiroir du visualiseur — UN composant, quatre modes.
 *
 * Avant cette passe il y avait trois panneaux fixes, chacun avec son voile,
 * sa classe `hidden` et sa ligne dans `closeAll()`. Trois fois le même
 * comportement écrit trois fois : trois occasions d'oublier l'échappement,
 * trois façons de ne pas rendre le focus, et sur téléphone trois calques qui
 * ne savaient pas qu'ils se recouvraient.
 *
 * Ici il y a un seul conteneur, un seul voile, et un mode :
 *
 *     rooms       changer de pièce, ou importer une photo
 *     catalog     choisir un parquet
 *     customize   motif, largeur, teinte, sens de pose, cadran libre
 *     favorites   le catalogue, filtré sur les favoris
 *
 * `favorites` n'a délibérément pas de panneau à lui : c'est le catalogue avec
 * une vue différente. Lui donner son propre panneau aurait fait un quatrième
 * endroit où afficher une carte produit, et une quatrième mise en page à
 * corriger le jour où la carte change.
 *
 * ## Ce que ce module ne fait pas
 *
 * Il ne peint rien. Les fonctions de peinture de la page (`paintRoomSheet`,
 * `paintCatalogue`, `paintCustom`) restent où elles sont et gardent leurs
 * éléments : le tiroir se contente de les héberger. C'est ce qui permet de
 * changer la présentation sans toucher au contenu — et donc de ne prendre le
 * risque que d'un côté à la fois.
 *
 * ## Script classique, pas module ES
 *
 * Le script de la page est exécuté tel quel sous Node par
 * `product-concept.check.js`, avec un DOM minimal. Un `import` y serait
 * inexécutable. Le tiroir s'expose donc sur `window`, et la batterie le charge
 * de la même façon que la page.
 */
(function (global) {
  'use strict';

  /** Éléments focalisables, pour le piège à focus. */
  const FOCUSABLE =
    'a[href],button:not([disabled]),input:not([disabled]),select,textarea,[tabindex]:not([tabindex="-1"])';

  /**
   * @param {object} options
   * @param {HTMLElement} options.root      où insérer le tiroir (le body)
   * @param {Record<string,HTMLElement>} options.panes  mode → panneau existant
   * @param {() => void} [options.onClose]  appelé après chaque fermeture
   */
  function createDrawer({ root, panes, onClose }) {
    const scrim = global.document.createElement('div');
    scrim.className = 'dw-scrim hidden';

    const shell = global.document.createElement('div');
    shell.className = 'dw hidden';
    shell.setAttribute('role', 'dialog');
    shell.setAttribute('aria-modal', 'true');

    /* La poignée n'est pas une décoration : sur un téléphone elle dit que le
       panneau est un tiroir et qu'il se ferme, avant qu'on ait lu le bouton. */
    const grip = global.document.createElement('div');
    grip.className = 'dw-grip';
    grip.setAttribute('aria-hidden', 'true');
    shell.appendChild(grip);

    /* Les panneaux existants deviennent les pages du tiroir. Ils gardent leur
       identifiant, leur contenu et leurs gestionnaires : rien de ce que la
       page sait faire d'eux ne change. */
    Object.values(panes).forEach((pane) => {
      if (!pane) return;
      pane.classList.add('dw-pane');
      shell.appendChild(pane);
    });

    root.appendChild(scrim);
    root.appendChild(shell);

    let mode = null;
    let rendu = null; // l'élément qui avait le focus avant l'ouverture

    function visible() {
      return !shell.classList.contains('hidden');
    }

    function close() {
      if (!visible()) return;
      shell.classList.add('hidden');
      scrim.classList.add('hidden');
      shell.removeAttribute('data-mode');
      Object.values(panes).forEach((p) => p && p.classList.add('hidden'));
      mode = null;
      /* Rendre le focus là où il était. Sans cela, fermer au clavier renvoie
         en haut du document et il faut retraverser la page pour revenir au
         bouton qu'on vient d'actionner. */
      if (rendu && typeof rendu.focus === 'function' && rendu.isConnected) rendu.focus();
      rendu = null;
      if (onClose) onClose();
    }

    /**
     * @param {'rooms'|'catalog'|'customize'|'favorites'} next
     */
    function open(next) {
      const pane = panes[next] || panes[next === 'favorites' ? 'catalog' : next];
      if (!pane) return;
      if (!visible()) rendu = global.document.activeElement;

      Object.values(panes).forEach((p) => p && p.classList.add('hidden'));
      pane.classList.remove('hidden');
      shell.dataset.mode = next;
      shell.classList.remove('hidden');
      scrim.classList.remove('hidden');
      mode = next;

      /* Le titre du panneau nomme le dialogue. Une étiquette générique
         (« Panneau ») ne dirait pas à un lecteur d'écran ce qui vient de
         s'ouvrir, et c'est la seule information qui compte à cet instant. */
      const titre = pane.querySelector('h2');
      if (titre) shell.setAttribute('aria-label', titre.textContent.trim());

      /* Un panneau rouvert doit repartir de son haut : un catalogue qui
         rouvre au milieu donne l'impression d'avoir sauté une partie. */
      const corps = pane.querySelector('.body, .dw-body');
      if (corps) corps.scrollTop = 0;

      const premier = pane.querySelector(FOCUSABLE);
      if (premier) premier.focus({ preventScroll: true });
    }

    scrim.addEventListener('click', close);

    /* Échappement et piège à focus, une fois pour les quatre modes. */
    global.document.addEventListener('keydown', (e) => {
      if (!visible()) return;
      if (e.key === 'Escape') {
        e.stopPropagation();
        close();
        return;
      }
      if (e.key !== 'Tab') return;
      const cibles = [...shell.querySelectorAll(FOCUSABLE)].filter(
        (n) => n.offsetParent !== null || n === global.document.activeElement
      );
      if (!cibles.length) return;
      const debut = cibles[0];
      const fin = cibles[cibles.length - 1];
      if (e.shiftKey && global.document.activeElement === debut) {
        e.preventDefault();
        fin.focus();
      } else if (!e.shiftKey && global.document.activeElement === fin) {
        e.preventDefault();
        debut.focus();
      }
    });

    return {
      open,
      close,
      get mode() { return mode; },
      get isOpen() { return visible(); },
      element: shell,
      scrim,
    };
  }

  global.PPDrawer = { createDrawer };
})(typeof window !== 'undefined' ? window : globalThis);
