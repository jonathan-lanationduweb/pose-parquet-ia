/** Actual action timings, no inference. Cold scene preparation and warm actions separated. */
import fs from'node:fs';import{createRequire}from'node:module';
const{chromium}=createRequire(import.meta.url)(process.env.PPAI_PLAYWRIGHT_CORE),browser=await chromium.launch({channel:'chrome',headless:true});
try{const p=await browser.newPage({viewport:{width:1440,height:900}});await p.goto('http://127.0.0.1:8000/tools/product-concept.html?dev=1&prefetch=0');await p.waitForFunction(()=>window.__concept?.adapter.connecte,null,{timeout:90000});
 const result=await p.evaluate(async()=>{const c=window.__concept,profiles=['BTRPF39009','CHENF39031'].map(id=>c.PREMIBEL_DEMO_PRODUCTS.find(p=>p.id===id).renderProfile);
 const start=performance.now();await c.adapter.openRoom('piece-claire');await c.adapter.applyProfile(profiles[0],0);const firstRender=performance.now()-start;
 const samples={productChange:[],rotation:[],roomSwitch:[]},cacheHits={productChange:0,rotation:0};
 for(let i=0;i<12;i++){
  let t=performance.now();await c.adapter.applyProfile(profiles[i%2],0);samples.productChange.push(performance.now()-t);cacheHits.productChange+=c.adapter.lastHit?1:0;
  t=performance.now();await c.adapter.applyProfile(profiles[i%2],i%2?30:60);samples.rotation.push(performance.now()-t);cacheHits.rotation+=c.adapter.lastHit?1:0;
  t=performance.now();await c.adapter.openRoom(i%2?'piece-claire':'premibel-chambre');await c.adapter.applyProfile(profiles[0],0);samples.roomSwitch.push(performance.now()-t);
 }
 const stat=a=>{a.sort((x,y)=>x-y);return{median:a[6],p95:a[11],max:a[11]}};
 return{firstRenderMs:firstRender,samples:12,timingsMs:Object.fromEntries(Object.entries(samples).map(([k,v])=>[k,stat(v)])),cacheHits,scope:'Local Chrome. First scene preparation; network/model startup excluded. Warm actions include cache hits; cold/warm room switches mixed.'};
 });fs.writeFileSync('review/visual-quality-s1-s8/performance-actions.json',JSON.stringify(result,null,2));console.log(result);
 const review=await browser.newPage();await review.goto('file:///'+process.cwd().replaceAll('\\','/')+'/review/visual-quality-s1-s8/index.html');
 for(const width of[1440,390]){await review.setViewportSize({width,height:900});await review.screenshot({path:'review/visual-quality-s1-s8/review-'+width+'.png'});if(!await review.evaluate(()=>document.documentElement.scrollWidth<=innerWidth))throw Error('review overflows '+width);}
 console.log('PASS native private review index at 1440/390');
}finally{await browser.close();}
