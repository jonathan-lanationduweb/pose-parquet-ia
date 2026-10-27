import assert from'node:assert/strict';import{createRequire}from'node:module';import fs from'node:fs';
const{chromium}=createRequire(import.meta.url)(process.env.PPAI_PLAYWRIGHT_CORE),browser=await chromium.launch({channel:'chrome',headless:true});const rows=[];
try{for(const canvas of[false,true]){
 const p=await browser.newPage({viewport:{width:390,height:844}});
 if(canvas)await p.addInitScript(()=>{const get=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(t,...a){return /webgl/.test(t)?null:get.call(this,t,...a)}});
 await p.goto('http://127.0.0.1:8000/tools/product-concept.html?dev=1&prefetch=0');await p.waitForFunction(()=>window.__concept?.adapter.connecte,null,{timeout:90000});
 rows.push(await p.evaluate(async()=>{const c=window.__concept;await c.adapter.openRoom('piece-claire');const profile=c.PREMIBEL_DEMO_PRODUCTS.find(p=>p.id==='BTRPF39009').renderProfile;
 const normal=await c.adapter.applyProfile(profile,0),saved=normal.toDataURL(),s=c.adapter.diagnosticSnapshot(),geometry=JSON.stringify(s.scene.floorZones.map(z=>z.plane.projection)),coverage=Array.from(s.masks.effectiveCoverage);
 const neutral=await c.adapter.diagnosticNeutralFrame();if(!neutral)throw Error('missing neutral');const data=neutral.getContext('2d').getImageData(0,0,neutral.width,neutral.height).data,src=s.photo.getContext('2d').getImageData(0,0,s.size.width,s.size.height).data;
 let floor=0,protectedPixels=0;
 for(let i=0;i<coverage.length;i+=41){if(coverage[i]===0){for(let k=0;k<3;k++)if(Math.abs(data[i*4+k]-src[i*4+k])>2)throw Error('neutral repainted foreground');protectedPixels++;}else if(coverage[i]>250)floor++;}
 const again=await c.adapter.applyProfile(profile,0);
 if(again.toDataURL()!==saved)throw Error('neutral changed normal rendering');
 if(JSON.stringify(c.adapter.diagnosticSnapshot().scene.floorZones.map(z=>z.plane.projection))!==geometry)throw Error('neutral changed camera');
 if(coverage.some((v,i)=>v!==s.masks.effectiveCoverage[i]))throw Error('neutral changed mask');
 return{backend:c.adapter.moteur.backend,floor,protectedPixels,geometryPreserved:true,normalPreserved:true};
 }));await p.close();
}
fs.writeFileSync('review/visual-quality-s1-s8/neutral-tests.json',JSON.stringify(rows,null,2));console.log('PASS real neutral floor WebGL/Canvas: unchanged geometry, masks, foreground, normal frame',rows);
}finally{await browser.close();}
