import assert from'node:assert/strict';import{ViewTransform}from'../web/product/view-transform.js';
let probes=0;for(const [imageWidth,imageHeight,viewportWidth,viewportHeight]of[[1920,1080,1440,900],[1080,1920,390,844],[1600,1200,390,844],[1600,900,1440,900]])for(const fit of['cover','contain'])for(const zoom of[.7,1,2.35]){
 const t=new ViewTransform({imageWidth,imageHeight,viewportWidth,viewportHeight,zoom,offsetX:-31.123456,offsetY:44.987654,fit});
 for(const p of[{x:0,y:0},{x:imageWidth,y:imageHeight},{x:imageWidth*.372,y:imageHeight*.721}]){const b=t.viewportToImage(t.imageToViewport(p));assert.ok(Math.hypot(p.x-b.x,p.y-b.y)<.5);probes++;}
}console.log('PASS ViewTransform: portrait/4:3/16:9, desktop/mobile, cover/contain/zoom/crop inverse <0.5px',probes);
