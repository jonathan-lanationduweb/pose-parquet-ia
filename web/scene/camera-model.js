/** Row-major CPU matrices. World/camera: +X right, +Y down, +Z forward.
 * Image pixels: top-left origin. WebGL NDC: +Y up, depth in [-1,1].
 * Only columnMajor() changes storage for gl.uniformMatrix4fv; it never changes axes.
 */
export const dot = (a, b) => a.reduce((sum, x, i) => sum + x * b[i], 0);
export const add = (a, b) => a.map((x, i) => x + b[i]);
export const subtract = (a, b) => a.map((x, i) => x - b[i]);
export const times = (a, k) => a.map(x => x * k);
export const cross = (a, b) => [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]];
export const normalized = a => { const n = Math.hypot(...a); if (!(n > 1e-12)) throw Error('Zero direction'); return times(a, 1/n); };
export const multiply4 = (a, b) => Array.from({length:16}, (_, i) => {
  const row = Math.floor(i/4), col = i%4;
  return [0,1,2,3].reduce((sum,k) => sum + a[row*4+k]*b[k*4+col], 0);
});
export const transform4 = (m, p) => [0,1,2,3].map(r => dot(m.slice(r*4,r*4+4), p));
export const columnMajor = m => new Float32Array(m.map((_,i) => m[(i%4)*4+Math.floor(i/4)]));
const IDENTITY = [1,0,0,0,1,0,0,0,1];

export class CameraModel {
  constructor({imageWidth,imageHeight,fx,fy=fx,cx=imageWidth/2,cy=imageHeight/2,skew=0,
    rotation=IDENTITY,center=[0,0,0],heightM=1.5,near=.01,far=1000}) {
    if (![imageWidth,imageHeight,fx,fy,near,far].every(x=>Number.isFinite(x)&&x>0) || far<=near) throw Error('Invalid camera intrinsics');
    if (![cx,cy,skew,heightM,...rotation,...center].every(Number.isFinite)) throw Error('Non-finite camera');
    if (rotation.length!==9 || center.length!==3) throw Error('Invalid camera pose');
    for(let i=0;i<3;i++) for(let j=0;j<3;j++) if(Math.abs(dot(rotation.slice(i*3,i*3+3),rotation.slice(j*3,j*3+3))-(i===j?1:0))>1e-6) throw Error('Non-orthonormal camera rotation');
    if(dot(cross(rotation.slice(0,3),rotation.slice(3,6)),rotation.slice(6,9))<.999999) throw Error('Reflected camera rotation');
    Object.assign(this,{imageWidth,imageHeight,fx,fy,cx,cy,skew,heightM,near,far});
    this.R=[...rotation];this.C=[...center];this.K=[fx,skew,cx,0,fy,cy,0,0,1];
    this.view=this.buildViewMatrix();this.projection=this.buildProjectionMatrix();
    this.viewProjection=multiply4(this.projection,this.view);
  }
  worldToCamera(point) { const p=subtract(point,this.C); return [0,1,2].map(i=>dot(this.R.slice(i*3,i*3+3),p)); }
  cameraDirectionToWorld(direction) { return [0,1,2].map(i=>this.R[i]*direction[0]+this.R[i+3]*direction[1]+this.R[i+6]*direction[2]); }
  project(point) {
    const [x,y,z]=this.worldToCamera(point);if (!(z>0)) return null;
    return {x:(this.fx*x+this.skew*y)/z+this.cx,y:this.fy*y/z+this.cy,depth:z};
  }
  ray(point) {
    const y=(point.y-this.cy)/this.fy,x=(point.x-this.cx-this.skew*y)/this.fx;
    return {origin:[...this.C],direction:normalized(this.cameraDirectionToWorld([x,y,1]))};
  }
  pixelToFloor(point, plane) {
    const ray=this.ray(point),denominator=dot(plane.normal,ray.direction);
    if(Math.abs(denominator)<1e-10)return null;
    const distance=dot(plane.normal,subtract(plane.origin,this.C))/denominator;
    if(!(distance>0))return null;
    const world=add(ray.origin,times(ray.direction,distance));
    return this.worldToCamera(world)[2]>=this.near?world:null;
  }
  buildViewMatrix() {
    const r=this.R,c=this.C;
    return [r[0],r[1],r[2],-dot(r.slice(0,3),c),r[3],r[4],r[5],-dot(r.slice(3,6),c),r[6],r[7],r[8],-dot(r.slice(6,9),c),0,0,0,1];
  }
  buildProjectionMatrix() {
    const {imageWidth:w,imageHeight:h,fx,fy,cx,cy,skew,near:n,far:f}=this;
    return [2*fx/w,2*skew/w,2*cx/w-1,0,0,-2*fy/h,1-2*cy/h,0,0,0,(f+n)/(f-n),-2*f*n/(f-n),0,0,1,0];
  }
  buildViewProjectionMatrix() { return [...this.viewProjection]; }
  homogeneousDirection(worldDirection) {
    const d=[0,1,2].map(i=>dot(this.R.slice(i*3,i*3+3),worldDirection));
    return [this.fx*d[0]+this.skew*d[1]+this.cx*d[2],this.fy*d[1]+this.cy*d[2],d[2]];
  }
  horizonLine(plane) {
    const n=[0,1,2].map(i=>dot(this.R.slice(i*3,i*3+3),plane.normal));
    const a=n[0]/this.fx,b=n[1]/this.fy-n[0]*this.skew/(this.fx*this.fy);
    return [a,b,n[2]-a*this.cx-b*this.cy];
  }
  horizonAt(x,plane) { const [a,b,c]=this.horizonLine(plane);return Math.abs(b)>1e-10?-(a*x+c)/b:null; }
  floorHomography(plane) {
    const a=this.homogeneousDirection(plane.axisU),b=this.homogeneousDirection(plane.axisV);
    const p=this.worldToCamera(plane.origin),o=[this.fx*p[0]+this.skew*p[1]+this.cx*p[2],this.fy*p[1]+this.cy*p[2],p[2]];
    return [a[0],b[0],o[0],a[1],b[1],o[1],a[2],b[2],o[2]];
  }
  resized(width,height) { const sx=width/this.imageWidth,sy=height/this.imageHeight;return new CameraModel({imageWidth:width,imageHeight:height,fx:this.fx*sx,fy:this.fy*sy,cx:this.cx*sx,cy:this.cy*sy,skew:this.skew*sx,rotation:this.R,center:this.C,heightM:this.heightM,near:this.near,far:this.far}); }
  toJSON() {return {imageWidth:this.imageWidth,imageHeight:this.imageHeight,fx:this.fx,fy:this.fy,cx:this.cx,cy:this.cy,skew:this.skew,rotation:this.R,center:this.C,heightM:this.heightM,near:this.near,far:this.far};}
}
