/** Catalogue responsive : navigation, filtres et présentation des mêmes produits. */
export function installCatalogBrowser(c) {
  const $ = id => document.getElementById(id);
  const pane = $('catSheet'), discovery = pane.querySelector('.catalog-discovery');
  const oldFilters = pane.querySelector('.catalog-filters');
  const create = (tag, cls, text) => { const n = document.createElement(tag); if(cls)n.className=cls; if(text)n.textContent=text; return n; };
  const button = (text, label) => { const b=create('button','',text);b.type='button';if(label)b.setAttribute('aria-label',label);return b; };
  const icon = paths => `<svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" aria-hidden="true">${paths}</svg>`;
  const search = create('div','catalog-search');
  search.innerHTML=icon('<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>');
  const searchInput=$('catSearch');searchInput.placeholder='Rechercher un parquet…';
  search.append(discovery.querySelector('label[for="catSearch"]'),searchInput);
  const toolbar=create('div','catalog-toolbar');
  const open=button('Filtres');open.id='catalogFiltersOpen';open.innerHTML=icon('<path d="M3 6h18M6 12h12M9 18h6"/>')+'<span>Filtres</span><span id="catalogFilterCount" hidden></span>';
  open.setAttribute('aria-controls','catalogFiltersPanel');open.setAttribute('aria-expanded','false');
  const layouts=create('div','catalog-layouts');layouts.setAttribute('role','group');layouts.setAttribute('aria-label','Affichage du catalogue');
  const grid=button('','Vue grille'),list=button('','Vue liste');grid.id='catalogGrid';list.id='catalogList';
  grid.innerHTML=icon('<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>');
  list.innerHTML=icon('<path d="M9 5h12M9 12h12M9 19h12M3 5h1M3 12h1M3 19h1"/>');
  layouts.append(list,grid);toolbar.append(open,layouts);
  const active=create('div','catalog-active');active.id='catalogActiveFilters';active.setAttribute('aria-label','Filtres actifs');
  const collection=$('catCollection'), preview=$('fApercu').closest('label'), about=pane.querySelector('.catalog-about');
  discovery.replaceChildren(search,toolbar,active);
  const panel=create('section','catalog-filter-panel');panel.id='catalogFiltersPanel';panel.hidden=true;panel.setAttribute('aria-label','Filtres du catalogue');
  const head=create('div','catalog-filter-head'), title=create('h2','','Filtres'), back=button('×','Fermer les filtres');back.id='catalogFiltersBack';head.append(title,back);
  const scroll=create('div','catalog-filter-scroll');
  function group(label,content,expanded=true,target=scroll){const d=create('details','catalog-filter-group');d.open=expanded;d.append(create('summary','',label),content);target.append(d);return d;}
  const groups={};
  for(const [id,label] of [['fPattern','Motif de pose'],['fTone','Teinte'],['fWidth','Largeur des lames']]){groups[id]=group(label,$(id));}
  const widths=groups.fWidth.querySelector('#fWidth');widths.hidden=true;
  const range=create('div','catalog-width-range'),rangeValue=create('output');rangeValue.id='catalogWidthValue';
  const limits=c.PREMIBEL_DEMO_PRODUCTS.map(p=>p.widthMm).filter(Number.isFinite);const ceiling=Math.ceil(Math.max(...limits)/10)*10;
  const sliders=[];
  for(const [id,label,value] of [['catalogWidthMin','Minimum',0],['catalogWidthMax','Maximum',ceiling]]){const row=create('label','',label),input=create('input');input.type='range';input.id=id;input.min=0;input.max=ceiling;input.step=5;input.value=value;row.htmlFor=id;row.append(input);range.append(row);sliders.push(input);}
  range.prepend(rangeValue);groups.fWidth.append(range);
  let rangeTimer=0;
  function rangeChange(){const [low,high]=sliders;let min=Number(low.value),max=Number(high.value);if(min>max){if(document.activeElement===low)high.value=min;else low.value=max;min=Number(low.value);max=Number(high.value);}const f=c.state.filters;f.widthMm=null;f.widthMinMm=min===0?null:min;f.widthMaxMm=max===ceiling?null:max;rangeValue.textContent=(!f.widthMinMm&&!f.widthMaxMm)?'Toutes les largeurs':`${min} – ${max} mm`;clearTimeout(rangeTimer);rangeTimer=setTimeout(()=>c.paintCatalogue(),100);}
  for(const slider of sliders){slider.addEventListener('input',rangeChange);slider.addEventListener('change',()=>{clearTimeout(rangeTimer);rangeChange();});}
  const extra=create('details','catalog-more-filters');extra.id='catalogMoreFilters';extra.append(create('summary','','Plus de filtres'));
  const extraBody=create('div');extra.append(extraBody);scroll.append(extra);
  const choices=new Map();
  for(const [key,label,all] of [['usage','Utilisation','Tous'],['finish','Finition','Toutes'],['species','Essence','Toutes'],['type','Type de parquet','Tous']]){
    const options=create('div','chips catalog-value-choices');options.setAttribute('role','group');options.setAttribute('aria-label',label);
    const values=key==='usage'?['interieur','terrasse']:[...new Set(c.PREMIBEL_DEMO_PRODUCTS.map(p=>p[key]).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'fr'));
    if(key==='species')values.sort((a,b)=>Number(b==='Chêne')-Number(a==='Chêne'));
    for(const value of ['',...values]){const b=button(value?(key==='finish'?(c.FINISHES[value]||value):key==='usage'?(value==='terrasse'?'Terrasse':'Intérieur'):value):all);b.className='chip';b.dataset.value=value;b.onclick=()=>{c.state.filters[key]=value||null;if(key==='usage'&&value==='terrasse')c.state.filters.apercu=null;if(key==='species'&&value&&!c.PREMIBEL_DEMO_PRODUCTS.some(p=>p.species===value&&p.renderable!==false))c.state.filters.apercu=null;c.paintCatalogue();};options.append(b);}
    const section=group(label,options,true,extraBody);choices.set(key,options);
    if(values.length>6){options.classList.add('choices-compact');const expand=button('Voir toutes les essences');expand.className='catalog-see-more';expand.setAttribute('aria-expanded','false');expand.onclick=()=>{const on=options.classList.toggle('choices-compact');expand.setAttribute('aria-expanded',String(!on));expand.textContent=on?'Voir toutes les essences':'Voir moins';};section.append(expand);}
  }
  const sources=create('div','catalog-sources');collection.setAttribute('aria-label','Catalogue');sources.append(collection,preview);group('Catalogues et inspirations',sources,false,extraBody);
  // Keep the existing reset and source controls without exposing raw collection codes.
  const legacy=create('div');legacy.hidden=true;legacy.append($('moods'),about.querySelector('p'));extraBody.append(legacy);
  const availability=create('p','catalog-material-note');availability.hidden=true;choices.get('species').after(availability);
  const footer=create('div','catalog-filter-footer'),reset=$('clearFilters'),apply=button('Voir les parquets');reset.textContent='Tout effacer';apply.id='catalogFiltersApply';footer.append(reset,apply);panel.append(head,scroll,footer);pane.append(panel);oldFilters.remove();
  function show(value){panel.hidden=!value;pane.classList.toggle('filters-open',value);open.setAttribute('aria-expanded',String(value));(value?back:open).focus({preventScroll:true});}
  open.onclick=()=>show(true);back.onclick=apply.onclick=()=>show(false);
  pane.addEventListener('keydown',e=>{if(e.key==='Escape'&&!panel.hidden){e.preventDefault();e.stopPropagation();show(false);}});
  // A closed catalogue must reopen on its products, including after a mobile drawer closes.
  new MutationObserver(()=>{if(pane.classList.contains('hidden')&&!panel.hidden){panel.hidden=true;pane.classList.remove('filters-open');open.setAttribute('aria-expanded','false');}}).observe(pane,{attributes:true,attributeFilter:['class']});
  function layout(value){$('prods').dataset.layout=value;grid.setAttribute('aria-pressed',String(value==='grid'));list.setAttribute('aria-pressed',String(value==='list'));}
  grid.onclick=()=>layout('grid');list.onclick=()=>layout('list');layout('grid');
  const labels={usage:'Utilisation',pattern:'Motif',tone:'Teinte',widthMm:'Largeur',finish:'Finition',species:'Essence',type:'Type',collection:'Collection',mood:'Style'};
  function sync(){
    const f=c.state.filters;active.replaceChildren();let count=0;
    if(f.widthMinMm!=null||f.widthMaxMm!=null){count++;const chip=button(`${f.widthMinMm||0} – ${f.widthMaxMm??ceiling} mm ×`,'Retirer le filtre Largeur');chip.onclick=()=>{f.widthMinMm=null;f.widthMaxMm=null;c.paintCatalogue();};active.append(chip);}
    for(const [key,label] of Object.entries(labels)){
      const value=f[key];if(!value)continue;count++;
      const text=key==='usage'?(value==='terrasse'?'Terrasse':'Intérieur'):key==='pattern'?c.PATTERNS[value]:key==='tone'?c.TONES[value]:key==='widthMm'?`${value} mm`:key==='finish'?(c.FINISHES[value]||value):key==='mood'?(c.MOODS.find(m=>m.id===value)?.label||value):value;
      const chip=button(`${text} ×`,`Retirer le filtre ${label} : ${text}`);chip.onclick=()=>{f[key]=null;c.paintCatalogue();};active.append(chip);
    }
    if(c.state.catalogCollection!=='all'){count++;const chip=button((c.state.catalogCollection==='premibel'?'Premibel':'Inspirations')+' ×','Retirer le filtre Catalogue');chip.onclick=()=>{c.state.catalogCollection='all';collection.value='all';c.paintCatalogue();};active.append(chip);}
    active.hidden=count===0;$('catalogFilterCount').textContent=String(count);$('catalogFilterCount').hidden=!count;
    for(const [key,options] of choices)for(const b of options.children)b.setAttribute('aria-pressed',String(b.dataset.value===(f[key]||'')));collection.value=c.state.catalogCollection;
    availability.hidden=!f.species||c.PREMIBEL_DEMO_PRODUCTS.some(p=>p.species===f.species&&p.renderable!==false);availability.textContent='Ces références sont consultables ; leur aperçu 3D reste à préparer.';
    const total=c.visible().filter(p=>c.state.catalogueView!=='favourites'||c.state.favourites.has(p.id)).length;
    apply.textContent=`Voir ${total} parquet${total>1?'s':''}`;
    sliders[0].value=f.widthMinMm??0;sliders[1].value=f.widthMaxMm??ceiling;
    rangeValue.textContent=(f.widthMinMm==null&&f.widthMaxMm==null)?'Toutes les largeurs':`${sliders[0].value} – ${sliders[1].value} mm`;
    for(const b of $('fTone').children){b.classList.add('tone-swatch');b.dataset.tone=b.dataset.v;}
    const diagrams={lames:'<path d="M5 2v24M14 2v24M23 2v24M32 2v24M5 10h9M14 18h9M23 8h9"/>','point-de-hongrie':'<path d="m1 2 17 10L35 2M1 9l17 10L35 9M1 16l17 10 17-10"/>','baton-rompu':'<path d="m2 8 8-8 16 16-8 8zM18 24l-6 6M26 16 36 6M14 4l8-8M2 8l-6 6M10 16 0 26M22 4l14 14M28 24l8 8"/>'};
    for(const b of $('fPattern').children){b.classList.add('pattern-choice');const label=b.textContent;b.replaceChildren();const diagram=create('span','catalog-pattern-icon');diagram.setAttribute('aria-hidden','true');diagram.innerHTML=`<svg width="36" height="28" viewBox="0 0 36 28" fill="none" stroke="currentColor" stroke-width="1">${diagrams[b.dataset.v]}</svg>`;b.append(diagram,document.createTextNode(label));}
    const empty=$('prods').querySelector('.empty');if(empty){empty.textContent='Aucun parquet ne correspond à votre recherche.';const clear=button('Effacer les filtres');clear.onclick=()=>reset.click();empty.append(clear);}
  }
  window.__catalogBrowser={sync};sync();
}
