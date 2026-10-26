/** Runs the PRODUCTION vertex shader through actual WebGL transform feedback. */
import assert from'node:assert/strict';import{createRequire}from'node:module';const{chromium}=createRequire(import.meta.url)(process.env.PPAI_PLAYWRIGHT_CORE);const browser=await chromium.launch({channel:'chrome',headless:true});
try{const page=await browser.newPage();await page.goto((process.env.PPAI_BASE||'http://127.0.0.1:8000')+'/tools/product-concept.html?prefetch=0');
const result=await page.evaluate(async()=>{
 const{CameraModel,columnMajor}=await import('../web/scene/camera-model.js'),{FloorPlane}=await import('../web/scene/floor-plane.js'),{METRIC_VERTEX_GLSL}=await import('../web/scene/metric-runtime.js');
 const gl=document.createElement('canvas').getContext('webgl2');if(!gl)throw Error('WebGL2 required');
 const shader=(type,text)=>{const s=gl.createShader(type);gl.shaderSource(s,text);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(s));return s;};
 const program=gl.createProgram();gl.attachShader(program,shader(gl.VERTEX_SHADER,METRIC_VERTEX_GLSL));gl.attachShader(program,shader(gl.FRAGMENT_SHADER,'#version 300 es\nprecision highp float;out vec4 color;void main(){color=vec4(1.0);}'));gl.transformFeedbackVaryings(program,['gl_Position','vFloorMeters','vSourceProjection'],gl.INTERLEAVED_ATTRIBS);gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error(gl.getProgramInfoLog(program));gl.useProgram(program);
 const floor=new FloorPlane({origin:[.7,1.5,3],axisU:[1,0,0],axisV:[0,0,1],normal:[0,1,0],widthMeters:4,depthMeters:8});const pitch=.14,c=Math.cos(pitch),s=Math.sin(pitch);
 const camera=new CameraModel({imageWidth:1920,imageHeight:1080,fx:1100,fy:1050,cx:900,cy:560,skew:18,rotation:[1,0,0,0,c,-s,0,s,c],center:[.2,-.1,-.2]});
 const points=[];for(let u=-2;u<=2;u+=.4)for(let v=0;v<=8;v+=.4)points.push(u,v);const input=new Float32Array(points),n=input.length/2;
 const buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,input,gl.STATIC_DRAW);const a=gl.getAttribLocation(program,'aFloorPosition');gl.enableVertexAttribArray(a);gl.vertexAttribPointer(a,2,gl.FLOAT,false,0,0);
 const output=gl.createBuffer();gl.bindBuffer(gl.TRANSFORM_FEEDBACK_BUFFER,output);gl.bufferData(gl.TRANSFORM_FEEDBACK_BUFFER,n*9*4,gl.DYNAMIC_READ);gl.bindBufferBase(gl.TRANSFORM_FEEDBACK_BUFFER,0,output);
 gl.uniform1i(gl.getUniformLocation(program,'uMetric'),1);for(const[name,value]of[['uFloorOrigin',floor.origin],['uFloorAxisU',floor.axisU],['uFloorAxisV',floor.axisV]])gl.uniform3fv(gl.getUniformLocation(program,name),value);
 gl.uniformMatrix4fv(gl.getUniformLocation(program,'uSourceViewProj'),false,columnMajor(camera.buildViewProjectionMatrix()));let maxPixelError=0,maxMaskPixelError=0;
 for(const [w,h]of[[1440,900],[390,844],[780,1688]]){
  const target=camera.resized(w,h);gl.uniformMatrix4fv(gl.getUniformLocation(program,'uViewProj'),false,columnMajor(target.buildViewProjectionMatrix()));
  gl.enable(gl.RASTERIZER_DISCARD);gl.beginTransformFeedback(gl.POINTS);gl.drawArrays(gl.POINTS,0,n);gl.endTransformFeedback();gl.disable(gl.RASTERIZER_DISCARD);const values=new Float32Array(n*9);gl.getBufferSubData(gl.TRANSFORM_FEEDBACK_BUFFER,0,values);
  for(let i=0;i<n;i++){const point=floor.floorLocalToWorld(input[2*i],input[2*i+1]),expected=target.project(point),source=camera.project(point),o=i*9,clip=values.slice(o,o+4);const pixel={x:(clip[0]/clip[3]+1)*w/2,y:(1-clip[1]/clip[3])*h/2};maxPixelError=Math.max(maxPixelError,Math.hypot(pixel.x-expected.x,pixel.y-expected.y));const uv=values.slice(o+6,o+9);maxMaskPixelError=Math.max(maxMaskPixelError,Math.hypot(uv[0]/uv[2]*1920-source.x,uv[1]/uv[2]*1080-source.y));}
 }
 return{points:n*3,maxPixelError,maxMaskPixelError};});assert.ok(result.maxPixelError<1);assert.ok(result.maxMaskPixelError<1);console.log('PASS production GPU camera + source-mask projection, desktop/mobile/DPR2',result);
}finally{await browser.close();}
