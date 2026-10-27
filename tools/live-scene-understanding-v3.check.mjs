/** Live local API, real inference, real photo import; no mocked response. */
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const {chromium}=createRequire(import.meta.url)(process.env.PPAI_PLAYWRIGHT_CORE);
const base=process.env.PPAI_BASE||'http://127.0.0.1:8001';
const root='review/scene-understanding-v3';
const cases=[['piece-claire',1440,900],['cuisine-ilot',1440,900],['owner-photo',1440,900],['owner-photo',390,844]];
const browser=await chromium.launch({channel:'chrome',headless:true});
const rows=[];
try{
 for(const [scene,width,height]of cases){
  for(let run=0;run<5;run++){
   const page=await browser.newPage({viewport:{width,height},isMobile:width===390,hasTouch:width===390});
   let posts=0,analysis=null,postMs=null;const errors=[];
   page.on('pageerror',e=>errors.push(e.message));
   page.on('request',r=>{if(r.method()==='POST'&&r.url().endsWith('/v1/analyze-room'))posts++;});
   page.on('response',async r=>{if(r.request().method()==='POST'&&r.url().endsWith('/v1/analyze-room')){analysis=await r.json();}});
   await page.goto(base+'/tools/product-concept.html?dev=1&prefetch=0&perf=1');
   await page.waitForFunction(()=>window.__concept?.adapter.connecte,null,{timeout:90000});
   const start=Date.now();
   await page.setInputFiles('#file',root+'/'+scene+'/01-original.png');
   await page.waitForFunction(()=>window.__concept.state.source==='uploaded');
   const displayMs=Date.now()-start;
   await page.waitForFunction(()=>window.__concept.state.photoScene?.raw||['rejected','error','timeout','unavailable'].includes(window.__concept.state.analysis?.status),null,{timeout:180000});
   postMs=Date.now()-start;
   const first=await page.evaluate(()=>{const c=window.__concept;return {status:c.state.photoScene?.status,decision:c.state.photoScene?.provenance?.sceneQuality,pass:c.state.photoScene?.provenance?.pass};});
   let firstRenderMs=null;
   if(['auto_render','approximate_render'].includes(first.status)){
    await page.waitForFunction(()=>window.__concept.etatProduit()==='RENDER_READY'&&!window.__concept.state.applying,null,{timeout:90000});
    firstRenderMs=Date.now()-start;
   }
   const pending=analysis?.experimental?.floor?.sceneProvenance?.refinement?.status==='pending';
   if(pending)await page.waitForFunction(()=>window.__concept.state.photoScene?.qualityUpdateMs!=null,null,{timeout:180000});
   const finalMs=Date.now()-start;
   const final=await page.evaluate(()=>{const c=window.__concept;return {status:c.state.photoScene?.status,decision:c.state.photoScene?.provenance?.sceneQuality,pass:c.state.photoScene?.provenance?.pass,qualityStages:c.state.photoScene?.provenance?.timingsMs,modelWarmupMs:c.state.photoScene?.provenance?.modelWarmupMs,posee:c.state.photoScene?.posee,overflow:document.documentElement.scrollWidth>innerWidth};});
   assert.equal(final.overflow,false);
   if(pending)assert.equal(final.pass,'quality');
   const switches=[];
   if(final.posee){
    for(const id of ['CHENF39031','BTRPF39009','CHENF36014','BTRPF39009','CHENF39031']){
     const t=Date.now();await page.evaluate(id=>window.__concept.select(id),id);
     await page.waitForFunction(()=>window.__concept.etatProduit()==='RENDER_READY'&&!window.__concept.state.applying,null,{timeout:90000});
     await page.evaluate(()=>new Promise(requestAnimationFrame));switches.push(Date.now()-t);
    }
   }
   assert.equal(posts,1,'Product switch repeated inference');assert.deepEqual(errors,[]);
   const row={scene,width,height,run,displayMs,firstResponseMs:postMs,firstRenderMs,finalMs,first,final,switches,posts,analysisTimings:analysis?.timings,semanticTimings:analysis?.experimental?.floor?.timingsMs,browserStages:await page.evaluate(()=>window.__perfRapport?.())};
   rows.push(row);fs.writeFileSync(root+'/live-benchmark.json',JSON.stringify(rows,null,2));
   if(run===0)await page.screenshot({path:root+'/'+scene+'/live-'+width+'.png'});
   console.log(JSON.stringify({scene,width,run,firstRenderMs,finalMs,firstStatus:first.status,finalStatus:final.status,switches,posts}));
   await page.close();
  }
 }
}finally{await browser.close();}
