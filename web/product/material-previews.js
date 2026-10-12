/** Vignettes issues du même moteur que le sol ; calcul hors du fil principal. */
export async function installMaterialPreviews(getConcept) {
  const concept = getConcept();
  if (!concept || typeof Worker === 'undefined' || typeof OffscreenCanvas === 'undefined') return;
  let materials;
  try {
    const response = await fetch(new URL('../data/parquets.json', import.meta.url));
    if (!response.ok) return;
    materials = (await response.json()).parquets;
  } catch { return; }
  const products = new Map(concept.PREMIBEL_DEMO_PRODUCTS.map(p => [p.id, p]));
  const materialById = new Map(materials.map(m => [m.id, m]));
  const cache = new Map();
  const queued = new Set();
  const queue = [];
  const observed = new WeakSet();
  let active = null;
  const worker = new Worker(new URL('../scene/texture-worker.js', import.meta.url), { type: 'module' });
  const apply = (id, url) => document.querySelectorAll(`[data-material-preview="${id}"]`).forEach(node => {
    node.style.backgroundImage = `url("${url}")`;
    node.classList.remove('noimg');
    node.dataset.materialPreviewReady = 'true';
  });
  const next = () => {
    if (active || !queue.length) return;
    active = queue.shift();
    const profile = products.get(active).renderProfile;
    worker.postMessage({ id: active, kind: 'apercu', material: materialById.get(profile.materialFamily),
      config: { pattern: profile.pattern, width: profile.widthM, plankLength: profile.lengthM, size: 256 } });
  };
  worker.onmessage = ({ data }) => {
    if (data.bitmap) {
      const canvas = document.createElement('canvas');
      canvas.width = data.bitmap.width; canvas.height = data.bitmap.height;
      canvas.getContext('2d').drawImage(data.bitmap, 0, 0);
      data.bitmap.close();
      const url = canvas.toDataURL('image/jpeg', 0.88);
      cache.set(data.id, url); apply(data.id, url);
    }
    queued.delete(data.id); active = null; next();
  };
  worker.onerror = () => { worker.terminate(); queue.length = 0; };
  const enqueue = id => {
    if (!queued.has(id) && products.has(id)) { queued.add(id); queue.push(id); }
  };
  const observer = new IntersectionObserver(entries => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      const id = entry.target.dataset.materialPreview;
      if (cache.has(id)) apply(id, cache.get(id));
      else enqueue(id);
      observer.unobserve(entry.target);
    }
    next();
  }, { rootMargin: '100px' });
  let scheduled = false;
  const scan = () => {
    scheduled = false;
    document.querySelectorAll('[data-material-preview]').forEach(node => {
      const id = node.dataset.materialPreview;
      if (cache.has(id)) { if (!node.dataset.materialPreviewReady) apply(id, cache.get(id)); }
      else {
        const r = node.getBoundingClientRect();
        if (r.width && r.height && r.bottom >= -100 && r.top <= innerHeight + 100 && r.right >= 0 && r.left <= innerWidth) enqueue(id);
        else if (!observed.has(node)) { observed.add(node); observer.observe(node); }
      }
    });
    next();
  };
  new MutationObserver(() => {
    if (!scheduled) { scheduled = true; setTimeout(scan, 0); }
  }).observe(document.body, { childList: true, subtree: true });
  document.addEventListener('scroll', () => { if (!scheduled) { scheduled = true; setTimeout(scan, 32); } }, true);
  scan();
}
