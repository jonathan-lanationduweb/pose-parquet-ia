import fs from 'node:fs';import assert from 'node:assert/strict';import {createRequire} from 'node:module';
const {chromium}=createRequire(import.meta.url)(process.env.PPAI_PLAYWRIGHT_CORE);
const browser=await chromium.launch({channel:'chrome',headless:true});
try{
 const p=await browser.newPage({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
 await p.goto('http://127.0.0.1:8000/tools/product-concept.html?prefetch=0');await p.waitForFunction(()=>window.__concept?.adapter.connecte);
 await p.setInputFiles('#file','C:/Users/jonat/Downloads/test salon parquet.png');await p.waitForFunction(()=>window.__concept.etatProduit()==='RENDER_READY',null,{timeout:120000});
 const screenshots='review/current-fixes/salon-reconciled';fs.mkdirSync(screenshots,{recursive:true});
 await p.locator('#photoMore').tap();await p.getByRole('button',{name:'Ajuster le sol',exact:true}).tap();await p.waitForFunction(()=>window.__concept.floorEdit.actif);
 await p.locator('#floorTools [data-size="6"]').tap();
 const point=await p.evaluate(()=>{const c=window.__concept,r=document.getElementById('floorEdit').getBoundingClientRect();return{x:r.x+r.width*620/1536,y:r.y+r.height*453/1024};});
 assert.ok(point.x>=0&&point.x<390&&point.y>60&&point.y<700,`Target outside phone: ${JSON.stringify(point)}`);
 const value=()=>p.evaluate(()=>{const s=window.__concept.adapter.visitSnapshot(),m=s.masks,i=Math.floor(453*m.height/1024)*m.width+Math.floor(620*m.width/1536);return{floor:m.coverage[i],object:m.occlusion?.[i]||0};});
 const before=await value();await p.touchscreen.tap(point.x,point.y);const painted=await value();assert.ok(painted.floor>250&&painted.object<3,`Correction blocked ${JSON.stringify(painted)}`);
 await p.locator('#floorUndo').tap();assert.deepEqual(await value(),before);await p.touchscreen.tap(point.x,point.y);await p.locator('#floorDone').tap();await p.waitForFunction(()=>!window.__concept.state.applying&&window.__concept.state.applied.key===window.__concept.appliedKey());
 for(const width of [320,390,430]){
  await p.setViewportSize({width,height:844});await p.waitForTimeout(150);
  for(const name of ['Choisir un parquet','Personnaliser']){const b=await p.locator('#card').getByRole('button',{name,exact:true}).boundingBox();assert.ok(b&&b.x>=0&&b.x+b.width<=width+1&&b.y+b.height<=844,`${width}: ${name} clipped`);}
  await p.locator('#card [data-open="cat"]').tap();await p.waitForTimeout(150);
  assert.ok(await p.locator('#catSheet').isVisible());const sheet=await p.locator('#catSheet').boundingBox();assert.ok(sheet.x>=0&&sheet.x+sheet.width<=width+1&&sheet.y>=54&&sheet.y+sheet.height<=845,`${width} catalogue clipped ${JSON.stringify(sheet)}`);
  await p.evaluate(()=>window.__concept.closeAll());await p.locator('#card [data-open="cus"]').tap();await p.waitForTimeout(150);assert.ok(await p.locator('#cusSheet').isVisible());await p.evaluate(()=>window.__concept.closeAll());
  await p.screenshot({path:`${screenshots}/mobile-${width}.jpg`,type:'jpeg',quality:90});console.log(`PASS ${width}px: imported salon, catalogue and customization accessible`);
 }
 console.log('PASS actual photo: touch Add corrects under TV, Undo restores original protection');
}finally{await browser.close();}
