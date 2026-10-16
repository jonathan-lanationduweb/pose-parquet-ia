/** Two genuine full-frame renders, or the existing draggable comparison. */
export function installComparisonView(c) {
  const stage=document.getElementById('stage'),split=document.getElementById('split');
  const controls=document.createElement('div');controls.id='compareViewControls';controls.hidden=true;controls.setAttribute('role','group');controls.setAttribute('aria-label','Présentation de la comparaison');
  const make=(text,id)=>{const b=document.createElement('button');b.type='button';b.id=id;b.textContent=text;controls.append(b);return b;};
  const slider=make('Curseur','compareSlider'),side=make('Côte à côte','compareSideBySide'),close=make('×','compareClose');close.setAttribute('aria-label','Fermer la comparaison');side.innerHTML='<span class="comparison-desktop-label">Côte à côte</span><span class="comparison-mobile-label">Deux vues</span>';
  const views=document.createElement('div');views.id='comparisonSides';views.hidden=true;
  const panels=['A','B'].map(letter=>{const panel=document.createElement('section'),label=document.createElement('h3'),canvas=document.createElement('canvas');canvas.id=`comparisonCanvas${letter}`;panel.append(label,canvas);views.append(panel);return{label,canvas};});
  stage.append(views,controls);let mode='slider',signature=null;
  split.setAttribute('role','slider');split.tabIndex=0;split.setAttribute('aria-label','Position du séparateur de comparaison');split.setAttribute('aria-valuemin','2');split.setAttribute('aria-valuemax','98');
  function setMode(next){mode=next;signature=null;c.paintChrome();}
  slider.onclick=()=>setMode('slider');side.onclick=()=>setMode('side');
  close.onclick=()=>{if(c.state.compare)c.startCompare();else document.getElementById('baBtn').click();};
  split.addEventListener('keydown',e=>{const dir={ArrowLeft:-1,ArrowRight:1,ArrowDown:-1,ArrowUp:1}[e.key];if(!dir&&!['Home','End'].includes(e.key))return;e.preventDefault();e.stopPropagation();c.state.split=e.key==='Home'?.02:e.key==='End'?.98:Math.max(.02,Math.min(.98,c.state.split+dir*(e.shiftKey?.1:.02)));c.paintChrome();});
  function copy(canvas,source){const w=source?.naturalWidth||source?.width,h=source?.naturalHeight||source?.height;if(!w||!h){canvas.width=0;canvas.height=0;return;}const scale=Math.min(1,1600/w);canvas.width=Math.round(w*scale);canvas.height=Math.round(h*scale);canvas.getContext('2d').drawImage(source,0,0,canvas.width,canvas.height);}
  function sync(){
    const after=document.getElementById('after'),compare=c.state.compare;
    const active=Boolean((compare||c.state.ba)&&after.width&&!c.photoSansScene());controls.hidden=!active;
    if(!active){mode='slider';signature=null;for(const p of panels)if(p.canvas.width){p.canvas.width=0;p.canvas.height=0;}}
    const both=active&&mode==='side';views.hidden=!both;stage.classList.toggle('side-by-side',both);
    slider.setAttribute('aria-pressed',String(mode==='slider'));side.setAttribute('aria-pressed',String(mode==='side'));
    split.setAttribute('aria-valuenow',String(Math.round(c.state.split*100)));split.setAttribute('aria-valuetext',`${Math.round(c.state.split*100)} %`);if(both)split.classList.add('hidden');
    if(!both)return;
    const readyB=Boolean(compare&&c.state.appliedB?.key?.split('|')[1]===compare.b);
    const key=JSON.stringify([c.state.applied.key,c.state.appliedB?.key,c.state.uploaded?.url,c.state.roomId,compare?.b,c.state.ba,readyB,window.__wallPaint?.revision]);if(key===signature)return;signature=key;
    panels[0].label.textContent=compare?`A · ${c.product().name}`:'Avant';
    panels[1].label.textContent=compare?(readyB?`B · ${c.product(compare.b).name}`:'Préparation du parquet B…'):'Après';
    copy(panels[0].canvas,compare?after:document.getElementById('photo'));
    copy(panels[1].canvas,compare?(readyB?document.getElementById('cmpB'):null):after);
  }
  document.getElementById('photo').addEventListener('load',()=>{signature=null;sync();});
  window.__comparisonView={sync};sync();
}
