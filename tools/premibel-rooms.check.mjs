import fs from 'node:fs';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const {chromium}=createRequire(import.meta.url)(process.env.PPAI_PLAYWRIGHT_CORE);
const browser=await chromium.launch({channel:'chrome',headless:true});const manifest=JSON.parse(fs.readFileSync('web/data/rooms.json','utf8'));
const ids=manifest.scenes.filter(s=>['premibel-salon','premibel-piano','premibel-entree','premibel-chambre'].includes(s.id)).map(s=>s.id);
assert.equal(ids.length,4);assert.equal(manifest.scenes.filter(s=>s.source.kind==='pexels'&&s.renderReady&&s.availableForGallery&&s.calibration.status==='validated').length>=11,true);
const out='review/premibel-room-pilot/gallery';fs.mkdirSync(out,{recursive:true});
try{for(const width of JSON.parse(process.env.PPAI_ROOM_WIDTHS||'[390,1440]')){
 const p=await browser.newPage({viewport:{width,height:900},isMobile:width<700,hasTouch:width<700});const errors=[];let analysis=0;p.on('pageerror',e=>errors.push(e.message));p.on('request',r=>{if(r.url().includes('/v1/analyze-room'))analysis++;});
 await p.goto('http://127.0.0.1:8000/tools/product-concept.html?prefetch=0');await p.waitForFunction(()=>window.__concept?.adapter.connecte&&window.__concept.DEMO_ROOMS.length>=15,null,{timeout:90000});
 assert.equal(await p.locator('#quickRooms [data-cat="premibel"]').count(),0);
 for(const id of ids){const category=manifest.scenes.find(s=>s.id===id).category;await p.locator(`#quickRooms [data-cat="${category}"]`).click();assert.ok(await p.locator(`#quickRooms [data-room="${id}"]`).isVisible());await p.locator('#homeCategories [data-cat-back]').click();}
 for(const id of ids){
  await p.locator(`#quickRooms [data-cat="${manifest.scenes.find(s=>s.id===id).category}"]`).click();await p.locator(`#quickRooms [data-room="${id}"]`).click();await p.waitForFunction(id=>{const c=window.__concept;return c.state.roomId===id&&!c.state.applying&&c.state.applied.source==='live'&&c.state.applied.key===c.appliedKey();},id,{timeout:90000});
  for(const product of ['CHENF39031','BTRPF39009']){await p.evaluate(product=>window.__concept.select(product,true),product);await p.waitForFunction(()=>{const c=window.__concept;return !c.state.applying&&c.state.applied.key===c.appliedKey();},null,{timeout:90000});}
  assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'Horizontal overflow');
  if(width<700){const b=await p.locator('#card').boundingBox();assert.ok(b.y+b.height<=901&&b.x>=0&&b.x+b.width<=width+1);}
  if(id==='premibel-chambre'){const protection=await p.evaluate(()=>{const s=window.__concept.adapter.visitSnapshot(),m=s.masks;return [[690,590],[320,340]].map(([x,y])=>m.occlusion[Math.floor(y*m.height/1029)*m.width+Math.floor(x*m.width/900)]);});assert.ok(protection.every(v=>v>240),'Cushion or blanket painted over');}
  await p.screenshot({path:`${out}/${width}-${id}.jpg`,type:'jpeg',quality:90});await p.evaluate(()=>window.__sessionRooms.home());await p.locator('#homeCategories [data-cat-back]').click();
 }
 assert.equal(analysis,0,'Gallery must not reanalyse precomputed rooms');assert.deepEqual(errors,[]);console.log(`PASS ${width}px: 4 Premibel rooms, original 11 Pexels retained, 2 parquet patterns, no reanalysis`);await p.close();
}}finally{await browser.close();}
