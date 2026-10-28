/** V4 final image-space pass. Constants/formulas are the supplied specification. */
export const CONTACT_DEFAULTS = Object.freeze({featherPx:1.5,strength:.45,spread:12});
export const COMPOSITE_FRAGMENT = `#version 300 es
precision highp float;
in vec2 vUv;
out vec4 fragColor;
uniform sampler2D uPhoto, uFloorRender, uFloorMask, uOccluderMask, uLightLayer;
uniform vec2 uImageSize;
uniform float uTexel, uFeatherPx, uContactShadowStrength, uContactShadowSpread;
uniform bool uForegroundOff;
uniform int uDebug;
float blurMask(sampler2D mask, vec2 uv, float radiusPx) {
  float sum=0.0;
  float w=radiusPx*uTexel;
  for(int i=-2;i<=2;i++) for(int j=-2;j<=2;j++) {
    vec2 off=vec2(float(i),float(j))*w;
    sum+=texture(mask,uv+off).r;
  }
  return sum/25.0;
}
void main() {
  // vUv is source-image UV supplied by the image quad. ViewTransform is
  // applied once when that source-domain canvas is displayed, never twice.
  vec2 vUV=vUv;
  vec3 photo=texture(uPhoto,vUV).rgb;
  float floorBlurred=blurMask(uFloorMask,vUV,uFeatherPx*2.0);
  float floorSoft=smoothstep(0.55,0.65,floorBlurred);
  float occluderSharp=uForegroundOff?0.0:texture(uOccluderMask,vUV).r;
  float occluderWide=uForegroundOff?0.0:blurMask(uOccluderMask,vUV,uContactShadowSpread);
  float contactShadow=clamp(occluderWide-occluderSharp,0.0,1.0);
  // Render-target storage has a bottom-left origin; uploaded image masks do not.
  vec4 floorCol=texture(uFloorRender,vec2(vUV.x,1.0-vUV.y));
  vec3 lightLayer=texture(uLightLayer,vUV).rgb;
  vec3 woodLit=floorCol.rgb*lightLayer;
  float visibleFloor=floorSoft*(1.0-occluderSharp);
  // Never paint an unassigned surface/product. FBO alpha is render availability.
  visibleFloor*=floorCol.a;
  vec3 woodShadowed=woodLit*mix(1.0,0.55,contactShadow*uContactShadowStrength);
  vec3 outColor=mix(photo,woodShadowed,visibleFloor);
  if(uDebug==1)outColor=vec3(texture(uFloorMask,vUV).r);
  if(uDebug==2)outColor=vec3(occluderSharp);
  if(uDebug==3)outColor=lightLayer/1.8;
  if(uDebug==4)outColor=mix(photo,floorCol.rgb,visibleFloor);
  if(uDebug==5)outColor=mix(photo,woodLit,visibleFloor);
  if(uDebug==6)outColor=vec3(contactShadow);
  fragColor=vec4(outColor,1.0);
}`;

/** Same 25 samples and scalar source-domain texel as the reference shader. */
export function blurMask25(mask,width,height,radiusPx) {
  const out=new Float32Array(width*height),den=Math.max(width,height);
  const dx=radiusPx*width/den,dy=radiusPx*height/den;
  for(let y=0;y<height;y++)for(let x=0;x<width;x++){
    let sum=0;
    for(let i=-2;i<=2;i++)for(let j=-2;j<=2;j++){
      const xx=Math.max(0,Math.min(width-1,Math.floor(x+.5+i*dx)));
      const yy=Math.max(0,Math.min(height-1,Math.floor(y+.5+j*dy)));
      sum+=mask[yy*width+xx]/255;
    }
    out[y*width+x]=sum/25;
  }
  return out;
}
const smooth=(x)=>{const t=Math.max(0,Math.min(1,(x-.55)/.1));return t*t*(3-2*t);};
export function buildContactMaps(masks,width,height) {
  const floor=blurMask25(masks.coverage,width,height,3);
  const wide=blurMask25(masks.occlusion||new Uint8Array(width*height),width,height,12);
  return {soft:floor.map(smooth),contact:wide.map((v,i)=>Math.max(0,Math.min(1,v-(masks.occlusion?.[i]||0)/255)))};
}

/** Decode lossless RG-packed gain; values >1 are never clipped to PNG's 0..1. */
export async function decodeLightLayer(raw) {
  if(!raw)return null;
  if(raw.encoding!=='png-rg-u16'||!(raw.scale>0)||!String(raw.data).startsWith('data:image/png;base64,'))throw Error('Invalid lightLayer');
  const image=new Image();image.src=raw.data;await image.decode();
  if(image.naturalWidth!==raw.width||image.naturalHeight!==raw.height)throw Error('LightLayer dimensions differ');
  const canvas=document.createElement('canvas');canvas.width=raw.width;canvas.height=raw.height;
  const ctx=canvas.getContext('2d',{willReadFrequently:true});ctx.drawImage(image,0,0);
  const bytes=ctx.getImageData(0,0,raw.width,raw.height).data,rgba=new Float32Array(bytes.length);
  for(let p=0;p<bytes.length;p+=4){const v=(bytes[p]+256*bytes[p+1])/raw.scale;rgba[p]=rgba[p+1]=rgba[p+2]=v;rgba[p+3]=1;}
  return {width:raw.width,height:raw.height,rgba};
}
export function sampleLight(layer,x,y,width,height) {
  if(!layer)return 1;
  // Match GL LINEAR sampling at source pixel centers.
  const sx=(x+.5)*layer.width/width-.5,sy=(y+.5)*layer.height/height-.5;
  const ix=Math.floor(sx),iy=Math.floor(sy),fx=sx-ix,fy=sy-iy;
  const at=(xx,yy)=>layer.rgba[4*(Math.max(0,Math.min(layer.height-1,yy))*layer.width+Math.max(0,Math.min(layer.width-1,xx)))];
  return (at(ix,iy)*(1-fx)+at(ix+1,iy)*fx)*(1-fy)+(at(ix,iy+1)*(1-fx)+at(ix+1,iy+1)*fx)*fy;
}
