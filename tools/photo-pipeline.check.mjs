/** Real private photo regression. Never copies a photo into web/ or Git. */
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const {chromium}=createRequire(import.meta.url)(process.env.PPAI_PLAYWRIGHT_CORE);
const BASE=process.env.PPAI_BASE||'http://127.0.0.1:8000';
const OUT=process.env.PPAI_PHOTO_REVIEW||'review/roomvo-photo-accuracy/final';
const owner=process.env.PPAI_OWNER_PHOTO;
if(!owner)throw Error('PPAI_OWNER_PHOTO required (private local path)');
fs.mkdirSync(OUT,{recursive:true});
const cases=[{id:'owner',file:owner},...(process.env.PPAI_PHOTO_MATRIX==='1'?['sejour','chambre','couloir','petite-piece','salon','appartement-ancien','entree-cadree'].map(id=>({id,file:path.resolve(`datasets/private-real/${id}.jpg`)})):[])];
const canvasOnly=process.env.PPAI_CANVAS==='1';
const browser=await chromium.launch({channel:'chrome',headless:true});
const matrix=[];
try {
 for(const item of cases){
  assert.ok(fs.existsSync(item.file),`Private input missing: ${item.id}`);
  const page=await browser.newPage({viewport:{width:1440,height:900}}),errors=[];
  if(canvasOnly)await page.addInitScript(()=>{const get=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(type,...args){return /webgl/.test(type)?null:get.call(this,type,...args);};});
  page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
  let count=0;page.on('request',r=>{if(r.url().endsWith('/v1/analyze-room'))count++;});
  await page.goto(`${BASE}/tools/product-concept.html?dev=1&prefetch=0&perf=1`);
  await page.waitForFunction(()=>window.__concept?.adapter.connecte,null,{timeout:120000});
  const healthStart=Date.now();
  while((await(await page.request.get(`${BASE}/health`)).json()).experimentalFloor!=='ready'){
   if(Date.now()-healthStart>600000)throw Error('Backend warmup failed or timed out');
   await page.waitForTimeout(1000);
  }
  if(process.env.PPAI_INITIAL_PRODUCT)await page.evaluate(id=>window.__concept.select(id,true),process.env.PPAI_INITIAL_PRODUCT);
  const start=Date.now();await page.setInputFiles('#file',item.file);
  await page.waitForFunction(()=>['RENDER_READY','NEEDS_MANUAL_ADJUSTMENT','ANALYSIS_ERROR','ANALYSIS_UNAVAILABLE'].includes(window.__concept.etatProduit()),null,{timeout:180000});
  await page.waitForTimeout(300);
  const result=await page.evaluate(()=>{const c=window.__concept;return {state:c.etatProduit(),analysis:c.state.roomAnalysis.analysis,scene:c.state.photoScene,firstRenderMs:c.state.photoScene?.firstRenderMs,refusal:c.adapter.refusScene,networkMs:c.state.roomAnalysis.networkMs};});
  const firstMs=Date.now()-start,analysisCount=count;
  fs.writeFileSync(`${OUT}/${item.id}-response-private.json`,JSON.stringify(result.analysis));
  if(result.state==='NEEDS_MANUAL_ADJUSTMENT'){
   await page.click('#noscene [data-open="floor"]');
   await page.waitForFunction(()=>window.__concept.floorEdit.actif,null,{timeout:60000});
   const stage=await page.locator('#stage').boundingBox();
   await page.click('#floorTools [data-brush="add"]');await page.click('#floorTools [data-size="60"]');
   await page.mouse.move(stage.x+stage.width*.25,stage.y+stage.height*.85);await page.mouse.down();await page.mouse.move(stage.x+stage.width*.75,stage.y+stage.height*.85,{steps:8});await page.mouse.up();await page.click('#floorUndo');
   await page.click('#floorDone');
   await page.waitForFunction(()=>window.__concept.etatProduit()==='RENDER_READY',null,{timeout:60000});
   assert.equal(count,analysisCount,'Manual completion must not reanalyse');
  }
  assert.equal(await page.evaluate(()=>window.__concept.etatProduit()),'RENDER_READY',`${item.id}: no usable final frame`);
  await page.click('#photoMore');assert.ok(await page.locator('#photoActions').getByRole('button',{name:'Ajuster le sol',exact:true}).isVisible(),'Imported photo correction missing from options');assert.ok(await page.locator('#photoActions').getByRole('button',{name:'Télécharger le rendu',exact:true}).isEnabled(),'Rendered photo export disabled');await page.click('#photoMore');
  const frame=await page.evaluate(()=>document.getElementById('after').toDataURL('image/jpeg',.95));
  fs.writeFileSync(`${OUT}/${item.id}-frame.jpg`,Buffer.from(frame.split(',')[1],'base64'));
  await page.screenshot({path:`${OUT}/${item.id}-ui.jpg`,type:'jpeg',quality:92});
  if(process.env.PPAI_GEOMETRY_CAPTURE==='1'&&item.id==='owner'){await page.evaluate(()=>window.__geometryReview?.show(true));await page.screenshot({path:`${OUT}/04-geometry.jpg`,type:'jpeg',quality:92});await page.evaluate(()=>window.__geometryReview?.show(false));}
  const checks=await page.evaluate(async()=>{
   const c=window.__concept;async function ready(){const start=performance.now();while(c.etatApplication()!=='rendered'||c.state.applied.key!==c.appliedKey()||c.state.applying){if(performance.now()-start>60000)throw Error('Frame timeout');await new Promise(r=>setTimeout(r,10));}}
   const start=performance.now();c.select('CHENF36014',true);await ready();const productMs=performance.now()-start;
   c.setOrientation(37,false);await ready();const rotation=c.state.orientationDeg===37;
   document.getElementById('baBtn').click();const beforeAfter=c.state.ba;document.getElementById('baBtn').click();
   c.startCompare();await new Promise(r=>setTimeout(r,200));c.select('BTRPF39009',true);
   const limit=performance.now()+60000;while(!c.state.appliedB?.source&&performance.now()<limit)await new Promise(r=>setTimeout(r,20));const compare=c.state.appliedB?.source==='live';c.startCompare();await ready();
   return {productMs,rotation,beforeAfter,compare};
  });
  assert.ok(checks.rotation&&checks.beforeAfter&&checks.compare,`${item.id}: product interactions failed`);assert.equal(count,analysisCount,'Product changes must not reanalyse');assert.deepEqual(errors,[]);
  const f=result.analysis?.experimental?.floor;
  const row={canvasOnly,id:item.id,analysisMs:result.analysis?.timings?.total_ms,firstMs,firstRenderMs:result.firstRenderMs,networkMs:result.networkMs,floorCoverage:f?.coverage,geometry:f?.perspective,decision:f?.sceneStatus,quality:f?.sceneProvenance?.decision?.quality,timings:f?.timingsMs,backend:f?.metadata?.backend,initial:result.state,refusal:result.refusal,manual:result.state==='NEEDS_MANUAL_ADJUSTMENT',final:'RENDER_READY',checks,errors};
  matrix.push(row);fs.writeFileSync(`${OUT}/matrix.json`,JSON.stringify(matrix,null,2));console.log(JSON.stringify({id:row.id,analysisMs:row.analysisMs,firstMs,backend:row.backend,initial:row.initial,decision:row.decision,final:row.final}));await page.close();
 }
}finally{await browser.close();}
