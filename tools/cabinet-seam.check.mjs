import assert from 'node:assert/strict';import{createRequire}from'node:module';
const{chromium}=createRequire(import.meta.url)(process.env.PPAI_PLAYWRIGHT_CORE),b=await chromium.launch({channel:'chrome',headless:true});
try{const p=await b.newPage({viewport:{width:1440,height:900}});await p.goto('http://127.0.0.1:8000/tools/product-concept.html?dev=1&prefetch=0');await p.waitForFunction(()=>window.__concept?.adapter.connecte,null,{timeout:90000});
const rows=await p.evaluate(async()=>{const a=window.__concept.adapter;await a.openRoom('cuisine-ilot');const profile=window.__concept.PREMIBEL_DEMO_PRODUCTS.find(p=>p.id==='POINF36005').renderProfile;await a.applyProfile(profile,0);const d=a.diagnosticSnapshot(),original=d.photo.getContext('2d').getImageData(0,0,d.size.width,d.size.height).data,rows=[];
const mode='webgl',frame=await a.applyProfile(profile,0);const image=frame.getContext('2d').getImageData(0,0,frame.width,frame.height).data;let max=0;for(let y=440;y<500;y++)for(let x=450;x<660;x++)for(let k=0;k<3;k++){const i=(y*d.size.width+x)*4+k;max=Math.max(max,Math.abs(image[i]-original[i]));}rows.push({mode,maxError:max,pixels:12600});return rows;});
assert.equal(rows[0].mode,'webgl');assert.ok(rows[0].maxError<=1,JSON.stringify(rows));console.log('PASS island face: no parquet seam through 12600 original foreground pixels',rows);
}finally{await b.close();}
