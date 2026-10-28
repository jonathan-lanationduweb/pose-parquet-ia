/** Repeated JSON mask transport decode; actual upload probes are in browser.json. */
import fs from 'node:fs';
import {createRequire} from 'node:module';
const {chromium}=createRequire(import.meta.url)(process.env.PPAI_PLAYWRIGHT_CORE);
const root=process.env.PPAI_FOREGROUND_REVIEW_ROOT||'review/foreground-mask-v5',browser=await chromium.launch({channel:'chrome',headless:true});
try{
 const page=await browser.newPage();await page.goto('http://127.0.0.1:8000/tools/product-concept.html?prefetch=0');
 const rows=[];
 for(const row of JSON.parse(fs.readFileSync(root+'/matrix.json'))){
  const rawText=fs.readFileSync(root+'/'+row.scene+'/after.json','utf8');
  const times=await page.evaluate(rawText=>{const samples=[];for(let i=0;i<5;i++){const t=performance.now(),raw=JSON.parse(rawText);if(!raw.occluders||!raw.floorZones)throw Error('Transport lost masks');samples.push(performance.now()-t);}return samples;},rawText);
  rows.push({scene:row.scene,decodeJsonMs:times,bytes:Buffer.byteLength(rawText)});
 }
 await page.route('**/__v5-raster-source',r=>r.fulfill({contentType:'image/png',body:fs.readFileSync(root+'/sofa/01-original.png')}));
 const rawText=fs.readFileSync(root+'/sofa/after.json','utf8');
 const raster=await page.evaluate(async rawText=>{
   const {createSceneMasks}=await import('/web/scene/mask.js');
   const scene=JSON.parse(rawText),image=new Image();image.src='/__v5-raster-source';await image.decode();
   const canvas=document.createElement('canvas');canvas.width=image.naturalWidth;canvas.height=image.naturalHeight;
   const ctx=canvas.getContext('2d',{willReadFrequently:true});ctx.drawImage(image,0,0);const source=ctx.getImageData(0,0,canvas.width,canvas.height);
   const times=[];for(let i=0;i<5;i++){const start=performance.now();const m=createSceneMasks(scene,canvas.width,canvas.height,source);if(m.occlusion.length!==canvas.width*canvas.height)throw Error('Raster lost source dimensions');times.push(performance.now()-start);}
   return {method:'createSceneMasks + forced occlusion raster/alpha, original source pixels, not JSON parse',size:[canvas.width,canvas.height],times};
 },rawText);
 fs.writeFileSync(root+'/mask-raster.json',JSON.stringify(raster,null,2));
 fs.writeFileSync(root+'/mask-decode.json',JSON.stringify(rows,null,2));console.log('PASS foreground mask JSON decode, 9 scenes × 5');
}finally{await browser.close();}
