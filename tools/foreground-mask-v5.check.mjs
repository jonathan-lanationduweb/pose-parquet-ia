/** Source-mask audit through the unchanged V4 renderer; private fixtures only. */
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {ViewTransform} from '../web/product/view-transform.js';
const {chromium}=createRequire(import.meta.url)(process.env.PPAI_PLAYWRIGHT_CORE);
const root='review/foreground-mask-v5',cases=JSON.parse(fs.readFileSync(root+'/matrix.json')).map(r=>r.scene);
for(const dpr of [1,2])for(const width of [1440,390]){
 const t=new ViewTransform({imageWidth:1536,imageHeight:1024,viewportWidth:width,viewportHeight:844,zoom:1.8,offsetX:-91,offsetY:17});
 const p={x:953,y:712},v=t.imageToViewport(p),q=t.viewportToImage({x:v.x*dpr/dpr,y:v.y*dpr/dpr});assert.ok(Math.hypot(p.x-q.x,p.y-q.y)<.01);
}
const browser=await chromium.launch({channel:'chrome',headless:true}),rows=[];
try{
 for(const canvas of [false,true]){
  const page=await browser.newPage({viewport:{width:1440,height:900},deviceScaleFactor:canvas?1:2});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  if(canvas)await page.addInitScript(()=>{const get=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(kind,...args){return /webgl/.test(kind)?null:get.call(this,kind,...args);};});
  await page.addInitScript(()=>{const get=HTMLCanvasElement.prototype.getContext;window.__maskUploads=[];HTMLCanvasElement.prototype.getContext=function(kind,...args){const gl=get.call(this,kind,...args);if(kind==='webgl2'&&args[0]?.preserveDrawingBuffer){window.__reviewGL=gl;const upload=gl.texImage2D.bind(gl);gl.texImage2D=(...a)=>{const unit=gl.getParameter(gl.ACTIVE_TEXTURE)-gl.TEXTURE0,t=performance.now();const r=upload(...a);if(unit===8)window.__maskUploads.push(performance.now()-t);return r;};}return gl;};});
  let current;
  await page.route('**/__v5-original*',r=>r.fulfill({contentType:'image/png',body:fs.readFileSync(root+'/'+current+'/01-original.png')}));
  await page.goto('http://127.0.0.1:8000/tools/product-concept.html?dev=1&prefetch=0');
  await page.waitForFunction(()=>window.__concept?.adapter.connecte,null,{timeout:90000});
  for(const width of [1440,390]){
   await page.setViewportSize({width,height:width===390?844:900});
   for(current of cases){
    const before=JSON.parse(fs.readFileSync(root+'/'+current+'/before.json'));
    const after=JSON.parse(fs.readFileSync(root+'/'+current+'/after.json'));
    for(const key of ['camera','planes','floorZones','light'])assert.deepEqual(after[key],before[key],key+' changed');
    for(const revision of canvas?['after']:['before','after']){
     const rawText=JSON.stringify(revision==='before'?before:after);
     const result=await page.evaluate(async({rawText,url,revision})=>{
      const c=window.__concept,a=c.adapter,t=performance.now(),raw=JSON.parse(rawText),decodeMs=performance.now()-t;
      window.__maskUploads=[];
      if(!await a.openPhotoScene(raw,url))throw Error(a.refusScene||'Scene refused');
      const profile=c.PREMIBEL_DEMO_PRODUCTS.find(p=>p.id==='BTRPF39009').renderProfile;
      if(!await a.applyProfile(profile,0))throw Error('No V4 frame');
      const geometry=JSON.stringify(a.diagnosticSnapshot().scene.floorZones.map(z=>z.plane));
      const snap=a.diagnosticSnapshot(),m=snap.masks,rgba=a.canvas.getContext('2d').getImageData(0,0,a.canvas.width,a.canvas.height).data;
      const photo=snap.photo.getContext('2d').getImageData(0,0,a.canvas.width,a.canvas.height).data;
      let protectedPixels=0;
      for(let i=0;i<m.coverage.length;i+=19)if(m.occlusion?.[i]===255){for(let k=0;k<3;k++)if(Math.abs(rgba[i*4+k]-photo[i*4+k])>2)throw Error('Opaque V5 object repainted');protectedPixels++;}
      const png=cv=>cv.toDataURL().split(',')[1];
      const images={final:png(a.canvas)};
      if(revision==='after')images.overlay=png(a.diagnosticForegroundOverlayFrame());
      for(let i=0;i<4;i++)await a.applyProfile(profile,i%2?15:0);
      if(JSON.stringify(a.diagnosticSnapshot().scene.floorZones.map(z=>z.plane))!==geometry)throw Error('Geometry changed');
      const mask=m.occlusion||new Uint8Array(m.coverage.length);
      const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',mask))).map(x=>x.toString(16).padStart(2,'0')).join('');
      return {images,decodeMs,maskUploadMs:window.__maskUploads,protectedPixels,digest,size:snap.size,backend:window.__reviewGL?'webgl2':'canvas'};
     },{rawText,url:'http://127.0.0.1:8000/__v5-original?scene='+current+'&revision='+revision,revision});
     const folder=root+'/'+current,backend=canvas?'canvas':'gl';
     fs.writeFileSync(folder+'/'+(revision==='before'?'04-final-before':'05-final-after')+'-'+width+'-'+backend+'.png',Buffer.from(result.images.final,'base64'));
     if(result.images.overlay)fs.writeFileSync(folder+'/03-overlay-renderer-'+width+'-'+backend+'.png',Buffer.from(result.images.overlay,'base64'));
     if(width===1440&&!canvas){fs.writeFileSync(folder+'/'+(revision==='before'?'04-final-before':'05-final-after')+'.png',Buffer.from(result.images.final,'base64'));}
     delete result.images;rows.push({scene:current,width,revision,...result});
     console.log(JSON.stringify({scene:current,width,revision,backend,protectedPixels:result.protectedPixels}));
    }
   }
  }
  // Actual A(sofa) -> B(empty) -> A uses identical source-size masks on return.
  const signatures=[];
  for(current of ['sofa','empty-room','sofa']){
   const raw=JSON.parse(fs.readFileSync(root+'/'+current+'/after.json'));
   signatures.push(await page.evaluate(async({raw,url})=>{const a=window.__concept.adapter;await a.openPhotoScene(raw,url);await a.applyProfile(window.__concept.PREMIBEL_DEMO_PRODUCTS.find(p=>p.id==='BTRPF39009').renderProfile,0);const m=a.visitSnapshot().masks;return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',m.occlusion))).join(',');},{raw,url:'http://127.0.0.1:8000/__v5-original?stale='+current}));
  }
  assert.equal(signatures[0],signatures[2]);assert.notEqual(signatures[0],signatures[1]);assert.deepEqual(errors,[]);await page.close();
 }
}finally{await browser.close();}
fs.writeFileSync(root+'/browser.json',JSON.stringify(rows,null,2));
console.log('PASS foreground / rug / mask mapping / stale A-B-A / same V4 GL-Canvas');
