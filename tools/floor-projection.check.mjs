/** Private paired captures through the real WebGL and Canvas renderer. */
import fs from'node:fs';import assert from'node:assert/strict';import{createRequire}from'node:module';
const {chromium}=createRequire(import.meta.url)(process.env.PPAI_PLAYWRIGHT_CORE);
const base=process.env.PPAI_BASE||'http://127.0.0.1:8000',root='review/floor-projection-v3';fs.mkdirSync(root,{recursive:true});
const allCases=['premibel-salon','premibel-piano','chambre-parisienne','chambre','piece-claire','terrasse-mer','couloir','appartement-ancien','owner'];
const cases=process.env.PPAI_PROJECTION_CASE?allCases.filter(id=>id===process.env.PPAI_PROJECTION_CASE):allCases;
const browser=await chromium.launch({channel:'chrome',headless:true});const results=[];
try{
for(const canvas of[false,true])for(const variant of['legacy','v3']){
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
  const t0=performance.now();const frame=await c.adapter.applyProfile(profile,0);const productMs=performance.now()-t0;if(!frame)throw Error('no frame');
  const snap=c.adapter.visitSnapshot(),scene=snap.scene;const {loadImage}=await import('../web/scene/image-loader.js');const photo=(await loadImage(image)).canvas;const rendered=frame.toDataURL('image/png').split(',')[1];const {zoneTransform}=await import('../web/scene/geometry.js');const {apply}=await import('../web/scene/perspective.js');
  const w=frame.width,h=frame.height;const grid=document.createElement('canvas');grid.width=w;grid.height=h;const g=grid.getContext('2d');
  for(const z of scene.floorZones){const t=zoneTransform(z,w,h);if(!t)continue;const mw=z.plane.meters.width,md=z.plane.meters.depth;const point=(u,v)=>apply(t.H,u/mw,v/md);const sign=(u,v)=>Math.sign(t.H[6]*u/mw+t.H[7]*v/md+t.H[8]);
   for(let k=-20;k<=20;k+=.5)for(let q=-20;q<20;q+=.2)for(const axis of[0,1]){const a=axis?[q,k]:[k,q],b=axis?[q+.2,k]:[k,q+.2];if(sign(...a)!==sign(mw/2,md/2)||sign(...b)!==sign(...a))continue;const pa=point(...a),pb=point(...b);if(![pa.x,pa.y,pb.x,pb.y].every(Number.isFinite))continue;g.strokeStyle=Number.isInteger(k)?'#00d9b8':'#ffffff99';g.lineWidth=Number.isInteger(k)?2:1;g.beginPath();g.moveTo(pa.x,pa.y);g.lineTo(pb.x,pb.y);g.stroke();}
  }
  const m=snap.masks,mask=document.createElement('canvas');mask.width=w;mask.height=h;const im=mask.getContext('2d').createImageData(w,h);for(let i=0;i<w*h;i++)im.data[4*i+3]=m.effectiveCoverage[i];mask.getContext('2d').putImageData(im,0,0);g.globalCompositeOperation='destination-in';g.drawImage(mask,0,0);g.globalCompositeOperation='destination-over';g.drawImage(photo,0,0,w,h);
  const sourcePixels=photo.getContext('2d').getImageData(0,0,w,h).data,renderPixels=frame.getContext('2d').getImageData(0,0,w,h).data;
  let protectedProbes=0;for(let i=0;i<w*h;i+=137)if(m.effectiveCoverage[i]===0){for(let ch=0;ch<3;ch++)if(Math.abs(sourcePixels[i*4+ch]-renderPixels[i*4+ch])>2)throw Error('source pixel lost outside effective floor');protectedProbes++;}
  const cameraSignature=JSON.stringify(scene.floorZones.map(z=>z.plane.projection));
  const rotations=[];for(const angle of[45,90,179,359]){const a=performance.now();await c.adapter.applyProfile(profile,angle);rotations.push(performance.now()-a);if(JSON.stringify(c.adapter.visitSnapshot().scene.floorZones.map(z=>z.plane.projection))!==cameraSignature)throw Error('rotation changed camera');}
  const cachedStart=performance.now();await c.adapter.applyProfile(profile,0);const cachedMs=performance.now()-cachedStart;if(!c.adapter.lastHit)throw Error('expected frame cache hit');
  const png=cv=>cv.toDataURL('image/png').split(',')[1];return {frame:rendered,grid:png(grid),original:png(photo),productMs,cachedMs,rotations,protectedProbes,projections:scene.floorZones.map(z=>{const p=z.plane.projection;if(!p)return null;return {status:p.status,reason:p.reason,shear:p.shear,legacyAxisScale:p.legacyAxisScale,camera:p.cameraModel,floorPlane:p.floorPlane,samples:p.samples};}),diagnostics:c.adapter.geometryDiagnostics(profile,0)};
 },{raw,image,id});
 fs.mkdirSync(`${root}/${id}`,{recursive:true});const suffix=canvas?'-canvas':'';
 for(const[k,n]of[['original','01-original'],['grid',variant==='legacy'?'02-grid-current':'03-grid-v3'],['frame',variant==='legacy'?'04-legacy-render':'05-v3-render']])fs.writeFileSync(`${root}/${id}/${n}${suffix}.png`,Buffer.from(out[k],'base64'));
 const {frame,grid,original,...measurement}=out;results.push({id,variant,canvas,...measurement});console.log('PASS capture',id,variant,canvas?'Canvas':'WebGL');
 }
 assert.deepEqual(errors,[]);await p.close();
}
const previous=process.env.PPAI_PROJECTION_CASE&&fs.existsSync(root+'/matrix.json')?JSON.parse(fs.readFileSync(root+'/matrix.json','utf8')).results.filter(x=>!cases.includes(x.id)):[];
fs.writeFileSync(root+'/matrix.json',JSON.stringify({results:[...previous,...results]},null,2));
}finally{await browser.close();}
