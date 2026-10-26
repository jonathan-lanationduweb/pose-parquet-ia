import {cross,normalized,add,times} from './camera-model.js';
export const GEOMETRY_LIMITS=Object.freeze({architectureReliableDeg:2,architectureFailedDeg:8,horizonReliablePx:2,horizonFailedFraction:.08,minHeightM:.8,maxHeightM:3.5,minWidthM:1.5,maxWidthM:12,minCoverage:.65,coverageSamples:32,maxScaleRatio:8,maxBoardImageFraction:.35});
export function inside(p,polygon){let value=false;for(let i=0,j=polygon.length-1;i<polygon.length;j=i++){
 const a=polygon[i],b=polygon[j];if((a.y>p.y)!==(b.y>p.y)&&p.x<(b.x-a.x)*(p.y-a.y)/(b.y-a.y)+a.x)value=!value;
}return value;}
function hull(points){const sorted=[...points].sort((a,b)=>a.x-b.x||a.y-b.y),turn=(a,b,c)=>(b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x);const half=values=>{const out=[];for(const p of values){while(out.length>1&&turn(out.at(-2),out.at(-1),p)<=0)out.pop();out.push(p);}return out;};return [...half(sorted).slice(0,-1),...half(sorted.reverse()).slice(0,-1)];}
/** Coverage is evaluated INSIDE the convex visible-floor envelope, with known
 * foreground excluded. It is never a percentage of the entire photograph.
 * This is a sampled completeness diagnostic, not segmentation ground truth.
 */
export function visibleFloorCoverage(zone,occluders=[],samples=GEOMETRY_LIMITS.coverageSamples){
 const polygon=zone.runtimeMask||zone.mask.polygon;if(polygon.length<3)return 0;
 const envelope=hull(polygon);if(envelope.length<3)return 0;
 const xs=envelope.map(p=>p.x),ys=envelope.map(p=>p.y),x0=Math.min(...xs),x1=Math.max(...xs),y0=Math.min(...ys),y1=Math.max(...ys);
 let domain=0,covered=0;
 for(let y=0;y<samples;y++)for(let x=0;x<samples;x++){
  const p={x:x0+(x+.5)/samples*(x1-x0),y:y0+(y+.5)/samples*(y1-y0)};
  if(!inside(p,envelope)||occluders.some(o=>inside(p,o.polygon)&&!(o.holes||[]).some(h=>inside(p,h))))continue;
  domain++;if(inside(p,polygon)&&!(zone.mask.holes||[]).some(h=>inside(p,h)))covered++;
 }
 return domain?covered/domain:0;
}
/** Compare projected axes with architectural evidence in IMAGE space.
 * A self-consistent camera can still be wrong for the photograph. Check both
 * line families at several floor locations, allowing swapped axes and VPs at
 * infinity. Angles avoid exploding pixel errors for distant vanishing points.
 * These supplied VPs remain estimates, not independent visual ground truth.
 */
