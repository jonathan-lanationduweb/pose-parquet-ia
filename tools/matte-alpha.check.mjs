import assert from 'node:assert/strict';import fs from'node:fs';import{refineOcclusion}from'../web/scene/occlusion-refiner.js';
const w=80,h=60,m=new Uint8Array(w*h),im=new Uint8ClampedArray(w*h*4);
for(let y=0;y<h;y++)for(let x=0;x<w;x++){
 const a=x>=25&&x<55&&y>=10&&y<50?x===25?.25:x===54?.75:1:0,i=y*w+x;
 m[i]=a?255:0;im.set([Math.round(180*(1-a)+20*a),Math.round(160*(1-a)+30*a),Math.round(130*(1-a)+40*a),255],i*4);
}
const before=m.slice(),result=refineOcclusion(m,im,w,h),samples=[result.alpha[30*w+25],result.alpha[30*w+54]];
fs.mkdirSync('review/visual-quality-s1-s8',{recursive:true});fs.writeFileSync('review/visual-quality-s1-s8/matte-alpha.json',JSON.stringify({expected:[64,191],actual:samples},null,2));
console.log({expected:[64,191],actual:samples});
assert.ok(Math.abs(samples[0]-64)<=3&&Math.abs(samples[1]-191)<=3,'image edge alpha was quantized to binary');
assert.deepEqual(m,before,'prior mutated');
assert.equal(result.alpha[30*w+40],255);assert.equal(result.alpha[30*w+10],0);
assert.deepEqual(refineOcclusion(m,im,w,h).alpha,result.alpha);
const flat=new Uint8ClampedArray(im.length).fill(128);
assert.deepEqual(refineOcclusion(m,flat,w,h).alpha,new Uint8ClampedArray(m),'ambiguous edge must retain prior');
console.log('PASS mixed pixel alpha, no global blur, confidence fallback, immutable deterministic prior');
