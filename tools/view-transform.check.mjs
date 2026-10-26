import assert from 'node:assert/strict';import {createViewTransform}from'../web/product/view-transform.js';
for(const [width,height]of[[1440,900],[390,844]])for(const fit of['cover','contain'])for(const zoom of[.7,1,2.35]){
 const t=createViewTransform({imageWidth:1536,imageHeight:1024,viewportWidth:width,viewportHeight:height,zoom,offsetX:-30.123456,offsetY:44.987654,fit});
 for(const p of[{x:0,y:0},{x:1536,y:1024},{x:528.432,y:767.832}]){const b=t.toImage(t.toViewport(p));assert.ok(Math.hypot(p.x-b.x,p.y-b.y)<.5);}
}console.log('PASS view-transform: desktop/mobile cover/contain crop/zoom inverse <0.5 px');
