import assert from 'node:assert/strict';
import { createRoomAnalysisClient } from '../web/product/room-analysis-client.js';
let posts = 0;
const original = globalThis.fetch;
globalThis.fetch = async () => { posts += 1; return {ok:true,status:200,json:async()=>({schema:'pose-parquet/analysis@2', marker:{value:1}})}; };
try {
  const client = createRoomAnalysisClient({base:'http://localhost'});
  const file = new File(['same photo bytes'], 'photo.jpg', {type:'image/jpeg'});
  const first = await client.analyzeRoom(file);
  first.analysis.marker.value = 99;
  const again = await client.analyzeRoom(new File(['same photo bytes'], 'renamed.jpg', {type:'image/jpeg'}));
  assert.equal(posts,1); assert.equal(again.cached,true); assert.equal(again.analysis.marker.value,1);
  await client.analyzeRoom(new File(['different photo'], 'photo.jpg', {type:'image/jpeg'}));
  assert.equal(posts,2);
  for (let i=0;i<4;i++) await client.analyzeRoom(new File([`other${i}`],'photo.jpg'));
  const evicted = await client.analyzeRoom(file);
  assert.equal(evicted.cached,undefined); assert.equal(posts,7);
  const errors = createRoomAnalysisClient({base:'http://localhost'});
  globalThis.fetch = async()=>{posts++;return {ok:false,status:500,json:async()=>({})};};
  await errors.analyzeRoom(file); await errors.analyzeRoom(file);
  assert.equal(posts,9);
  console.log('PASS: identical bytes reused, changed bytes reanalysed, mutation isolated, four-result eviction, errors never cached');
} finally { globalThis.fetch=original; }
