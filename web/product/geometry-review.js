/** DEV interface only; loaded lazily by the product page. */
import {DEBUG_FLAGS,buildDiagnosticLayers,composeDiagnostic,rawMaskCanvas,patternAt} from './diagnostic-layers.js';
const LABELS={debugGrid:'Grille 50 cm',debugMasks:'Masques',debugCamera:'Caméra',debugFloorPlane:'Plan du sol',debugScale:'Échelle',debugPattern:'IDs / joints'};
export function installGeometryReview(getConcept){
 const c=getConcept();if(!c?.DEV)return;
 const stage=document.getElementById('stage'),group=document.createElement('div');
 group.className='vp';group.dataset.vp='';group.id='visualDebugOverlay';group.style.cssText='pointer-events:none;z-index:6;display:none';
 const canvas=document.createElement('canvas');group.append(canvas);stage.append(group);
 const panel=document.createElement('details');panel.id='visualDebugPanel';
 panel.style.cssText='position:absolute;right:8px;top:74px;z-index:20;max-width:calc(100% - 16px);max-height:50%;overflow:auto;padding:8px;background:#fffef5f5;color:#222;border:1px solid #aaa;border-radius:10px;font:12px/1.4 monospace';
 for(const type of ['pointerdown','pointermove','pointerup','keydown'])panel.addEventListener(type,e=>e.stopPropagation());panel.addEventListener('wheel',e=>e.stopPropagation(),{passive:true});
 const summary=document.createElement('summary');summary.textContent='Diagnostic DEV';summary.style.cursor='pointer';panel.append(summary);
 const options=document.createElement('div');options.style.cssText='display:grid;grid-template-columns:repeat(2,minmax(110px,1fr))';
 const inputs={},flags=Object.fromEntries(DEBUG_FLAGS.map(k=>[k,false]));let last=null,timer=0,refreshing=false;
 for(const key of DEBUG_FLAGS){const label=document.createElement('label');label.style.cssText='display:flex;align-items:center;gap:5px;min-height:44px';const input=document.createElement('input');input.type='checkbox';input.dataset.debugFlag=key;input.onchange=()=>setFlags({[key]:input.checked});inputs[key]=input;label.append(input,document.createTextNode(LABELS[key]));options.append(label);}
 panel.append(options);
 const flatPreview=document.createElement('canvas');flatPreview.style.cssText='display:none;width:180px;height:180px';panel.append(flatPreview);
 const unlit=document.createElement('button');unlit.type='button';unlit.textContent='Comparer sans lumière';unlit.style.cssText='display:block;width:100%;min-height:44px;margin-top:6px;padding:6px;border:1px solid #aaa;border-radius:6px';unlit.onclick=async()=>{
  const intent=c.state.intent,scene=c.adapter.scene;unlit.disabled=true;
  try{const frame=await c.adapter.diagnosticUnlitFrame();if(frame&&scene===c.adapter.scene&&intent===c.state.intent){canvas.width=frame.width;canvas.height=frame.height;canvas.getContext('2d').drawImage(frame,0,0);group.style.display='';c.applyTransform();}}
  finally{unlit.disabled=false;}
 };
 const restore=document.createElement('button');restore.type='button';restore.textContent='Rétablir les overlays';restore.style.cssText='display:block;width:100%;min-height:44px;margin-top:6px;padding:6px;border:1px solid #aaa;border-radius:6px';restore.onclick=()=>draw();
 const neutral=unlit.cloneNode(true);neutral.textContent='Sol neutre';
  neutral.onclick=async()=>{const intent=c.state.intent,scene=c.adapter.scene;neutral.disabled=true;
   try{const frame=await c.adapter.diagnosticNeutralFrame();if(frame&&scene===c.adapter.scene&&intent===c.state.intent){canvas.width=frame.width;canvas.height=frame.height;canvas.getContext('2d').drawImage(frame,0,0);group.style.display='';c.applyTransform();}}
   finally{neutral.disabled=false;}
  };
  const foreground=unlit.cloneNode(true);foreground.textContent='Comparer sans objets';
  foreground.onclick=async()=>{const intent=c.state.intent,scene=c.adapter.scene;foreground.disabled=true;
   try{const frame=await c.adapter.diagnosticForegroundFrame();if(frame&&scene===c.adapter.scene&&intent===c.state.intent){canvas.width=frame.width;canvas.height=frame.height;canvas.getContext('2d').drawImage(frame,0,0);group.style.display='';c.applyTransform();}}
   finally{foreground.disabled=false;}
  };
  panel.append(unlit,neutral,foreground,restore);
  for(const [mode,label]of [[1,'V4 · sol'],[2,'V4 · objets'],[3,'V4 · lumière'],[4,'V4 · parquet sans lumière'],[5,'V4 · parquet éclairé'],[6,'V4 · contact'],[0,'V4 · composite final']]){
    const button=unlit.cloneNode(true);button.textContent=label;
    button.onclick=async()=>{const intent=c.state.intent,scene=c.adapter.scene;button.disabled=true;
      try{const frame=await c.adapter.diagnosticCompositeFrame(mode);if(frame&&scene===c.adapter.scene&&intent===c.state.intent){canvas.width=frame.width;canvas.height=frame.height;canvas.getContext('2d').drawImage(frame,0,0);group.style.display='';c.applyTransform();}}
      finally{button.disabled=false;}
    };panel.append(button);
  }

 const legend=document.createElement('pre');legend.style.cssText='white-space:pre-wrap;max-width:300px;margin:8px 0 0';panel.append(legend);stage.append(panel);
 const snapshot=()=>{
  const snap=c.adapter.diagnosticSnapshot();if(!snap)throw Error('Ouvrez une scène dans le moteur');
  if(c.state.source&&c.adapter.scene!==c.room()?.id)throw Error('La scène moteur ne correspond pas à la photo affichée');
  if(c.state.source==='uploaded'&&!c.state.photoScene?.posee&&!(c.state.photoScene?.raw&&c.state.photoScene?.geometryValidation?.status==='failed'))throw Error('Attendez la scène de cette nouvelle photo');
  if(c.state.applying)throw Error('Attendez la fin du rendu');
  return snap;
 };
 function draw(){
  if(!DEBUG_FLAGS.some(k=>flags[k])){flatPreview.style.display='none';group.style.display='none';legend.textContent='Choisissez une couche. Vert : sol ; rouge : objets ; violet : recouvrement sol/objet (normal sous un meuble).';return null;}
  let snap;try{snap=snapshot();}catch(e){group.style.display='none';flatPreview.style.display='none';last=null;legend.textContent=e.message;return null;}
  const data=buildDiagnosticLayers(snap,DEBUG_FLAGS.filter(k=>flags[k]));last=data;
  canvas.width=snap.size.width;canvas.height=snap.size.height;const ctx=canvas.getContext('2d');
  for(const key of DEBUG_FLAGS)if(data.layers[key])ctx.drawImage(data.layers[key],0,0);
  group.style.display='';
  if(data.floorSpacePattern){flatPreview.width=640;flatPreview.height=640;flatPreview.getContext('2d').drawImage(data.floorSpacePattern,0,0);flatPreview.style.display='block';flatPreview.title='Plan 2 m x 2 m, sans caméra';}else flatPreview.style.display='none';
  const s=data.metadata.scale;
  legend.textContent=[
   snap.scene.id+' · '+(snap.scene.geometryValidation?.decision||'non évaluée'),
   s.available?'Lame '+s.boardWidthMeters+' × '+s.boardLengthMeters+' m · multiplicateur '+s.scaleMultiplier:'Dimensions indisponibles',
   'Échelle absolue supposée, sauf mesure externe.',
   ...(s.zones||[]).map(z=>z.id+' : '+Object.entries(z.samples||{}).map(([k,v])=>k+' '+(v?v.pixels.toFixed(1)+' px':'non visible')).join(' · ')),
   ...data.metadata.warnings
  ].join('\n');
  c.applyTransform();return data;
 }
 function setFlags(values){
  for(const [k,v]of Object.entries(values)){if(!DEBUG_FLAGS.includes(k)||typeof v!=='boolean')throw Error('Invalid debug flag');flags[k]=v;inputs[k].checked=v;}
  return draw();
 }
 function capture(requested=DEBUG_FLAGS){
  const snap=snapshot(),data=buildDiagnosticLayers(snap,requested),images={original:composeDiagnostic(snap.photo),render:composeDiagnostic(snap.photo,snap.scene.geometryValidation?.status==='failed'||snap.renderAvailable===false?null:snap.canvas)};
  for(const [k,layer]of Object.entries(data.layers))images[k]=composeDiagnostic(snap.photo,layer);
  if(data.floorSpacePattern)images.floorSpacePattern=data.floorSpacePattern;
  images.floorMask=rawMaskCanvas(snap,'floor');images.occluderMask=rawMaskCanvas(snap,'occluder');
  const stageBox=stage.getBoundingClientRect(),photoBox=document.getElementById('vpPhoto').getBoundingClientRect();
  const metadata={schema:'pose-parquet/defect-pack@1',...data.metadata,geometryVersion:snap.scene.geometryVersion,materialProfileId:snap.config.material?.id||null,sceneId:snap.scene.id,viewportSize:{width:innerWidth,height:innerHeight},productId:c.state.productId,pattern:snap.config.pattern,floorAngle:snap.config.angle||0,geometryStatus:snap.scene.geometryValidation?.decision||null,renderBlocked:snap.scene.geometryValidation?.status==='failed',renderAvailable:snap.renderAvailable!==false,
   ViewTransform:{coordinateSystem:'source-image pixels, top-left',sourceSize:snap.size,stage:{width:stageBox.width,height:stageBox.height},matrix:[photoBox.width/snap.size.width,0,0,photoBox.height/snap.size.height,photoBox.x,photoBox.y],cssLayerMatrix:getComputedStyle(document.getElementById('vpPhoto')).transform,cssLayerImageSize:c.sceneSize(),sourceToViewportScale:{x:photoBox.width/snap.size.width,y:photoBox.height/snap.size.height},offsetInViewport:{x:photoBox.x,y:photoBox.y}},
   boardWidthMeters:data.metadata.scale.boardWidthMeters??null,boardLengthMeters:data.metadata.scale.boardLengthMeters??null,
   scaleNear:data.metadata.scale.zones?.[0]?.samples?.near??null,scaleMid:data.metadata.scale.zones?.[0]?.samples?.mid??null,scaleFar:data.metadata.scale.zones?.[0]?.samples?.far??null,
   horizon:data.metadata.cameras.map(z=>z.horizonLine),vanishingPoints:data.metadata.cameras.map(z=>z.vanishingPoints),cameraHeight:data.metadata.cameras.map(z=>z.camera.heightM),cameraHeightKind:'assumed unless externally measured'};
  return {images,metadata};
 }
 window.__visualDiagnostics={flags,setFlags,draw,capture,get metadata(){return last?.metadata||null;},sample(pixel){const snap=snapshot();if(!Number.isFinite(pixel?.x)||!Number.isFinite(pixel?.y)||pixel.x<0||pixel.y<0||pixel.x>=snap.size.width||pixel.y>=snap.size.height)throw Error('Point outside source image');const i=Math.floor(pixel.y)*snap.size.width+Math.floor(pixel.x),label=snap.masks.labels[i];return{floor:snap.masks.coverage[i],occluder:snap.masks.occlusion?.[i]||0,effective:snap.masks.effectiveCoverage[i],board:label?patternAt(snap,snap.scene.floorZones[label-1],pixel):null};}};
 // Preserve the previous diagnostic entry point for existing review tools.
 window.__geometryReview={show(value=true){for(const key of DEBUG_FLAGS){flags[key]=value&&['debugGrid','debugCamera','debugFloorPlane','debugScale'].includes(key);inputs[key].checked=flags[key];}draw();return value?c.adapter.geometryDiagnostics():null;},draw(){draw();return c.adapter.geometryDiagnostics();}};
 const refresh=()=>{if(!refreshing){clearTimeout(timer);timer=setTimeout(()=>{refreshing=true;try{if(DEBUG_FLAGS.some(k=>flags[k]))draw();}finally{refreshing=false;}},150);}};
 stage.addEventListener('pointerup',refresh);document.addEventListener('click',e=>{if(!panel.contains(e.target))refresh();});
 window.addEventListener('resize',refresh);window.addEventListener('pp:journey',refresh);draw();
}
