/** Actual GLSL pixels versus the supplied equations, with independent mask domains. */
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const {chromium}=createRequire(import.meta.url)(process.env.PPAI_PLAYWRIGHT_CORE);
const browser=await chromium.launch({channel:'chrome',headless:true});
try{
 const page=await browser.newPage();await page.goto('http://127.0.0.1:8000/tools/product-concept.html?prefetch=0');
 const result=await page.evaluate(async()=>{
  const {COMPOSITE_FRAGMENT,buildContactMaps}=await import('/web/scene/contact-compositor.js');
  const width=160,height=120,canvas=document.createElement('canvas');canvas.width=width;canvas.height=height;
  const gl=canvas.getContext('webgl2',{preserveDrawingBuffer:true,antialias:false});
  if(!gl)throw Error('WebGL unavailable');
  const shader=(type,source)=>{const s=gl.createShader(type);gl.shaderSource(s,source);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(s));return s;};
  const program=gl.createProgram();gl.attachShader(program,shader(gl.VERTEX_SHADER,`#version 300 es
  in vec2 a;out vec2 vUv;void main(){vUv=vec2(a.x,1.-a.y);gl_Position=vec4(a*2.-1.,0.,1.);}`));gl.attachShader(program,shader(gl.FRAGMENT_SHADER,COMPOSITE_FRAGMENT));gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error(gl.getProgramInfoLog(program));gl.useProgram(program);
  const buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([0,0,1,0,0,1,1,1]),gl.STATIC_DRAW);const a=gl.getAttribLocation(program,'a');gl.enableVertexAttribArray(a);gl.vertexAttribPointer(a,2,gl.FLOAT,false,0,0);
  const N=width*height,photo=new Uint8Array(N*4),floor=new Uint8Array(N*4),coverage=new Uint8Array(N),occlusion=new Uint8Array(N),light=new Uint8Array(N*4);
  for(let y=0;y<height;y++)for(let x=0;x<width;x++){
   const i=y*width+x;photo.set([20+x,30+y,70,255],i*4);
   // FBO is stored in the opposite vertical direction, deliberately nonconstant.
   floor.set([150,40+(height-1-y),100,255],i*4);
   coverage[i]=y>=35?255:0;
   occlusion[i]=(x>=60&&x<70&&y>=50&&y<95)||(x>=95&&x<130&&y>=75&&y<95)?255:0;
   light.set([128+x/2,128+x/2,128+x/2,255],i*4);
  }
  const names=['uPhoto','uFloorRender','uFloorMask','uOccluderMask','uLightLayer'],arrays=[photo,floor,coverage,occlusion,light];
  for(let i=0;i<5;i++){const texture=gl.createTexture();gl.activeTexture(gl.TEXTURE0+i);gl.bindTexture(gl.TEXTURE_2D,texture);for(const k of [gl.TEXTURE_MIN_FILTER,gl.TEXTURE_MAG_FILTER])gl.texParameteri(gl.TEXTURE_2D,k,gl.NEAREST);for(const k of [gl.TEXTURE_WRAP_S,gl.TEXTURE_WRAP_T])gl.texParameteri(gl.TEXTURE_2D,k,gl.CLAMP_TO_EDGE);const mask=i===2||i===3;gl.texImage2D(gl.TEXTURE_2D,0,mask?gl.R8:gl.RGBA8,width,height,0,mask?gl.RED:gl.RGBA,gl.UNSIGNED_BYTE,arrays[i]);if(!gl.getUniformLocation(program,names[i]))throw Error('Missing sampler '+names[i]);gl.uniform1i(gl.getUniformLocation(program,names[i]),i);}
  const uniform=(n,v)=>{const u=gl.getUniformLocation(program,n);if(!u)throw Error('Missing '+n);gl.uniform1f(u,v);};
  uniform('uTexel',1/Math.max(width,height));uniform('uFeatherPx',1.5);uniform('uContactShadowStrength',.45);uniform('uContactShadowSpread',12);
  gl.uniform2f(gl.getUniformLocation(program,'uImageSize'),width,height);
  gl.viewport(0,0,width,height);gl.drawArrays(gl.TRIANGLE_STRIP,0,4);
  const bytes=new Uint8Array(N*4);gl.readPixels(0,0,width,height,gl.RGBA,gl.UNSIGNED_BYTE,bytes);
  const maps=buildContactMaps({coverage,occlusion},width,height);let maxError=0,count=0,edgeCount=0,contactCount=0;
  for(let y=0;y<height;y++)for(let x=0;x<width;x++){
   const i=y*width+x,q=((height-1-y)*width+x)*4;
   const vis=maps.soft[i]*(1-occlusion[i]/255),factor=1-.45*maps.contact[i]*.45;
   const wood=[150,40+y,100],gain=light[i*4]/255;
   for(let k=0;k<3;k++){const expected=photo[i*4+k]*(1-vis)+wood[k]*gain*factor*vis;maxError=Math.max(maxError,Math.abs(expected-bytes[q+k]));count++;}
   if(maps.soft[i]>0&&maps.soft[i]<1)edgeCount++;if(maps.contact[i]>0)contactCount++;
  }
  if(gl.getError()!==0)throw Error('GL error');
  return {maxError,count,edgeCount,contactCount};
 });
 assert.ok(result.maxError<1.6,JSON.stringify(result));assert.ok(result.edgeCount>0);assert.ok(result.contactCount>0);
 fs.writeFileSync('review/contact-shadow-lighting-v4/pixel-alignment.json',JSON.stringify(result,null,2));console.log('PASS',result);
}finally{await browser.close();}
