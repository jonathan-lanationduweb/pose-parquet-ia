/** Transform feedback checks the actual GLSL board mapping against Canvas math. */
import assert from'node:assert/strict';import{createRequire}from'node:module';const{chromium}=createRequire(import.meta.url)(process.env.PPAI_PLAYWRIGHT_CORE);const browser=await chromium.launch({channel:'chrome',headless:true});
try{const page=await browser.newPage();await page.goto((process.env.PPAI_BASE||'http://127.0.0.1:8000')+'/tools/product-concept.html?prefetch=0');
const result=await page.evaluate(async()=>{const{PHYSICAL_PATTERN_GLSL,METRIC_CELL_GLSL,METRIC_JOINT_GLSL,physicalPattern,patternCellMeters,metricJointShade}=await import('../web/scene/world-pattern.js');const cv=document.createElement('canvas'),gl=cv.getContext('webgl2');if(!gl)throw Error('no actual WebGL2');
const compile=(type,source)=>{const s=gl.createShader(type);gl.shaderSource(s,source);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(s));return s;};
const vs=compile(gl.VERTEX_SHADER,'#version 300 es\nprecision highp float;\nin vec2 position;out vec3 ids;out vec2 localUV;out vec2 metrics;uniform vec3 uChevron;\n'+PHYSICAL_PATTERN_GLSL+METRIC_CELL_GLSL+METRIC_JOINT_GLSL+'\nvoid main(){MetricBoard c=metricBoard(position);ids=vec3(c.boardId);localUV=c.localUV;metrics=vec2(c.jointDistance,metricJointShade(c.jointDistance,.002,.0005));gl_Position=vec4(0.0,0.0,0.0,1.0);}');
const fs=compile(gl.FRAGMENT_SHADER,'#version 300 es\nprecision highp float;out vec4 color;void main(){color=vec4(1.0);}');const program=gl.createProgram();gl.attachShader(program,vs);gl.attachShader(program,fs);gl.transformFeedbackVaryings(program,['ids','localUV','metrics'],gl.INTERLEAVED_ATTRIBS);gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error(gl.getProgramInfoLog(program));gl.useProgram(program);
const n=512,input=new Float32Array(n*2);for(let i=0;i<n;i++){input[2*i]=((i*.75487766)%1)*4-2;input[2*i+1]=((i*.56984029)%1)*4-2;}
const buf=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buf);gl.bufferData(gl.ARRAY_BUFFER,input,gl.STATIC_DRAW);const attribute=gl.getAttribLocation(program,'position');gl.enableVertexAttribArray(attribute);gl.vertexAttribPointer(attribute,2,gl.FLOAT,false,0,0);const output=gl.createBuffer();gl.bindBuffer(gl.TRANSFORM_FEEDBACK_BUFFER,output);gl.bufferData(gl.TRANSFORM_FEEDBACK_BUFFER,n*7*4,gl.DYNAMIC_READ);gl.bindBufferBase(gl.TRANSFORM_FEEDBACK_BUFFER,0,output);
let maximum=0,probes=0;for(const pattern of['lames','point-de-hongrie','baton-rompu'])for(const width of[.09,.092,.15]){
 const p=physicalPattern({boardWidth:.15,boardLength:1.8},{pattern,width,plankLength:.5});gl.uniform4f(gl.getUniformLocation(program,'uPhysical'),p.w,p.l,p.angle,p.type);gl.uniform2f(gl.getUniformLocation(program,'uSourceBoard'),p.sourceW,p.sourceL);gl.uniform3f(gl.getUniformLocation(program,'uChevron'),p.period?.colonne||0,p.period?.pas||0,p.period?.rangs||0);
 gl.enable(gl.RASTERIZER_DISCARD);gl.beginTransformFeedback(gl.POINTS);gl.drawArrays(gl.POINTS,0,n);gl.endTransformFeedback();gl.disable(gl.RASTERIZER_DISCARD);const actual=new Float32Array(n*7);gl.getBufferSubData(gl.TRANSFORM_FEEDBACK_BUFFER,0,actual);
 for(let i=0;i<n;i++){
  const expected=patternCellMeters(input[i*2],input[i*2+1],p),at=i*7;
  if(expected.jointDistance<.00005)continue;
  if(expected.boardId.some((v,j)=>v!==actual[at+j]))throw Error(JSON.stringify({pattern,width,i,expected,actual:Array.from(actual.slice(at,at+7))}));
  const values=[...expected.boardLocalUV,expected.jointDistance,metricJointShade(expected.jointDistance,.002,.0005,p)];
  const error=Math.max(...values.map((v,j)=>Math.abs(v-actual[at+3+j])));
  if(error>2e-4)throw Error(JSON.stringify({pattern,width,i,error,values,actual:Array.from(actual.slice(at,at+7))}));maximum=Math.max(maximum,error);probes++;
 }}return{probes,maximumUVError:maximum};});assert.ok(result.probes>4000);console.log('PASS actual GPU/Canvas metric board IDs/local UV/joint/AA parity',result);
}finally{await browser.close();}
