import assert from 'node:assert/strict';
import {CameraModel,transform4} from '../web/scene/camera-model.js';
import {FloorPlane} from '../web/scene/floor-plane.js';
const floor=new FloorPlane({origin:[0,1.5,3],axisU:[1,0,0],axisV:[0,0,1],normal:[0,1,0],widthMeters:4,depthMeters:8});
for(const dims of [[1920,1080],[1080,1920],[1440,900]])for(const pitch of[0,.15,-.1]){
 const c=Math.cos(pitch),s=Math.sin(pitch),camera=new CameraModel({imageWidth:dims[0],imageHeight:dims[1],fx:900,fy:850,cx:dims[0]*.47,cy:dims[1]*.53,skew:12,rotation:[1,0,0,0,c,-s,0,s,c],center:[.2,-.1,-.3]});
 for(const u of[-2,0,1.4])for(const v of[0,2,8]){
  const p=floor.floorLocalToWorld(u,v),image=camera.project(p),hit=camera.pixelToFloor(image,floor);assert.ok(hit);assert.ok(Math.hypot(...p.map((x,i)=>x-hit[i]))<1e-8);
  const clip=transform4(camera.buildViewProjectionMatrix(),[...p,1]);const gpu={x:(clip[0]/clip[3]+1)*dims[0]/2,y:(1-clip[1]/clip[3])*dims[1]/2};assert.ok(Math.hypot(gpu.x-image.x,gpu.y-image.y)<1e-8);
 }
}
const camera=new CameraModel({imageWidth:1920,imageHeight:1080,fx:900,heightM:1.5});
for(const z of[2,4,8]){const a=camera.project([-.045,1.5,z]),b=camera.project([.045,1.5,z]);assert.ok(Math.abs((b.x-a.x)-900*.09/z)<1e-10);}
assert.equal(camera.pixelToFloor({x:960,y:100},floor),null);
assert.throws(()=>new CameraModel({imageWidth:100,imageHeight:100,fx:100,rotation:[1,0,0,0,1,0,0,0,-1]}));
console.log('PASS CameraModel: pinhole, full K/skew/pose, viewProjection <1px, ray/floor round trips, 90mm theoretical 1/depth');
