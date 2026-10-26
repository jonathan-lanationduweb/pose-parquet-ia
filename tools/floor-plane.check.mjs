import assert from 'node:assert/strict';import{FloorPlane}from'../web/scene/floor-plane.js';
const p=new FloorPlane({origin:[1,2,3],axisU:[1,0,0],axisV:[0,0,1],widthMeters:4,depthMeters:8});
for(const [u,v]of[[0,0],[-3,7],[.092,.5]]){const q=p.worldToFloorLocal(p.floorLocalToWorld(u,v));assert.ok(Math.abs(q.u-u)+Math.abs(q.v-v)<1e-10);}
assert.throws(()=>new FloorPlane({origin:[0,0,0],axisU:[1,0,0],axisV:[1,0,0],widthMeters:1,depthMeters:1}));
console.log('PASS FloorPlane: orthonormal metre basis, stable origin, local/world conversion');
