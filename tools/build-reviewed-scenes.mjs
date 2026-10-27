/** Assemble existing diagnostic captures; never recapture or infer quality. */
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {visualQualityReport,qualityReportText} from '../web/product/visual-quality-report.js';
const rows=[
 ['cuisine-ilot','POINF36005','Cuisine et coin repas','Bande oubliée devant le four et au seuil arrière réduite. La bouche de ventilation et les seuils restent visibles.','Contours de l’îlot encore anguleux en gros plan.'],
 ['cuisine-blanche','POINF36005','Cuisine blanche','Ancien sol couvert sous la colonne et les meubles à droite.','Bords de plinthes encore perfectibles ; aucun changement de projection.'],
 ['terrasse-mer','VLAME16012','Terrasse','Libellé undefined remplacé par le motif du profil réellement rendu.','Pas de modification du masque de cette terrasse ; matière et répétition restent à évaluer.'],
 ['couloir-enfilade','BTRPF39009','Couloir bleu','Sol prolongé dans l’ouverture de droite et jusqu’à la plinthe gauche. Le montant vertical en bois est conservé.','Jonction oblique près du chambranle encore approximative.'],
 ['premibel-entree','BTRPF39009','Entrée Premibel','Fragments d’ancien parquet retirés sous le pot ; fine bande près de la plinthe couverte.','Franges du tapis et contact de la petite table encore irréguliers.'],
 ['salle-a-manger-meublee','BTRPF39009','Salle à manger','Grande zone de sol libérée entre les supports de chaise ; pieds conservés.','Quelques halos et fragments d’ancien sol restent le long des supports.'],
 ['bureau-meuble','BTRPF39009','Bureau','Sol ajouté sous la chaise ; bord inférieur du vrai tapis protégé.','Le tapis et les câbles sous le bureau appartiennent à la photo originale et restent visibles.'],
 ['premibel-chambre','BTRPF39009','Chambre Premibel','Limites derrière le lit corrigées sur la jonction réelle mur/fenêtre et près de la table de chevet.','Contacts du lit, du pouf et petits objets encore grossiers par endroits.']
];
const afterPrefix=process.argv[2]||'eight-after', beforePrefix=process.argv[3]||'eight-before';
const root=process.argv[4]||'review/eight-scene-review';fs.mkdirSync(root,{recursive:true});
const escape=s=>s.replaceAll('&','&amp;').replaceAll('<','&lt;');
let sections='';
for(const[id,product,title,change,remaining]of rows){
 const before=JSON.parse(fs.readFileSync(`review/defects/${beforePrefix}-${id}/metadata.json`));
 const after=JSON.parse(fs.readFileSync(`review/defects/${afterPrefix}-${id}/metadata.json`));
 const cameras=m=>[...new Set(m.cameras.map(({camera,floorPlane,viewProjection})=>JSON.stringify({camera,floorPlane,viewProjection})))].sort();
 assert.deepEqual(cameras(before),cameras(after),id+' changed metric geometry');
 assert.equal(after.renderBlocked,false,id+' blocked render');
 const c=(observation,status='PARTIAL')=>({status,severity:'MODERATE',observation});
 const report=visualQualityReport({sceneId:id,productId:product,viewport:{width:1440,height:900},criteria:{
  S1:c('Caméra, plan et matrices métriques strictement identiques avant/après. Calibration architecturale non recertifiée pendant cette correction.'),
  S2:c('Dimensions physiques produit inchangées ; aucune nouvelle mesure indépendante de la pièce.'),
  S3:c(change+' '+remaining),S4:c(change+' '+remaining),
  S5:c('Algorithme lumineux inchangé. Les masques corrigés modifient localement le support du calcul ; aucune certification photométrique.'),
  S6:c('Données fabricant et référence photographique de finition insuffisantes.','NOT_EVALUABLE'),
  S7:c('Textures et motifs conservés. Répétition encore perceptible ; cette correction porte sur les masques.'),
  S8:c(remaining)
 },priorityFailures:[remaining],debugMetadata:{geometryStatus:after.geometryStatus,renderBlocked:after.renderBlocked},humanReviewPending:true});
 fs.writeFileSync(`${root}/${id}.json`,JSON.stringify(report,null,2));fs.writeFileSync(`${root}/${id}.txt`,qualityReportText(report));
 sections+=`<section><h2>${title}</h2><p>${escape(change)}</p><p class="remaining">À améliorer : ${escape(remaining)}</p><div class="pair"><figure><figcaption>Avant</figcaption><img loading="lazy" src="../defects/${beforePrefix}-${id}/02-render.png"></figure><figure><figcaption>Après</figcaption><img loading="lazy" src="../defects/${afterPrefix}-${id}/02-render.png"></figure></div><details><summary>Photo originale et diagnostic neutre</summary><div class="pair"><img loading="lazy" src="../defects/${afterPrefix}-${id}/01-original.png"><img loading="lazy" src="../defects/${afterPrefix}-${id}/14-neutral.png"></div></details><a href="${id}.txt">Rapport S1–S8</a></section>`;
}
fs.writeFileSync(root+'/index.html',`<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Revue des huit photos</title><style>body{font:16px system-ui;background:#f5f3ed;color:#292820;max-width:1500px;margin:auto;padding:24px}section{background:white;padding:20px;border-radius:16px;margin:24px 0}.pair{display:grid;grid-template-columns:1fr 1fr;gap:16px}figure{margin:0;min-width:0}img{width:100%;height:auto;display:block}figcaption{padding:8px;font-weight:bold}.remaining{color:#75533a}a{display:inline-block;margin-top:14px}@media(max-width:650px){body{padding:10px}.pair{grid-template-columns:1fr}}</style><h1>Huit photos : corrections de masques</h1><p>Comparaison avec les mêmes produits, angles et matrices. Les points encore imparfaits sont indiqués sous chaque scène. Ces annotations du catalogue ne constituent pas une amélioration automatique des photos importées.</p>${sections}</html>`);
console.log('8 reports and before/after comparison built; metric geometry preserved.');
