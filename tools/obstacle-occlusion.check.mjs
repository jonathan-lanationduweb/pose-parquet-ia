/** Production occlusion regression: real WebGL/Canvas, source probes, DPR and resize. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {createRequire} from 'node:module';
import {refineOcclusion} from '../web/scene/occlusion-refiner.js';
import {ViewTransform} from '../web/product/view-transform.js';
const w=100,h=80,alpha=new Uint8Array(w*h),rgb=new Uint8ClampedArray(w*h*4);
for(let y=0;y<h;y++)for(let x=0;x<w;x++){
 const i=y*w+x,fg=x>=30&&x<60&&y>=20&&y<60;
 rgb.set(fg?[25,30,35,255]:[190,170,140,255],i*4);
 // Coarse boundary is 2 pixels inside the actual foreground.
 if(x>=32&&x<58&&y>=22&&y<58)alpha[i]=255;
}
const refined=refineOcclusion(alpha,rgb,w,h);
assert.ok(refined.alpha[40*w+30]>250,'image-supported edge not recovered');
assert.ok(refined.changed>0);
assert.equal(refined.alpha[40*w+28],0,'floor expanded into object');
const thin=new Uint8Array(w*h);for(let y=20;y<60;y++)thin[y*w+50]=255;
assert.ok(refineOcclusion(thin,rgb,w,h).alpha.every((v,i)=>!thin[i]||v===255),'thin prior lost');
assert.deepEqual(refineOcclusion(new Uint8Array(w*h),rgb,w,h).alpha,new Uint8ClampedArray(w*h));
let roundtrip=0;
for(const dpr of [1,2])for(const width of [1440,390,1440]){
 const t=new ViewTransform({imageWidth:1600,imageHeight:1067,viewportWidth:width,viewportHeight:844,zoom:1.8,offsetX:-93,offsetY:21});
 for(const p of [{x:495,y:910},{x:800,y:920},{x:1295,y:900}]){
  const v=t.imageToViewport(p),q=t.viewportToImage({x:v.x*dpr/dpr,y:v.y*dpr/dpr});
  roundtrip=Math.max(roundtrip,Math.hypot(q.x-p.x,q.y-p.y));
 }
}
assert.ok(roundtrip<.5);
const {chromium}=createRequire(import.meta.url)(process.env.PPAI_PLAYWRIGHT_CORE);
const browser=await chromium.launch({channel:'chrome',headless:true}),rows=[];
try{
 for(const canvas of [false,true])for(const dpr of [1,2]){
  const context=await browser.newContext({viewport:{width:1440,height:900},deviceScaleFactor:dpr});
  const p=await context.newPage(),errors=[];let analyses=0;
  p.on('pageerror',e=>errors.push(e.message));p.on('request',r=>{if(r.url().includes('/analyze-room'))analyses++;});
  if(canvas)await p.addInitScript(()=>{const get=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(kind,...args){return /webgl/.test(kind)?null:get.call(this,kind,...args);};});
  await p.goto((process.env.PPAI_BASE||'http://127.0.0.1:8000')+'/tools/product-concept.html?dev=1&prefetch=0');
  await p.waitForFunction(()=>window.__concept?.adapter.connecte,null,{timeout:90000});
  for(const width of [1440,390,1440]){
   await p.setViewportSize({width,height:900});
   const result=await p.evaluate(async()=>{
    const c=window.__concept,raw=await(await fetch('../web/data/scenes/piece-claire.json')).json();
    raw.id='occlusion-fixture';const W=raw.image.width,H=raw.image.height,src=document.createElement('canvas');src.width=W;src.height=H;
    const ctx=src.getContext('2d');ctx.fillStyle='#a88e74';ctx.fillRect(0,0,W,H);
    // Four-pixel leg, broad furniture, rug and one-pixel vertical support.
    const rects=[[.31,.80,4/W,.12,'#102a93'],[.42,.79,.10,.09,'#c52c40'],[.57,.84,.10,.06,'#d8ad33'],[.73,.91,1/W,.05,'#18372a']];
    raw.occluders=rects.map(([x,y,w,h,color],i)=>{ctx.fillStyle=color;ctx.fillRect(x*W,y*H,w*W,h*H);return{id:'known-'+i,kind:i===2?'rug':'furniture',polygon:[{x,y},{x:x+w,y},{x:x+w,y:y+h},{x,y:y+h}]};});
    const input=src.toDataURL(),profile=c.PREMIBEL_DEMO_PRODUCTS.find(p=>p.id==='CHENF39031').renderProfile;
    if(!await c.adapter.openPhotoScene(raw,input))throw Error('fixture refused '+c.adapter.refusScene);
    let frame=await c.adapter.applyProfile(profile,0);if(!frame)throw Error('missing frame');
    const snapshot=c.adapter.visitSnapshot(),m=snapshot.masks,photo=c.adapter.diagnosticSnapshot().photo;
    const pixel=(cv,x,y)=>Array.from(cv.getContext('2d').getImageData(Math.min(cv.width-1,Math.floor(x*cv.width)),Math.min(cv.height-1,Math.floor(y*cv.height)),1,1).data).slice(0,3);
    let checks=0;const partial=[];
    for(const[x,y,w,h]of rects){
     const X=x+w/2,Y=y+h/2,i=Math.floor(Y*m.height)*m.width+Math.floor(X*m.width);
     if(!m.occlusion||m.occlusion[i]<80)throw Error('CPU lost thin occluder '+i);
     const a=pixel(photo,X,Y),b=pixel(frame,X,Y);
     if(m.occlusion[i]>=250){if(a.some((v,k)=>Math.abs(v-b[k])>3))throw Error('GPU/Canvas repainted opaque mask pixel '+JSON.stringify({a,b,X,Y,occlusion:m.occlusion[i]}));}else partial.push({a,b,X,Y,alpha:m.occlusion[i]});
     checks++;
    }
    // Manual Retirer, undo, and A -> B -> A must invalidate cached frames.
    c.adapter.pinceau.begin('remove',8,{x:.37,y:.91});c.adapter.pinceau.end();c.adapter.forget();
    frame=await c.adapter.applyProfile(profile,0);
    if(pixel(photo,.37,.91).some((v,k)=>Math.abs(v-pixel(frame,.37,.91)[k])>2))throw Error('remove did not protect original');
    const empty=structuredClone(raw);empty.occluders=[];
    await c.adapter.openPhotoScene(empty,input);const emptyFrame=await c.adapter.applyProfile(profile,0);for(const q of partial){const b=pixel(emptyFrame,q.X,q.Y),delta=q.b.reduce((s,v,k)=>s+Math.abs(v-q.a[k]),0),unprotected=b.reduce((s,v,k)=>s+Math.abs(v-q.a[k]),0);if(delta>=unprotected)throw Error('subpixel protection had no effect');}
    if(c.adapter.visitSnapshot().masks.occlusion!==null)throw Error('stale mask on B');
    await c.adapter.openPhotoScene(raw,input);frame=await c.adapter.applyProfile(profile,0);
    const X=rects[1][0]+rects[1][2]/2,Y=rects[1][1]+rects[1][3]/2;
    if(pixel(c.adapter.diagnosticSnapshot().photo,X,Y).some((v,k)=>Math.abs(v-pixel(frame,X,Y)[k])>2))throw Error('A mask not restored');
    return {backend:c.adapter.moteur.backend,sourceSize:{width:m.width,height:m.height},checks,refinement:m.refinement,manual:true,roomSwitch:true};
   });
   rows.push({canvas,dpr,width,...result});
  }
  assert.deepEqual(errors,[]);assert.equal(analyses,0);await context.close();
 }
 fs.mkdirSync('review/occlusion-obstacles',{recursive:true});
 fs.writeFileSync('review/occlusion-obstacles/regressions.json',JSON.stringify({roundtrip,rows},null,2));
 console.log('PASS image-supported refinement, thin priors, production source mask sampling, 1440→390→1440 DPR1/2 WebGL/Canvas, remove, A→B→A; no AI',rows.length);
}finally{await browser.close();}
