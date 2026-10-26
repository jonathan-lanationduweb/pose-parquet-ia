/** Diagnostic vocabulary; PASS always describes evidence with an explicit scope. */
export const SEVERITIES=Object.freeze(['MINOR','MODERATE','SEVERE','BLOCKING']);
export const REGIONS=Object.freeze(['top-left','top-center','top-right','middle-left','center','middle-right','bottom-left','bottom-center','bottom-right']);
export const DEFECTS=Object.freeze({
 D1:{name:'CONTOUR',modules:['RoomUnderstanding','FloorMaskRefiner','mask sampling','ViewTransform'],test:'Afficher Masks : si le vert déborde, contour source ; sinon comparer coordonnées source et compositing.'},
 D2:{name:'OCCLUSION',modules:['occluderMask','RoomUnderstanding','compositing','ViewTransform'],test:'Objet rouge et pourtant repeint : échantillonnage/compositing ; objet absent du rouge : génération des occlusions.'},
 D3:{name:'PERSPECTIVE',modules:['CameraModel','FloorPlane','uViewProj','CameraSolver'],test:'Comparer Grid aux lignes architecturales. Grille correcte et parquet faux : isoler le motif, sans changer la caméra.'},
 D4:{name:'ÉCHELLE',modules:['metric scale','camera height','board dimensions','FloorPlane'],test:'Comparer Scale near/middle/far, dimensions produit et référence mesurée. Sans mesure, échelle absolue non confirmée.'},
 D5:{name:'ORIENTATION',modules:['floorAngle','pattern orientation','product options'],test:'Comparer 0° et 90° avec la même signature caméra. Une préférence de pose ne justifie pas une nouvelle calibration.'},
 D6:{name:'HORIZON',modules:['CameraModel','horizon','focal length','camera pose'],test:'Comparer Camera et Grid aux fuites de la photo. Le contrôle interne de la caméra ne prouve pas la justesse des fuites estimées.'},
 D7:{name:'LUMIÈRE',modules:['lighting map','compositing','contact shadows','relighting'],test:'Comparer render et unlit en DEV, avec mêmes masque/caméra/produit. Vérifier sur original la présence de l’ombre avant de modifier la lumière.'},
 D8:{name:'LIMITE / EDGE',modules:['mask compositing','feathering','sampling','anti-aliasing'],test:'Examiner les masques bruts à 100 % ou plus. Distinguer escalier déjà dans le contour et aliasing créé au compositing.'},
 D9:{name:'JOINTS',modules:['physical joint width','pattern shader'],test:'Comparer la distance aux joints dans Pattern aux dimensions métriques et à leur empreinte projetée. Un joint sous-pixel doit être filtré.'},
 D10:{name:'MOTIF',modules:['pattern generation','floor-space coordinates','shader'],test:'Comparer IDs de lames en floor-space et en projection. Motif déjà faux à plat : génération ; sinon projection ou mapping.'}
});
const text=(v,label)=>{if(typeof v!=='string'||!v.trim()||v.length>2000)throw Error('Invalid '+label);return v;};
export function validateRegion(r){
 if(typeof r==='string'){if(!REGIONS.includes(r))throw Error('Invalid region');return r;}
 if(!r||!['x0','y0','x1','y1'].every(k=>Number.isFinite(r[k])&&r[k]>=0&&r[k]<=1)||r.x0>=r.x1||r.y0>=r.y1)throw Error('Invalid normalized region');
 return {x0:r.x0,y0:r.y0,x1:r.x1,y1:r.y1};
}
export function defectReport(input){
 if(!input||!Object.hasOwn(input,'confirmedCorrect'))throw Error('CONFIRMED CORRECT is required (may be empty)');
 const id=text(input.id,'case id');if(!/^[a-zA-Z0-9_-]+$/.test(id))throw Error('Unsafe case id');
 const defects=(input.defects||[]).map(d=>{
  if(!Object.hasOwn(DEFECTS,d.code)||!SEVERITIES.includes(d.severity))throw Error('Invalid defect code/severity');
  if(!Array.isArray(d.suspectedModules)||d.suspectedModules.length<1||d.suspectedModules.length>2||d.suspectedModules.some(m=>!DEFECTS[d.code].modules.includes(m)))throw Error('Select one or two taxonomy modules');
  const result={code:d.code,severity:d.severity,region:validateRegion(d.region),description:text(d.description,'description'),suspectedModules:[...d.suspectedModules],confirmationTest:text(d.confirmationTest,'confirmation test'),status:d.status||'OBSERVED'};
  if(!['OBSERVED','CONFIRMED','RESOLVED'].includes(result.status))throw Error('Invalid defect status');
  for(const k of ['result','rootCause','fix','regression'])if(d[k])result[k]=text(d[k],k);
  if(result.status!=='OBSERVED'&&(!result.result||!result.rootCause))throw Error('Confirmed defect needs result and root cause');
  if(result.status==='RESOLVED'&&(!result.fix||!result.regression||!['better','same','worse'].includes(d.visualResult)))throw Error('Resolved defect needs fix, regression and visual result');
  result.visualResult=d.visualResult||'not_reviewed';return result;
 });
 const confirmedCorrect=input.confirmedCorrect.map(p=>{
  if(!Object.hasOwn(DEFECTS,p.code)||p.status!=='PASS')throw Error('Invalid confirmed-correct item');
  if(defects.some(d=>d.code===p.code&&d.status!=='RESOLVED'))throw Error('Cannot mark an unresolved defect correct');
  return {code:p.code,status:'PASS',scope:text(p.scope,'PASS scope'),evidence:text(p.evidence,'PASS evidence')};
 });
 return {schema:'pose-parquet/defect-report@1',id,sceneId:text(input.sceneId,'scene id'),imageSize:input.imageSize||null,defects,confirmedCorrect,references:{original:input.references?.original===true,roomvo:input.references?.roomvo===true},reviewStatus:input.reviewStatus||'PENDING_HUMAN_REVIEW'};
}
export function reportText(r){
 const lines=['DEFECT REPORT',r.id,'Scene: '+r.sceneId,'Image: '+JSON.stringify(r.imageSize),''];
 for(const d of r.defects)lines.push('DEFECT',d.code+' '+d.severity+' · '+JSON.stringify(d.region),'OBSERVATION',d.description,'SUSPECTED MODULE',d.suspectedModules.join(' / '),'CONFIRMATION TEST',d.confirmationTest,'RESULT',d.result||'Not executed','ROOT CAUSE',d.rootCause||'Not confirmed','FIX',d.fix||'None','REGRESSION',d.regression||'Not executed','VISUAL RESULT',d.visualResult,'');
 lines.push('CONFIRMED CORRECT',...(r.confirmedCorrect.length?r.confirmedCorrect.map(p=>p.code+' PASS · '+p.scope+' · '+p.evidence):['None confirmed. Do not infer visual PASS from numeric invariants.']),'REFERENCE',JSON.stringify(r.references),r.reviewStatus);
 return lines.join('\n');
}
