/** Isolated original-photo lighting stages, using the renderer's prepared pixels/masks. */
import fs from 'node:fs';
import {createRequire} from 'node:module';
const {chromium}=createRequire(import.meta.url)(process.env.PPAI_PLAYWRIGHT_CORE);
const root='review/scene-understanding-v3',base=process.env.PPAI_BASE||'http://127.0.0.1:8000';
const cases=[['piece-claire',1440,900],['cuisine-ilot',1440,900],['owner-photo',1440,900],['owner-photo',390,844]];
const browser=await chromium.launch({channel:'chrome',headless:true});
try{
 const page=await browser.newPage();let source;
 await page.route('**/__v3-light-source*',r=>r.fulfill({contentType:'image/png',body:fs.readFileSync(source)}));
 await page.goto(base+'/tools/product-concept.html?dev=1&prefetch=0');
 await page.waitForFunction(()=>window.__concept?.adapter.connecte,null,{timeout:90000});
 const rows=[];
 for(const [scene,width,height]of cases){
  await page.setViewportSize({width,height});source=root+'/'+scene+'/01-original.png';
  const raw=JSON.parse(fs.readFileSync(root+'/'+scene+'/quality.json'));
  const samples=await page.evaluate(async({raw,url})=>{
   const a=window.__concept.adapter;if(!await a.openPhotoScene(raw,url))throw Error(a.refusScene);
   const d=a.diagnosticSnapshot(),photo=d.photo,ctx=photo.getContext('2d'),src=ctx.getImageData(0,0,photo.width,photo.height);
   const {buildShadingMap,buildResidualMaps}=await import('/web/scene/shading.js');
   const rows=[];
   for(let i=0;i<5;i++){
    const t=performance.now(),shading=buildShadingMap(src,d.masks.effectiveCoverage,d.scene.light),middle=performance.now();
    buildResidualMaps(src,d.masks.effectiveCoverage,shading);
    rows.push({illuminationMs:middle-t,contactAndLightResidualsMs:performance.now()-middle});
   }
   return {source:[photo.width,photo.height],runs:rows};
  },{raw,url:base+'/__v3-light-source?case='+scene+'-'+width});
  rows.push({scene,viewport:[width,height],...samples});
 }
 fs.writeFileSync(root+'/lighting-stage-benchmark.json',JSON.stringify({method:'Isolated real estimator functions on prepared original-photo pixels and visibility masks; residuals include contact shadows, highlights and mid-light. Not upload-to-render latency.',cases:rows},null,2));
 console.log('PASS lighting stage profile: 4 cases x 5 runs');
}finally{await browser.close();}
