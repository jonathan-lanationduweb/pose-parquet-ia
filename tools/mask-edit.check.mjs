/** Verify actual mask edits retain cached occlusions and detect furniture edits. */
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const {chromium}=createRequire(import.meta.url)(process.env.PPAI_PLAYWRIGHT_CORE);
const browser=await chromium.launch({channel:'chrome',headless:true});
try {
 const page=await browser.newPage();await page.goto(`${process.env.PPAI_BASE||'http://127.0.0.1:8000'}/health`);
 const result=await page.evaluate(async()=>{
  const {createSceneMasks}=await import('/web/scene/mask.js');
  const box=(x,y,w,h)=>[{x,y},{x:x+w,y},{x:x+w,y:y+h},{x,y:y+h}];
  const scene={floorZones:[{id:'f',mask:{polygon:box(0,0,1,1),holes:[]}}],occluders:[{polygon:box(.4,.4,.2,.2),holes:[],feather:0}]};
  let reads=0;const read=CanvasRenderingContext2D.prototype.getImageData;
  CanvasRenderingContext2D.prototype.getImageData=function(...args){reads++;return read.apply(this,args);};
  try {
   const m=createSceneMasks(scene,320,240);const pixel=(x,y)=>Math.floor(y*240)*320+Math.floor(x*320);
   const protectedBefore=m.occlusion[pixel(.5,.5)];const initialReads=reads;
   m.beginStroke('f','remove',12,{x:.2,y:.2});const removed=m.coverage[pixel(.2,.2)];const strokeReads=reads-initialReads;
   const protectedAfter=m.occlusion[pixel(.5,.5)];m.undo();const restored=m.coverage[pixel(.2,.2)];
   scene.occluders[0].polygon=box(.7,.7,.2,.2);m.invalidate();const oldFurniture=m.occlusion[pixel(.5,.5)],newFurniture=m.occlusion[pixel(.8,.8)];
   return{protectedBefore,protectedAfter,removed,restored,strokeReads,oldFurniture,newFurniture};
  }finally{CanvasRenderingContext2D.prototype.getImageData=read;}
 });
 assert.equal(result.protectedBefore,255);assert.equal(result.protectedAfter,255);assert.equal(result.removed,0);assert.equal(result.restored,255);assert.equal(result.strokeReads,1,'Static furniture masks were repainted');assert.equal(result.oldFurniture,0);assert.equal(result.newFurniture,255);console.log('PASS real mask stroke / undo / cached and edited furniture',result);
}finally{await browser.close();}
