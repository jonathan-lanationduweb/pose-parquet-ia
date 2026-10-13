import assert from 'node:assert/strict';
class FakeWorker { static all=[]; constructor(){this.sent=[];FakeWorker.all.push(this);}postMessage(m){this.sent.push(m);}terminate(){this.terminated=true;}finish(value=3){const m=this.sent.at(-1);this.onmessage({data:{id:m.id,albedo:{size:2,data:new Uint8ClampedArray(16).fill(value)},relief:{size:2,data:new Uint8ClampedArray(16)},etapes:{total:0,dessin:0,lecturePixels:0,relief:0}}});}}
globalThis.Worker=FakeWorker;globalThis.OffscreenCanvas=class{};
const {materialMapsAsync,enCache,clearMaterialCache,apercuAsync}=await import('../web/scene/material.js');
const config={pattern:'lames',width:.15,plankLength:1,textureSize:512};
const idle=materialMapsAsync({id:'idle',surface:{}},config,{priority:'background'}).catch(e=>e.message);const old=FakeWorker.all.at(-1);
const user=materialMapsAsync({id:'chosen',surface:{}},config);assert.equal(old.terminated,true);assert.match(await idle,/interrupted/);FakeWorker.all.at(-1).finish();const first=await user;assert.equal(first.size,2);assert.ok(enCache({id:'chosen'},config));
const calls=FakeWorker.all.at(-1).sent.length;assert.equal(await materialMapsAsync({id:'chosen'}, {...config,angle:90}),first);assert.equal(FakeWorker.all.at(-1).sent.length,calls);
const length=materialMapsAsync({id:'chosen',surface:{}},{...config,plankLength:2});FakeWorker.all.at(-1).finish(9);assert.notEqual(await length,first);
const size=materialMapsAsync({id:'chosen',surface:{}},{...config,textureSize:1024});FakeWorker.all.at(-1).finish();assert.notEqual(await size,first);
const revision=materialMapsAsync({id:'chosen',surface:{},atlas:{version:'new'}},config);FakeWorker.all.at(-1).finish();assert.notEqual(await revision,first);
const shared=materialMapsAsync({id:'promoted',surface:{}},config,{priority:'background'});const worker=FakeWorker.all.at(-1);assert.equal(materialMapsAsync({id:'promoted',surface:{}},config),shared);assert.ok(!worker.terminated);worker.finish();await shared;
clearMaterialCache();worker.onerror();await assert.rejects(materialMapsAsync({id:'exact',atlas:{url:'real-atlas.webp'},surface:{}},config),/substitution refused/);
await assert.rejects(apercuAsync({id:'exact',atlas:{url:'real-atlas.webp'}},'lames'),/requires its atlas worker/);
console.log('PASS: user priority, shared promotion, rotation reuse, length/size/version invalidation, exact failure safety');
