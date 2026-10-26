import assert from'node:assert/strict';import{physicalPattern,patternCellMeters}from'../web/scene/world-pattern.js';import{CameraModel}from'../web/scene/camera-model.js';import{FloorPlane}from'../web/scene/floor-plane.js';
const material={boardWidth:.15,boardLength:1.8};let probes=0;
for(const pattern of['lames','point-de-hongrie','baton-rompu'])for(const width of[.09,.092,.15]){
 const profile=physicalPattern(material,{pattern,width,plankLength:.5});const floor=new FloorPlane({origin:[0,1.5,3],axisU:[1,0,0],axisV:[0,0,1],normal:[0,1,0],widthMeters:4,depthMeters:8});
 for(const [u,v]of[[.132,.327],[-.716,2.319],[1.237,3.451]]){
  const expected=patternCellMeters(u,v,profile);assert.ok(expected);assert.ok(expected.jointDistance>=0);assert.equal(expected.boardId.length,3);
  for(const [w,h]of[[1920,1080],[390,844],[780,1688]]){const camera=new CameraModel({imageWidth:w,imageHeight:h,fx:w*.7});const world=floor.floorLocalToWorld(u,v),image=camera.project(world),local=floor.pixelToFloorLocal(image,camera);const actual=patternCellMeters(local.u,local.v,profile);assert.deepEqual(actual.boardId,expected.boardId);assert.ok(Math.abs(actual.jointDistance-expected.jointDistance)<1e-10);probes++;}
 }
}
const running=physicalPattern(material,{pattern:'lames',width:.09,plankLength:.5});
assert.deepEqual(patternCellMeters(.01,.01,running).boardId,[0,0,0]);assert.deepEqual(patternCellMeters(.01,.1,running).boardId,[0,1,0]);
assert.ok(patternCellMeters(.01,.09,running).jointDistance<1e-10);
console.log('PASS metric cells: board IDs, local UVs, physical joints, running bond, camera/viewport independence',probes);
