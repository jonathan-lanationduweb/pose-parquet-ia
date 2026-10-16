/** Peinture expérimentale : masques indépendants, éclairage conservé, aucune IA simulée. */
export function installWallPaint(c) {
  const $=id=>document.getElementById(id),stage=$('stage'),photo=$('photo');
  const open=document.createElement('button');open.type='button';open.id='wallPaintOpen';open.textContent='Murs';open.setAttribute('aria-label','Choisir un mur');const modes=document.createElement('div');modes.id='surfaceModes';modes.setAttribute('role','group');modes.setAttribute('aria-label','Surface à personnaliser');const floors=document.createElement('button');floors.type='button';floors.id='floorSurfaceMode';floors.textContent='Sols';floors.setAttribute('aria-pressed','true');modes.append(floors,open);$('photoActions').append(modes);
  const dialog=document.createElement('dialog');dialog.id='wallPaintPanel';dialog.setAttribute('aria-label','Peinture des murs');
  dialog.innerHTML=`<header><h2>Murs <small>Peinture · essai</small></h2><button type="button" id="wallClose" aria-label="Fermer la peinture">×</button></header><p id="wallHelp">Touchez directement le mur à modifier dans la photo.</p><label for="wallSelect">Mur à personnaliser</label><select id="wallSelect"></select><div id="wallColors" role="group" aria-label="Teintes d’essai"></div><label class="wall-custom">Autre teinte <input id="wallColor" type="color" value="#d3c4ac"></label><p class="wall-note">Teintes de démonstration, sans référence commerciale. L’écran ne garantit pas la couleur réelle.</p><div class="wall-actions wall-contour-actions"><button id="wallNew" type="button">Tracer un mur</button><button id="wallProtect" type="button">Protéger une zone</button><button id="wallReset" type="button">Couleur d’origine</button><button id="wallUndo" type="button">Annuler la retouche</button></div><p id="wallMessage" role="status"></p>`;
  document.body.append(dialog);
  const vp=document.createElement('div');vp.className='vp';vp.id='vpWallPaint';vp.setAttribute('data-vp','');vp.hidden=true;
  const outline=document.createElement('canvas');outline.id='wallOutline';outline.setAttribute('aria-label','Ajouter les angles du contour du mur');vp.append(outline);stage.append(vp);
  const edit=document.createElement('div');edit.id='wallDrawTools';edit.hidden=true;edit.innerHTML='<p id="wallDrawHint">Touchez les angles du mur, puis validez.</p><div><button id="wallPointUndo" type="button">Retirer un point</button><button id="wallConfirm" type="button">Valider</button><button id="wallCancel" type="button">Annuler</button></div>';stage.append(edit);
  const colors=[['Lin','#d3c4ac'],['Blanc cassé','#eee9df'],['Sauge','#98a58b'],['Terracotta','#b87155'],['Bleu grisé','#78929d'],['Argile','#a99b91']];
  for(const [name,color]of colors){const b=document.createElement('button');b.type='button';b.title=name;b.setAttribute('aria-label',name);b.dataset.color=color;b.style.setProperty('--swatch',color);b.onclick=()=>setColor(color);$('wallColors').append(b);}
  const scenes=new Map(),bases=new Map(),history=[];let key='',walls=[],selected='',draft=null,drawingView=null,revision=0,raf=0,selecting=false,lastAnalysis=null;
  const current=()=>walls.find(w=>w.id===selected);
  const sceneKey=()=>c.state.source==='uploaded'?c.state.uploaded?.url||'':c.state.roomId||'';
  const copy=n=>{const b=document.createElement('canvas');b.width=n.width;b.height=n.height;b.getContext('2d').drawImage(n,0,0);return b;};
  function polygon(ctx,points,w,h){ctx.beginPath();points.forEach((p,i)=>i?ctx.lineTo(p.x*w,p.y*h):ctx.moveTo(p.x*w,p.y*h));ctx.closePath();}
  function apply(canvas,base){
    const w=canvas.width,h=canvas.height;if(!w||!h)return;
    const ctx=canvas.getContext('2d');ctx.clearRect(0,0,w,h);ctx.drawImage(base,0,0,w,h);
    if(!walls.some(x=>x.color))return;
    const src=base.getContext('2d').getImageData(0,0,w,h),out=ctx.getImageData(0,0,w,h);
    for(const wall of walls){if(!wall.color)continue;
      const mask=document.createElement('canvas');mask.width=w;mask.height=h;const m=mask.getContext('2d');m.fillStyle='#fff';polygon(m,wall.polygon,w,h);m.fill();m.globalCompositeOperation='destination-out';for(const hole of wall.holes||[]){polygon(m,hole,w,h);m.fill();}
      const alpha=m.getImageData(0,0,w,h).data;let mean=0,count=0;
      for(let i=0;i<alpha.length;i+=4)if(alpha[i+3]>128){mean+=src.data[i]*.2126+src.data[i+1]*.7152+src.data[i+2]*.0722;count++;}
      if(!count)continue;mean/=count;const rgb=wall.color.match(/[a-f\d]{2}/gi).map(x=>parseInt(x,16));
      for(let i=0;i<alpha.length;i+=4){if(!alpha[i+3])continue;const luminance=src.data[i]*.2126+src.data[i+1]*.7152+src.data[i+2]*.0722;const light=Math.max(.25,Math.min(1.6,Math.pow(luminance/Math.max(1,mean),.85))),a=alpha[i+3]/255;for(let ch=0;ch<3;ch++)out.data[i+ch]=Math.min(255,rgb[ch]*light)*a+out.data[i+ch]*(1-a);}
    }
    ctx.putImageData(out,0,0);
  }
  function captureLayer(id,canvas){if(!['after','cmpB'].includes(id))return;syncScene();bases.set(id,copy(canvas));apply(canvas,bases.get(id));}
  function repaint(){revision++;for(const[id,base]of bases){const canvas=$(id);if(canvas.width===base.width&&canvas.height===base.height)apply(canvas,base);}renderPanel();c.paintChrome();}
  function remember(){history.push(JSON.stringify({walls,selected}));if(history.length>20)history.shift();}
  function setColor(color){const w=current();if(!w||w.color===color)return;remember();w.color=color;$('wallColor').value=color;cancelAnimationFrame(raf);raf=requestAnimationFrame(repaint);}
  function renderPanel(){
    const select=$('wallSelect');select.replaceChildren();for(const w of walls){const o=document.createElement('option');o.value=w.id;o.textContent=w.label;select.append(o);}select.value=selected;
    $('wallUndo').disabled=!history.length;select.disabled=!walls.length;$('wallProtect').disabled=!current();$('wallReset').disabled=!current()?.color;
    const w=current();$('wallColor').disabled=!w;if(w?.color)$('wallColor').value=w.color;
    for(const b of $('wallColors').children){b.disabled=!w;b.setAttribute('aria-pressed',String(w?.color===b.dataset.color));}
    $('wallHelp').textContent=walls.length?'Touchez un mur dans la photo, puis choisissez sa teinte. Les contours proposés restent corrigibles.':'Aucun mur proposé pour cette photo. Vous pouvez en tracer un manuellement.';
  }
  function stopDrawing(restore=true){if(restore&&drawingView)c.setVp(drawingView,false);drawingView=null;draft=null;vp.hidden=!selecting;edit.hidden=true;draw();document.body.classList.remove('wall-drawing');}
  function syncScene(){
    const next=sceneKey();if(next===key)return;stopDrawing(false);if(dialog.open)dialog.close();key=next;revision++;bases.clear();history.length=0;lastAnalysis=null;selecting=false;
    if(!scenes.has(key)){scenes.set(key,[]);while(scenes.size>8)scenes.delete(scenes.keys().next().value);}walls=scenes.get(key);selected=walls[0]?.id||'';
    if(c.state.source!=='uploaded'&&next){const requestKey=key;fetch(`../web/data/scenes/${encodeURIComponent(next)}.json`).then(r=>r.ok?r.json():null).then(raw=>{if(!raw?.wallZones||key!==requestKey||walls.length)return;walls.push(...raw.wallZones.map(w=>({...w,polygon:w.polygon.map(p=>({...p})),holes:(w.holes||[]).map(h=>h.map(p=>({...p}))),color:null,prepared:!w.detected})));selected=walls[0]?.id||'';renderPanel();draw();}).catch(()=>{});}
    renderPanel();
  }
  function sync(){syncScene();const analysis=c.state.roomAnalysis?.analysis;if(analysis&&analysis!==lastAnalysis){lastAnalysis=analysis;const zones=analysis.experimental?.walls?.zones;if(c.state.source==='uploaded'&&zones?.length&&!walls.length&&!draft){walls.push(...zones.map(w=>({...w,color:null})));selected=walls[0].id;renderPanel();draw();}}open.disabled=c.state.applying||!$('after').width;open.hidden=c.state.immersive||false;}
  function draw(){const {w,h}=c.sceneSize();outline.width=w;outline.height=h;const ctx=outline.getContext('2d');if(!draft){if(selecting){ctx.strokeStyle='#fff';ctx.lineWidth=2/c.cssScale();const wall=current();if(wall){polygon(ctx,wall.polygon,w,h);ctx.stroke();for(const hole of wall.holes||[]){polygon(ctx,hole,w,h);ctx.stroke();}}}return;}ctx.lineWidth=2/c.cssScale();ctx.strokeStyle='#fff';ctx.fillStyle='rgba(170,105,58,.2)';const points=draft.points;if(points.length){polygon(ctx,points,w,h);ctx.fill();ctx.stroke();}ctx.fillStyle='#fff';for(const p of points){ctx.beginPath();ctx.arc(p.x*w,p.y*h,5/c.cssScale(),0,Math.PI*2);ctx.fill();}$('wallConfirm').disabled=points.length<3;$('wallPointUndo').disabled=!points.length;}
  function startDrawing(kind){c.closeAll();if(c.state.ba)$('baBtn').click();if(c.state.compare)c.startCompare();dialog.close();drawingView={...c.state.vp};c.fitAll(false);draft={kind,points:[],wallId:selected};vp.hidden=false;edit.hidden=false;document.body.classList.add('wall-drawing');$('wallDrawHint').textContent=kind==='hole'?'Touchez les angles de la zone à protéger, puis validez.':'Touchez les angles du mur, puis validez.';c.applyTransform();draw();}
  function contains(points,p){let inside=false;for(let i=0,j=points.length-1;i<points.length;j=i++){const a=points[i],b=points[j];if((a.y>p.y)!==(b.y>p.y)&&p.x<(b.x-a.x)*(p.y-a.y)/(b.y-a.y)+a.x)inside=!inside;}return inside;}
  outline.addEventListener('pointerdown',e=>{e.preventDefault();e.stopPropagation();const r=outline.getBoundingClientRect(),p={x:Math.max(0,Math.min(1,(e.clientX-r.left)/r.width)),y:Math.max(0,Math.min(1,(e.clientY-r.top)/r.height))};if(draft)draft.points.push(p);else if(selecting){const wall=walls.find(w=>contains(w.polygon,p)&&!(w.holes||[]).some(h=>contains(h,p)));if(wall){selected=wall.id;renderPanel();$('wallMessage').textContent=wall.label+' sélectionné.';}else $('wallMessage').textContent='Aucun mur à cet endroit.';}draw();});
  outline.addEventListener('pointermove',e=>e.stopPropagation());outline.addEventListener('pointerup',e=>e.stopPropagation());
  for(const n of [dialog,edit,open])n.addEventListener('pointerdown',e=>e.stopPropagation());
  $('wallNew').onclick=()=>startDrawing('wall');$('wallProtect').onclick=()=>startDrawing('hole');$('wallPointUndo').onclick=()=>{draft?.points.pop();draw();};
  $('wallCancel').onclick=()=>{stopDrawing();dialog.show();};
  $('wallConfirm').onclick=()=>{if(!draft||draft.points.length<3)return;remember();if(draft.kind==='hole'){walls.find(w=>w.id===draft.wallId)?.holes.push(draft.points);}else{const id=`mur-${Date.now()}`;walls.push({id,label:`Mur ${walls.length+1}`,polygon:draft.points,holes:[],color:null});selected=id;}stopDrawing();repaint();dialog.show();$('wallMessage').textContent='Contour enregistré. Choisissez une teinte ou protégez une autre zone.';};
  $('wallUndo').onclick=()=>{if(!history.length)return;const prior=JSON.parse(history.pop());walls.splice(0,walls.length,...prior.walls);selected=prior.selected;repaint();};$('wallReset').onclick=()=>{remember();if(current())current().color=null;repaint();};$('wallSelect').onchange=e=>{selected=e.target.value;renderPanel();draw();};$('wallColor').oninput=e=>setColor(e.target.value);
  $('wallClose').onclick=()=>{selecting=false;vp.hidden=true;open.setAttribute('aria-pressed','false');floors.setAttribute('aria-pressed','true');dialog.close();};open.onclick=()=>{if($('photoMore').getAttribute('aria-expanded')==='true')$('photoMore').click();c.closeAll();if(c.state.ba)$('baBtn').click();if(c.state.compare)c.startCompare();syncScene();selecting=true;vp.hidden=false;open.setAttribute('aria-pressed','true');floors.setAttribute('aria-pressed','false');renderPanel();$('wallMessage').textContent='';dialog.show();c.applyTransform();draw();};
  floors.onclick=()=>$('wallClose').click();window.addEventListener('keydown',e=>{if(selecting&&!draft&&e.key==='Escape'){$('wallClose').click();return;}if(draft&&e.key==='Escape'){e.preventDefault();stopDrawing();dialog.show();}});
  window.addEventListener('pagehide',()=>{bases.clear();scenes.clear();});
  window.__wallPaint={sync,captureLayer,get revision(){return revision;},get walls(){return walls;}};sync();
}