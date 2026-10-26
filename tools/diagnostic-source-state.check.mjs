import fs from'node:fs';import assert from'node:assert/strict';import{createRequire}from'node:module';
const{chromium}=createRequire(import.meta.url)(process.env.PPAI_PLAYWRIGHT_CORE),browser=await chromium.launch({channel:'chrome',headless:true});
try{const page=await browser.newPage();await page.route('**/v1/analyze-room',r=>r.fulfill({status:503,json:{detail:'Analysis disabled for source-transition test'}}));
await page.goto('http://127.0.0.1:8000/tools/product-concept.html?dev=1&prefetch=0');await page.waitForFunction(()=>window.__concept?.adapter.connecte&&window.__visualDiagnostics,null,{timeout:90000});
await page.evaluate(()=>window.__concept.openRoom('piece-claire'));await page.waitForFunction(()=>window.__concept.etatApplication()==='rendered'&&!window.__concept.state.applying,null,{timeout:90000});
await page.evaluate(()=>{window.__sourceCameraSignature=JSON.stringify(window.__concept.adapter.diagnosticSnapshot().scene.floorZones.map(z=>z.plane.projection));window.__visualDiagnostics.setFlags({debugMasks:true});});
await page.setInputFiles('#file',{name:'next-photo.jpg',mimeType:'image/jpeg',buffer:fs.readFileSync(new URL('../web/assets/images/room-chambre.jpg',import.meta.url))});
await page.waitForFunction(()=>window.__concept.state.source==='uploaded'&&window.__concept.state.uploaded,null,{timeout:10000});
const result=await page.evaluate(()=>{window.__visualDiagnostics.draw();let refused=false;try{window.__visualDiagnostics.capture(['debugMasks']);}catch{refused=true;}return{cameraUnchanged:JSON.stringify(window.__concept.adapter.diagnosticSnapshot().scene.floorZones.map(z=>z.plane.projection))===window.__sourceCameraSignature,refused,hidden:document.getElementById('visualDebugOverlay').style.display==='none',engineScene:window.__concept.adapter.scene,currentScene:window.__concept.room().id};});
console.log(JSON.stringify(result));assert.ok(result.cameraUnchanged);assert.ok(result.refused&&result.hidden,'Old scene overlay/capture leaked onto the newly imported photo');console.log('PASS source transition: old renderer scene cannot annotate or export a newly imported photo');
}finally{await browser.close();}
