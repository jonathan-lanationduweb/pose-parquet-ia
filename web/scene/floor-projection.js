import { projectionRuntime } from './metric-runtime.js';
import { validateGeometry } from './geometry-validation.js';
import { CameraModel } from './camera-model.js';
import { FloorPlane } from './floor-plane.js';
/** One calibrated pinhole camera and an orthonormal metric ground plane.
 * The homography below is K [axisU axisV origin], not a second image warp.
 * Camera height is an explicit assumption, never a measured room dimension.
 */
import { squareToQuad, invert, apply } from './perspective.js';
export const GEOMETRY_VERSION = 'floor-projection-metric@1';
const dot=(a,b)=>a.reduce((s,v,i)=>s+v*b[i],0);
const mul=(a,s)=>a.map(v=>v*s);
const sub=(a,b)=>a.map((v,i)=>v-b[i]);
const unit=a=>mul(a,1/Math.hypot(...a));
const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
const column=(m,i)=>[m[i],m[i+3],m[i+6]];
export function metricFloor(plane,camera={},image={}) {
 const width=image.width,height=image.height;
 const fail=reason=>({version:GEOMETRY_VERSION,status:'NEEDS_MANUAL_GEOMETRY',reason});
 if(!(width>0&&height>0))return fail('missing-image-dimensions');
 const H=squareToQuad(plane.quad.map(p=>({x:p.x*width,y:p.y*height})));
 if(!H)return fail('degenerate-plane');
 // Convert the legacy unit-square homography to metres before decomposition.
 const old=H.map((v,i)=>i%3===0?v/plane.meters.width:i%3===1?v/plane.meters.depth:v);
 let focal=camera.focalPx;
 if(!(focal>0)&&camera.fovDeg>0&&camera.fovDeg<170)focal=width/(2*Math.tan(camera.fovDeg*Math.PI/360));
 const cx=width/2,cy=height/2;
 // The two columns encode the plane VPs even when the metadata lost focalPx.
 const a=column(old,0),b=column(old,1);
 const inferred=-((a[0]-cx*a[2])*(b[0]-cx*b[2])+(a[1]-cy*a[2])*(b[1]-cy*b[2]))/(a[2]*b[2]);
 let source='declared';
 if(!(focal>0)){focal=inferred>0?Math.sqrt(inferred):width*.7;source=inferred>0?'plane-orthogonality':'prior';}
 if(!(focal>width*.2&&focal<width*3))return fail('implausible-focal');
 const unproject=p=>[(p[0]-cx*p[2])/focal,(p[1]-cy*p[2])/focal,p[2]];
 let u=unit(unproject(a)),v0=unit(unproject(b));
 const shear=dot(u,v0);
 if(!Number.isFinite(shear)||Math.abs(shear)>.25)return fail('camera-plane-disagreement');
 // Symmetric orthogonalization, avoiding a preferred material/pattern axis.
 const diagonal=unit(u.map((x,i)=>x+v0[i])),anti=unit(sub(u,v0));
 u=mul(diagonal.map((x,i)=>x+anti[i]),Math.SQRT1_2);
 const v=mul(sub(diagonal,anti),Math.SQRT1_2);
 let normal=unit(cross(u,v));if(normal[1]<0)normal=mul(normal,-1);
 const heightM=Number.isFinite(camera.heightM)?camera.heightM:1.5;
 if(heightM<=0)return fail('invalid-camera-height');
 const oldOrigin=unproject(column(old,2)),distance=dot(normal,oldOrigin);
 if(!(distance>1e-8))return fail('plane-behind-camera');
 const origin=mul(oldOrigin,heightM/distance);
 const centralCamera=new CameraModel({imageWidth:width,imageHeight:height,fx:focal,fy:focal,cx,cy,heightM:heightM});
 const centralFloor=new FloorPlane({origin,axisU:u,axisV:v,normal,widthMeters:plane.meters.width,depthMeters:plane.meters.depth});
 const metric=centralCamera.floorHomography(centralFloor),inverse=invert(metric);
 if(!inverse)return fail('singular-projection');
 const cu=centralCamera.homogeneousDirection(u),cv=centralCamera.homogeneousDirection(v);
 const horizonY=centralCamera.horizonAt(cx,centralFloor); if(!Number.isFinite(horizonY)||horizonY>height*.85||horizonY< -height*.25)return fail('implausible-horizon');
 const project=(x,y)=>apply(metric,x,y);
 const atPixel=(x,y)=>apply(inverse,x,y);
 const widthAt=(x,y,plank=.09)=>{
  const q=atPixel(x,y),p=project(q.x,q.y),pu=project(q.x+plank,q.y),pv=project(q.x,q.y+plank);
  return {u:Math.hypot(pu.x-p.x,pu.y-p.y),v:Math.hypot(pv.x-p.x,pv.y-p.y)};
 };
 // Uniform samples below the horizon; reject poles or nonphysical scale jumps.
 const samples=[.2,.55,.9].map(k=>{const y=horizonY+(height-horizonY)*k;return {y,...widthAt(cx,y)};});
 const ratios=['u','v'].flatMap(axis=>samples.slice(1).map((s,i)=>s[axis]/samples[i][axis]));
 if(samples.some(s=>!Number.isFinite(s.u+s.v)||Math.max(s.u,s.v)>width*.3)||ratios.some(r=>r<.8||r>12))return fail('scale-sanity');
 const unitH=metric.map((x,i)=>i%3===0?x*plane.meters.width:i%3===1?x*plane.meters.depth:x);
 const confidence=source==='prior'||Math.abs(shear)>.05||!camera.heightM?'APPROXIMATE':'CALIBRATED_ASSUMED_SCALE';
 return {version:GEOMETRY_VERSION,imageWidth:width,imageHeight:height,status:confidence,source,assumedScale:true,legacyAxisScale:[Math.hypot(...unproject(a))*heightM/distance,Math.hypot(...unproject(b))*heightM/distance],shear,
  cameraModel:{projection:'pinhole',focalLength:focal,principalPoint:{x:cx,y:cy},position:[0,0,0],rotation:[1,0,0,0,1,0,0,0,1],heightM,horizon:horizonY/height,vanishingPoints:[cu,cv]},
  floorPlane:{originWorld:origin,axisU:u,axisV:v,normal,widthMeters:plane.meters.width,depthMeters:plane.meters.depth},
  metric, inverse, H:unitH, M:invert(unitH),samples,project,atPixel,widthAt};
}
/** No pattern, material, screen crop or rotation can change this calibration. */
export function installMetricProjection(scene) {
 const query=typeof location!=='undefined'?new URLSearchParams(location.search):null;
 // Metric projection is the product path. The historical renderer is an explicit DEV comparison only.
 const legacy=Boolean(query?.get('dev')==='1'&&query.get('renderer')==='legacy');
 for(const z of scene.floorZones){
  if(legacy){z.plane.projection=null;continue;}
  const {project,atPixel,widthAt,...serializable}=metricFloor(z.plane,scene.camera,scene.image);
  z.plane.projection=serializable;
 }
 if(!legacy){
  for(const zone of scene.floorZones){
   const runtime=projectionRuntime(zone.plane,scene.image.width,scene.image.height);
   zone.geometryValidation=runtime?validateGeometry(runtime.source,runtime.floor,scene,zone):{status:'failed',reasons:[zone.plane.projection.reason]};
  }
  const validations=scene.floorZones.map(z=>z.geometryValidation);
  scene.geometryValidation={status:validations.some(v=>v.status==='failed')?'failed':validations.some(v=>v.status==='degraded')?'degraded':'reliable',zones:validations,reasons:[...new Set(validations.flatMap(v=>v.reasons))]};
 }
 if(scene.geometryValidation)scene.geometryValidation.decision=scene.geometryValidation.status==='failed'?'MANUAL_REQUIRED':scene.geometryValidation.status==='degraded'?'APPROXIMATE':'AUTO_RENDER';
 scene.geometryVersion=legacy?'legacy':GEOMETRY_VERSION;
 return scene;
}
