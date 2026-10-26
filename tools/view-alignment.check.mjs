import fs from'node:fs';import assert from'node:assert/strict';import{execFileSync}from'node:child_process';import{createRequire}from'node:module';
const{chromium}=createRequire(import.meta.url)(process.env.PPAI_PLAYWRIGHT_CORE);const base=process.env.PPAI_BASE||'http://127.0.0.1:8000',root='review/floor-projection-v3';
const before=execFileSync('git',['show','2600cc8:tools/product-concept.html'],{maxBuffer:2e6});const browser=await chromium.launch({channel:'chrome',headless:true});const results=[];
try{for(const width of[1440,390])for(const variant of['before','after']){
 const p=await browser.newPage({viewport:{width,height:844},isMobile:width===390,hasTouch:width===390});const errors=[];p.on('pageerror',e=>errors.push(e.message));
 if(variant==='before')await p.route('**/tools/product-concept.html*',r=>r.fulfill({contentType:'text/html',body:before}));
 await p.goto(base+'/tools/product-concept.html?prefetch=0');await p.waitForFunction(()=>window.__concept?.adapter.connecte,null,{timeout:90000});
 for(const id of['premibel-piano','premibel-salon','terrasse-mer']){
 await p.evaluate(id=>{const c=window.__concept;c.enter();c.openRoom(id);},id);
 await p.waitForFunction(id=>{const c=window.__concept,im=document.getElementById('photo');return c.adapter.scene===id&&c.state.applied.source==='live'&&im.complete&&im.naturalWidth;},id,{timeout:90000});
 await p.evaluate(()=>{const c=window.__concept;c.closeAll();c.fitToView(false);c.applyTransform();});
 const r=await p.evaluate(()=>{const c=window.__concept,im=document.getElementById('photo'),sz=c.sceneSize(),s=c.adapter.visitSnapshot();const rects=['vpPhoto','vpA','vpEdit'].map(id=>{const el=document.getElementById(id),r=el.getBoundingClientRect();return {id,width:r.width,height:r.height,transform:el.style.transform};});return {size:sz,photo:{width:im.naturalWidth,height:im.naturalHeight},rects,scene:JSON.stringify(s.scene),overflow:document.documentElement.scrollWidth>innerWidth};});
 if(variant==='after'){assert.ok(Math.abs(r.size.w/r.size.h-r.photo.width/r.photo.height)<1e-6);assert.equal(new Set(r.rects.map(x=>x.transform)).size,1);assert.equal(r.overflow,false);assert.equal(await p.locator('#wallPaintOpen').count(),0);}
 await p.screenshot({path:`${root}/${id}/07-viewport-${variant}-${width}.png`});results.push({id,width,variant,...r});console.log('PASS viewport',id,width,variant);
 }
 assert.deepEqual(errors,[]);await p.close();
}}finally{await browser.close();fs.writeFileSync(root+'/viewport-matrix.json',JSON.stringify(results,null,2));}
