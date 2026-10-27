/** Controlled transport timing, actual renderer and manual edit controls. */
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const {chromium}=createRequire(import.meta.url)(process.env.PPAI_PLAYWRIGHT_CORE);
const base=process.env.PPAI_BASE||'http://127.0.0.1:8000',root='review/scene-understanding-v3';
const template=JSON.parse(fs.readFileSync('review/room-understanding-v2-1/owner/final-api-private.json'));
const fast=JSON.parse(fs.readFileSync(root+'/owner-photo/fast.json'));
const quality=JSON.parse(fs.readFileSync(root+'/owner-photo/quality.json'));
const browser=await chromium.launch({channel:'chrome',headless:true,args:[]});
try{
 for(const scenario of ['quality','manual','no-floor']){
  const manual=scenario==='manual',noFloor=scenario==='no-floor';
  const page=await browser.newPage({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
  if(process.env.PPAI_CANVAS==='1')await page.addInitScript(()=>{const get=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(kind,...args){return /webgl/.test(kind)?null:get.call(this,kind,...args);};});
  let release=false,posts=0,deleted=0;const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const response=structuredClone(template);response.experimental.floor.sceneData=fast;response.experimental.floor.sceneStatus='approximate_render';response.experimental.floor.sceneProvenance={pass:'fast',refinement:{status:'pending',token:'test-capability'}};
  const final={...response.experimental,floor:{...response.experimental.floor,sceneData:noFloor?null:quality,sceneStatus:noFloor?'no_floor':'approximate_render',sceneProvenance:{pass:'quality',refinement:{status:'complete'}}}};
  await page.route('**/health',r=>r.fulfill({json:{status:'ok',experimentalFloor:'ready'}}));
  await page.route('**/v1/analyze-room',r=>{posts++;return r.fulfill({json:response});});
  await page.route('**/v1/analyze-room/refinements/*',r=>{if(r.request().method()==='DELETE'){deleted++;return r.fulfill({status:204});}return r.fulfill({json:release?{status:'ready',experimental:final}:{status:'pending'}});});
  await page.goto(base+'/tools/product-concept.html?dev=1&prefetch=0');
  await page.waitForFunction(()=>window.__concept?.adapter.connecte,null,{timeout:90000});
  await page.setInputFiles('#file',root+'/owner-photo/01-original.png');
  await page.waitForFunction(()=>window.__concept.etatProduit()==='RENDER_READY'&&!window.__concept.state.applying,null,{timeout:90000});
  const signature=await page.evaluate(()=>JSON.stringify([window.__concept.state.photoScene.raw.camera,window.__concept.state.photoScene.raw.planes]));
  if(noFloor){
   release=true;
   await page.waitForFunction(()=>window.__concept.state.photoScene?.status==='no_floor',null,{timeout:90000});
   assert.equal(await page.evaluate(()=>window.__concept.state.photoScene.posee),false);
   assert.equal(await page.evaluate(()=>window.__concept.state.applied.source),null);
  }else if(!manual){
   await page.evaluate(()=>window.__concept.select('CHENF39031'));
   release=true;
   await page.waitForFunction(()=>window.__concept.state.photoScene?.qualityUpdateMs!=null,null,{timeout:90000});
   assert.equal(await page.evaluate(()=>window.__concept.state.productId),'CHENF39031');
   assert.equal(await page.evaluate(()=>JSON.stringify([window.__concept.state.photoScene.raw.camera,window.__concept.state.photoScene.raw.planes])),signature);
   const foreground=await page.evaluate(async()=>{
    const a=window.__concept.adapter,m=a.visitSnapshot().masks,normal=a.canvas.getContext('2d').getImageData(0,0,a.canvas.width,a.canvas.height).data;
    const before=Array.from(m.occlusion),frame=await a.diagnosticForegroundFrame(),without=frame.getContext('2d').getImageData(0,0,frame.width,frame.height).data;
    let maxDifference=0,points=0;for(let i=0;i<m.coverage.length;i++)if(m.coverage[i]>250&&m.occlusion[i]>250){points++;maxDifference=Math.max(maxDifference,Math.abs(normal[i*4]-without[i*4]));}
    return {points,maxDifference,unchanged:before.every((v,i)=>v===m.occlusion[i])};
   });
   assert.ok(foreground.points>100&&foreground.maxDifference>20);assert.equal(foreground.unchanged,true);
  }else{
   await page.locator('#photoMore').click();await page.locator('#photoActions').getByRole('button',{name:'Ajuster le sol',exact:true}).click();
   await page.waitForFunction(()=>window.__concept.floorEdit.actif);
   const point=await page.evaluate(()=>{const c=window.__concept,m=c.adapter.visitSnapshot().masks;for(let y=Math.floor(m.height*.6);y<m.height;y++)for(let x=0;x<m.width;x++)if(m.effectiveCoverage[y*m.width+x]>250)return {x:x+.5,y:y+.5};throw Error('No visible floor');});
   await page.evaluate(p=>{const b=window.__concept.adapter.pinceau;const m=window.__concept.adapter.visitSnapshot().masks;b.begin('remove',8,{x:p.x/m.width,y:p.y/m.height});b.end();},point);
   await page.locator('#floorDone').click();release=true;await page.waitForTimeout(900);
   assert.equal(await page.evaluate(()=>window.__concept.state.photoScene.provenance.pass),'fast','Late quality overwrote manual edit');
   assert.equal(await page.evaluate(p=>{const m=window.__concept.adapter.visitSnapshot().masks;return m.effectiveCoverage[Math.floor(p.y)*m.width+Math.floor(p.x)];},point),0);
  }
  assert.equal(posts,1);assert.deepEqual(errors,[]);
  console.log('PASS '+(noFloor?'quality refusal clears the coarse floor':manual?'manual correction supersedes pending quality':'stable camera, product selection preserved, DEV foreground OFF')+'; one analysis; '+(process.env.PPAI_CANVAS==='1'?'Canvas':'WebGL'));
  await page.close();
 }
}finally{await browser.close();}
