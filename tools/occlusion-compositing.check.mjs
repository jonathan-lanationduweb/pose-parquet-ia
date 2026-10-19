/** Actual production compositing, private before/after replay and pixel assertions. */
import fs from 'node:fs';import assert from 'node:assert/strict';import {execFileSync} from 'node:child_process';import {createRequire}from'node:module';
const {chromium}=createRequire(import.meta.url)(process.env.PPAI_PLAYWRIGHT_CORE);
const root='review/room-occlusion-v2-2',base=process.env.PPAI_BASE||'http://127.0.0.1:8000';
const browser=await chromium.launch({channel:'chrome',headless:true});const results=[];
const old=new Map(['mask.js','renderer.js'].map(file=>[file,execFileSync('git',['show',`88a7a11:web/scene/${file}`])]));
async function pageFor(variant,canvas){const page=await browser.newPage({viewport:{width:1440,height:900}});page.errors=[];page.analyses=0;page.on('pageerror',e=>page.errors.push(e.message));page.on('request',r=>{if(r.url().endsWith('/v1/analyze-room'))page.analyses++;});
 await page.addInitScript(force=>{window.__glCount=0;const get=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(type,...args){if(force&&/webgl/.test(type))return null;const value=get.call(this,type,...args);if(/webgl/.test(type)&&value)window.__glCount++;return value;};},canvas);
 if(variant==='before')for(const[file,body]of old)await page.route(`**/web/scene/${file}`,r=>r.fulfill({contentType:'text/javascript',body}));
 await page.route('**/occlusion-input/*',r=>{const id=new URL(r.request().url()).pathname.split('/').pop();assert.ok(/^[a-z-]+$/.test(id));return r.fulfill({contentType:'image/jpeg',body:fs.readFileSync(`${root}/${id}/01-original.jpg`)});});
 await page.goto(base+'/tools/product-concept.html?prefetch=0');await page.waitForFunction(()=>window.__concept?.adapter.connecte,null,{timeout:90000});return page;}
