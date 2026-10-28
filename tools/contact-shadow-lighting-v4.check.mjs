/** Real renderer review and before/after measurements; all photos stay local. */
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {blurMask25,buildContactMaps} from '../web/scene/contact-compositor.js';
import {ViewTransform} from '../web/product/view-transform.js';
const {chromium}=createRequire(import.meta.url)(process.env.PPAI_PLAYWRIGHT_CORE);
const root='review/contact-shadow-lighting-v4',base=process.env.PPAI_BASE||'http://127.0.0.1:8000';
// contact-shadow / floor-feather / alignment: exact reference samples, no invented dilation.
const w=100,h=80,floor=new Uint8Array(w*h),occ=new Uint8Array(w*h);
for(let y=20;y<h;y++)for(let x=0;x<w;x++)floor[y*w+x]=255;
for(let y=30;y<60;y++)for(let x=40;x<48;x++)occ[y*w+x]=255;
const maps=buildContactMaps({coverage:floor,occlusion:occ},w,h);
assert.equal(maps.contact[40*w+43],0);assert.ok(maps.contact[40*w+35]>0);assert.equal(maps.soft[5*w+30],0);assert.equal(maps.soft[70*w+30],1);
assert.ok(blurMask25(floor,w,h,3)[20*w+20]>.5);
for(const viewportWidth of [1440,390,1000]){
 const t=new ViewTransform({imageWidth:1600,imageHeight:1067,viewportWidth,viewportHeight:844,zoom:1.6,offsetX:-83,offsetY:19});
 const p={x:789,y:823},q=t.viewportToImage(t.imageToViewport(p));assert.ok(Math.hypot(p.x-q.x,p.y-q.y)<1e-8);
}
const cases=['empty','sofa','thin-legs','rug','dark','bright','old-floor','plant'];
const modes=process.env.PPAI_V4_MODE?[process.env.PPAI_V4_MODE]:['before','after'];
const browser=await chromium.launch({channel:'chrome',headless:true});
const rows=[];
try{
 for(const revision of modes)for(const width of [1440,390]){
  const page=await browser.newPage({viewport:{width,height:width===390?844:900},deviceScaleFactor:2});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  if(revision==='before')for(const file of ['renderer-gl.js','renderer-canvas.js','renderer.js'])await page.route('**/web/scene/'+file,r=>r.fulfill({contentType:'text/javascript',body:fs.readFileSync(root+'/'+file)}));
  if(process.env.PPAI_CANVAS==='1')await page.addInitScript(()=>{const get=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(kind,...args){return /webgl/.test(kind)?null:get.call(this,kind,...args);};});
  await page.addInitScript(()=>{const get=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(kind,...args){const result=get.call(this,kind,...args);if(kind==='webgl2'&&args[0]?.preserveDrawingBuffer)window.__reviewGL=result;return result;};});
  let name;
  await page.route('**/__v4-original*',r=>r.fulfill({contentType:'image/png',body:fs.readFileSync(root+'/'+name+'/01-original.png')}));
  await page.goto(base+'/tools/product-concept.html?dev=1&prefetch=0&perf=1');
  await page.waitForFunction(()=>window.__concept?.adapter.connecte,null,{timeout:90000});
  for(name of cases){
   const raw=JSON.parse(fs.readFileSync(root+'/'+name+'/scene.json'));
   const result=await page.evaluate(async({raw,url,revision})=>{
    const c=window.__concept,a=c.adapter;if(!await a.openPhotoScene(raw,url))throw Error(a.refusScene||'open refused');
    const profile=c.PREMIBEL_DEMO_PRODUCTS.find(p=>p.id==='BTRPF39009').renderProfile;
    if(!await a.applyProfile(profile,0))throw Error('no render');
    const snap=a.diagnosticSnapshot(),geometry=JSON.stringify(snap.scene.floorZones.map(z=>z.plane));
    const png=cv=>cv.toDataURL('image/png').split(',')[1],images={};
    const timings=[],gpuMs=[],compositeGpuMs=[];
    const gpu=window.__reviewGL,ext=gpu?.getExtension('EXT_disjoint_timer_query_webgl2');
    async function queryResult(query){
      for(let n=0;n<100&&!gpu.getQueryParameter(query,gpu.QUERY_RESULT_AVAILABLE);n++)await new Promise(r=>setTimeout(r,10));
      if(!gpu.getParameter(ext.GPU_DISJOINT_EXT)&&gpu.getQueryParameter(query,gpu.QUERY_RESULT_AVAILABLE)){const ms=gpu.getQueryParameter(query,gpu.QUERY_RESULT)/1e6;gpu.deleteQuery(query);return ms;}
      gpu.deleteQuery(query);return null;
    }
    for(let i=0;i<(gpu?11:4);i++){
      const query=ext?gpu.createQuery():null;if(query)gpu.beginQuery(ext.TIME_ELAPSED_EXT,query);
      const t=performance.now();await a.diagnosticCompositeFrame(0);
      if(query)gpu.endQuery(ext.TIME_ELAPSED_EXT);gpu?.finish();
      if(i)timings.push(performance.now()-t);
      if(query){const ms=await queryResult(query);if(i&&ms!==null)gpuMs.push(ms);}
    }
    if(ext&&revision==='after'){
      const originalDraw=gpu.drawArrays.bind(gpu);let query=null;
      gpu.drawArrays=(...args)=>{
        const isComposite=gpu.getUniformLocation(gpu.getParameter(gpu.CURRENT_PROGRAM),'uFloorRender')!==null;
        if(isComposite){query=gpu.createQuery();gpu.beginQuery(ext.TIME_ELAPSED_EXT,query);}
        originalDraw(...args);if(isComposite)gpu.endQuery(ext.TIME_ELAPSED_EXT);
      };
      try{for(let i=0;i<5;i++){await a.diagnosticCompositeFrame(0);gpu.finish();if(query){const ms=await queryResult(query);if(ms!==null)compositeGpuMs.push(ms);query=null;}}}
      finally{gpu.drawArrays=originalDraw;}
    }
    images['08-final']=png(a.canvas);
    if(revision==='after')for(const [mode,file]of [[1,'02-floor-mask'],[2,'03-occluder-mask'],[3,'04-light-layer'],[4,'05-floor-no-light'],[5,'06-floor-with-light'],[6,'07-contact-shadow'],[0,'08-final']])images[file]=png(await a.diagnosticCompositeFrame(mode));
    // Product and rotation must leave the geometry untouched.
    await a.applyProfile(c.PREMIBEL_DEMO_PRODUCTS.find(p=>p.id==='CHENF39031').renderProfile,30);
    if(JSON.stringify(a.diagnosticSnapshot().scene.floorZones.map(z=>z.plane))!==geometry)throw Error('geometry changed');
    const gl=window.__reviewGL,glError=gl?gl.getError():0;
    const binding=gl?{gpu:gl.getParameter(gl.RENDERER),timerExtension:!!gl.getExtension('EXT_disjoint_timer_query_webgl2'),glError}:null;
    const probes=[];const canvas=await a.diagnosticCompositeFrame(0),ctx=canvas.getContext('2d'),final=ctx.getImageData(0,0,canvas.width,canvas.height).data;
    const photo=snap.photo.getContext('2d').getImageData(0,0,canvas.width,canvas.height).data;
    for(let i=0;i<snap.masks.occlusion.length;i+=17)if(snap.masks.occlusion[i]===255){for(let k=0;k<3;k++)if(Math.abs(final[i*4+k]-photo[i*4+k])>2)throw Error('Opaque foreground repainted '+i);probes.push(i);}
    return {backend:gl?'webgl2':'canvas',timings,gpuMs,compositeGpuMs,binding,opaqueProbes:probes.length,images,size:snap.size};
   },{raw,url:base+'/__v4-original?case='+name,revision});
   assert.equal(result.binding?.glError||0,0);assert.equal(result.backend,process.env.PPAI_CANVAS==='1'?'canvas':'webgl2');
   const folder=root+'/'+name+'/'+revision+'-'+width+(process.env.PPAI_CANVAS==='1'?'-canvas':'');fs.mkdirSync(folder,{recursive:true});
   for(const [file,data]of Object.entries(result.images))fs.writeFileSync(folder+'/'+file+'.png',Buffer.from(data,'base64'));
   delete result.images;
   await page.screenshot({path:folder+'/ui.png'});
   rows.push({name,revision,viewport:width,...result});console.log(JSON.stringify({name,revision,viewport:width,backend:result.backend,frames:result.timings.length,opaque:result.opaqueProbes}));
  }
  // Same image domain survives viewport resize (ViewTransform applies to the complete canvas).
  await page.setViewportSize({width:width===390?1000:390,height:844});
  await page.evaluate(async()=>{const a=window.__concept.adapter;if(!await a.diagnosticCompositeFrame(0))throw Error('resize failed');});
  assert.deepEqual(errors,[]);await page.close();
 }
}finally{await browser.close();}
const file=root+'/benchmark-'+(process.env.PPAI_CANVAS==='1'?'canvas-':'')+(process.env.PPAI_V4_MODE||'both')+'.json';
fs.writeFileSync(file,JSON.stringify({method:'Warm real render + Canvas copy + gl.finish (10 GL / 3 Canvas samples); GPU query total frame (10), isolated final compositor (5) when EXT_disjoint_timer_query_webgl2 is available; source-resolution frame, viewport reported separately; Chrome emulation, not physical mobile GPU.',rows},null,2));
console.log('PASS contact-shadow / floor-feather / lighting-layer / compositing-alignment / mobile-compositing');
