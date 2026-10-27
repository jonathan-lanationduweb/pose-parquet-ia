/** Private performance replay; full-frame timings include material render/copy. */
import fs from 'node:fs';import {createRequire} from 'node:module';
const {chromium}=createRequire(import.meta.url)(process.env.PPAI_PLAYWRIGHT_CORE);
const browser=await chromium.launch({channel:'chrome',headless:true});
try{
 const p=await browser.newPage({viewport:{width:1440,height:900}});
 await p.addInitScript(()=>{window.__occlusionGl=[];const get=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(type,...args){const c=get.call(this,type,...args);if(/webgl/.test(type)&&c)window.__occlusionGl.push(c);return c;};});
 await p.goto((process.env.PPAI_BASE||'http://127.0.0.1:8000')+'/tools/product-concept.html?dev=1&prefetch=0');
 await p.waitForFunction(()=>window.__visualDiagnostics&&window.__concept?.adapter.connecte,null,{timeout:90000});
 const rows=await p.evaluate(async()=>{
  const {createSceneMasks}=await import('../web/scene/mask.js'),{refineOcclusion}=await import('../web/scene/occlusion-refiner.js'),{createGlRenderer}=await import('../web/scene/renderer-gl.js');
  const c=window.__concept,out=[];
  const summary=a=>{a.sort((a,b)=>a-b);return {median:a[Math.floor(a.length/2)],p95:a[Math.min(a.length-1,Math.ceil(a.length*.95)-1)],max:a.at(-1)};};
  for(const id of ['premibel-salon','premibel-chambre','piece-claire','chambre','terrasse-mer']){
   await c.adapter.openRoom(id);const profile=c.PREMIBEL_DEMO_PRODUCTS.find(p=>p.id==='CHENF39031').renderProfile;
   await c.adapter.applyProfile(profile,0);
   const s=c.adapter.diagnosticSnapshot(profile,0),{width:w,height:h}=s.size;
   const src=s.photo.getContext('2d').getImageData(0,0,w,h),gl=createGlRenderer(),samples={coarse:[],refinement:[],upload:[],samplingCompositeFullFrame:[]};
   if(!gl)throw Error('WebGL2 required for upload timing');
   gl.setPhoto(src); // Allocate mask texture/buffer at the actual source dimensions.
   for(let run=0;run<13;run++){
    let t=performance.now();const masks=createSceneMasks(s.scene,w,h);const coarse=masks.occlusion;const coarseMs=performance.now()-t;
    t=performance.now();if(coarse&&s.scene.occluders.some(o=>['furniture','rug','mask-opening'].includes(o.kind)))refineOcclusion(coarse,src.data,w,h);const refinement=performance.now()-t;
    t=performance.now();gl.setMasks(s.masks);window.__occlusionGl.forEach(g=>g.finish());const upload=performance.now()-t;
    t=performance.now();await c.adapter.diagnosticUnlitFrame(profile,0);window.__occlusionGl.forEach(g=>g.finish());const paint=performance.now()-t;
    if(run){samples.coarse.push(coarseMs);samples.refinement.push(refinement);samples.upload.push(upload);samples.samplingCompositeFullFrame.push(paint);}
   }
   out.push({scene:id,runs:12,size:s.size,changedPixels:s.masks.refinement.changed,timingsMs:Object.fromEntries(Object.entries(samples).map(([k,v])=>[k,summary(v)]))});
  }return out;
 });
 fs.writeFileSync('review/occlusion-obstacles/browser-performance.json',JSON.stringify(rows,null,2));console.log(JSON.stringify(rows,null,2));
}finally{await browser.close();}
