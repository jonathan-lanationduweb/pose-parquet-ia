/** Exact V5/V5.1 alpha + inverse-blend non-regression; no renderer changes. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {execFileSync} from 'node:child_process';
import * as next from '../web/scene/occlusion-refiner.js';
const old=await import('data:text/javascript;base64,'+Buffer.from(execFileSync('git',['show','d87781f:web/scene/occlusion-refiner.js'],{encoding:'utf8'})).toString('base64'));
let seed=1927;const random=()=>{seed=(Math.imul(seed,1664525)+1013904223)|0;return seed>>>24;};
const rows=[];
for(const [width,height] of [[12,12],[80,60],[390,844],[1000,700]]){
 for(const mode of ['empty','solid','legs-rug','grain']){
  const coarse=new Uint8ClampedArray(width*height),image=new Uint8ClampedArray(width*height*4);
  for(let y=0;y<height;y++)for(let x=0;x<width;x++){
   const i=y*width+x;
   coarse[i]=mode==='solid'?255:mode==='empty'?0:mode==='grain'?random():
     ((x%79<3&&y>40)||(x>width*.3&&x<width*.8&&y>height*.2&&y<height*.5)?255:0);
   image[i*4]=random();image[i*4+1]=random();image[i*4+2]=random();image[i*4+3]=255;
  }
  const times={old:[],next:[]};
  for(let run=0;run<6;run++){
   let t=performance.now();const a=old.refineOcclusion(coarse,image,width,height);times.old.push(performance.now()-t);
   t=performance.now();const b=next.refineOcclusion(coarse,image,width,height);times.next.push(performance.now()-t);
   assert.deepEqual(b.alpha,a.alpha);assert.deepEqual(b.backgrounds,a.backgrounds);
   assert.equal(b.changed,a.changed);assert.equal(b.boundaryPixels,a.boundaryPixels);
  }
  rows.push({width,height,mode,times});
 }
}
fs.mkdirSync('review/foreground-mask-v5-1',{recursive:true});
fs.writeFileSync('review/foreground-mask-v5-1/alpha-exact.json',JSON.stringify(rows,null,2));
console.log('PASS 16 alpha fixtures x 6; identical alpha, backgrounds, changed counts');
