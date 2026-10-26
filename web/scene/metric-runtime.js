import {CameraModel,columnMajor} from './camera-model.js';
import {FloorPlane} from './floor-plane.js';
const runtimeCache=new WeakMap();
/** Restore class instances outside serializable SceneData, once per geometry version. */
export function projectionRuntime(plane,width,height){
 const p=plane.projection;if(!p?.cameraModel||!p?.floorPlane)return null;
 let sizes=runtimeCache.get(p);if(!sizes){sizes=new Map();runtimeCache.set(p,sizes);}
 const key=`${width}x${height}`;if(sizes.has(key))return sizes.get(key);
 const c=p.cameraModel,principal=c.principalPoint;
 const source=new CameraModel({imageWidth:p.imageWidth,imageHeight:p.imageHeight,fx:c.fx||c.focalLength,fy:c.fy||c.focalLength,cx:c.cx??principal.x,cy:c.cy??principal.y,skew:c.skew||0,rotation:c.rotation,center:c.center||c.position,heightM:c.heightM,near:.01,far:200});
 const floor=new FloorPlane(p.floorPlane),camera=source.resized(width,height);
 const result={source,camera,floor,viewProjection:columnMajor(camera.buildViewProjectionMatrix()),sourceViewProjection:columnMajor(source.buildViewProjectionMatrix())};
 sizes.set(key,result);return result;
}
/** The visible floor is the intersection of the camera frustum with the plane; its
 * local AABB gives ONE quad covering the visible floor, without using the mask
 * as a perspective mesh or rebuilding when the brush/product changes.
 */
export function floorQuad(camera,floor){
 const corners=[];
 for(const depth of[camera.near,camera.far])for(const x of[0,camera.imageWidth])for(const y of[0,camera.imageHeight]){
  const ray=camera.ray({x,y}),d=camera.worldToCamera(ray.origin.map((v,i)=>v+ray.direction[i]));
  corners.push(ray.origin.map((v,i)=>v+ray.direction[i]*depth/d[2]));
 }
 // Intersect the 12 frustum edges with the floor. Bounding the whole frustum
 // in floor coordinates creates enormous off-plane triangles and loses
 // subpixel raster accuracy after near-plane clipping.
 const signed=p=>floor.normal.reduce((sum,n,i)=>sum+n*(p[i]-floor.origin[i]),0),points=[];
 for(let a=0;a<8;a++)for(let b=a+1;b<8;b++){
  const difference=a^b;if(![1,2,4].includes(difference))continue;
  const da=signed(corners[a]),db=signed(corners[b]);if(da*db>0||Math.abs(da-db)<1e-12)continue;
  const k=da/(da-db);points.push(floor.worldToFloorLocal(corners[a].map((v,i)=>v+(corners[b][i]-v)*k)));
 }
 if(points.length<3)throw Error('Floor outside camera frustum');
 const u0=Math.min(...points.map(p=>p.u)),u1=Math.max(...points.map(p=>p.u));
 const v0=Math.min(...points.map(p=>p.v)),v1=Math.max(...points.map(p=>p.v));
 return new Float32Array([u0,v0,u1,v0,u0,v1,u1,v1]);
}
/** Shared by production and transform-feedback tests. Ordinary perspective
 * interpolation of vFloorMeters gives the metric intersection at each fragment.
 * Source-mask projection is independent of the target viewport/clip transform.
 */
export const METRIC_VERTEX_GLSL=`#version 300 es
in vec2 aUnit;
in vec2 aFloorPosition;
uniform bool uMetric;
uniform mat3 uQuad;
uniform vec2 uViewport;
uniform mat4 uViewProj;
uniform mat4 uSourceViewProj;
uniform vec3 uFloorOrigin;
uniform vec3 uFloorAxisU;
uniform vec3 uFloorAxisV;
out vec2 vFloorMeters;
out vec3 vSourceProjection;
void main(){
 if(uMetric){
  vec3 world=uFloorOrigin+aFloorPosition.x*uFloorAxisU+aFloorPosition.y*uFloorAxisV;
  vec4 source=uSourceViewProj*vec4(world,1.0);
  vFloorMeters=aFloorPosition;
  vSourceProjection=vec3((source.x+source.w)*0.5,(source.w-source.y)*0.5,source.w);
  gl_Position=uViewProj*vec4(world,1.0);
 }else{
  vec3 p=uQuad*vec3(aUnit,1.0);vec2 pix=p.xy/p.z;
  gl_Position=vec4(pix.x/uViewport.x*2.0-1.0,1.0-pix.y/uViewport.y*2.0,0.0,1.0);
  vFloorMeters=vec2(0.0);vSourceProjection=vec3(0.0,0.0,1.0);
 }
}`;
