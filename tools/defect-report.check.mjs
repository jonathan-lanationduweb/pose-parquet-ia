import assert from 'node:assert/strict';
import {DEFECTS,SEVERITIES,defectReport,reportText} from '../web/product/defect-report.js';
import {reviewGeometry} from '../web/scene/geometry-review.js';
const input={id:'fixture-001',sceneId:'fixture',imageSize:{width:100,height:100},defects:[],confirmedCorrect:[],references:{original:true}};
assert.equal(Object.keys(DEFECTS).length,10);
for(const item of Object.values(DEFECTS)){assert.ok(item.test.length>30);assert.ok(item.modules.length>=2);}
assert.equal(SEVERITIES.length,4);assert.match(reportText(defectReport(input)),/CONFIRMED CORRECT/);
assert.throws(()=>defectReport({...input,confirmedCorrect:undefined}));
assert.throws(()=>defectReport({...input,id:'../private'}));
const d={code:'D2',severity:'SEVERE',region:{x0:.1,y0:.6,x1:.3,y1:.8},description:'Pied recouvert',suspectedModules:['occluderMask','compositing'],confirmationTest:'Comparer masque rouge et pixel rendu.'};
assert.equal(defectReport({...input,defects:[d]}).defects[0].status,'OBSERVED');
assert.throws(()=>defectReport({...input,defects:[{...d,region:{x0:.9,x1:.1,y0:0,y1:1}}]}));
assert.throws(()=>defectReport({...input,defects:[{...d,suspectedModules:['occluderMask','compositing','ViewTransform']}]}));
assert.throws(()=>defectReport({...input,defects:[{...d,status:'CONFIRMED'}]}));
assert.throws(()=>defectReport({...input,defects:[d],confirmedCorrect:[{code:'D2',status:'PASS',scope:'all',evidence:'none'}]}));
assert.throws(()=>defectReport({...input,confirmedCorrect:[{code:'D3',status:'PASS',scope:'geometry'}]}));
// CASE #001: diagnostic claimed a 150 mm default for an actual 190 mm board.
const zone={id:'floor',plane:{quad:[{x:0,y:0},{x:1,y:0},{x:1,y:1},{x:0,y:1}],meters:{width:4,depth:4},rotationDeg:0}};
const scene={id:'fixture',floorZones:[zone]};
const masks={box:()=>({x0:0,y0:0,x1:100,y1:100}),labels:new Uint8Array(10000).fill(1),coverage:new Uint8Array(10000).fill(255),getPolygon:()=>zone.plane.quad};
const original=JSON.stringify(scene);
for(const [widthOverride,scale,expected]of[[null,1,.19],[null,2,.38],[.09,1,.09]]){
 const out=reviewGeometry(scene,masks,{width:100,height:100},{pattern:'lames',material:{boardWidth:.19,boardLength:1.8},width:widthOverride,scale,angle:0});
 assert.equal(out.plankM,expected);assert.equal(out.nominalLengthM,1.8);assert.equal(JSON.stringify(scene),original);
 assert.ok(masks.coverage.every(v=>v===255));assert.ok(masks.labels.every(v=>v===1));
}
console.log('PASS taxonomy, severity/region validation, mandatory scoped evidence, confirmed/resolved lifecycle; CASE #001 width/length/default/scale/override with scene and masks unchanged');
