/** Reviewed catalogue scenes: real renderer, desktop/mobile and label regression. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {createRequire} from 'node:module';
const {chromium}=createRequire(import.meta.url)(process.env.PPAI_PLAYWRIGHT_CORE);
const cases=[['cuisine-ilot','POINF36005'],['cuisine-blanche','POINF36005'],['terrasse-mer','VLAME16012'],['couloir-enfilade','BTRPF39009'],['premibel-entree','BTRPF39009'],['salle-a-manger-meublee','BTRPF39009'],['bureau-meuble','BTRPF39009'],['premibel-chambre','BTRPF39009']];
const browser=await chromium.launch({channel:'chrome',headless:true});
const rows=[];
try{
 for(const width of [1440,390]){
  const page=await browser.newPage({viewport:{width,height:width===390?844:900},isMobile:width===390,hasTouch:width===390});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:8000/tools/product-concept.html?dev=1&prefetch=0');
  await page.waitForFunction(()=>window.__concept?.adapter.connecte,null,{timeout:90000});
  for(const[id,product]of cases){
   const row=await page.evaluate(async({id,product})=>{
    const c=window.__concept,t=performance.now();
    if(!await c.adapter.openRoom(id))throw Error('Open failed: '+id);
    c.state.productId=product;
    const profile=c.PREMIBEL_DEMO_PRODUCTS.find(p=>p.id===product).renderProfile;
    const frame=await c.adapter.applyProfile(profile,0);
    if(!frame)throw Error('Rendering blocked: '+id+' '+JSON.stringify(c.adapter.geometryValidation));
    c.paintCard();
    const d=c.adapter.diagnosticSnapshot();
    return {id,width:innerWidth,elapsedMs:performance.now()-t,summary:document.getElementById('card').innerText,
     geometry:d.scene.floorZones.map(z=>({projection:z.plane.projection,planeRef:z.planeRef})),
     overflow:document.documentElement.scrollWidth>innerWidth};
   },{id,product});
   assert.ok(!row.summary.includes('undefined'),id+' undefined product label');
   assert.ok(!row.overflow,id+' horizontal overflow');
   assert.ok(row.geometry.length>0);rows.push(row);
  }
  assert.deepEqual(errors,[]);await page.close();
 }
 fs.mkdirSync('review/eight-scene-review',{recursive:true});
 fs.writeFileSync('review/eight-scene-review/runtime.json',JSON.stringify(rows,null,2));
 console.log(JSON.stringify(rows.map(({id,width,elapsedMs,summary})=>({id,width,elapsedMs:Math.round(elapsedMs),summary:summary.slice(0,100)})),null,2));
}finally{await browser.close();}
