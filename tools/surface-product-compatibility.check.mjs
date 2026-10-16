import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const {chromium}=createRequire(import.meta.url)(process.env.PPAI_PLAYWRIGHT_CORE);
const base=process.env.PPAI_BASE||'http://127.0.0.1:8000';
const out='review/room-understanding-v2-1';
const browser=await chromium.launch({channel:'chrome',headless:true});
const results=[];
try {
 for(const width of [1440,390]) {
  const page=await browser.newPage({viewport:{width,height:width===390?844:900},isMobile:width===390,hasTouch:width===390});
  const errors=[];let analyses=0;page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.url().endsWith('/v1/analyze-room'))analyses++;});
  await page.goto(base+'/tools/product-concept.html?dev=1&prefetch=0');
  await page.waitForFunction(()=>window.__concept?.adapter.connecte,null,{timeout:90000});
  const unknown=await page.evaluate(()=>window.PPSurfaceProducts.status({name:'Wood without supplier usage'},'exterior_terrace'));assert.equal(unknown,'unknown');
  const frames=new Map();
  for(const id of ['sejour','terrasse-mer','chambre','terrasse-mer','sejour']) {
   const start=Date.now(); await page.evaluate(id=>window.__concept.openRoom(id),id);
   await page.waitForFunction(id=>window.__concept.state.roomId===id&&window.__concept.etatProduit()==='RENDER_READY'&&!window.__concept.state.applying,id,{timeout:90000});
   const data=await page.evaluate(()=>{const c=window.__concept,s=c.adapter.visitSnapshot();return{room:c.state.roomId,product:c.state.productId,surface:c.room().surfaceType,compatibility:window.PPSurfaceProducts.status(c.product(),c.room().surfaceType),scene:JSON.stringify(s.scene),key:c.adapter.lastKey,frame:document.getElementById('after').toDataURL('image/jpeg',.9),overflow:document.documentElement.scrollWidth>innerWidth,cardBottom:document.getElementById('card').getBoundingClientRect().bottom,height:innerHeight};});
   assert.equal(data.compatibility,'compatible');assert.equal(data.overflow,false);assert.ok(data.cardBottom<=data.height+1);
   if(id==='terrasse-mer')assert.equal(data.product,'VLAME16012');
   if(frames.has(id))assert.equal(data.scene,frames.get(id).scene,'SceneData changed unexpectedly on A/B/A');
   if([...frames.keys()].some(k=>k!==id))assert.ok([...frames].filter(([k])=>k!==id).every(([,v])=>v.key!==data.key),'Cross-scene render key reused');
   frames.set(id,data);results.push({width,id,product:data.product,surface:data.surface,switchMs:Date.now()-start});
   await page.screenshot({path:`${out}/${id}-${width}.jpg`,type:'jpeg',quality:90});
   if(id==='terrasse-mer'&&width===1440)fs.writeFileSync(`${out}/terrace-ipe-correct.jpg`,Buffer.from(data.frame.split(',')[1],'base64'));
  }
  // An explicit incompatible selection is rejected, including compare mode.
  await page.evaluate(()=>window.__concept.openRoom('terrasse-mer'));
  await page.waitForFunction(()=>window.__concept.etatProduit()==='RENDER_READY',null,{timeout:90000});
  const product=await page.evaluate(()=>{window.__concept.select('POINF36005',true);return window.__concept.state.productId;});assert.equal(product,'VLAME16012');
  assert.equal(analyses,0);assert.deepEqual(errors,[]);
  await page.close();
 }
 // Shared uploaded id: same material, same URL, changed geometry AND light.
 const page=await browser.newPage();
 await page.route('**/rd-cache-photo',r=>r.fulfill({contentType:'image/jpeg',body:fs.readFileSync(`${out}/owner/original.jpg`)}));
 await page.goto(base+'/tools/product-concept.html?prefetch=0');await page.waitForFunction(()=>window.__concept?.adapter.connecte,null,{timeout:90000});
 const raw=JSON.parse(fs.readFileSync(`${out}/owner/scene-after.json`,'utf8'));
 const frames=[];
 for(let index=0;index<3;index++) {
  const scene=structuredClone(raw);if(index===1){scene.planes.sol.rotationDeg=28;scene.light={...scene.light,strength:.55,exposure:.6};scene.floorZones[0].mask.polygon[0].y-=.002;}
  const frame=await page.evaluate(async scene=>{const c=window.__concept;if(!await c.adapter.openPhotoScene(scene,location.origin+'/rd-cache-photo'))throw Error('scene refused');const profile=c.PREMIBEL_DEMO_PRODUCTS.find(p=>p.id==='CHENF39031').renderProfile;const frame=await c.adapter.applyProfile(profile,0);return{key:c.adapter.lastKey,hit:c.adapter.lastHit,image:frame.toDataURL('image/jpeg',.9)};},scene);
  assert.equal(frame.hit,false);frames.push(frame);
 }
 assert.notEqual(frames[0].key,frames[1].key);assert.notEqual(frames[0].image,frames[1].image);assert.equal(frames[0].image,frames[2].image);
 await page.close();fs.writeFileSync(`${out}/compatibility-cache.json`,JSON.stringify({results,uploadedCacheIsolation:true,pageErrors:[]},null,2));console.log('PASS surface compatibility, A/B/A isolation, uploaded geometry/light isolation, desktop + 390 mobile',results);
} finally {await browser.close();}
