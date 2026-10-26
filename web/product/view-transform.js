/** A single image/viewport affine transform, shared by every photo layer.
 * cover is intentional in the existing product; contain remains the explicit Fit action.
 */
export class ViewTransform {
  constructor({imageWidth,imageHeight,viewportWidth,viewportHeight,zoom=1,offsetX=0,offsetY=0,fit='cover'}){
    if(!(imageWidth>0&&imageHeight>0&&zoom>0))throw Error('Invalid image transform');
    Object.assign(this,{imageWidth,imageHeight,viewportWidth,viewportHeight,offsetX,offsetY});
    this.scale=(fit==='contain'?Math.min:Math.max)(viewportWidth/imageWidth,viewportHeight/imageHeight)*zoom;
  }
  imageToViewport({x,y}){return {x:x*this.scale+this.offsetX,y:y*this.scale+this.offsetY};}
  viewportToImage({x,y}){return {x:(x-this.offsetX)/this.scale,y:(y-this.offsetY)/this.scale};}
  toViewport(point){return this.imageToViewport(point);}
  toImage(point){return this.viewportToImage(point);}
  get css(){return `translate3d(${this.offsetX}px, ${this.offsetY}px, 0) scale(${this.scale})`;}
}
export const createViewTransform=options=>new ViewTransform(options);
