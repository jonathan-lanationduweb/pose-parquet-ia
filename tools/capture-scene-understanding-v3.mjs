/** Reuse the real renderer/diagnostic layers; never substitute a static frame. */
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
const {chromium}=createRequire(import.meta.url)(process.env.PPAI_PLAYWRIGHT_CORE);
const base=process.env.PPAI_BASE||'http://127.0.0.1:8000';
const root=process.env.PPAI_V3_REVIEW_DIR||'review/scene-understanding-v3';
const matrix=JSON.parse(fs.readFileSync(root+'/matrix.json'));
const browser=await chromium.launch({channel:'chrome',headless:true});
try{
 const page=await browser.newPage({viewport:{width:1440,height:900}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 let source;
 await page.route('**/__v3-original*',r=>r.fulfill({contentType:'image/png',body:fs.readFileSync(source)}));
 await page.goto(base+'/tools/product-concept.html?dev=1&prefetch=0');
 await page.waitForFunction(()=>window.__concept?.adapter.connecte&&window.__visualDiagnostics,null,{timeout:90000});
 for(const row of matrix){
  const directory=path.join(root,row.id);source=path.join(directory,'01-original.png');
  if(!fs.existsSync(path.join(directory,'quality.json'))){row.renderer={blocked:true,reason:'No supported floor'};continue;}
  const revisions=['before','quality'];
  for(const revision of revisions){
   const raw=JSON.parse(fs.readFileSync(path.join(directory,revision+'.json')));
   const result=await page.evaluate(async ({raw,url,revision})=>{
    const c=window.__concept;
    if(!await c.adapter.openPhotoScene(raw,url))throw Error(c.adapter.refusScene||"Cannot open scene");
    const product=c.PREMIBEL_DEMO_PRODUCTS.find(p=>p.id==='BTRPF39009');
    const start=performance.now();
    await c.adapter.applyProfile(product.renderProfile,0);
    if(c.adapter.geometryValidation?.status==='failed')return {blocked:true,validation:c.adapter.geometryValidation};
    const png=canvas=>canvas.toDataURL('image/png').split(',')[1];
    const snapshot=c.adapter.diagnosticSnapshot();
    const out={blocked:false,renderMs:performance.now()-start,images:{[revision==='before'?'before-final':'10-final']:png(c.adapter.canvas)},validation:c.adapter.geometryValidation};
    if(revision==='quality'){
     const pack=window.__visualDiagnostics.capture(['debugGrid','debugMasks','debugCamera']);
     out.images['05-camera-grid']=png(pack.images.debugGrid);
     out.images['06-neutral-floor']=png(await c.adapter.diagnosticNeutralFrame());
     out.images['09-material-no-lighting']=png(await c.adapter.diagnosticUnlitFrame());
     const {buildShadingMap,buildResidualMaps}=await import('/web/scene/shading.js');
     const original=document.createElement('canvas');original.width=snapshot.size.width;original.height=snapshot.size.height;
     original.getContext('2d').drawImage(snapshot.photo,0,0,original.width,original.height);
     const src=original.getContext('2d').getImageData(0,0,original.width,original.height);
     const shading=buildShadingMap(src,snapshot.masks.effectiveCoverage,snapshot.scene.light);
     const residual=buildResidualMaps(src,snapshot.masks.effectiveCoverage,shading);
     const map=(width,height,read)=>{const canvas=document.createElement('canvas');canvas.width=width;canvas.height=height;const ctx=canvas.getContext('2d'),im=ctx.createImageData(width,height);for(let i=0;i<width*height;i++){const v=read(i);im.data[i*4]=im.data[i*4+1]=im.data[i*4+2]=Math.round(v);im.data[i*4+3]=255;}ctx.putImageData(im,0,0);return png(canvas);};
     out.images['07-illumination']=map(shading.width,shading.height,i=>Math.min(255,shading.rgba[i*4]*128));
     out.images['08-contact-shadows']=map(residual.width,residual.height,i=>255*(1-residual.shadow[i]));
     await c.adapter.applyProfile(product.renderProfile,0);
     const samples=[];
     for(let i=0;i<5;i++){const t=performance.now();await c.adapter.applyProfile(product.renderProfile,i%2?15:0);samples.push(performance.now()-t);}
     out.productSwitchMs=samples;
     out.camera=pack.metadata.cameras;
    }
    return out;
   },{raw,url:base+'/__v3-original?case='+encodeURIComponent(row.id)+'&revision='+revision,revision});
   for(const [name,data]of Object.entries(result.images||{}))fs.writeFileSync(path.join(directory,name+'.png'),Buffer.from(data,'base64'));
   delete result.images;
   if(revision==='quality')row.renderer=result;
  }
  fs.writeFileSync(path.join(directory,'renderer.json'),JSON.stringify(row.renderer,null,2));
  console.log(JSON.stringify({scene:row.id,blocked:row.renderer.blocked,renderMs:row.renderer.renderMs,productSwitchMs:row.renderer.productSwitchMs}));
 }
 if(errors.length)throw Error(errors.join('; '));
 fs.writeFileSync(root+'/matrix-rendered.json',JSON.stringify(matrix,null,2));
}finally{await browser.close();}
