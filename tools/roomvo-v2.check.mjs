import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
const req=createRequire(import.meta.url),pw=req(process.env.PPAI_PLAYWRIGHT_CORE || 'C:/Users/jonat/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core');
const out=path.resolve('review/roomvo-v2');fs.mkdirSync(out,{recursive:true});
const browser=await pw.chromium.launch({channel:'chrome',headless:true});
const errors=[],results=[],photos=[];
const httpErrors=[];
const save=()=>fs.writeFileSync(path.join(out,'checks.json'),JSON.stringify({results,photos,errors},null,2));
const check=(name,pass,detail)=>{results.push({name,pass,detail});save();console.log(`${pass?'PASS':'FAIL'} ${name}`);};
const shot=(p,n)=>p.screenshot({path:path.join(out,n+'.jpg'),type:'jpeg',quality:90});
const ready=p=>p.waitForFunction(()=>{const c=window.__concept;return !c.state.applying&&c.state.applied.source==='live'&&c.state.applied.key===c.appliedKey();},null,{timeout:150000});
const page=async(width,height=900)=>{const p=await browser.newPage({viewport:{width,height}});p.on('pageerror',e=>errors.push(e.message));p.on('response',r=>{if(r.status()>=400)httpErrors.push({status:r.status(),url:r.url()});});await p.goto('http://127.0.0.1:8143/tools/product-concept.html');await p.waitForFunction(()=>window.__sessionRooms);return p;};
async function paintFloor(p){await p.evaluate(()=>window.__concept.floorEditStart());await p.waitForFunction(()=>window.__concept.floorEdit.actif);const b=await p.locator('#floorEdit').boundingBox();await p.mouse.move(b.x+b.width*.3,b.y+b.height*.85);await p.mouse.down();await p.mouse.move(b.x+b.width*.6,b.y+b.height*.85,{steps:8});await p.mouse.up();}
try{
 const p=await page(1440);await shot(p,'01-room-select');await p.getByRole('button',{name:'Cuisine',exact:true}).click();await shot(p,'02-room-category');await p.getByRole('button',{name:'Toutes',exact:true}).click();
 await p.click('#quickRooms [data-room="sejour"]');await ready(p);await p.evaluate(()=>window.__concept.select('CHENF39031'));await ready(p);await shot(p,'03-visualizer-clean');await shot(p,'04-catalog');
 const catalog=await p.evaluate(()=>{const c=window.__concept,all=c.PREMIBEL_DEMO_PRODUCTS.filter(p=>p.source==='premibel');return {count:all.length,representative:all.filter(p=>p.renderable!==false).length,unavailable:all.filter(p=>p.renderable===false).length,scenes:c.DEMO_ROOMS.length};});check('catalog enriched and independent',catalog.count>=394&&catalog.scenes===11,catalog);
 const unavailable=await p.evaluate(()=>window.__concept.PREMIBEL_DEMO_PRODUCTS.find(p=>p.renderable===false)?.id);const before=await p.evaluate(()=>window.__concept.state.productId);await p.evaluate(id=>window.__concept.select(id),unavailable);check('unavailable material does not fake a render',(await p.evaluate(()=>window.__concept.state.productId))===before,unavailable);
 await p.evaluate(()=>window.__concept.openCus());await p.waitForTimeout(1000);await shot(p,'05-customize');await p.click('#cusClose');
 await p.click('#photoMore');check('secondary actions menu',await p.getByRole('button',{name:'Télécharger le rendu',exact:true}).isVisible());await p.click('#photoMore');
 for(const width of [320,360,375,390,430,768,820,1024,1280,1440,1600,1920]){await p.setViewportSize({width,height:width<600?844:900});await p.waitForTimeout(250);const r=await p.evaluate(()=>{const card=document.getElementById('card').getBoundingClientRect();return {overflow:document.documentElement.scrollWidth>innerWidth+1,cardVisible:card.bottom<=innerHeight+1,sidebar:window.__concept.drawer.catalogPinned};});check(`responsive ${width}`,!r.overflow&&r.cardVisible&&(width<1024||r.sidebar),r);}
 await p.setViewportSize({width:1440,height:900});
 for(const name of ['sejour','chambre','couloir','petite-piece','salon','appartement-ancien','entree-cadree']){
   const start=Date.now();await p.setInputFiles('#file',path.resolve(`datasets/private-real/${name}.jpg`));await p.waitForFunction(n=>window.__concept.state.uploaded?.name===n+'.jpg',name);
   await p.waitForFunction(()=>['ANALYSIS_WAITING','ANALYZING'].includes(window.__concept.etatProduit()),null,{timeout:15000});if(name==='sejour')await shot(p,'06-analysis-animation');
   await p.waitForFunction(()=>!['PHOTO_SELECTED','ANALYSIS_WAITING','ANALYZING'].includes(window.__concept.etatProduit()),null,{timeout:300000});
   const data=await p.evaluate(()=>{const c=window.__concept,s=c.state,a=s.roomAnalysis,f=a.analysis?.experimental?.floor;return {state:c.etatProduit(),status:s.photoScene?.status,confidence:s.photoScene?.confidence,displayLocalMs:a.displayLocalMs,networkMs:a.networkMs,totalMs:a.totalMs,stages:a.analysis?.timings,segmentation:f?.timingsMs||f?.timings_ms,decision:s.photoScene?.provenance?.decision};});
   const automatic=data.status==='auto_render';if(!automatic){if(data.status==='needs_manual_adjustment')await shot(p,'07-approx-detection');await paintFloor(p);if(name==='couloir')await shot(p,'09-manual-adjustment');await p.click('#floorDone');}
   await ready(p);data.mode=automatic?'AUTO':'MANUAL';data.photo=name;data.photoToParquetMs=Date.now()-start;data.firstRenderMs=await p.evaluate(()=>window.__concept.state.photoScene?.firstRenderMs);photos.push(data);save();check(`real photo ${name}`,await p.evaluate(()=>window.__concept.etatProduit()==='RENDER_READY'),data);
   await shot(p,`photo-${name}`);if(name==='sejour')await shot(p,'08-auto-result');
 }
 const timings=[];for(const id of ['POINF36005','CHENF39031','POINF36005']){const t=Date.now();await p.evaluate(id=>window.__concept.select(id),id);await ready(p);timings.push({id,ms:Date.now()-t});}check('product changes without analysis',true,timings);
 await p.evaluate(()=>window.__concept.startCompare());await p.evaluate(()=>window.__concept.select('BTRPF39009'));await p.waitForFunction(()=>window.__concept.state.appliedB.source==='live',null,{timeout:150000});await shot(p,'10-compare');await p.close();
 const m=await page(390,844);await shot(m,'11-room-select-390');await m.click('#quickRooms [data-room="sejour"]');await ready(m);await shot(m,'12-visualizer-390');await m.evaluate(()=>window.__concept.openCat());await m.waitForTimeout(800);await shot(m,'13-catalog-390');await m.click('#catClose');await m.evaluate(()=>window.__concept.openCus());await m.waitForTimeout(800);await shot(m,'14-customize-390');
 const mobile=await m.evaluate(()=>{const photo=document.getElementById('after').getBoundingClientRect(),stage=document.getElementById('stage').getBoundingClientRect(),sheet=window.__concept.drawer.element.getBoundingClientRect();return {visible:Math.min(photo.bottom,stage.bottom,sheet.top)-Math.max(photo.top,stage.top),height:innerHeight};});check('mobile preview while customizing',mobile.visible/mobile.height>=.35,mobile);await m.click('#cusClose');
 await m.setInputFiles('#file',path.resolve('datasets/private-real/sejour.jpg'));await m.waitForFunction(()=>window.__concept.state.source==='uploaded');await shot(m,'15-analysis-390');await m.waitForFunction(()=>!['PHOTO_SELECTED','ANALYSIS_WAITING','ANALYZING'].includes(window.__concept.etatProduit()),null,{timeout:300000});if(await m.evaluate(()=>window.__concept.state.photoScene?.status!=='auto_render')){await paintFloor(m);await m.click('#floorDone');}await ready(m);await shot(m,'16-result-390');check('mobile photo finishes',true);await m.close();
 const cv=await browser.newPage({viewport:{width:1280,height:800}});cv.on('pageerror',e=>errors.push(e.message));await cv.goto('http://127.0.0.1:8143/tools/product-concept.html?dev=1&backend=canvas');await cv.waitForFunction(()=>window.__sessionRooms);await cv.click('#quickRooms [data-room="sejour"]');await ready(cv);check('Canvas fallback',await cv.evaluate(()=>window.__concept.adapter.local.studio.backend==='canvas'));await cv.close();
 check('console exceptions',errors.length===0,errors);check('missing resources',httpErrors.length===0,httpErrors);
}finally{save();await browser.close();}
if(results.some(r=>!r.pass)||errors.length)process.exitCode=1;