try{
 for(const[variant,canvas]of (process.env.PPAI_PIXEL_ONLY==='1'?[]:[['before',false],['after',false],['after',true]])){
  const p=await pageFor(variant,canvas);
  const folders=fs.readdirSync(root).filter(id=>fs.existsSync(`${root}/${id}/scene-${variant}.json`)&&(!canvas||['owner-photo','chambre','petite-piece','terrasse'].includes(id)));
  for(const id of folders){const scene=JSON.parse(fs.readFileSync(`${root}/${id}/scene-${variant}.json`,'utf8'));const measurement=JSON.parse(fs.readFileSync(`${root}/${id}/measurement.json`,'utf8'));
   const data=await p.evaluate(async({scene,id,measurement})=>{const c=window.__concept;
    const start=performance.now();if(!await c.adapter.openPhotoScene(scene,location.origin+'/occlusion-input/'+id))throw Error(c.adapter.refusScene);
    const sceneMs=performance.now()-start;const profile=c.PREMIBEL_DEMO_PRODUCTS.find(p=>p.id===(measurement.product||'CHENF39031')).renderProfile;
    const renderStart=performance.now(),frame=await c.adapter.applyProfile(profile,0);if(!frame)throw Error('No frame');if(c.adapter.lastHit)throw Error('stale mask frame');
    const renderMs=performance.now()-renderStart;const snap=c.adapter.visitSnapshot(),m=snap.masks;
    function maskImage(values){const cv=document.createElement('canvas');cv.width=m.width;cv.height=m.height;const ctx=cv.getContext('2d'),im=ctx.createImageData(m.width,m.height);for(let i=0;i<values.length;i++){im.data[i*4]=im.data[i*4+1]=im.data[i*4+2]=values[i];im.data[i*4+3]=255;}ctx.putImageData(im,0,0);return cv.toDataURL('image/png');}
    const frameData=frame.toDataURL('image/jpeg',.96);const crop=document.createElement('canvas');crop.width=frame.width;crop.height=Math.round(frame.height*.55);crop.getContext('2d').drawImage(frame,0,frame.height*.4,frame.width,frame.height*.55,0,0,crop.width,crop.height);
    return{png:frame.toDataURL('image/png'),frame:frameData,crop:crop.toDataURL('image/jpeg',.96),floor:maskImage(m.coverage),occlusion:maskImage(m.occlusion||new Uint8Array(m.width*m.height)),sceneMs,renderMs,gl:window.__glCount};
   },{scene,id,measurement});
   const suffix=canvas?'-canvas':'';if(!canvas)fs.writeFileSync(`${root}/${id}/${variant==='before'?'04-before':'05-after'}.png`,Buffer.from(data.png.split(',')[1],'base64'));fs.writeFileSync(`${root}/${id}/${variant==='before'?'04-before':'05-after'}${suffix}.jpg`,Buffer.from(data.frame.split(',')[1],'base64'));
   if(variant==='after'&&!canvas){for(const[k,file]of [['floor','02-floor-mask.png'],['occlusion','03-occluder-mask.png'],['crop','06-crop-objects.jpg']])fs.writeFileSync(`${root}/${id}/${file}`,Buffer.from(data[k].split(',')[1],'base64'));}
   results.push({id,variant,canvas,sceneMs:data.sceneMs,renderMs:data.renderMs,glContexts:data.gl});console.log('PASS',variant,canvas?'Canvas':'WebGL',id);
  }
  assert.deepEqual(p.errors,[]);assert.equal(p.analyses,0);await p.close();
 }
 for(const canvas of [false,true]){
  const p=await pageFor('after',canvas);
  const outcome=await p.evaluate(async()=>{const c=window.__concept;const source=document.createElement('canvas');source.width=600;source.height=400;const ctx=source.getContext('2d');ctx.fillStyle='#b8b0a0';ctx.fillRect(0,0,600,400);
   const rects=[[.25,.5,.2,.15,'#c52c40'],[.55,.7,.004,.23,'#173b78'],[.65,.72,.25,.15,'#d8ad33'],[.1,.72,.08,.035,'#18372a']];
   const raw=await(await fetch('../web/data/scenes/terrasse-mer.json')).json();raw.image={width:600,height:400};raw.camera={horizon:.2};raw.planes={sol:{quad:[{x:0,y:.4},{x:1,y:.4},{x:1,y:1},{x:0,y:1}],meters:{width:4,depth:4}}};raw.floorZones=[{id:'sol',surfaceId:'sol',planeRef:'sol',mask:{polygon:[{x:0,y:.4},{x:1,y:.4},{x:1,y:1},{x:0,y:1}],holes:[]}}];
   raw.occluders=rects.map(([x,y,w,h,color],i)=>{ctx.fillStyle=color;ctx.fillRect(x*600,y*400,w*600,h*400);return{id:'test-'+i,kind:i===2?'rug':'furniture',feather:.01,polygon:[{x,y},{x:x+w,y},{x:x+w,y:y+h},{x,y:y+h}]};});
   const url=source.toDataURL('image/png'),profile=c.PREMIBEL_DEMO_PRODUCTS.find(p=>p.id==='CHENF39031').renderProfile;
   const pixel=(cv,x,y)=>Array.from(cv.getContext('2d').getImageData(Math.floor(x*600),Math.floor(y*400),1,1).data).slice(0,3);
   const probes=rects.map(([x,y,w,h])=>[x+w/2,y+h/2]);
   if(!await c.adapter.openPhotoScene(raw,url))throw Error('fixture refused');let frame=await c.adapter.applyProfile(profile,0);
   for(const[x,y]of probes){const a=pixel(source,x,y),b=pixel(frame,x,y);if(a.some((v,i)=>Math.abs(v-b[i])>2))throw Error('foreground painted '+JSON.stringify({a,b,x,y}));}
   const overlay=c.adapter.pinceau.overlay().canvas;for(const[x,y]of probes){if(overlay.getContext('2d').getImageData(Math.floor(x*600),Math.floor(y*400),1,1).data[3]>2)throw Error('Brush overlay covered a foreground object');}
   const masks=c.adapter.visitSnapshot().masks,idx=Math.floor(.8*400)*600+Math.floor(.4*600);if(masks.coverage[idx]<250)throw Error('no independent floor coverage');
   c.adapter.pinceau.begin('remove',8,{x:.4,y:.8});c.adapter.pinceau.end();c.adapter.forget();frame=await c.adapter.applyProfile(profile,0);
   if(pixel(source,.4,.8).some((v,i)=>Math.abs(v-pixel(frame,.4,.8)[i])>2))throw Error('manual remove failed');
   const other=structuredClone(raw);other.occluders=[];await c.adapter.openPhotoScene(other,url);frame=await c.adapter.applyProfile(profile,0);if(c.adapter.visitSnapshot().masks.occlusion!==null)throw Error('stale A occluder on B');
   const [x,y]=probes[0];if(pixel(source,x,y).every((v,i)=>Math.abs(v-pixel(frame,x,y)[i])<2))throw Error('B retained old foreground frame');
   await c.adapter.openPhotoScene(raw,url);frame=await c.adapter.applyProfile(profile,0);if(pixel(source,x,y).some((v,i)=>Math.abs(v-pixel(frame,x,y)[i])>2))throw Error('A/B/A failed');
   return{massive:true,thinLeg:true,rug:true,grille:true,manualRemove:true,staleIsolation:true,glContexts:window.__glCount};
  });results.push({synthetic:true,canvas,...outcome});assert.deepEqual(p.errors,[]);await p.close();console.log('PASS pixel assertions',canvas?'Canvas':'WebGL');
 }
 const previous=process.env.PPAI_PIXEL_ONLY==='1'?JSON.parse(fs.readFileSync(`${root}/render-matrix.json`,'utf8')).results.filter(r=>!r.synthetic):[];fs.writeFileSync(`${root}/render-matrix.json`,JSON.stringify({results:[...previous,...results],pageErrors:[]},null,2));
}finally{await browser.close();}
