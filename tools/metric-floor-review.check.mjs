/** Private paired captures through the real WebGL and Canvas renderer. */
import fs from'node:fs';import assert from'node:assert/strict';import{createRequire}from'node:module';
const {chromium}=createRequire(import.meta.url)(process.env.PPAI_PLAYWRIGHT_CORE);
const base=process.env.PPAI_BASE||'http://127.0.0.1:8000',root='review/floor-projection-metric';fs.mkdirSync(root,{recursive:true});
const allCases=['premibel-salon','premibel-piano','chambre-parisienne','chambre','piece-claire','terrasse-mer','couloir','appartement-ancien','owner'];
const cases=process.env.PPAI_PROJECTION_CASE?allCases.filter(id=>id===process.env.PPAI_PROJECTION_CASE):allCases;
const browser=await chromium.launch({channel:'chrome',headless:true});const results=[];
try{
for(const canvas of[false,true])for(const variant of['legacy','metric']){
 const p=await browser.newPage({viewport:{width:1440,height:900}});const errors=[];p.on('pageerror',e=>errors.push(e.message));
 if(canvas)await p.addInitScript(()=>{const get=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(t,...a){return /webgl/.test(t)?null:get.call(this,t,...a);};});
 await p.route('**/private-owner.png',r=>r.fulfill({contentType:'image/png',body:fs.readFileSync('C:/Users/jonat/Downloads/test salon parquet.png')}));
 await p.goto(base+`/tools/product-concept.html?dev=1&prefetch=0&renderer=${variant}`);await p.waitForFunction(()=>window.__concept?.adapter.connecte,null,{timeout:90000});
 assert.equal(await p.locator('#wallPaintOpen').count(),0);
 for(const id of cases.filter(x=>!canvas||['owner','chambre','terrasse-mer'].includes(x))){
 const raw=id==='owner'?JSON.parse(fs.readFileSync('review/room-occlusion-v2-2/owner-photo/scene-after.json','utf8')):JSON.parse(fs.readFileSync(`web/data/scenes/${id}.json`,'utf8'));
 const image=id==='owner'?base+'/private-owner.png':base+'/web/assets/images/'+raw.image.file;
 const out=await p.evaluate(async({raw,image,id})=>{
  const c=window.__concept;if(!await c.adapter.openPhotoScene(raw,image))throw Error(c.adapter.refusScene);
  const product=c.PREMIBEL_DEMO_PRODUCTS.find(p=>p.id===(id==='terrasse-mer'?'VLAME16012':'BTRPF39009'))||c.PREMIBEL_DEMO_PRODUCTS.find(p=>p.id==='CHENF39031');const profile=product.renderProfile;
  const validation=c.adapter.geometryValidation;
  if(validation?.status==='failed'){
   const {loadImage}=await import('../web/scene/image-loader.js');const original=(await loadImage(image)).canvas.toDataURL('image/png').split(',')[1];
   return {frame:original,grid:original,original,overlay:original,blocked:true,validation,projectionStats:c.adapter.moteur.projectionStats};
  }
  const t0=performance.now();const frame=await c.adapter.applyProfile(profile,0);const productMs=performance.now()-t0;if(!frame)throw Error('no frame');
  const snap=c.adapter.visitSnapshot(),scene=snap.scene;const {loadImage}=await import('../web/scene/image-loader.js');const photo=(await loadImage(image)).canvas;const rendered=frame.toDataURL('image/png').split(',')[1];const {zoneTransform}=await import('../web/scene/geometry.js');const {apply}=await import('../web/scene/perspective.js');
  const w=frame.width,h=frame.height;const grid=document.createElement('canvas');grid.width=w;grid.height=h;const g=grid.getContext('2d');
  for(const z of scene.floorZones){const t=zoneTransform(z,w,h);if(!t)continue;const mw=z.plane.meters.width,md=z.plane.meters.depth;const point=(u,v)=>apply(t.H,u/mw,v/md);const sign=(u,v)=>Math.sign(t.H[6]*u/mw+t.H[7]*v/md+t.H[8]);
   for(let k=-20;k<=20;k+=.5)for(let q=-20;q<20;q+=.2)for(const axis of[0,1]){const a=axis?[q,k]:[k,q],b=axis?[q+.2,k]:[k,q+.2];if(sign(...a)!==sign(mw/2,md/2)||sign(...b)!==sign(...a))continue;const pa=point(...a),pb=point(...b);if(![pa.x,pa.y,pb.x,pb.y].every(Number.isFinite))continue;g.strokeStyle=Number.isInteger(k)?'#00d9b8':'#ffffff99';g.lineWidth=Number.isInteger(k)?2:1;g.beginPath();g.moveTo(pa.x,pa.y);g.lineTo(pb.x,pb.y);g.stroke();}
  }
  const m=snap.masks,mask=document.createElement('canvas');mask.width=w;mask.height=h;const im=mask.getContext('2d').createImageData(w,h);for(let i=0;i<w*h;i++)im.data[4*i+3]=m.effectiveCoverage[i];mask.getContext('2d').putImageData(im,0,0);g.globalCompositeOperation='destination-in';g.drawImage(mask,0,0);g.globalCompositeOperation='destination-over';g.drawImage(photo,0,0,w,h);
  const sourcePixels=photo.getContext('2d').getImageData(0,0,w,h).data,renderPixels=frame.getContext('2d').getImageData(0,0,w,h).data;
  let protectedProbes=0;for(let i=0;i<w*h;i+=137)if(m.effectiveCoverage[i]===0){for(let ch=0;ch<3;ch++)if(Math.abs(sourcePixels[i*4+ch]-renderPixels[i*4+ch])>2)throw Error(JSON.stringify({problem:'source pixel lost outside effective floor',i,x:i%w,y:Math.floor(i/w),channel:ch,source:sourcePixels[i*4+ch],render:renderPixels[i*4+ch],w,h,photo:[photo.width,photo.height]}));protectedProbes++;}
  const overlay=document.createElement('canvas');overlay.width=w;overlay.height=h;const og=overlay.getContext('2d');og.drawImage(photo,0,0,w,h);
  og.strokeStyle='#ff4848';og.lineWidth=2;for(const z of scene.floorZones){og.beginPath();z.mask.polygon.forEach((p,i)=>og[i?'lineTo':'moveTo'](p.x*w,p.y*h));og.closePath();og.stroke();}
  const line=(a,b,color)=>{if(!a||!b||![a.x,a.y,b.x,b.y].every(Number.isFinite))return;og.strokeStyle=color;og.beginPath();og.moveTo(a.x,a.y);og.lineTo(b.x,b.y);og.stroke();};
  og.fillStyle='#00bda0';for(const z of scene.floorZones){const {projectionRuntime}=await import('../web/scene/metric-runtime.js');const rt=projectionRuntime(z.plane,w,h);if(rt){const hy0=rt.camera.horizonAt(0,rt.floor),hy1=rt.camera.horizonAt(w,rt.floor);line({x:0,y:hy0},{x:w,y:hy1},'#ffcf00');
   const o=rt.camera.project(rt.floor.origin);
   line(o,rt.camera.project(rt.floor.floorLocalToWorld(1,0)),'#00bda0');line(o,rt.camera.project(rt.floor.floorLocalToWorld(0,1)),'#ffbf52');
   og.font='16px monospace';og.fillText('U / V : 1 m',15,25);
   for(const axis of[rt.floor.axisU,rt.floor.axisV]){const vp=rt.camera.homogeneousDirection(axis);if(Math.abs(vp[2])>1e-8){const x=Math.max(7,Math.min(w-7,vp[0]/vp[2])),y=Math.max(7,Math.min(h-7,vp[1]/vp[2]));og.beginPath();og.arc(x,y,6,0,Math.PI*2);og.stroke();}}
   if(o){og.beginPath();og.arc(o.x,o.y,7,0,Math.PI*2);og.fill();}}}
  const patterns={};if(new URL(location).searchParams.get('renderer')==='metric'){for(const [name,pattern]of[['running','lames'],['herring','baton-rompu'],['chevron','point-de-hongrie']]){const f=await c.adapter.applyProfile({...profile,pattern},0);patterns[name]=f.toDataURL('image/png').split(',')[1];}}
  const cameraSignature=JSON.stringify(scene.floorZones.map(z=>z.plane.projection));
  const rotations=[];for(const angle of[45,90,179,359]){const a=performance.now();await c.adapter.applyProfile(profile,angle);rotations.push(performance.now()-a);if(JSON.stringify(c.adapter.visitSnapshot().scene.floorZones.map(z=>z.plane.projection))!==cameraSignature)throw Error('rotation changed camera');}
  const cachedStart=performance.now();await c.adapter.applyProfile(profile,0);const cachedMs=performance.now()-cachedStart;if(!c.adapter.lastHit)throw Error('expected frame cache hit');
  const png=cv=>cv.toDataURL('image/png').split(',')[1];return {frame:rendered,grid:png(grid),original:png(photo),overlay:png(overlay),patterns,validation,projectionStats:c.adapter.moteur.projectionStats,productMs,cachedMs,rotations,protectedProbes,projections:scene.floorZones.map(z=>{const p=z.plane.projection;if(!p)return null;return {status:p.status,reason:p.reason,shear:p.shear,legacyAxisScale:p.legacyAxisScale,camera:p.cameraModel,floorPlane:p.floorPlane,samples:p.samples};}),diagnostics:c.adapter.geometryDiagnostics(profile,0)};
 },{raw,image,id});
 fs.mkdirSync(`${root}/${id}`,{recursive:true});const suffix=canvas?'-canvas':'';
 for(const[k,n]of[['original','01-original'],['grid',variant==='legacy'?'02-grid-current':'03-metric-grid'],['frame',variant==='legacy'?'04-legacy-render':'07-final']])fs.writeFileSync(`${root}/${id}/${n}${suffix}.png`,Buffer.from(out[k],'base64'));
  fs.writeFileSync(`${root}/${id}/02-geometry-overlay-${variant}${suffix}.png`,Buffer.from(out.overlay,'base64'));
 if(out.patterns&&Object.keys(out.patterns).length)for(const [key,n]of[['running','04-running-bond'],['herring','05-herringbone'],['chevron','06-chevron']])fs.writeFileSync(`${root}/${id}/${n}${suffix}.png`,Buffer.from(out.patterns[key],'base64'));
 const {frame,grid,original,overlay,patterns,...measurement}=out;results.push({id,variant,canvas,...measurement});console.log('PASS capture',id,variant,canvas?'Canvas':'WebGL');
 }
 assert.deepEqual(errors,[]);await p.close();
}
const previous=process.env.PPAI_PROJECTION_CASE&&fs.existsSync(root+'/matrix.json')?JSON.parse(fs.readFileSync(root+'/matrix.json','utf8')).results.filter(x=>!cases.includes(x.id)):[];
fs.writeFileSync(root+'/matrix.json',JSON.stringify({results:[...previous,...results]},null,2));
}finally{await browser.close();}
