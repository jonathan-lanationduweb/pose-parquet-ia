import assert from 'node:assert/strict';
import {foregroundCompositeSource,refineOcclusion}from'../web/scene/occlusion-refiner.js';
// Known photograph C=aF+(1-a)B. Replacing its background must not square a.
for(const a of [.25,.5,.75])for(const f of [.5,1]){
 const F=[20,30,40],B=[180,160,130],N=[90,100,110],alpha=Math.round(a*255),q=alpha/255;
 const source={width:1,height:1,data:new Uint8ClampedArray([...F.map((v,k)=>Math.round(q*v+(1-q)*B[k])),255])};
 const original=source.data.slice(),coverage=Uint8Array.of(Math.round(f*255)),occ=Uint8Array.of(alpha);
 const plate=foregroundCompositeSource(source,coverage,occ,occ,[0,...B]);
 const t=coverage[0]/255*(1-q);
 for(let k=0;k<3;k++){
  const actual=plate.data[k]*(1-t)+N[k]*t,expected=source.data[k]+t*(N[k]-B[k]);
  assert.ok(Math.abs(actual-expected)<=1,{a,f,k,actual,expected});
 }
 assert.deepEqual(source.data,original,'Original photo was modified');
 assert.equal(foregroundCompositeSource(source,coverage,Uint8Array.of(0),occ,[0,...B]),source,'Manual add ignored');
}
const w=80,h=60,m=new Uint8Array(w*h),im=new Uint8ClampedArray(w*h*4);
for(let y=0;y<h;y++)for(let x=0;x<w;x++){
 const a=x>=25&&x<55&&y>=10&&y<50?x===25?.25:x===54?.75:1:0,i=y*w+x;
 m[i]=a?255:0;im.set([Math.round(180*(1-a)+20*a),Math.round(160*(1-a)+30*a),Math.round(130*(1-a)+40*a),255],i*4);
}
const result=refineOcclusion(m,im,w,h);
const coverage=new Uint8Array(w*h).fill(255),source={width:w,height:h,data:im};
const plate=foregroundCompositeSource(source,coverage,result.alpha,result.alpha,result.backgrounds);
for(const x of[25,54]){
 const i=30*w+x,p=i*4;
 assert.ok(Math.abs(plate.data[p]-20)<=3,'Old floor colour survives edge');
}
for(const x of[10,40])assert.deepEqual([...plate.data.slice((30*w+x)*4,(30*w+x)*4+4)],[...im.slice((30*w+x)*4,(30*w+x)*4+4)],'Opaque source changed');
console.log('PASS inverse blend: old-floor contamination removed, partial coverage, original pixels, manual override');