export function architecturalAlignment(camera,plane,scene,zone){
 const declared=scene.camera?.vanishingPoints;
 if(!Array.isArray(declared)||declared.length!==2)return null;
 const measured=declared.map(v=>[v.x*camera.imageWidth,v.y*camera.imageHeight,v.w??1]);
 if(measured.some(v=>!v.every(Number.isFinite)||Math.hypot(...v)<1e-10))return null;
 const projected=[plane.axisU,plane.axisV].map(axis=>camera.homogeneousDirection(axis));
 const polygon=zone.runtimeMask||zone.mask.polygon;
 const xs=polygon.map(p=>p.x),ys=polygon.map(p=>p.y),points=[];
 for(const y of[.15,.5,.85])for(const x of[.15,.5,.85]){
  const p={x:Math.min(...xs)+x*(Math.max(...xs)-Math.min(...xs)),y:Math.min(...ys)+y*(Math.max(...ys)-Math.min(...ys))};
  if(inside(p,polygon))points.push({x:p.x*camera.imageWidth,y:p.y*camera.imageHeight});
 }
 if(!points.length)return null;
 const angle=(a,b,p)=>{
  const ax=a[0]-p.x*a[2],ay=a[1]-p.y*a[2],bx=b[0]-p.x*b[2],by=b[1]-p.y*b[2];
  if(Math.hypot(ax,ay)<1e-8||Math.hypot(bx,by)<1e-8)return null;
  return Math.atan2(Math.abs(ax*by-ay*bx),Math.abs(ax*bx+ay*by))*180/Math.PI;
 };
 const candidates=[[0,1],[1,0]].map(order=>{
  const errors=points.flatMap(p=>projected.map((vp,i)=>angle(vp,measured[order[i]],p))).filter(Number.isFinite);
  return errors.length?{maxErrorDeg:Math.max(...errors),meanErrorDeg:errors.reduce((a,b)=>a+b,0)/errors.length,order,samples:errors.length}:null;
 }).filter(Boolean).sort((a,b)=>a.maxErrorDeg-b.maxErrorDeg);
 return candidates[0]||null;
}
export function validateGeometry(camera,plane,scene,zone,limits=GEOMETRY_LIMITS){
 const reasons=[],failures=[],degraded=[];
 const mark=(reason,failed=false)=>(failed?failures:degraded).push(reason);
 const horizon=camera.horizonAt(camera.cx,plane),provided=scene.camera?.horizon;
 const horizonErrorPx=Number.isFinite(provided)&&Number.isFinite(horizon)?Math.abs(provided*camera.imageHeight-horizon):null;
 if(horizonErrorPx===null)mark('horizon_not_measured');else if(horizonErrorPx>limits.horizonReliablePx)mark('horizon_reprojection_mismatch',horizonErrorPx>camera.imageHeight*limits.horizonFailedFraction);
 const architecture=architecturalAlignment(camera,plane,scene,zone);
 if(!architecture)mark('architecture_not_measured');
 else if(architecture.maxErrorDeg>limits.architectureReliableDeg)mark('architectural_directions_mismatch',architecture.maxErrorDeg>limits.architectureFailedDeg);
 const cameraHeight=plane.cameraHeight(camera);
 if(cameraHeight<limits.minHeightM||cameraHeight>limits.maxHeightM||camera.heightM<limits.minHeightM||camera.heightM>limits.maxHeightM)mark('camera_height_implausible',true);
 const polygon=zone.runtimeMask||zone.mask.polygon,world=polygon.map(p=>plane.pixelToFloorLocal({x:p.x*camera.imageWidth,y:p.y*camera.imageHeight},camera)).filter(Boolean);
 const span=key=>world.length?Math.max(...world.map(p=>p[key]))-Math.min(...world.map(p=>p[key])):0;
 const roomWidthMeters=Math.min(span('u'),span('v')),depthMeters=Math.max(span('u'),span('v'));
 if(roomWidthMeters<limits.minWidthM||roomWidthMeters>limits.maxWidthM)mark('visible_floor_width_implausible');
 const floorCoverage=visibleFloorCoverage(zone,scene.occluders);
 if(floorCoverage<limits.minCoverage)mark('visible_floor_coverage_low',floorCoverage<.1);
 const ys=polygon.map(p=>p.y*camera.imageHeight),top=Math.min(...ys),bottom=Math.max(...ys);
 const forward=camera.cameraDirectionToWorld([0,0,1]);let across;
 try{across=normalized(cross(plane.normal,forward));}catch{mark('floor_facing_camera',true);across=plane.axisU;}
 const samples={};
 for(const [name,k] of [['far',.15],['mid',.5],['near',.9]]){
  const y=top+k*(bottom-top);let pixel=null;
  for(let i=0;i<41;i++){const x=(i+.5)/41*camera.imageWidth;if(inside({x:x/camera.imageWidth,y:y/camera.imageHeight},polygon))pixel={x,y};}
  const point=pixel&&camera.pixelToFloor(pixel,plane);
  if(!point){mark('floor_not_visible',true);continue;}
  const a=camera.project(add(point,times(across,-.045))),b=camera.project(add(point,times(across,.045)));
  const pixels=Math.hypot(b.x-a.x,b.y-a.y),depth=camera.worldToCamera(point)[2];samples[name]={pixels,depth,at:pixel};
 }
 let score=0;
 if(Object.keys(samples).length===3){
  const {near,mid,far}=samples,factors=[near,mid,far].map(s=>s.pixels*s.depth),mean=factors.reduce((a,b)=>a+b)/3;
  score=Math.max(0,1-Math.max(...factors.map(x=>Math.abs(x-mean)/mean)));
  if(!(near.depth<mid.depth&&mid.depth<far.depth&&near.pixels>mid.pixels&&mid.pixels>far.pixels))mark('scale_non_monotonic',true);
  if(near.pixels/mid.pixels>limits.maxScaleRatio||mid.pixels/far.pixels>limits.maxScaleRatio)mark('scale_depth_jump',true);
  if(near.pixels>camera.imageWidth*limits.maxBoardImageFraction)mark('foreground_scale_explosion',true);
  if(far.pixels<.25)mark('far_scale_microscopic');
 }
 if(zone.plane.projection?.status==='APPROXIMATE')mark('camera_estimate_approximate');
 reasons.push(...failures,...degraded);
 const status=failures.length?'failed':degraded.length?'degraded':'reliable';
 return {status,decision:status==='failed'?'MANUAL_REQUIRED':status==='degraded'?'APPROXIMATE':'AUTO_RENDER',architecture,horizonErrorPx,cameraHeight,roomWidthMeters,depthMeters,dimensionsKind:'visible-floor-spans-not-room-measurements',projectedScale:{...samples,boardWidthMeters:.09,score},floorCoverage,coverageDomain:'convex-visible-floor-envelope-minus-foreground',absoluteScaleMeasured:false,reasons};
}
