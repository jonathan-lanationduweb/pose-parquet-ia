/** DEV-only, source-image coordinates. No independent camera or mask estimate. */
import {projectionRuntime,floorQuad} from '../scene/metric-runtime.js';
import {physicalPattern,patternCellMeters} from '../scene/world-pattern.js';
import {patternProfile,TILE_METERS} from '../scene/texture.js';
export const DEBUG_FLAGS=Object.freeze(['debugGrid','debugMasks','debugCamera','debugFloorPlane','debugScale','debugPattern']);
const make=(w,h)=>{const c=document.createElement('canvas');c.width=w;c.height=h;return c;};
function line(ctx,a,b,color,width=2,dash=[]){
 if(!a||!b||![a.x,a.y,b.x,b.y].every(Number.isFinite))return;
 ctx.strokeStyle=color;ctx.lineWidth=width;ctx.setLineDash(dash);ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke();
}
function segment(runtime,a,b){
 const {camera,floor}=runtime;
 let wa=floor.floorLocalToWorld(a[0],a[1]),wb=floor.floorLocalToWorld(b[0],b[1]);
 const za=camera.worldToCamera(wa)[2],zb=camera.worldToCamera(wb)[2];
 let lo=0,hi=1;
 for(const [bound,near]of[[camera.near,true],[camera.far,false]]){
  const aa=near?za-bound:bound-za,bb=near?zb-bound:bound-zb;
  if(aa<0&&bb<0)return null;
  if(aa<0)lo=Math.max(lo,aa/(aa-bb));
  if(bb<0)hi=Math.min(hi,aa/(aa-bb));
 }
 if(lo>hi)return null;
 const p=t=>wa.map((v,i)=>v+(wb[i]-v)*t);
 return [camera.project(p(lo)),camera.project(p(hi))];
}
function applyCoverage(canvas,masks,label=null){
 const ctx=canvas.getContext('2d'),im=ctx.getImageData(0,0,canvas.width,canvas.height),cover=masks.effectiveCoverage,labels=masks.labels;
 for(let i=0;i<cover.length;i++)im.data[i*4+3]=Math.round(im.data[i*4+3]*(label===null||labels[i]===label?cover[i]/255:0));
 ctx.putImageData(im,0,0);
}
const patternContexts=new WeakMap();
export function patternAt(snapshot,zone,pixel){
 let zones=patternContexts.get(snapshot);if(!zones){zones=new Map();patternContexts.set(snapshot,zones);}
 if(!zones.has(zone)){
  const {width,height}=snapshot.size,runtime=projectionRuntime(zone.plane,width,height),config=snapshot.config;
  const a=((config?.angle||0)+(zone.plane.rotationDeg||0))*Math.PI/180;
  zones.set(zone,runtime&&config?.material?{runtime,config,p:physicalPattern(config.material,config),scale:config.scale||1,a,cos:Math.cos(a),sin:Math.sin(a)}:null);
 }
 const context=zones.get(zone);if(!context)return null;
 const {runtime,config,p,scale,a,cos,sin}=context,hit=runtime.floor.pixelToFloorLocal(pixel,runtime.camera);if(!hit)return null;
 const u=hit.u+(zone.plane.origin?.u||0)+(config.patternOffset?.u||0),v=hit.v+(zone.plane.origin?.v||0)+(config.patternOffset?.v||0);
 const cell=patternCellMeters((u*cos-v*sin)/scale,(u*sin+v*cos)/scale,p);
 return cell?{...cell,zoneId:zone.id,pattern:p,scale,floor:{u:hit.u,v:hit.v},angle:a}:null;
}
export function scaleData(snapshot){
 const {config,scene,masks,size:{width,height}}=snapshot;
 if(!config?.material)return {available:false};
 const profile=patternProfile(config.material,config.pattern,config.width||null,config.plankLength||null),scale=config.scale||1;
 const zones=scene.floorZones.map((zone,index)=>{
  const runtime=projectionRuntime(zone.plane,width,height),box=masks.box(zone.id);if(!runtime||!box)return {id:zone.id,available:false};
  const samples={};
  for(const [name,k]of[['far',.12],['mid',.5],['near',.88]]){
   const y=Math.floor(box.y0+(box.y1-box.y0-1)*k),xs=[];
   for(let x=box.x0;x<box.x1;x++)if(masks.labels[y*width+x]===index+1&&masks.effectiveCoverage[y*width+x]>192)xs.push(x);
   if(!xs.length){samples[name]=null;continue;}
   const at={x:xs[Math.floor(xs.length/2)]+.5,y:y+.5},cell=patternAt(snapshot,zone,at);if(!cell){samples[name]=null;continue;}
   // Normal to the REAL board orientation, transformed back out of pattern space.
   const phi=cell.orientation,theta=cell.angle,nx=-Math.sin(phi),ny=Math.cos(phi),half=profile.width*scale/2;
   const du=(nx*Math.cos(theta)+ny*Math.sin(theta))*half,dv=(-nx*Math.sin(theta)+ny*Math.cos(theta))*half;
   const project=(u,v)=>runtime.camera.project(runtime.floor.floorLocalToWorld(u,v));
   const a=project(cell.floor.u-du,cell.floor.v-dv),b=project(cell.floor.u+du,cell.floor.v+dv);
   samples[name]=a&&b?{at,a,b,pixels:Math.hypot(a.x-b.x,a.y-b.y),boardId:cell.boardId}:null;
  }
  return {id:zone.id,available:true,samples};
 });
 return {available:true,boardWidthMeters:profile.width,boardLengthMeters:profile.length,physicalWidthMeters:profile.width*scale,physicalLengthMeters:profile.length*scale,scaleMultiplier:scale,absoluteScaleMeasured:false,jointWidthMeters:(config.jointWidth??config.material.jointWidthM??.0005)*scale,boardGapMeters:(config.material.surfaceFamily==='exterior_deck'?Number(config.material.spacingM)||0:0)*scale,effectiveJointWidthMeters:Math.max(config.jointWidth??config.material.jointWidthM??.0005,config.material.surfaceFamily==='exterior_deck'?Number(config.material.spacingM)||0:0)*scale,zones};
}
function paintBoardPixel(data,p,cell,alpha,jointWidth){
 const [a,b,t]=cell.boardId,hash=((Math.imul(a,73856093)^Math.imul(b,19349663)^Math.imul(t,83492791))>>>0);
 data[p]=64+(hash&127);data[p+1]=64+((hash>>>8)&127);data[p+2]=64+((hash>>>16)&127);data[p+3]=alpha;
 if(cell.jointDistance<jointWidth/2){data[p]=255;data[p+1]=235;data[p+2]=0;}
}
export function floorSpacePattern(snapshot){
 const config=snapshot.config;if(!config?.material)return null;
 const size=640,span=2,c=make(size,size),ctx=c.getContext('2d'),im=ctx.createImageData(size,size),p=physicalPattern(config.material,config),scale=config.scale||1,zone=snapshot.scene.floorZones[0];
 const theta=((config.angle||0)+(zone?.plane.rotationDeg||0))*Math.PI/180,cos=Math.cos(theta),sin=Math.sin(theta),origin=zone?.plane.origin||{u:0,v:0};
 const gap=config.material.surfaceFamily==='exterior_deck'?Number(config.material.spacingM)||0:0,joint=Math.max(config.jointWidth??config.material.jointWidthM??.0005,gap);
 for(let y=0;y<size;y++)for(let x=0;x<size;x++){
  const u=(x+.5)/size*span+origin.u+(config.patternOffset?.u||0),v=(y+.5)/size*span+origin.v+(config.patternOffset?.v||0);
  const cell=patternCellMeters((u*cos-v*sin)/scale,(u*sin+v*cos)/scale,p);
  if(cell)paintBoardPixel(im.data,(y*size+x)*4,cell,255,joint);
 }
 ctx.putImageData(im,0,0);return c;
}
export function buildDiagnosticLayers(snapshot,flags=DEBUG_FLAGS){
 if(!snapshot?.scene||!snapshot.masks||!snapshot.size)throw Error('No renderer snapshot');
 if(!Array.isArray(flags)||flags.some(k=>!DEBUG_FLAGS.includes(k)))throw Error('Unknown diagnostic flag');
 const {scene,masks,size:{width:w,height:h}}=snapshot;
 const layers={},metadata={imageSize:{width:w,height:h},gridSpacingMeters:.5,cameras:[],scale:scaleData(snapshot),warnings:[]};
 const enabled=name=>flags.includes(name),canvas=name=>layers[name]||(layers[name]=make(w,h));
 for(const flag of flags)canvas(flag);
 if(enabled('debugMasks')){
  const c=canvas('debugMasks'),ctx=c.getContext('2d'),im=ctx.createImageData(w,h),floor=masks.coverage,occ=masks.occlusion;
  for(let i=0;i<floor.length;i++){const f=floor[i]/255,o=(occ?.[i]||0)/255,over=Math.min(f,o),p=i*4;im.data[p]=Math.round(255*o);im.data[p+1]=Math.round(210*f*(1-o));im.data[p+2]=Math.round(255*over);im.data[p+3]=Math.round(120*Math.max(f,o));}
  ctx.putImageData(im,0,0);
 }
 scene.floorZones.forEach((zone,index)=>{
  const runtime=projectionRuntime(zone.plane,w,h);
  if(!runtime){metadata.warnings.push(zone.id+': no metric projection; no guessed grid');return;}
  const {camera,floor}=runtime;
  const vp=[floor.axisU,floor.axisV].map(axis=>camera.homogeneousDirection(axis));
  metadata.cameras.push({zoneId:zone.id,camera:camera.toJSON(),floorPlane:floor.toJSON(),viewProjection:camera.buildViewProjectionMatrix(),horizonLine:camera.horizonLine(floor),vanishingPoints:vp});
  if(enabled('debugGrid')){
   const c=make(w,h),ctx=c.getContext('2d'),quad=floorQuad(camera,floor),us=[quad[0],quad[2],quad[4],quad[6]],vs=[quad[1],quad[3],quad[5],quad[7]],u0=Math.min(...us),u1=Math.max(...us),v0=Math.min(...vs),v1=Math.max(...vs);
   for(const axis of[0,1]){
    const lo=Math.ceil((axis?v0:u0)*2),hi=Math.floor((axis?v1:u1)*2);
    if(hi-lo>4096)metadata.warnings.push(zone.id+': grid limited to 4096 lines per direction');
    for(let k=lo;k<=Math.min(hi,lo+4096);k++){
     const value=k/2,points=segment(runtime,axis?[u0,value]:[value,v0],axis?[u1,value]:[value,v1]);
     if(points)line(ctx,...points,k%2?'#ffffffaa':'#00d9b8',k%2?1:2);
    }
   }
   applyCoverage(c,masks,index+1);canvas('debugGrid').getContext('2d').drawImage(c,0,0);
  }
  if(enabled('debugCamera')){
   const ctx=canvas('debugCamera').getContext('2d'),hy=x=>camera.horizonAt(x,floor);
   line(ctx,{x:0,y:hy(0)},{x:w,y:hy(w)},'#ffd400',2,[12,6]);
   ctx.font=Math.max(12,w/75)+'px monospace';
   vp.forEach((p,i)=>{
    const finite=Math.abs(p[2])>1e-10,x=finite?p[0]/p[2]:Math.sign(p[0])*1e9,y=finite?p[1]/p[2]:h/2;
    const mx=Math.max(12,Math.min(w-12,x)),my=Math.max(18,Math.min(h-12,y));
    ctx.fillStyle='#ffd400';ctx.beginPath();ctx.arc(mx,my,6,0,Math.PI*2);ctx.fill();
    ctx.fillText('VP'+(i+1)+(x<0||x>w||y<0||y>h||!finite?' hors champ':''),Math.min(w-160,mx+9),my-9);
   });
  }
  for(const target of [...(enabled('debugCamera')?[canvas('debugCamera')]:[]),...(enabled('debugFloorPlane')?[canvas('debugFloorPlane')]:[])]){
   const ctx=target.getContext('2d'),origin=camera.project(floor.origin);
   for(const [u,v,color,label]of[[1,0,'#00e0c0','U 1 m'],[0,1,'#ffbd54','V 1 m']]){
    const end=camera.project(floor.floorLocalToWorld(u,v));line(ctx,origin,end,color,3);if(end){ctx.fillStyle=color;ctx.font='16px monospace';ctx.fillText(label,end.x+6,end.y);}
   }
   if(origin){ctx.fillStyle='#fff';ctx.beginPath();ctx.arc(origin.x,origin.y,5,0,Math.PI*2);ctx.fill();}
  }
 });
 if(enabled('debugScale')){
  const ctx=canvas('debugScale').getContext('2d');
  for(const zone of metadata.scale.zones||[])for(const [name,s]of Object.entries(zone.samples||{}))if(s){
   line(ctx,s.a,s.b,'#ff65e2',3);ctx.fillStyle='#ff65e2';ctx.font=Math.max(12,w/85)+'px monospace';ctx.fillText(name+' '+s.pixels.toFixed(1)+' px',s.b.x+5,s.b.y-7);
  }
 }
 if(enabled('debugPattern')){
  const c=canvas('debugPattern'),ctx=c.getContext('2d'),im=ctx.createImageData(w,h);
  // DEV CPU diagnostic uses the production board partition. Not a replacement GPU shader.
  for(let y=0;y<h;y++)for(let x=0;x<w;x++){
   const i=y*w+x,label=masks.labels[i];if(!label||!masks.effectiveCoverage[i])continue;
   const cell=patternAt(snapshot,scene.floorZones[label-1],{x:x+.5,y:y+.5});if(!cell)continue;
   paintBoardPixel(im.data,i*4,cell,Math.round(masks.effectiveCoverage[i]*.85),metadata.scale.effectiveJointWidthMeters/cell.scale);
  }
  ctx.putImageData(im,0,0);
 }
 metadata.layerAvailability=Object.fromEntries(flags.map(flag=>[flag,flag==='debugMasks'?true:flag==='debugScale'?Boolean(metadata.scale.available&&metadata.scale.zones?.some(z=>z.available)):flag==='debugPattern'?Boolean(snapshot.config?.material&&metadata.cameras.length):metadata.cameras.length>0]));
 let coverage=0,occlusion=0;for(let i=0;i<w*h;i++){coverage+=masks.coverage[i]/255;occlusion+=(masks.occlusion?.[i]||0)/255;}
 metadata.maskCoverage={floorFraction:coverage/(w*h),occluderFraction:occlusion/(w*h),domain:'entire source image; not segmentation accuracy'};
 const flat=enabled('debugPattern')?floorSpacePattern(snapshot):null;
 metadata.floorPatternPreview=flat?{imageSize:{width:640,height:640},boundsMeters:{u0:0,v0:0,u1:2,v1:2},cameraApplied:false}:null;
 return {layers,metadata,floorSpacePattern:flat};
}
export function composeDiagnostic(photo,layer){
 const c=make(photo.width,photo.height),ctx=c.getContext('2d');ctx.drawImage(photo,0,0);if(layer)ctx.drawImage(layer,0,0);return c;
}
export function rawMaskCanvas(snapshot,kind){
 const {width,height}=snapshot.size,c=make(width,height),ctx=c.getContext('2d'),im=ctx.createImageData(width,height),data=kind==='occluder'?snapshot.masks.occlusion:snapshot.masks.coverage;
 for(let i=0;i<width*height;i++){const p=i*4;im.data[p]=im.data[p+1]=im.data[p+2]=data?.[i]||0;im.data[p+3]=255;}ctx.putImageData(im,0,0);return c;
}
