import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const {chromium}=createRequire(import.meta.url)(process.env.PPAI_PLAYWRIGHT_CORE);
const base=process.env.PPAI_UI_BASE||'http://127.0.0.1:8000';
const browser=await chromium.launch({channel:'chrome',headless:true,args:['--host-resolver-rules=MAP parquet.test 127.0.0.1','--no-proxy-server']});
fs.mkdirSync('review/qr-comparison',{recursive:true});
try {
 for(const width of [320,390,1440]) {
  const p=await browser.newPage({viewport:{width,height:900},isMobile:width<700,hasTouch:width<700});const errors=[];p.on('pageerror',e=>errors.push(e.message));
  await p.goto(`${base}/tools/product-concept.html?prefetch=0`);await p.waitForFunction(()=>window.__comparisonView&&window.__catalogBrowser&&window.__concept.adapter.connecte,null,{timeout:90000});
  await p.evaluate(()=>window.__concept.openRoom('sejour'));await p.waitForFunction(()=>!window.__concept.state.applying&&window.__concept.state.applied.source==='live',null,{timeout:90000});
  await p.evaluate(()=>window.__concept.select('CHENF39031',true));await p.waitForFunction(()=>!window.__concept.state.applying&&window.__concept.state.applied.key===window.__concept.appliedKey());
  await p.locator('#cmpBtn').click();await p.locator('#prods .pd[data-id="BTRPF39009"]').click();
  await p.waitForFunction(()=>window.__concept.state.compare?.b==='BTRPF39009'&&window.__concept.state.appliedB.source==='live'&&!window.__concept.state.applying,null,{timeout:90000});
  const viewport=await p.evaluate(()=>({...window.__concept.state.vp}));
  const bounds=await p.locator('#stage').boundingBox();const handle=await p.locator('#split').boundingBox();
  await p.mouse.move(handle.x+handle.width/2,handle.y+handle.height*.45);await p.mouse.down();await p.mouse.move(bounds.x+bounds.width*.72,handle.y+handle.height*.45,{steps:10});await p.mouse.up();
  const split=await p.evaluate(()=>window.__concept.state.split);assert.ok(split>.65&&split<.8,`Divider did not move: ${split}`);assert.deepEqual(await p.evaluate(()=>({...window.__concept.state.vp})),viewport,'Divider panned room');
  await p.locator('#split').focus();await p.keyboard.press('ArrowLeft');assert.ok(await p.evaluate(()=>window.__concept.state.split)<split);
  await p.locator('#compareSideBySide').click();assert.ok(await p.locator('#comparisonSides').isVisible());
  const renders=await p.evaluate(()=>['A','B'].map(s=>{const n=document.getElementById('comparisonCanvas'+s);return{w:n.width,h:n.height,data:n.toDataURL()};}));assert.ok(renders.every(x=>x.w>100&&x.h>100));assert.notEqual(renders[0].data,renders[1].data,'Both sides show same parquet');
  for(const id of ['compareSideBySide','compareSlider','compareClose']){const box=await p.locator('#'+id).boundingBox();assert.ok(box.x>=0&&box.x+box.width<=width+1,`${width} comparison actions clipped`);}
  await p.screenshot({path:`review/qr-comparison/${width}-side.jpg`,type:'jpeg',quality:88});
  await p.locator('#compareSlider').click();assert.ok(await p.locator('#split').isVisible());await p.screenshot({path:`review/qr-comparison/${width}-slider.jpg`,type:'jpeg',quality:88});
  await p.locator('#compareClose').click();assert.equal(await p.evaluate(()=>window.__concept.state.compare),null);
  await p.locator('#baBtn').click();await p.locator('#compareSideBySide').click();assert.equal(await p.locator('#comparisonSides h3').first().textContent(),'Avant');assert.equal(await p.locator('#comparisonSides h3').last().textContent(),'Après');
  await p.locator('#compareClose').click();assert.equal(await p.evaluate(()=>window.__concept.state.ba),false);
  assert.deepEqual(errors,[]);console.log(`PASS ${width}px: distinct A/B, draggable and keyboard divider, full side-by-side, before/after, close`);await p.close();
 }
 // Two isolated browser contexts stand for the PC and phone. The .test host resolves only to loopback.
 const pcContext=await browser.newContext({viewport:{width:1440,height:900}}),phoneContext=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
 const pc=await pcContext.newPage(),phone=await phoneContext.newPage(),origin=base.replace('127.0.0.1','parquet.test');
 const errors=[];pc.on('pageerror',e=>errors.push(e.message));phone.on('pageerror',e=>errors.push(e.message));
 await pc.route('**/v1/analyze-room',route=>route.fulfill({status:503,contentType:'application/json',body:'{"detail":"Analyse non lancée pendant le test du transfert"}'}));
 let transfer=null;pc.on('response',async r=>{if(r.request().method()==='POST'&&r.url().endsWith('/v1/photo-transfers'))transfer=await r.json();});
 await pc.goto(`${origin}/tools/product-concept.html?prefetch=0`);await pc.locator('#transferQr').waitFor({state:'visible'});assert.ok(transfer?.phoneUrl);assert.equal(await pc.locator('#transferLink').getAttribute('href'),transfer.phoneUrl);assert.ok((await pc.locator('#transferLink').innerText()).includes(new URL(transfer.phoneUrl).hostname));
 const left=await pc.locator('#doorImport').boundingBox(),right=await pc.locator('#phoneImport').boundingBox();assert.ok(right.x>=left.x+left.width-1&&Math.abs(left.y-right.y)<2,'QR not beside photo import');
 await pc.locator('#transferQr').screenshot({path:'review/qr-comparison/qr.png'});fs.writeFileSync('review/qr-comparison/phone-url.txt',transfer.phoneUrl);
 await pc.screenshot({path:'review/qr-comparison/desktop-qr.jpg',type:'jpeg',quality:88});
 await phone.goto(transfer.phoneUrl);await phone.setInputFiles('#phonePhoto','web/assets/images/room-premibel-salon.jpg');await phone.locator('#phoneSend').waitFor({state:'visible'});await phone.screenshot({path:'review/qr-comparison/phone-preview.jpg',type:'jpeg',quality:88});await phone.locator('#phoneSend').click();await phone.getByRole('status').filter({hasText:'Photo envoyée'}).waitFor();
 await pc.waitForFunction(()=>window.__concept.state.source==='uploaded'&&window.__concept.state.uploaded?.name==='photo-telephone.jpg',null,{timeout:15000});
 await pc.waitForFunction(()=>!document.getElementById('phoneTransfer').open);
 assert.ok(await pc.locator('#entry').evaluate(n=>n.classList.contains('hidden')));
 const deleted=await pc.request.get(`${base}/v1/photo-transfers/${transfer.id}`,{headers:{'X-Transfer-Key':transfer.ownerKey}});assert.equal(deleted.status(),404,'Received photo retained on server');
 assert.deepEqual(errors,[]);console.log('PASS QR: phone preview, send without login, PC receives automatically, server photo deleted');
 await phoneContext.close();await pcContext.close();
}finally{await browser.close();}
