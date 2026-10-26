/** Pinhole/metric invariants, deliberately independent of a browser. */
import assert from 'node:assert/strict';import {metricFloor}from'../web/scene/floor-projection.js';import {apply}from'../web/scene/perspective.js';
const plane={quad:[{x:.3,y:.55},{x:.7,y:.55},{x:1,y:1},{x:0,y:1}],meters:{width:4,depth:6}};
const p=metricFloor(plane,{focalPx:800,heightM:1.5},{width:1200,height:800});
assert.notEqual(p.status,'NEEDS_MANUAL_GEOMETRY');const f=p.floorPlane;
const dot=(a,b)=>a.reduce((s,v,i)=>s+v*b[i],0);
assert.ok(Math.abs(dot(f.axisU,f.axisV))<1e-12);assert.ok(Math.abs(Math.hypot(...f.axisU)-1)<1e-12);
for(const [x,y]of [[0,0],[1,1],[-2,4],[4,6]]){const a=p.project(x,y),b=p.atPixel(a.x,a.y);assert.ok(Math.hypot(b.x-x,b.y-y)<1e-9);const w=f.originWorld.map((v,i)=>v+x*f.axisU[i]+y*f.axisV[i]);const c=p.cameraModel;assert.ok(Math.abs(a.x-(w[0]/w[2]*c.focalLength+c.principalPoint.x))<1e-8);}
const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
const hp=q=>[q.x,q.y,1];
for(const axis of [0,1]){const point=(t,s)=>p.project(axis?s:t,axis?t:s);const line=s=>cross(hp(point(0,s)),hp(point(1,s)));const vp=cross(line(0),line(1)),expected=p.cameraModel.vanishingPoints[axis];const residual=cross(vp,expected);assert.ok(Math.hypot(...residual)/Math.hypot(...vp)/Math.hypot(...expected)<1e-9);}
const widths=p.samples.map(s=>s.u);assert.ok(widths[0]<widths[1]&&widths[1]<widths[2]);
assert.equal(metricFloor({...plane,quad:plane.quad.map(()=>({x:0,y:0}))},{},{width:1200,height:800}).status,'NEEDS_MANUAL_GEOMETRY');
console.log('PASS camera-floor-plane: metric axes, pinhole projection, round trips, VP convergence, scale gate');
