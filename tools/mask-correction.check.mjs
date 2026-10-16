import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const {chromium}=createRequire(import.meta.url)(process.env.PPAI_PLAYWRIGHT_CORE);
const browser=await chromium.launch({channel:'chrome',headless:true});
try {
 const page=await browser.newPage();await page.goto('http://127.0.0.1:8000/tools/product-concept.html?prefetch=0');
 const result=await page.evaluate(async()=>{
  const {normalizeScene}=await import('/web/scene/schema.js');
  const {createSceneMasks}=await import('/web/scene/mask.js');
  const raw=await(await fetch('/web/data/scenes/piece-claire.json')).json();
  const rectangle=(l,t,r,b)=>[{x:l,y:t},{x:r,y:t},{x:r,y:b},{x:l,y:b}];
  raw.floorZones=[{id:'sol',surfaceId:'sol',planeRef:'sol',mask:{polygon:rectangle(0,0,1,1),holes:[]}}];
  raw.occluders=[{id:'tapis',kind:'rug',polygon:rectangle(.3,.3,.7,.7),feather:0}];
  const masks=createSceneMasks(normalizeScene(raw),120,120),at=()=>({floor:masks.coverage[60*120+60],object:masks.occlusion[60*120+60],outside:masks.occlusion[40*120+40]});
  const states=[at()];masks.beginStroke('sol','add',8,{x:.5,y:.5});states.push(at());masks.undo();states.push(at());masks.redo();states.push(at());masks.beginStroke('sol','remove',8,{x:.5,y:.5});states.push(at());masks.undo();states.push(at());return states;
 });
 assert.deepEqual(result.map(s=>s.object),[255,0,255,0,0,0]);assert.deepEqual(result.map(s=>s.floor),[255,255,255,255,0,255]);assert.ok(result.every(s=>s.outside===255));
 console.log('PASS Add overrides automatic protection locally; undo/redo and Remove preserve correct masks');
}finally{await browser.close();}
