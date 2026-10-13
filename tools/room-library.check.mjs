/*
  Batterie de la bibliothèque de pièces — `web/product/room-library.js`.

      node tools/room-library.check.mjs

  Fonctions pures, exécutées telles quelles : rien n'est réimplémenté ici.
*/
import fs from 'node:fs';
import {
  problemesBibliotheque, categoriesGalerie, scenesDe, scenesProposees, proposable,
} from '../web/product/room-library.js';

let bad = 0;
const ok = (n, c, d) => { if (!c) bad += 1; console.log(`${c ? 'OK  ' : 'ECHEC'} ${n}${d !== undefined ? '  -> ' + d : ''}`); };

const m = JSON.parse(fs.readFileSync('web/data/rooms.json', 'utf8'));
ok('le manifeste est cohérent', problemesBibliotheque(m).length === 0, problemesBibliotheque(m).join(', '));

/* Chaque fichier déclaré existe. */
for (const s of m.scenes) {
  ok(`${s.id} : photo présente`, fs.existsSync(`web/assets/images/${s.image}`));
  ok(`${s.id} : vignette présente`, fs.existsSync(`web/assets/images/${s.thumbnail}`));
  if (s.sceneData) ok(`${s.id} : SceneData présente`, fs.existsSync(`web/data/${s.sceneData}`));
}

/* Une catégorie est une collection : plusieurs scènes, comptées. */
const cats = categoriesGalerie(m);
ok('au moins six catégories montrées', cats.length >= 6, cats.map((c) => `${c.label} (${c.count})`).join(' · '));
ok('au moins une catégorie contient plusieurs scènes', cats.some((c) => c.count > 1));
ok('le compte est le nombre de scènes proposées', cats.every((c) => c.count === scenesDe(m, c.id).length));
ok('aucune catégorie vide', cats.every((c) => c.count > 0));
ok('les couvertures diffèrent', new Set(cats.map((c) => c.cover.id)).size === cats.length);
ok('chaque scène proposée a une calibration validée',
  scenesProposees(m).every((s) => s.calibration.status === 'validated' && s.renderReady));
ok('une scène refusée n’est pas proposée',
  m.scenes.filter((s) => s.calibration.status !== 'validated').every((s) => !proposable(s)));

/* Le compte suit le manifeste : ajouter une scène suffit. */
const plus = structuredClone(m);
const base = scenesDe(plus, 'chambre').length;
plus.scenes.push({ ...structuredClone(plus.scenes.find((s) => s.id === 'chambre')), id: 'chambre-test' });
ok('ajouter une scène au manifeste augmente le compte', scenesDe(plus, 'chambre').length === base + 1,
  `${base} -> ${scenesDe(plus, 'chambre').length}`);

/* La porte renderReady ne s'ouvre pas sans calibration validée. */
const faux = structuredClone(m);
const s0 = faux.scenes.find((s) => s.calibration.status !== 'validated');
if (s0) {
  s0.renderReady = true;
  ok('renderReady sans calibration validée est refusé',
    problemesBibliotheque(faux).some((p) => p.includes('renderReady_sans_calibration_validee')));
  ok('et la scène reste non proposée', !proposable(s0));
}
const inconnue = structuredClone(m);
inconnue.scenes[0].alsoIn = ['grenier'];
ok('une catégorie inconnue est signalée', problemesBibliotheque(inconnue).some((p) => p.includes('categorie_inconnue')));

console.log(`\n${bad ? `${bad} ECHEC(S)` : 'AUCUN ECHEC'}`);
process.exit(bad ? 1 : 0);
