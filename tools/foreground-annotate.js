/** Human gestures only. No model output, auto-mask, contour suggestion or sample GT. */
const $=id=>document.getElementById(id), NS='http://www.w3.org/2000/svg';
const state={scene:null,record:null,selected:null,mode:'foreground',scale:1,draft:[],gesture:null,visible:true,dirty:false};
let manifest;
const say=(text,error=false)=>{$('status').textContent=text;$('status').style.color=error?'#a32b19':'#375438';};
const object=()=>state.record?.objects.find(o=>o.id===state.selected);
function changed(){state.dirty=true;state.record.status='draft';state.record.humanConfirmed=false;$('human').checked=false;const o=object();if(o){o.reviewed=false;$('reviewed').checked=false;}say('Modifications non enregistrées');}
const svg=(tag,attrs)=>{const node=document.createElementNS(NS,tag);for(const [key,value] of Object.entries(attrs))node.setAttribute(key,String(value));return node;};
function path(points){return points.map((p,i)=>(i?'L':'M')+p.join(' ')).join(' ');}
function render(){
 const overlay=$('overlay');overlay.replaceChildren();if(!state.scene||!state.visible)return;
 for(const o of state.record.objects){
  const selected=o.id===state.selected,group=svg('g',{opacity:selected ? 0.75 : 0.3});
  const mask=svg('mask',{id:'mask-'+o.id,maskUnits:'userSpaceOnUse',x:0,y:0,width:state.scene.width,height:state.scene.height});
  for(const d of o.drawings){if(d.mode==='uncertain')continue;const attrs={d:path(d.points)+(d.kind==='polygon'?' Z':''),fill:d.kind==='polygon'?(d.mode==='erase'?'black':'white'):'none',stroke:d.mode==='erase'?'black':'white','stroke-width':d.kind==='brush'?d.radius*2:0,'stroke-linecap':'round','stroke-linejoin':'round'};if(d.points.length===1)mask.append(svg('circle',{cx:d.points[0][0],cy:d.points[0][1],r:d.radius,fill:attrs.stroke}));else mask.append(svg('path',attrs));}
  overlay.append(mask);group.append(svg('rect',{x:0,y:0,width:state.scene.width,height:state.scene.height,fill:'#f13d3d',mask:'url(#mask-'+o.id+')'}));
  const unsureMask=svg('mask',{id:'uncertain-'+o.id,maskUnits:'userSpaceOnUse',x:0,y:0,width:state.scene.width,height:state.scene.height});
  for(const d of o.drawings){if(d.mode==='foreground')continue;const color=d.mode==='erase'?'black':'white';if(d.points.length===1)unsureMask.append(svg('circle',{cx:d.points[0][0],cy:d.points[0][1],r:d.radius,fill:color}));else unsureMask.append(svg('path',{d:path(d.points)+(d.kind==='polygon'?' Z':''),fill:d.kind==='polygon'?color:'none',stroke:color,'stroke-width':d.kind==='brush'?d.radius*2:0,'stroke-linecap':'round','stroke-linejoin':'round'}));}
  overlay.append(unsureMask);group.append(svg('rect',{x:0,y:0,width:state.scene.width,height:state.scene.height,fill:'#ffd132',mask:'url(#uncertain-'+o.id+')'}));
  if(selected&&o.region){const [x0,y0,x1,y1]=o.region;group.append(svg('rect',{x:x0,y:y0,width:x1-x0,height:y1-y0,fill:'none',stroke:'#1679dc','stroke-width':2/state.scale,'stroke-dasharray':'8 5','vector-effect':'non-scaling-stroke'}));}
  overlay.append(group);
 }
 const pending=state.gesture?.points||state.draft;
 if(pending.length){overlay.append(svg('path',{d:path(pending),fill:'none',stroke:state.mode==='uncertain'?'#ffd132':state.mode==='erase'?'white':'#ff3535','stroke-width':state.gesture?Number($('radius').value)*2:2,'vector-effect':state.gesture?'none':'non-scaling-stroke','stroke-linecap':'round'}));for(const p of state.draft)overlay.append(svg('circle',{cx:p[0],cy:p[1],r:2.5*state.scene.width/$('board').getBoundingClientRect().width,fill:'white',stroke:'#f33'}));}
 if(state.gesture?.region){const [a,b]=state.gesture.region;overlay.append(svg('rect',{x:Math.min(a[0],b[0]),y:Math.min(a[1],b[1]),width:Math.abs(a[0]-b[0]),height:Math.abs(a[1]-b[1]),fill:'#1679dc22',stroke:'#1679dc','vector-effect':'non-scaling-stroke'}));}
}
function objectList(){const select=$('objects');select.replaceChildren();for(const o of state.record.objects){const option=new Option(($('category').querySelector('option[value="'+o.category+'"]')?.textContent||o.category)+' · '+o.id.slice(-6)+(o.reviewed?' ✓':''),o.id);select.add(option);}select.value=state.selected||'';const o=object();$('notes').value=o?.notes||'';$('reviewed').checked=!!o?.reviewed;$('delete').disabled=!o;$('reviewed').disabled=!o;$('notes').disabled=!o;render();}
function point(event){const rect=$('board').getBoundingClientRect();return [Math.max(0,Math.min(state.scene.width-1,(event.clientX-rect.left)*state.scene.width/rect.width)),Math.max(0,Math.min(state.scene.height-1,(event.clientY-rect.top)*state.scene.height/rect.height))];}
function finish(){if(state.draft.length<3){say('Placez au moins trois points pour fermer le contour.',true);return;}object().drawings.push({kind:'polygon',mode:state.mode,radius:Number($('radius').value),points:state.draft});state.draft=[];changed();render();}
function setMode(mode){if(state.draft.length&&!confirm('Abandonner le contour en cours ?'))return;state.mode=mode;state.draft=[];state.gesture=null;$('board').classList.toggle('hand',mode==='hand');for(const b of document.querySelectorAll('[data-mode]'))b.classList.toggle('selected',b.dataset.mode===mode);render();}
function zoom(value){state.scale=Math.max(1,Math.min(12,value));$('board').style.width=(state.scale*100)+'%';$('zoom').textContent=Math.round(state.scale*100)+' %';render();}
async function load(ident){
 if(state.dirty&&!confirm('Cette photo contient des modifications non enregistrées. Changer sans les enregistrer ?')){$('scene').value=state.scene.id;return;}
 state.scene=manifest.scenes.find(s=>s.id===ident);state.draft=[];state.gesture=null;state.selected=null;
 const response=await fetch('/api/annotation/'+ident);if(!response.ok)throw Error('Lecture du relevé impossible');
 const saved=await response.json();if(saved&&saved.sourceSha256!==state.scene.sha256)throw Error('Le relevé existant appartient à une autre version de la photo.');
 state.record=saved||{schema:'pose-parquet-ai/human-foreground@1',scene:ident,sourceSha256:state.scene.sha256,width:state.scene.width,height:state.scene.height,status:'draft',annotator:$('author').value,objects:[],humanConfirmed:false,emptySceneConfirmed:false};
 if(saved?.annotator)$('author').value=saved.annotator;
 $('human').checked=!!saved?.humanConfirmed;$('empty').checked=!!saved?.emptySceneConfirmed;
 $('photo').src='/photo/'+ident;await $('photo').decode();$('overlay').setAttribute('viewBox','0 0 '+state.scene.width+' '+state.scene.height);
 $('dimensions').textContent=state.scene.width+' × '+state.scene.height+' px · '+(saved?.status==='reviewed-regions'?'Zones relues enregistrées':'Brouillon / aucun masque GT validé');
 state.selected=state.record.objects[0]?.id||null;state.dirty=false;zoom(1);$('stage').scrollTo(0,0);objectList();say(saved?'Relevé local chargé':'Masques vierges : ajoutez le premier objet');
}
async function save(reviewed){
 if(state.draft.length||state.gesture){say('Fermez ou abandonnez le tracé courant avant d’enregistrer.',true);return;}
 const payload={...state.record,annotator:$('author').value.trim(),humanConfirmed:$('human').checked,emptySceneConfirmed:$('empty').checked,status:reviewed?'reviewed-regions':'draft'};
 $('save').disabled=$('draft').disabled=true;
 try{const response=await fetch('/api/annotation/'+state.scene.id,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}),result=await response.json();if(!response.ok)throw Error(result.error||'Échec de sauvegarde');state.record=payload;state.dirty=false;say(reviewed?'Zones humaines validées et masques PNG enregistrés':'Brouillon enregistré sur ce PC');}
 catch(error){say(error.message,true);}finally{$('save').disabled=$('draft').disabled=false;}
}
$('board').addEventListener('pointerdown',event=>{
 if(!state.scene)return;event.preventDefault();const pos=point(event);
 if(state.mode==='hand'){state.gesture={pan:[event.clientX,event.clientY,$('stage').scrollLeft,$('stage').scrollTop]};$('board').setPointerCapture(event.pointerId);return;}
 if(!object()){say('Ajoutez puis sélectionnez un objet.',true);return;}
 if(state.mode==='region')state.gesture={region:[pos,pos]};
 else if($('kind').value==='brush')state.gesture={points:[pos]};
 else{state.draft.push(pos);state.dirty=true;render();return;}
 $('board').setPointerCapture(event.pointerId);render();
});
$('board').addEventListener('pointermove',event=>{const g=state.gesture;if(!g)return;if(g.pan){$('stage').scrollLeft=g.pan[2]+g.pan[0]-event.clientX;$('stage').scrollTop=g.pan[3]+g.pan[1]-event.clientY;}else if(g.region){g.region[1]=point(event);render();}else if(g.points){g.points.push(point(event));render();}});
$('board').addEventListener('pointerup',()=>{const g=state.gesture;if(!g)return;state.gesture=null;if(g.region){const [a,b]=g.region;if(Math.abs(a[0]-b[0])<1||Math.abs(a[1]-b[1])<1){say('La zone doit avoir une surface positive.',true);render();return;}object().region=[Math.min(a[0],b[0]),Math.min(a[1],b[1]),Math.max(a[0],b[0])+1,Math.max(a[1],b[1])+1];changed();}else if(g.points){object().drawings.push({kind:'brush',mode:state.mode,radius:Number($('radius').value),points:g.points});changed();}render();});
$('board').addEventListener('pointercancel',()=>{state.gesture=null;render();});
for(const button of document.querySelectorAll('[data-mode]'))button.onclick=()=>setMode(button.dataset.mode);
$('scene').onchange=()=>load($('scene').value).catch(e=>say(e.message,true));
$('add').onclick=()=>{const id='object-'+crypto.randomUUID();state.record.objects.push({id,category:$('category').value,notes:'',region:null,reviewed:false,drawings:[]});state.selected=id;$('empty').checked=false;changed();objectList();setMode('region');};
$('objects').onchange=()=>{if(state.draft.length&&!confirm('Abandonner le contour en cours ?')){$('objects').value=state.selected;return;}state.draft=[];state.selected=$('objects').value;objectList();};
$('delete').onclick=()=>{if(!object()||!confirm('Supprimer cet objet et ses tracés ?'))return;state.record.objects=state.record.objects.filter(o=>o.id!==state.selected);state.selected=state.record.objects[0]?.id||null;changed();objectList();};
$('notes').oninput=()=>{if(object()){object().notes=$('notes').value;changed();}};
$('reviewed').onchange=()=>{if(object()){object().reviewed=$('reviewed').checked;state.dirty=true;objectList();say('État de relecture modifié, à enregistrer');}};
$('author').oninput=()=>{if(state.record)changed();};$('empty').onchange=()=>{if($('empty').checked&&state.record.objects.length){$('empty').checked=false;say('Une photo avec des objets tracés ne peut pas être déclarée vide.',true);return;}state.dirty=true;};$('human').onchange=()=>{state.dirty=true;};
$('draft').onclick=()=>save(false);$('save').onclick=()=>save(true);$('finish').onclick=finish;
$('undo').onclick=()=>{if(state.draft.length)state.draft.pop();else if(object()?.drawings.length){object().drawings.pop();changed();}render();};
$('plus').onclick=()=>zoom(state.scale*1.5);$('minus').onclick=()=>zoom(state.scale/1.5);$('fit').onclick=()=>zoom(1);
$('visibility').onclick=()=>{state.visible=!state.visible;$('visibility').textContent='Masques : '+(state.visible?'visibles':'masqués');render();};
$('stage').addEventListener('wheel',event=>{if(!event.ctrlKey)return;event.preventDefault();zoom(state.scale*(event.deltaY<0?1.15:1/1.15));},{passive:false});
window.addEventListener('keydown',event=>{if(['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName))return;if(event.key==='Enter'&&state.draft.length){event.preventDefault();finish();}if(event.key==='Escape'){state.draft=[];state.gesture=null;render();}});
window.addEventListener('beforeunload',event=>{if(state.dirty){event.preventDefault();event.returnValue='';}});
try{const response=await fetch('/api/manifest');manifest=await response.json();for(const scene of manifest.scenes)$('scene').add(new Option(scene.title,scene.id));const labels={sofa:'Canapé',table:'Table',chair:'Chaise','thin-leg':'Pied fin',rug:'Tapis','low-cabinet':'Meuble bas',radiator:'Radiateur',plant:'Plante',cable:'Câble',bed:'Lit','other-furniture':'Autre meuble','small-object':'Petit objet'};for(const category of manifest.categories)$('category').add(new Option(labels[category]||category,category));if(!manifest.scenes.length)throw Error('Aucune photo privée disponible');await load(manifest.scenes[0].id);}catch(error){say(error.message,true);}
