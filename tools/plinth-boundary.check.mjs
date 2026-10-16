import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const {chromium}=createRequire(import.meta.url)(process.env.PPAI_PLAYWRIGHT_CORE);
const browser=await chromium.launch({channel:'chrome',headless:true});
const plinth=[[120,737],[180,728],[300,709],[350,702],[400,691],[480,680],[850,749]];
const floor=[[120,770],[180,756],[300,740],[350,733],[400,725],[480,712],[850,795]];
try {for (const cpu of [false,true]) {
 const page=await browser.newPage({viewport:{width:1440,height:900}});
 if(cpu)await page.addInitScript(()=>{const get=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(type,...args){return /webgl/.test(type)?null:get.call(this,type,...args);};});
 await page.goto('http://127.0.0.1:8000/tools/product-concept.html?prefetch=0');await page.waitForFunction(()=>window.__concept?.adapter.connecte);
 await page.evaluate(()=>window.__concept.openRoom('piece-claire'));
 for(const product of ['BTRPF39009','CHENF39031'])for(const angle of [0,45,90]) {
  await page.evaluate(({product,angle})=>{const c=window.__concept;c.select(product,true);c.setOrientation(angle,false);},{product,angle});
  await page.waitForFunction(()=>{const c=window.__concept;return c.state.roomId==='piece-claire'&&!c.state.applying&&c.state.applied.source==='live'&&c.state.applied.key===c.appliedKey();},null,{timeout:90000});
  const values=await page.evaluate(({plinth,floor})=>{const s=window.__concept.adapter.visitSnapshot(),m=s.masks;const read=([x,y])=>m.coverage[Math.floor(y*m.height/1067)*m.width+Math.floor(x*m.width/1600)];return {plinth:plinth.map(read),floor:floor.map(read)};},{plinth,floor});
  assert.ok(values.plinth.every(v=>v===0),`Plinth painted: ${JSON.stringify({cpu,product,angle,values})}`);
  assert.ok(values.floor.every(v=>v>250),`Floor missing: ${JSON.stringify({cpu,product,angle,values})}`);
 }
 const frame=await page.evaluate(()=>document.getElementById('after').toDataURL('image/jpeg',.96));fs.writeFileSync(`review/current-fixes/plinth-${cpu?'canvas':'gpu'}.jpg`,Buffer.from(frame.split(',')[1],'base64'));
 console.log(`PASS ${cpu?'Canvas':'WebGL'}: plinth protected and floor covered, two products, three orientations`);await page.close();
}}finally {await browser.close();}
