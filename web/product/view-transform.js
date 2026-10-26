/** Image coordinates are shared by photo, mask, floor, objects and brush. */
export function createViewTransform({imageWidth,imageHeight,viewportWidth,viewportHeight,zoom=1,offsetX=0,offsetY=0,fit='cover'}) {
 const scale=(fit==='contain'?Math.min:Math.max)(viewportWidth/imageWidth,viewportHeight/imageHeight)*zoom;
 return {imageWidth,imageHeight,viewportWidth,viewportHeight,scale,offsetX,offsetY,
  toViewport:({x,y})=>({x:x*scale+offsetX,y:y*scale+offsetY}),
  toImage:({x,y})=>({x:(x-offsetX)/scale,y:(y-offsetY)/scale}),
  css:`translate3d(${offsetX}px, ${offsetY}px, 0) scale(${scale})`};
}
