/** Prototype 2.5D : géométrie supposée, aucune profondeur IA ni zone inventée. */
export function photoPoint(u, v, depth, aspect, tanHalfFov) {
  return [(u - .5) * 2 * aspect * tanHalfFov * depth, (.5 - v) * 2 * tanHalfFov * depth, depth];
}
export function cameraPoint(point, camera) {
  const x = point[0] - camera.x, y = point[1], z = point[2] - camera.z;
  const c = Math.cos(camera.yaw), s = Math.sin(camera.yaw);
  return [c * x - s * z, y, s * x + c * z];
}
export function floorDepth(v, horizon, heightM, tanHalfFov) {
  return Math.min(12, Math.max(.7, heightM / Math.max(.05, (v - horizon) * 2 * tanHalfFov)));
}
export function buildVisitMesh({ scene, masks, size }, columns = 160) {
  const aspect = size.width / size.height;
  const fov = Math.min(90, Math.max(35, scene.camera?.fovDeg || 60)) * Math.PI / 180;
  const tan = Math.tan(fov / 2) / aspect;
  const horizon = Math.min(.7, Math.max(.15, scene.camera?.horizon || .4));
  const heightM = scene.camera?.heightM || 1.5;
  const rows = Math.max(48, Math.round(columns / aspect));
  const points = [], depths = [], vertices = [];
  const floorAt = (x,y) => masks.coverage[Math.min(size.height-1,y)*size.width+Math.min(size.width-1,x)] > 128;
  for (let j=0;j<=rows;j++) for(let i=0;i<=columns;i++) {
    const u=i/columns,v=j/rows,x=Math.min(size.width-1,Math.round(u*size.width)),y=Math.min(size.height-1,Math.round(v*size.height));
    let depth;
    if (floorAt(x,y) || (masks.occlusion?.[y*size.width+x] > 128 && v > horizon)) depth=floorDepth(v,horizon,heightM,tan);
    else {
      // Un objet est attaché au premier contact avec le sol sous lui. Au-dessus
      // de l'horizon, le fond est un plan distant : pas une reconstruction IA.
      let contact=y;
      while(contact<size.height-1&&!floorAt(x,contact)) contact+=1;
      depth=contact<size.height-1?floorDepth(contact/size.height,horizon,heightM,tan):12;
    }
    points.push([...photoPoint(u,v,depth,aspect,tan),u,v]);depths.push(depth);
  }
  const triangle=(a,b,c)=> {
    const lo=Math.min(depths[a],depths[b],depths[c]),hi=Math.max(depths[a],depths[b],depths[c]);
    if(hi-lo>Math.max(.45,lo*.18)) return; // Pas de triangle étiré entre un meuble et le fond.
    vertices.push(...points[a],...points[b],...points[c]);
  };
  for(let j=0;j<rows;j++)for(let i=0;i<columns;i++){
    const a=j*(columns+1)+i,b=a+1,c=a+columns+1,d=c+1;triangle(a,c,b);triangle(b,c,d);
  }
  return {vertices:new Float32Array(vertices),aspect,tan,depths,columns,rows,horizon,heightM};
}
function createVisitRenderer(canvas, snapshot) {
  const gl=canvas.getContext('webgl',{alpha:false,antialias:true});
  if(!gl) throw new Error('Mode Visite indisponible sur cet appareil.');
  const mesh=buildVisitMesh(snapshot);
  const shader=(type,code)=>{const s=gl.createShader(type);gl.shaderSource(s,code);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw new Error(gl.getShaderInfoLog(s));return s;};
  const vs=shader(gl.VERTEX_SHADER,`attribute vec3 p;attribute vec2 uv;varying vec2 tex;uniform vec3 cam;uniform vec2 lens;
    void main(){vec3 q=p-vec3(cam.x,0.,cam.y);float c=cos(cam.z),s=sin(cam.z);q=vec3(c*q.x-s*q.z,q.y,s*q.x+c*q.z);gl_Position=vec4(q.x/lens.x,q.y/lens.y,1.001001*q.z-.02001,q.z);tex=uv;}`);
  const fs=shader(gl.FRAGMENT_SHADER,'precision mediump float;varying vec2 tex;uniform sampler2D photo;void main(){gl_FragColor=texture2D(photo,tex);}');
  const prog=gl.createProgram();gl.attachShader(prog,vs);gl.attachShader(prog,fs);gl.linkProgram(prog);if(!gl.getProgramParameter(prog,gl.LINK_STATUS))throw new Error(gl.getProgramInfoLog(prog));gl.useProgram(prog);
  const buf=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buf);gl.bufferData(gl.ARRAY_BUFFER,mesh.vertices,gl.STATIC_DRAW);
  for(const [name,n,offset] of [['p',3,0],['uv',2,12]]){const a=gl.getAttribLocation(prog,name);gl.enableVertexAttribArray(a);gl.vertexAttribPointer(a,n,gl.FLOAT,false,20,offset);}
  const texture=gl.createTexture();gl.bindTexture(gl.TEXTURE_2D,texture);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,snapshot.canvas);
  gl.enable(gl.DEPTH_TEST);gl.clearColor(.14,.14,.12,1);
  const camLoc=gl.getUniformLocation(prog,'cam'),lensLoc=gl.getUniformLocation(prog,'lens');
  return {
    draw(camera){const r=canvas.getBoundingClientRect();canvas.width=Math.max(1,Math.round(r.width));canvas.height=Math.max(1,Math.round(r.height));gl.viewport(0,0,canvas.width,canvas.height);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);const displayAspect=canvas.width/canvas.height;const t=Math.max(mesh.tan,mesh.tan*mesh.aspect/displayAspect);gl.uniform2f(lensLoc,t*displayAspect,t);gl.uniform3f(camLoc,camera.x,camera.z,camera.yaw);gl.drawArrays(gl.TRIANGLES,0,mesh.vertices.length/5);},
    dispose(){gl.deleteBuffer(buf);gl.deleteTexture(texture);gl.deleteProgram(prog);gl.deleteShader(vs);gl.deleteShader(fs);gl.getExtension('WEBGL_lose_context')?.loseContext();},
    mesh,
  };
}
export function installVisit(getConcept) {
  const c=getConcept();if(!c)return;
  const toggle=document.createElement('button');toggle.type='button';toggle.textContent='Visite';toggle.setAttribute('aria-label','Mode Visite expérimental');document.getElementById('tools').appendChild(toggle);
  let layer=null,renderer=null,observer=null;
  const close=()=>{observer?.disconnect();observer=null;renderer?.dispose();renderer=null;layer?.remove();layer=null;document.body.classList.remove('visiting');toggle.focus();};
  toggle.onclick=()=>{
    const snapshot=c.adapter.visitSnapshot?.();if(!snapshot||c.state.applying){c.etatProduit?.();return;}
    c.closeAll();document.body.classList.add('visiting');
    layer=document.createElement('section');layer.className='visit-layer';layer.setAttribute('aria-label','Photo immersive expérimentale');
    layer.innerHTML='<canvas aria-label="Scène 2.5D avec caméra virtuelle"></canvas><div class="visit-controls"><p>Visite expérimentale · géométrie supposée · déplacement limité. Les zones cachées ne sont pas reconstruites.</p><button type="button" data-exit>Retour au parquet</button><button type="button" data-reset>Recentrer</button><label>Gauche / droite <input aria-label="Déplacement latéral" type="range" min="-6" max="6" value="0"></label><label>Avancer <input aria-label="Avancer dans la pièce" type="range" min="0" max="12" value="0"></label><label>Tourner <input aria-label="Rotation de la caméra" type="range" min="-3" max="3" value="0" step="0.1"></label></div>';
    layer.addEventListener('pointerdown', e => e.stopPropagation());
    document.getElementById('stage').appendChild(layer);
    try{renderer=createVisitRenderer(layer.querySelector('canvas'),snapshot);}catch(e){close();alert(e.message);return;}
    const inputs=[...layer.querySelectorAll('input')];const draw=()=>renderer?.draw({x:Number(inputs[0].value)/100,z:Number(inputs[1].value)/100,yaw:Number(inputs[2].value)*Math.PI/180});
    inputs.forEach(i=>i.addEventListener('input',draw));layer.querySelector('[data-exit]').onclick=close;layer.querySelector('[data-reset]').onclick=()=>{inputs.forEach(i=>i.value='0');draw();};
    observer=new ResizeObserver(draw);observer.observe(layer.querySelector('canvas'));draw();layer.querySelector('[data-exit]').focus();
  };
  document.addEventListener('click',e=>{if(layer&&e.target.closest('header'))close();},true);
  document.addEventListener('keydown',e=>{if(layer&&e.key==='Escape'){e.preventDefault();close();}});
}
