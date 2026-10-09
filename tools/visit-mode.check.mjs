import assert from 'node:assert/strict';
import { photoPoint, cameraPoint, floorDepth, buildVisitMesh } from '../web/product/visit-mode.js';
const aspect=1.5,tan=.4;
for(const depth of [1,3,10])for(const [u,v] of [[.1,.2],[.5,.5],[.8,.9]]) {
  const p=photoPoint(u,v,depth,aspect,tan);
  assert.ok(Math.abs(p[0]/p[2]/(2*aspect*tan)+.5-u)<1e-10);
  assert.ok(Math.abs(.5-p[1]/p[2]/(2*tan)-v)<1e-10);
}
const cam={x:.06,z:0,yaw:0};
const near=cameraPoint(photoPoint(.5,.5,2,aspect,tan),cam);
const far=cameraPoint(photoPoint(.5,.5,8,aspect,tan),cam);
assert.ok(Math.abs(near[0]/near[2])>3*Math.abs(far[0]/far[2]));
assert.ok(floorDepth(.9,.4,1.5,.5)<floorDepth(.6,.4,1.5,.5));
const size={width:120,height:80},coverage=new Uint8Array(120*80);
for(let y=40;y<80;y++)coverage.fill(255,y*120,(y+1)*120);
const mesh=buildVisitMesh({scene:{camera:{horizon:.4,heightM:1.5,fovDeg:60}},masks:{coverage,occlusion:null},size},24);
assert.ok(mesh.vertices.length>0&&[...mesh.vertices].every(Number.isFinite));
assert.ok(mesh.depths.every(x=>x>=.7&&x<=12));
console.log('PASS: projection initiale fidèle, parallaxe différentielle réelle, profondeur de sol et maillage bornés');
