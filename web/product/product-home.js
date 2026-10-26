import { installComparisonView } from './comparison-view.js';
import { installPhoneTransfer } from './phone-transfer.js';
import { installCatalogBrowser } from './catalog-browser.js';
/** Room select, session-only photos and local export. No persistent photo storage. */
export function installProductHome(getConcept) {
  const c=getConcept();if(!c)return;
  const session=new Map();let next=0;
  const root=document.getElementById('sessionRooms');
  const renderSession=()=>{
    root.replaceChildren();
    if(!session.size){const p=document.createElement('p');p.className='empty-session';p.textContent='Vos photos apparaîtront ici pendant cette session. Elles disparaissent lorsque vous fermez la page.';root.appendChild(p);return;}
    for(const [id,room] of session){
      const item=document.createElement('div');item.className='session-room';
      const open=document.createElement('button');open.type='button';open.className='session-open';
      const img=document.createElement('img');img.src=room.url;img.alt='';
      const name=document.createElement('span');name.textContent=room.name;
      open.append(img,name);open.onclick=()=>c.loadUpload(room.file);
      const remove=document.createElement('button');remove.type='button';remove.className='session-remove';remove.textContent='×';remove.setAttribute('aria-label',`Supprimer ${room.name}`);
      remove.onclick=()=>{if(c.state.uploaded?.url===room.url)home();URL.revokeObjectURL(room.url);session.delete(id);renderSession();};
      item.append(open,remove);root.appendChild(item);
    }
  };
  function home(){c.closeAll();c.releaseUpload();c.state.source=null;c.state.intent+=1;c.state.applied={key:null,source:null};c.state.compare=null;c.adapter.forget();document.getElementById('entry').classList.remove('hidden');document.getElementById('stage').classList.add('hidden');document.getElementById('hSwap').classList.add('hidden');c.drawer.syncLayout();c.paintChrome();c.paintQuick();renderSession();}
  window.__sessionRooms={
    owns:url=>[...session.values()].some(r=>r.url===url),
    remember(file,url){const existing=[...session.entries()].find(([,r])=>r.file===file);if(existing){URL.revokeObjectURL(existing[1].url);session.set(existing[0],{file,url,name:existing[1].name});}else session.set(++next,{file,url,name:`Ma pièce ${next}`});renderSession();},
    clear(){if(c.state.source==='uploaded')home();for(const room of session.values())URL.revokeObjectURL(room.url);session.clear();renderSession();},
    get count(){return session.size;},home,
  };
  const back=document.createElement('button');back.id='homeReturn';back.className='home-return';back.type='button';back.textContent='‹ Pièces';back.setAttribute('aria-label','Retour à mes pièces');back.onclick=home;document.querySelector('header').insertBefore(back,document.getElementById('hSwap'));
  const download=document.createElement('button');download.type='button';download.textContent='Télécharger le rendu';download.title='Télécharger le rendu';download.setAttribute('aria-label','Télécharger le rendu');
  download.onclick=()=>{if(c.state.applying)return;const canvas=document.getElementById('after');if(!canvas?.width||!c.state.applied.source)return;canvas.toBlob(blob=>{if(!blob)return;const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='mon-parquet.jpg';a.click();window.dispatchEvent(new Event('pp:download'));setTimeout(()=>URL.revokeObjectURL(url),5000);},'image/jpeg',.94);};
  const tools=document.getElementById('tools');
  const actions=document.createElement('div');actions.id='photoActions';actions.hidden=true;
  const more=document.createElement('button');more.type='button';more.id='photoMore';more.textContent='⋯';more.setAttribute('aria-label','Options de la photo');more.setAttribute('aria-expanded','false');
  const toggle=show=>{actions.hidden=!show;more.setAttribute('aria-expanded',String(show));};
  more.onclick=()=>toggle(actions.hidden);
  const fullscreen=document.getElementById('fsBtn');const fsLabel=document.createElement('span');fsLabel.className='photo-option-label';fsLabel.textContent='Plein écran';fullscreen.appendChild(fsLabel);actions.appendChild(fullscreen);actions.appendChild(download);actions.appendChild(document.getElementById('zoombar'));
  const whole=document.createElement('button');whole.type='button';whole.textContent='Voir toute la pièce';whole.onclick=()=>{toggle(false);c.fitAll(true);};actions.appendChild(whole);
  const adjust=document.createElement('button');adjust.type='button';adjust.textContent='Ajuster le sol';adjust.onclick=()=>{toggle(false);c.floorEditStart();};actions.appendChild(adjust);
  tools.append(more,actions);
  document.addEventListener('keydown',e=>{if(e.key==='Escape')toggle(false);});
  document.addEventListener('pointerdown',e=>{if(!tools.contains(e.target))toggle(false);});
  const scan=document.createElement('div');scan.id='photoScan';scan.setAttribute('aria-hidden','true');document.getElementById('stage').appendChild(scan);
  const sync=()=>{back.hidden=!c.state.source;adjust.hidden=c.state.source!=='uploaded';download.disabled=c.state.applying||!c.state.applied.source;};
  const observer=new MutationObserver(sync);observer.observe(document.getElementById('stage'),{attributes:true,attributeFilter:['class']});observer.observe(document.body,{attributes:true,attributeFilter:['data-product-state']});sync();
  document.getElementById('hSwap').onclick=home;
  document.getElementById('menuRooms').onclick=home;
  document.getElementById('developerMenu').hidden=!c.DEV;
  const closeOptions=()=>toggle(false);
  document.getElementById('hSwap').addEventListener('click',closeOptions);
  back.addEventListener('click',closeOptions);
  document.getElementById('menuRooms').addEventListener('click',closeOptions);
  document.getElementById('catalogSummary').textContent=c.resumeCatalogue();
  installCatalogBrowser(c);
  installPhoneTransfer(c);
  installComparisonView(c);
  renderSession();
}
