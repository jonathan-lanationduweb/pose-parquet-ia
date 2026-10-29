/** Proposals are editable drafts. Only an explicit human validation exports GT. */
const $=id=>document.getElementById(id),NS='http://www.w3.org/2000/svg';
const state={scene:null,record:null,selected:null,mode:'foreground',workflow:'assisted-review',scale:1,draft:[],gesture:null,visible:true,dirty:false,proposals:[],history:new Map(),redo:new Map()};
const labels={sofa:'Canapé',table:'Table',chair:'Chaise','thin-leg':'Pied fin',rug:'Tapis','low-cabinet':'Meuble bas',radiator:'Radiateur',plant:'Plante',cable:'Câble',bed:'Lit','other-furniture':'Autre meuble','small-object':'Petit objet','negative-region':'Sol contrôlé (négatif)'};
let manifest;
const say=(text,error=false)=>{$('status').textContent=text;$('status').style.color=error?'#a32b19':'#375438';};
const object=()=>state.record?.objects.find(o=>o.id===state.selected);
const proposal=o=>state.proposals.find(p=>p.id===o?.proposal?.id);
const approved=o=>o?.reviewed===true&&o?.humanConfirmed===true;
const clone=value=>JSON.parse(JSON.stringify(value));
function editable(o){return clone({drawings:o.drawings,region:o.region,useProposal:o.useProposal||false,category:o.category});}
function remember(){const o=object();if(!o)return;const history=state.history.get(o.id)||[];history.push(editable(o));if(history.length>40)history.shift();state.history.set(o.id,history);state.redo.set(o.id,[]);}
function changed(){state.dirty=true;state.record.status='draft';state.record.humanConfirmed=false;$('human').checked=false;const o=object();if(o){o.reviewed=false;o.humanConfirmed=false;o.humanReviewed=false;$('reviewed').checked=false;}say('Brouillon modifié — non validé');badge();}
const svg=(tag,attrs)=>{const node=document.createElementNS(NS,tag);for(const [key,value] of Object.entries(attrs))node.setAttribute(key,String(value));return node;};
const path=points=>points.map((p,i)=>(i?'L':'M')+p.join(' ')).join(' ');
function stamp(mask,d,color){const attrs={d:path(d.points)+(d.kind==='polygon'?' Z':''),fill:d.kind==='polygon'?color:'none',stroke:color,'stroke-width':d.kind==='brush'?d.radius*2:0,'stroke-linecap':'round','stroke-linejoin':'round'};mask.append(d.points.length===1?svg('circle',{cx:d.points[0][0],cy:d.points[0][1],r:d.radius,fill:color}):svg('path',attrs));}
function bitmap(p){const [x0,y0,x1,y1]=p.bounds;return svg('image',{x:x0,y:y0,width:x1-x0,height:y1-y0,href:p.png,'image-rendering':'pixelated'});}
function fullMask(id){return svg('mask',{id,maskUnits:'userSpaceOnUse',x:0,y:0,width:state.scene.width,height:state.scene.height});}
function badge(){const o=object();$('origin').textContent=o?(approved(o)?'VALIDÉ HUMAINEMENT · ':'NON VALIDÉ · ')+(o.annotationMode==='assisted-review'?'Annotation assistée, source V5.1':'Tracé manuel'):state.workflow==='assisted-review'?'Cliquez une zone orange ou ajoutez un objet manquant.':'Mode manuel : masques vierges pour les nouveaux objets.';}
function render(){
 const overlay=$('overlay');overlay.replaceChildren();if(!state.scene||!state.visible)return;
 if(state.workflow==='assisted-review')for(const p of state.proposals){
  const mask=fullMask('suggest-'+p.id);mask.append(bitmap(p));overlay.append(mask);
  overlay.append(svg('rect',{x:0,y:0,width:state.scene.width,height:state.scene.height,fill:'#f58b22',opacity:.38,mask:'url(#suggest-'+p.id+')','pointer-events':'none'}));
 }
 for(const o of state.record.objects){
  const selected=o.id===state.selected,group=svg('g',{opacity:selected ? 0.8 : 0.35,'pointer-events':'none'});
  const mask=fullMask('mask-'+o.id),base=proposal(o);
  if(o.useProposal&&base)mask.append(bitmap(base));
  for(const d of o.drawings)if(d.mode!=='uncertain')stamp(mask,d,d.mode==='erase'?'black':'white');
  overlay.append(mask);group.append(svg('rect',{x:0,y:0,width:state.scene.width,height:state.scene.height,fill:'#ef3535',mask:'url(#mask-'+o.id+')'}));
  const unsure=fullMask('uncertain-'+o.id);for(const d of o.drawings)if(d.mode!=='foreground')stamp(unsure,d,d.mode==='erase'?'black':'white');overlay.append(unsure);
  group.append(svg('rect',{x:0,y:0,width:state.scene.width,height:state.scene.height,fill:'#ffd132',mask:'url(#uncertain-'+o.id+')'}));
  if(o.region){const [x0,y0,x1,y1]=o.region,clip=svg('clipPath',{id:'roi-'+o.id});clip.append(svg('rect',{x:x0,y:y0,width:x1-x0,height:y1-y0}));overlay.append(clip);group.setAttribute('clip-path','url(#roi-'+o.id+')');}
  overlay.append(group);
  if(selected&&o.region){const [x0,y0,x1,y1]=o.region;overlay.append(svg('rect',{x:x0,y:y0,width:x1-x0,height:y1-y0,fill:'none',stroke:'#1679dc','stroke-width':2,'stroke-dasharray':'8 5','vector-effect':'non-scaling-stroke','pointer-events':'none'}));}
 }
 const pending=state.gesture?.points||state.draft;
 if(pending.length){overlay.append(svg('path',{d:path(pending),fill:'none',stroke:state.mode==='uncertain'?'#ffd132':state.mode==='erase'?'white':'#ff3535','stroke-width':state.gesture?Number($('radius').value)*2:2,'vector-effect':state.gesture?'none':'non-scaling-stroke','stroke-linecap':'round','pointer-events':'none'}));for(const p of state.draft)overlay.append(svg('circle',{cx:p[0],cy:p[1],r:2.5*state.scene.width/$('board').getBoundingClientRect().width,fill:'white',stroke:'#f33','pointer-events':'none'}));}
 if(state.gesture?.region){const [a,b]=state.gesture.region;overlay.append(svg('rect',{x:Math.min(a[0],b[0]),y:Math.min(a[1],b[1]),width:Math.abs(a[0]-b[0]),height:Math.abs(a[1]-b[1]),fill:'#1679dc22',stroke:'#1679dc','vector-effect':'non-scaling-stroke','pointer-events':'none'}));}
}
function objectList(){const select=$('objects');select.replaceChildren();for(const o of state.record.objects)select.add(new Option((labels[o.category]||o.category)+' · '+o.id.slice(-6)+(approved(o)?' ✓':''),o.id));select.value=state.selected||'';const o=object();$('notes').value=o?.notes||'';$('reviewed').checked=!!o?.reviewed;$('objectCategory').value=o?.category||'sofa';for(const id of ['delete','reviewed','notes','objectCategory','validateObject'])$(id).disabled=!o;$('useProposal').disabled=$('dropProposal').disabled=!proposal(o);badge();render();}
function point(event){const rect=$('board').getBoundingClientRect();return [Math.max(0,Math.min(state.scene.width-1,(event.clientX-rect.left)*state.scene.width/rect.width)),Math.max(0,Math.min(state.scene.height-1,(event.clientY-rect.top)*state.scene.height/rect.height))];}
function insideProposal(p,pos){const index=Math.floor(pos[1])*state.scene.width+Math.floor(pos[0]);let low=0,high=p.runs.length-1;while(low<=high){const mid=(low+high)>>1,[start,length]=p.runs[mid];if(index<start)high=mid-1;else if(index>=start+length)low=mid+1;else return true;}return false;}
function chooseProposal(p){let o=state.record.objects.find(o=>o.proposal?.id===p.id);if(!o){o={id:'object-'+crypto.randomUUID(),category:p.category,notes:'',region:[...p.region],reviewed:false,humanConfirmed:false,drawings:[],annotationMode:'assisted-review',useProposal:true,proposal:{id:p.id,hash:p.hash,source:p.source}};state.record.objects.push(o);state.selected=o.id;changed();}else state.selected=o.id;state.draft=[];$('human').checked=false;$('kind').value='brush';setMode('foreground');objectList();}
function finish(){if(state.draft.length<3){say('Placez au moins trois points pour fermer le contour.',true);return;}remember();object().drawings.push({kind:'polygon',mode:state.mode,radius:Number($('radius').value),points:state.draft});state.draft=[];changed();objectList();}
function setMode(mode){if(state.draft.length&&!confirm('Abandonner le contour en cours ?'))return;state.mode=mode;state.draft=[];state.gesture=null;$('board').classList.toggle('hand',mode==='hand');for(const b of document.querySelectorAll('[data-mode]'))b.classList.toggle('selected',b.dataset.mode===mode);render();}
function zoom(value){state.scale=Math.max(1,Math.min(12,value));$('board').style.width=(state.scale*100)+'%';$('zoom').textContent=Math.round(state.scale*100)+' %';render();}
async function load(ident){
 if(state.dirty&&!confirm('Cette photo contient des modifications non enregistrées. Changer sans les enregistrer ?')){$('scene').value=state.scene.id;return;}
 state.scene=manifest.scenes.find(s=>s.id===ident);state.draft=[];state.gesture=null;state.selected=null;state.history.clear();state.redo.clear();
 const responses=await Promise.all([fetch('/api/annotation/'+ident),fetch('/api/proposals/'+ident)]);
 if(!responses[0].ok)throw Error('Lecture du relevé impossible');const saved=await responses[0].json(),suggestions=await responses[1].json();
 if(saved&&saved.sourceSha256!==state.scene.sha256)throw Error('Le relevé appartient à une autre version de la photo.');
 state.proposals=suggestions.proposals||[];
 state.record=saved||{schema:'pose-parquet-ai/human-foreground@1',scene:ident,sourceSha256:state.scene.sha256,width:state.scene.width,height:state.scene.height,status:'draft',annotator:$('author').value,objects:[],humanConfirmed:false,emptySceneConfirmed:false};
 if(saved?.status==='reviewed-regions'&&saved.humanConfirmed)for(const o of state.record.objects)if(o.reviewed)o.humanConfirmed=true;
 if(saved?.annotator)$('author').value=saved.annotator;$('human').checked=false;$('empty').checked=!!saved?.emptySceneConfirmed;
 $('photo').src='/photo/'+ident;await $('photo').decode();$('overlay').setAttribute('viewBox','0 0 '+state.scene.width+' '+state.scene.height);
 $('dimensions').textContent=state.scene.width+' × '+state.scene.height+' px · '+state.proposals.length+' propositions, '+state.record.objects.filter(approved).length+' objets validés';
 state.selected=state.record.objects[0]?.id||null;state.dirty=false;zoom(1);$('stage').scrollTo(0,0);setMode(state.workflow==='assisted-review'?'select':'foreground');objectList();say(saved?'Relevé local chargé':state.proposals.length?'Propositions prêtes — aucune GT validée':'Masques vierges : ajoutez le premier objet');
}
async function save(all=false){
 if(state.draft.length||state.gesture){say('Fermez ou abandonnez le tracé courant avant d’enregistrer.',true);return false;}
 const payload={...state.record,annotator:$('author').value.trim(),humanConfirmed:all&&$('human').checked,emptySceneConfirmed:$('empty').checked,status:all?'reviewed-regions':'draft'};
 $('save').disabled=$('draft').disabled=$('validateObject').disabled=true;
 try{const response=await fetch('/api/annotation/'+state.scene.id,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}),result=await response.json();if(!response.ok)throw Error(result.error||'Échec de sauvegarde');state.record=result.record||payload;state.dirty=false;objectList();say(result.status==='draft'?'Brouillon enregistré sur ce PC':'Validation humaine enregistrée ; masques PNG et suivi mis à jour');await progress();return true;}
 catch(error){say(error.message,true);return false;}finally{$('save').disabled=$('draft').disabled=false;$('validateObject').disabled=!object();}
}
function newObject(category){const o={id:'object-'+crypto.randomUUID(),category,notes:'',region:null,reviewed:false,humanConfirmed:false,drawings:[],annotationMode:'manual',useProposal:false};state.record.objects.push(o);state.selected=o.id;$('empty').checked=false;changed();objectList();setMode('region');}
$('board').addEventListener('pointerdown',event=>{
 if(!state.scene)return;event.preventDefault();const pos=point(event);
 if(state.mode==='select'){const candidates=state.proposals.filter(p=>insideProposal(p,pos)).sort((a,b)=>a.area-b.area);if(candidates.length)chooseProposal(candidates[0]);else say('Aucune proposition ici : utilisez « Ajouter un objet manquant ».');return;}
 if(state.mode==='hand'){state.gesture={pan:[event.clientX,event.clientY,$('stage').scrollLeft,$('stage').scrollTop]};$('board').setPointerCapture(event.pointerId);return;}
 if(!object()){say('Choisissez un objet proposé ou ajoutez un objet manquant.',true);return;}
 if(state.mode==='region')state.gesture={region:[pos,pos]};else if($('kind').value==='brush')state.gesture={points:[pos]};else{state.draft.push(pos);state.dirty=true;render();return;}$('board').setPointerCapture(event.pointerId);render();
});
$('board').addEventListener('pointermove',event=>{const g=state.gesture;if(!g)return;if(g.pan){$('stage').scrollLeft=g.pan[2]+g.pan[0]-event.clientX;$('stage').scrollTop=g.pan[3]+g.pan[1]-event.clientY;}else if(g.region){g.region[1]=point(event);render();}else if(g.points){g.points.push(point(event));render();}});
$('board').addEventListener('pointerup',()=>{const g=state.gesture;if(!g)return;state.gesture=null;if(g.region){const [a,b]=g.region;if(Math.abs(a[0]-b[0])<1||Math.abs(a[1]-b[1])<1){say('La zone doit avoir une surface positive.',true);render();return;}remember();object().region=[Math.min(a[0],b[0]),Math.min(a[1],b[1]),Math.max(a[0],b[0])+1,Math.max(a[1],b[1])+1];changed();}else if(g.points){remember();object().drawings.push({kind:'brush',mode:state.mode,radius:Number($('radius').value),points:g.points});changed();}objectList();});
$('board').addEventListener('pointercancel',()=>{state.gesture=null;render();});
for(const b of document.querySelectorAll('[data-mode]'))b.onclick=()=>setMode(b.dataset.mode);
$('workflow').onchange=()=>{state.workflow=$('workflow').value;$('proposalLabel').hidden=state.workflow!=='assisted-review';$('kind').value=state.workflow==='manual'?'polygon':'brush';setMode(state.workflow==='manual'?'foreground':'select');badge();};
$('scene').onchange=()=>load($('scene').value).catch(e=>say(e.message,true));$('add').onclick=()=>newObject($('category').value);$('negative').onclick=()=>newObject('negative-region');
$('objects').onchange=()=>{if(state.draft.length&&!confirm('Abandonner le contour en cours ?')){$('objects').value=state.selected;return;}state.draft=[];state.selected=$('objects').value;$('human').checked=false;objectList();};
$('objectCategory').onchange=()=>{if(object()){remember();object().category=$('objectCategory').value;changed();objectList();}};
$('delete').onclick=()=>{if(!object()||!confirm('Supprimer cet objet et ses tracés ?'))return;state.record.objects=state.record.objects.filter(o=>o.id!==state.selected);state.selected=state.record.objects[0]?.id||null;changed();objectList();};
$('notes').oninput=()=>{if(object()){object().notes=$('notes').value;changed();}};
$('reviewed').onchange=()=>{if(object()){object().reviewed=$('reviewed').checked;if(!object().reviewed)object().humanConfirmed=false;state.dirty=true;objectList();say('Relecture déclarée ; cliquez « Valider cet objet » pour confirmer.');}};
$('author').oninput=()=>{if(state.record){state.dirty=true;$('human').checked=false;}};$('empty').onchange=()=>{if($('empty').checked&&state.record.objects.length){$('empty').checked=false;say('Une photo avec objets ne peut pas être déclarée vide.',true);return;}state.dirty=true;};$('human').onchange=()=>{state.dirty=true;};
$('useProposal').onclick=()=>{if(proposal(object())){remember();object().useProposal=true;changed();objectList();}};$('dropProposal').onclick=()=>{if(object()){remember();object().useProposal=false;changed();objectList();}};
$('validateObject').onclick=async()=>{const o=object();if(!o)return;if(!$('author').value.trim()||!$('reviewed').checked){say('Indiquez votre nom et confirmez la relecture de l’objet et du vrai sol autour.',true);return;}o.reviewed=true;o.humanConfirmed=true;o.humanReviewed=true;o.annotator=$('author').value.trim();if(!await save(false)){o.humanConfirmed=false;badge();}};
$('next').onclick=async()=>{if(state.dirty&&!await save(false))return;const pending=state.record.objects.find(o=>o.id!==state.selected&&!approved(o));if(pending){state.selected=pending.id;$('human').checked=false;objectList();return;}const p=state.proposals.find(p=>!state.record.objects.some(o=>o.proposal?.id===p.id));if(p)chooseProposal(p);else{setMode('select');say('Plus de proposition : ajoutez les objets manquants ou une zone négative.');}};
$('draft').onclick=()=>save(false);$('save').onclick=()=>save(true);$('finish').onclick=finish;
function historyMove(undo){const o=object();if(!o)return;if(state.draft.length&&undo){state.draft.pop();render();return;}const from=(undo?state.history:state.redo).get(o.id)||[],to=(undo?state.redo:state.history).get(o.id)||[];if(!from.length)return;to.push(editable(o));Object.assign(o,from.pop());(undo?state.redo:state.history).set(o.id,to);changed();objectList();}
$('undo').onclick=()=>historyMove(true);$('redo').onclick=()=>historyMove(false);
$('plus').onclick=()=>zoom(state.scale*1.5);$('minus').onclick=()=>zoom(state.scale/1.5);$('fit').onclick=()=>zoom(1);$('visibility').onclick=()=>{state.visible=!state.visible;$('visibility').textContent='Masques : '+(state.visible?'visibles':'masqués');render();};
$('stage').addEventListener('wheel',e=>{if(!e.ctrlKey)return;e.preventDefault();zoom(state.scale*(e.deltaY<0?1.15:1/1.15));},{passive:false});
window.addEventListener('keydown',e=>{if(['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName))return;if(e.key==='Enter'&&state.draft.length){e.preventDefault();finish();}if(e.key==='Escape'){state.draft=[];state.gesture=null;render();}});
window.addEventListener('beforeunload',e=>{if(state.dirty){e.preventDefault();e.returnValue='';}});
async function progress(){try{const r=await fetch('/api/evaluation'),p=await r.json();$('evaluation').textContent=p.status==='checking'?'Vérification des régions humaines enregistrées…':p.status==='evaluating'?'Évaluation en cours : métriques puis observation locale si CASE C…':p.status==='error'?'Évaluation à reprendre : '+p.error:(p.objects||0)+'/5 objets relus · '+(p.categories?.length||0)+'/3 catégories · '+(p.negativeRegions||0)+'/1 zone négative'+(p.status==='complete'?' · PRELIMINARY HUMAN GT · '+p.verdict:' · En attente du minimum humain');$('evaluationReport').hidden=p.status!=='complete';}catch{$('evaluation').textContent='Suivi temporairement indisponible ; vos tracés restent dans le navigateur.';}}
try{const response=await fetch('/api/manifest');manifest=await response.json();for(const s of manifest.scenes)$('scene').add(new Option(s.title,s.id));for(const category of manifest.categories){if(category!=='negative-region')$('category').add(new Option(labels[category]||category,category));$('objectCategory').add(new Option(labels[category]||category,category));}if(!manifest.scenes.length)throw Error('Aucune photo privée disponible');await load(manifest.scenes[0].id);await progress();setInterval(progress,4000);}catch(e){say(e.message,true);}
