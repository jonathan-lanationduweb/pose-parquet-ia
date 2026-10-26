/** Actual default URL, stable photo/render registration through four viewports. */
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const {chromium}=createRequire(import.meta.url)(process.env.PPAI_PLAYWRIGHT_CORE);
const browser=await chromium.launch({channel:'chrome',headless:true});
const root='review/floor-projection-metric';
fs.mkdirSync(root,{recursive:true});
try{
 const page=await browser.newPage({viewport:{width:1440,height:900}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto((process.env.PPAI_BASE||'http://127.0.0.1:8000')+'/tools/product-concept.html?prefetch=0');
 await page.waitForFunction(()=>window.__concept?.adapter.connecte,null,{timeout:90000});
 await page.evaluate(()=>window.__concept.openRoom('piece-claire'));
 await page.waitForFunction(()=>window.__concept.etatApplication()==='rendered'&&!window.__concept.state.applying,null,{timeout:90000});
 const signature=await page.evaluate(()=>JSON.stringify(window.__concept.adapter.visitSnapshot().scene.floorZones.map(z=>z.plane.projection)));
 const frame=await page.locator('#after').evaluate(c=>c.toDataURL());
 const rows=[];
 for(const [width,height]of[[1440,900],[390,844],[844,390],[900,1440]]){
  await page.setViewportSize({width,height});
  await page.waitForTimeout(400);
  const row=await page.evaluate(()=>{
   const c=window.__concept,photo=document.getElementById('photo'),a=document.getElementById('after');
   const transforms=['vpPhoto','vpA'].map(id=>{const e=document.getElementById(id),r=e.getBoundingClientRect();return {transform:getComputedStyle(e).transform,x:r.x,y:r.y,width:r.width,height:r.height};});
   const mask=c.adapter.visitSnapshot().masks,r=photo.getBoundingClientRect(),card=document.getElementById('card').getBoundingClientRect();let visibleFloorSamples=0;
   for(let v=.5;v<1;v+=.025)for(let u=0;u<1;u+=.025){const x=r.x+u*r.width,y=r.y+v*r.height,index=Math.floor(v*mask.height)*mask.width+Math.floor(u*mask.width);if(mask.effectiveCoverage[index]>200&&x>4&&x<innerWidth-4&&y>130&&y<card.top-4)visibleFloorSamples++;}
   return {visibleFloorSamples,width:innerWidth,height:innerHeight,geometryVersion:c.adapter.visitSnapshot().scene.geometryVersion,signature:JSON.stringify(c.adapter.visitSnapshot().scene.floorZones.map(z=>z.plane.projection)),transforms,photo:[photo.naturalWidth,photo.naturalHeight],render:[a.width,a.height],overflow:document.documentElement.scrollWidth>innerWidth,status:c.adapter.geometryValidation.decision};
  });
  assert.equal(row.geometryVersion,'floor-projection-metric@1');assert.equal(row.signature,signature);
  assert.deepEqual(row.transforms[0],row.transforms[1]);assert.ok(Math.abs(row.photo[0]*row.render[1]/row.render[0]-row.photo[1])<.5,'Source thumbnail and render aspect differ by more than half a source pixel');
  assert.equal(await page.locator('#after').evaluate(c=>c.toDataURL()),frame);
  assert.ok(row.visibleFloorSamples>0,'Floor is hidden by viewport crop or dock');assert.equal(row.overflow,false);assert.equal(row.status,'AUTO_RENDER');
  await page.screenshot({path:root+'/default-'+width+'x'+height+'.png'});
  delete row.signature;rows.push(row);
 }
 assert.deepEqual(errors,[]);fs.writeFileSync(root+'/default-viewports.json',JSON.stringify(rows,null,2));
 console.log('PASS default metric renderer: identical frame, camera, photo/canvas registration in desktop/mobile portrait/landscape; no overflow or page errors');
}finally{await browser.close();}