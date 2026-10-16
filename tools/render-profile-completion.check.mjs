import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const {chromium}=createRequire(import.meta.url)(process.env.PPAI_PLAYWRIGHT_CORE);
const browser=await chromium.launch({channel:'chrome',headless:true});
try {
 const p=await browser.newPage({viewport:{width:1200,height:800}});
 await p.goto('http://127.0.0.1:8000/tools/product-concept.html?prefetch=0');
 await p.waitForFunction(()=>window.__concept?.adapter.connecte,null,{timeout:90000});
 await p.evaluate(()=>window.__concept.openRoom('chambre-parisienne'));
 await p.waitForFunction(()=>!window.__concept.state.applying&&window.__concept.state.applied.source==='live',null,{timeout:90000});
 const raw=JSON.parse(fs.readFileSync('web/data/scenes/chambre-parisienne.json','utf8'));
 const result=await p.evaluate(async raw=>{
   const c=window.__concept;
   const {createLocalRenderer}=await import('/web/product/local-renderer.js');
   const r=await createLocalRenderer({base:'/web/'});
   await r.openScene(raw,`/web/assets/images/${raw.image.file}`,'chambre-parisienne');
   const profiles=[{materialFamily:'chene-naturel',pattern:'lames',widthM:.19,lengthM:1.9,scale:1},{materialFamily:'ipe-terrasse',pattern:'lames',widthM:.14,lengthM:2,scale:1},{materialFamily:'chene-fume',pattern:'point-de-hongrie',widthM:.09,lengthM:.6,scale:1}];
   const pixels=n=>{const t=document.createElement('canvas');t.width=n.width;t.height=n.height;t.getContext('2d').drawImage(n,0,0);return t.getContext('2d').getImageData(0,0,t.width,t.height).data;};
   const comparisons=[];
   for(const profile of profiles){
     const actual=await c.adapter.applyProfile(profile,13);
     r.selectMaterial(profile.materialFamily);r.setPattern(profile.pattern);r.setWidth(profile.widthM);r.setPlankLength(profile.lengthM);r.setScale(1);r.setAngle(13);await r.rendre();
     const a=pixels(actual),b=pixels(r.canvas);let delta=0;for(let i=0;i<a.length;i++)delta+=Math.abs(a[i]-b[i]);
     comparisons.push({material:profile.materialFamily,meanDelta:delta/a.length});
   }
   return comparisons;
 },raw);
 for(const row of result)assert.ok(row.meanDelta<.1,JSON.stringify(row));
 console.log('PASS: each cold material matches an independently completed renderer',result);
} finally {await browser.close();}