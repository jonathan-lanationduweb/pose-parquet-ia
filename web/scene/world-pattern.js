/** Physical pattern geometry; the old periodic tile supplies appearance only.
 * u/v are ground metres / TILE_METERS, after the one in-plane rotation.
 * Each board maps locally into an appearance board; camera parameters never enter.
 */
import {TILE_METERS,patternProfile,motifPeriode}from'./texture.js';
const fract=x=>x-Math.floor(x),mod=(x,n)=>((x%n)+n)%n;
export function physicalPattern(material,config){
 const p=patternProfile(material,config.pattern,config.width||null,config.plankLength||null),period=motifPeriode(material,config.pattern,config.width||null,config.plankLength||null);
 const gap=material.surfaceFamily==='exterior_deck'?Number(material.spacingM)||0:0;
 const w=p.width/TILE_METERS,l=p.length/TILE_METERS;
 return {type:config.pattern==='baton-rompu'?3:config.pattern==='point-de-hongrie'?2:1,w:w+(config.pattern==='lames'?gap/TILE_METERS:0),l,angle:p.angleDeg*Math.PI/180,
  sourceW:period?.type==='baton'?period.w:1/Math.max(1,Math.round(TILE_METERS/(p.width+gap))),
  sourceL:period?.type==='baton'?period.l:1/Math.max(1,Math.round(TILE_METERS/Math.min(TILE_METERS,p.length))),period};
}
/** Locate the physical rectangle in constant work, even for long narrow boards. */
export function physicalHerringbone(u,v,w,l){
 const s=Math.SQRT2*(v-.5),d=Math.SQRT2*(u-.5),last=Math.floor(s/(2*l));
 for(let i=last-1;i<=last;i++){
  const sa=s-2*i*l;
  let j=Math.ceil((d-sa)/(2*w)),q=(sa-d+2*j*w)/2,a=sa-q;
  if(a>=-1e-8&&a<l+1e-8&&q>=-1e-8&&q<w+1e-8)return{i,j,t:0};
  j=Math.floor((sa+d-2*l)/(2*w));a=(sa+d-2*j*w)/2-l;q=sa-l-a;
  if(a>=-1e-8&&a<w+1e-8&&q>=-1e-8&&q<l+1e-8)return{i,j,t:1};
 }
 return null;
}
export function patternUV(u,v,p,out=[0,0]){
 if(p.type===1){
  const row=Math.floor(v/p.w),offset=(mod(row,3)+mod(row,5)*.13)*p.l/3;
  const col=Math.floor((u-offset)/p.l),sourceRow=mod(row,Math.round(1/p.sourceW));
  const sourceOffset=(mod(sourceRow,3)+mod(sourceRow,5)*.13)*p.sourceL/3;
  out[0]=(col+fract((u-offset)/p.l))*p.sourceL+sourceOffset;
  out[1]=(sourceRow+fract(v/p.w))*p.sourceW;
 }else if(p.type===2){
  const column=2*p.l*Math.sin(p.angle),step=p.w/Math.sin(p.angle),q=fract(u/column);
  const triangle=1-Math.abs(q*2-1),base=triangle*column/(2*Math.tan(p.angle));
  const sourceColumn=p.period.colonne,sourceStep=p.period.pas;
  const sourceBase=triangle*sourceColumn/(2*Math.tan(p.angle));
  out[0]=u/column*sourceColumn;out[1]=(v-base)/step*sourceStep+sourceBase;
 }else{
  const found=physicalHerringbone(u,v,p.w,p.l);
  if(!found){out[0]=u;out[1]=v;return out;}
  const {i,j,t}=found,s=Math.SQRT2*(v-.5)-2*i*p.l,d=Math.SQRT2*(u-.5)-2*j*p.w;
  let a=(s+d)/2,b=(s-d)/2;
  if(t){a=(a-p.l)/p.w*p.sourceW+p.sourceL;b=b/p.l*p.sourceL;}
  else{a=a/p.l*p.sourceL;b=b/p.w*p.sourceW;}
  out[0]=.5+(2*j*p.sourceW+a-b)/Math.SQRT2;
  out[1]=.5+(2*i*p.sourceL+a+b)/Math.SQRT2;
 }
 return out;
}
/** The same local board mapping for WebGL. No extra draw call per board. */
export const PHYSICAL_PATTERN_GLSL=`
uniform vec4 uPhysical; // width, length (tile fractions), angle, pattern kind
uniform vec2 uSourceBoard;
float physicalModulo(float row,float count){
 int n=max(1,int(count));return float((int(row)%n+n)%n);
}
vec4 locatePhysicalHerringbone(vec2 uv, float w, float l){
 float s=1.41421356*(uv.y-0.5),d=1.41421356*(uv.x-0.5),last=floor(s/(2.0*l));
 for(int n=0;n<2;n++){
  float i=last-1.0+float(n),sa=s-2.0*i*l;
  float j=ceil((d-sa)/(2.0*w)),q=(sa-d+2.0*j*w)*0.5,a=sa-q;
  if(a>=-1e-6&&a<l+1e-6&&q>=-1e-6&&q<w+1e-6)return vec4(i,j,0.0,1.0);
  j=floor((sa+d-2.0*l)/(2.0*w));a=(sa+d-2.0*j*w)*0.5-l;q=sa-l-a;
  if(a>=-1e-6&&a<w+1e-6&&q>=-1e-6&&q<l+1e-6)return vec4(i,j,1.0,1.0);
 }
 return vec4(0.0);
}
vec2 physicalPatternUV(vec2 uv) {
 float w=uPhysical.x,l=uPhysical.y;
 if(uPhysical.w<0.5)return uv;
 if(uPhysical.w<1.5){
  float row=floor(uv.y/w),offset=(physicalModulo(row,3.0)+physicalModulo(row,5.0)*0.13)*l/3.0;
  float col=floor((uv.x-offset)/l),sourceRow=physicalModulo(row,round(1.0/uSourceBoard.x));
  float sourceOffset=(physicalModulo(sourceRow,3.0)+physicalModulo(sourceRow,5.0)*0.13)*uSourceBoard.y/3.0;
  return vec2((col+fract((uv.x-offset)/l))*uSourceBoard.y+sourceOffset,(sourceRow+fract(uv.y/w))*uSourceBoard.x);
 }
 if(uPhysical.w<2.5){
  float column=2.0*l*sin(uPhysical.z),step=w/sin(uPhysical.z),q=fract(uv.x/column);
  float triangle=1.0-abs(q*2.0-1.0),base=triangle*column/(2.0*tan(uPhysical.z));
  float sourceBase=triangle*uChevron.x/(2.0*tan(uPhysical.z));
  return vec2(uv.x/column*uChevron.x,(uv.y-base)/step*uChevron.y+sourceBase);
 }
 vec4 board=locatePhysicalHerringbone(uv,w,l);if(board.w<0.5)return uv;
 float s=1.41421356*(uv.y-0.5)-2.0*board.x*l,d=1.41421356*(uv.x-0.5)-2.0*board.y*w;
 float a=(s+d)*0.5,b=(s-d)*0.5;
 if(board.z>0.5){a=(a-l)/w*uSourceBoard.x+uSourceBoard.y;b=b/l*uSourceBoard.y;}
 else{a=a/l*uSourceBoard.y;b=b/w*uSourceBoard.x;}
 return vec2(0.5+(2.0*board.y*uSourceBoard.x+a-b)/1.41421356,0.5+(2.0*board.x*uSourceBoard.y+a+b)/1.41421356);
}
`;
