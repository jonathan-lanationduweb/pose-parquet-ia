import fs from'node:fs';import assert from'node:assert/strict';import{createRequire}from'node:module';
const{chromium}=createRequire(import.meta.url)(process.env.PPAI_PLAYWRIGHT_CORE),b=await chromium.launch({channel:'chrome',headless:true}),base=process.env.PPAI_BASE||'http://127.0.0.1:8000',root='review/retailer-ux';
fs.mkdirSync(root,{recursive:true});const rows=[];
try{
 for(const width of[320,360,375,390,430]){
  const p=await b.newPage({viewport:{width,height:844},isMobile:true,hasTouch:true}),errors=[];p.on('pageerror',e=>errors.push(e.message));
  await p.goto(base+'/tools/product-concept.html?productId=CHENF39031&telemetry=0');await p.waitForFunction(()=>window.__retailerUX&&window.__concept.DEMO_ROOMS.length);
  assert.equal(await p.evaluate(()=>window.__concept.state.productId),'CHENF39031');
  await p.locator('#guidedPhotoOpen').tap();assert.ok(await p.locator('#captureGuide').isVisible());await p.locator('#captureGuide .pp-close').tap();
  await p.evaluate(()=>window.__concept.openRoom('chambre'));await p.waitForFunction(()=>window.__concept.etatProduit()==='RENDER_READY',null,{timeout:90000});
  await p.locator('#photoMore').tap();await p.locator('#shareResultOpen').tap();assert.ok((await p.locator('#shareResultLink').inputValue()).includes('productId=CHENF39031'));await p.locator('#shareResult .pp-close').tap();
  await p.evaluate(()=>{const c=window.__concept;c.setOrientation(90,false);c.toggleFav('CHENF39031');});
  await p.waitForFunction(()=>window.__concept.etatProduit()==='RENDER_READY',null,{timeout:90000});
  const state=await p.evaluate(()=>({overflow:document.documentElement.scrollWidth>innerWidth,cardBottom:document.getElementById('card').getBoundingClientRect().bottom,height:innerHeight,perf:window.__retailerUX.performance.snapshot()}));
  assert.equal(state.overflow,false);assert.ok(state.cardBottom<=state.height+1);assert.deepEqual(state.perf,[]);assert.deepEqual(errors,[]);
  await p.screenshot({path:root+'/mobile-'+width+'.png'});rows.push({width,...state});
  await p.goto(base+'/tools/product-concept.html');await p.waitForFunction(()=>window.__retailerUX&&window.__concept.state.source==='demo'&&window.__concept.state.orientationDeg===90,null,{timeout:90000});assert.equal(await p.evaluate(()=>window.__concept.state.productId),'CHENF39031');
  await p.close();console.log('PASS mobile/deep link/share/restore',width);
 }
 const p=await b.newPage({viewport:{width:390,height:844},isMobile:true,hasTouch:true});const errors=[];p.on('pageerror',e=>errors.push(e.message));let requests=0;
 const response=JSON.parse(fs.readFileSync('review/room-understanding-v2-1/owner/final-api-private.json','utf8'));response.experimental.floor.sceneData=JSON.parse(fs.readFileSync('review/room-occlusion-v2-2/owner-photo/scene-after.json','utf8'));
 await p.route('**/health',r=>r.fulfill({json:{status:'ok',experimentalFloor:'ready'}}));await p.route('**/v1/analyze-room',async r=>{requests++;await new Promise(resolve=>setTimeout(resolve,700));await r.fulfill({json:response});});
 await p.goto(base+'/tools/product-concept.html');await p.waitForFunction(()=>window.__retailerUX&&window.__concept.adapter.connecte,null,{timeout:90000});await p.setInputFiles('#file','C:/Users/jonat/Downloads/test salon parquet.png');
 await p.waitForFunction(()=>window.__concept.state.source==='uploaded');assert.ok(await p.locator('#photo').isVisible());await p.waitForFunction(()=>window.__concept.etatProduit()==='RENDER_READY'&&window.__retailerUX.performance.snapshot().length===5,null,{timeout:90000});
 const performance=await p.evaluate(()=>window.__retailerUX.performance.snapshot());assert.ok(performance.every(x=>x.ms>=0));await p.locator('#photoMore').tap();await p.locator('#shareResultOpen').tap();assert.equal(await p.locator('#shareResultLink').count(),0);assert.match(await p.locator('#shareResult').innerText(),/photo par lien n’est pas encore disponible/);await p.locator('#shareResult .pp-close').tap();
 await p.setInputFiles('#file','C:/Users/jonat/Downloads/test salon parquet.png');await p.waitForFunction(()=>window.__concept.etatProduit()==='RENDER_READY',null,{timeout:90000});assert.equal(requests,1);assert.deepEqual(errors,[]);await p.close();
 const host=await b.newPage({viewport:{width:320,height:844}});host.on('pageerror',e=>errors.push(e.message));
 await host.route('**/tools/product-concept.html?**',async route=>{const r=await route.fetch(),headers={...r.headers()};delete headers['x-frame-options'];headers['content-security-policy']="frame-ancestors 'self'";await route.fulfill({response:r,headers});});
 await host.goto(base+'/tools/retailer-embed-demo.html');await host.waitForFunction(()=>window.PoseParquetVisualizer);await host.locator('#open').click();
 await host.waitForFunction(()=>document.getElementById('events').textContent.includes('READY'),null,{timeout:90000});const frame=host.frames().find(f=>f.url().includes('product-concept.html'));
 await frame.waitForFunction(()=>window.__retailerUX&&window.__concept.DEMO_ROOMS.length);assert.equal(await frame.evaluate(()=>window.__concept.state.productId),'CHENF39031');
 await host.evaluate(()=>window.PoseParquetVisualizer.setFavorites(['CHENF39031']));await frame.waitForFunction(()=>window.__concept.state.favourites.size===1);await frame.evaluate(()=>window.__concept.toggleFav('CHENF39031'));await host.waitForFunction(()=>document.getElementById('events').textContent.includes('FAVORITE_REMOVED'));
 await host.evaluate(()=>{const f=document.createElement('iframe');f.srcdoc='<script>parent.frames[0].postMessage({source:"pose-parquet-retailer",version:1,type:"SET_FAVORITES",payload:{favoriteIds:["CHENF39031"]}},parent.location.origin)<\/script>';document.body.append(f);});await host.waitForTimeout(150);assert.equal(await frame.evaluate(()=>window.__concept.state.favourites.size),0);
 await host.evaluate(()=>window.PoseParquetVisualizer.setProduct('NOT_A_PRODUCT'));await host.waitForFunction(()=>document.getElementById('events').textContent.includes('unsupported_or_unavailable'));
 const embed=await frame.evaluate(()=>({width:innerWidth,overflow:document.documentElement.scrollWidth>innerWidth}));assert.equal(embed.overflow,false);
 await host.screenshot({path:root+'/embed-320.png'});assert.deepEqual(errors,[]);await host.close();
 fs.writeFileSync(root+'/results.json',JSON.stringify({mobile:rows,performance,analysisRequests:requests,embed,iframeTestDeployment:'Test-only frame-ancestors self override; live server DENY unchanged',pageErrors:errors},null,2));
 console.log('PASS iframe READY, favorites sync, sibling spoof rejection, invalid product, responsive embed; photo immediately visible, cache reused, real performance marks',performance);
}finally{await b.close();}