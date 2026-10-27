import assert from 'node:assert/strict';
import {buildShadingMap,buildResidualMaps} from '../web/scene/shading.js';
const width=320,height=200,coverage=new Uint8Array(width*height).fill(255);
const data=new Uint8ClampedArray(width*height*4);
for(let i=0;i<width*height;i++){data.set([150,150,150,255],i*4);}
for(let y=70;y<140;y++)for(let x=130;x<175;x++)coverage[y*width+x]=0;
const source={width,height,data};
const flat=buildShadingMap(source,coverage,{blurRadius:.045,contact:.9});
// A white object on a uniformly lit floor must not acquire a fabricated black outline.
for(let i=0;i<flat.width*flat.height;i++)assert.ok(flat.rgba[i*4+3]>.999);
for(let y=0;y<height;y++)for(let x=0;x<width;x++){
 const dark=(x>=176&&x<198&&y>=100&&y<150);
 const v=dark?45:(x%32<2?85:150);
 data.set([v,v,v,255],(y*width+x)*4);
}
const shade=buildShadingMap(source,coverage,{blurRadius:.045,contact:.4});
const residual=buildResidualMaps(source,coverage,shade).fullRes();
const avg=(x0,x1,y0,y1)=>{let sum=0,n=0;for(let y=y0;y<y1;y++)for(let x=x0;x<x1;x++){sum+=residual.shadow[y*width+x];n++;}return sum/n;};
assert.ok(avg(180,192,112,140)>.1,'Observed contact shadow lost');
assert.ok(avg(32,34,20,60)<.02,'Old tile joint leaked into contact shadows');
console.log('PASS observed shadows preserved, tile joints suppressed, no invented dark outline');
