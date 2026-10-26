import assert from'node:assert/strict';import{CameraModel}from'../web/scene/camera-model.js';import{FloorPlane}from'../web/scene/floor-plane.js';import{validateGeometry,visibleFloorCoverage}from'../web/scene/geometry-validation.js';
const c=new CameraModel({imageWidth:1200,imageHeight:800,fx:800}),f=new FloorPlane({origin:[0,1.5,3],axisU:[1,0,0],axisV:[0,0,1],normal:[0,1,0],widthMeters:4,depthMeters:6});
const polygon=[{x:.1,y:.65},{x:.9,y:.65},{x:.9,y:.95},{x:.1,y:.95}],zone={mask:{polygon,holes:[]},plane:{}};const scene={camera:{horizon:.5,vanishingPoints:[{x:1,y:0,w:0},{x:.5,y:.5}]},occluders:[]};
const reliable=validateGeometry(c,f,scene,zone);assert.equal(reliable.status,'reliable',JSON.stringify(reliable));assert.equal(reliable.floorCoverage,1);assert.ok(reliable.projectedScale.score>.999999);
assert.equal(validateGeometry(c,f,{...scene,camera:{horizon:.504}},zone).status,'degraded');assert.equal(validateGeometry(c,f,{...scene,camera:{horizon:.7}},zone).status,'failed');
assert.equal(validateGeometry(new CameraModel({imageWidth:1200,imageHeight:800,fx:800,heightM:9}),f,scene,zone).status,'failed');
const hole=[{x:.3,y:.7},{x:.6,y:.7},{x:.6,y:.9},{x:.3,y:.9}];const withHole={...zone,mask:{polygon,holes:[hole]}};
assert.ok(visibleFloorCoverage(withHole,[{polygon:hole}])>.99);assert.ok(visibleFloorCoverage(withHole,[])<.85);
assert.ok(reliable.projectedScale.near.pixels>reliable.projectedScale.mid.pixels&&reliable.projectedScale.mid.pixels>reliable.projectedScale.far.pixels);
console.log('PASS geometry validation: horizon reprojection, no height clamp, perspective scale, visible-floor coverage excluding foreground, three UX statuses');

// A rotated floor has the SAME horizon, camera height and 1/depth scale.
// Only comparison to the photographed architecture catches its wrong yaw.
const angle=12*Math.PI/180;
const rotated=new FloorPlane({origin:f.origin,axisU:[Math.cos(angle),0,Math.sin(angle)],axisV:[-Math.sin(angle),0,Math.cos(angle)],normal:[0,1,0],widthMeters:4,depthMeters:6});
const rejected=validateGeometry(c,rotated,scene,zone);
assert.equal(rejected.decision,'MANUAL_REQUIRED');
assert.ok(rejected.reasons.includes('architectural_directions_mismatch'));
assert.ok(rejected.horizonErrorPx<1e-8);
assert.equal(validateGeometry(c,f,{...scene,camera:{horizon:.5}},zone).decision,'APPROXIMATE');
assert.equal(validateGeometry(c,f,{...scene,camera:{...scene.camera,vanishingPoints:[...scene.camera.vanishingPoints].reverse()}},zone).decision,'AUTO_RENDER');
const scaled=c.resized(390,844);
assert.ok(validateGeometry(scaled,f,scene,zone).architecture.maxErrorDeg<1e-7);
assert.equal(validateGeometry(c,f,{...scene,camera:{...scene.camera,vanishingPoints:[{x:NaN,y:0}, {x:.5,y:.5}]}},zone).decision,'APPROXIMATE');
console.log('PASS architecture: wrong yaw blocked despite matching horizon, missing evidence approximate, axis permutation/infinity/resize preserved');