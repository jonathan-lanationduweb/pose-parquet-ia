/** DEV-only overlay: floor contour, projected axes and actual plank width. */
export function installGeometryReview(getConcept) {
  const c = getConcept();
  if (!c || !c.DEV) return;
  const stage = document.getElementById('stage');
  const group = document.createElement('div');
  group.className = 'vp'; group.dataset.vp = ''; group.style.pointerEvents = 'none';
  group.style.zIndex = '6'; group.style.display = 'none';
  const canvas = document.createElement('canvas'); group.appendChild(canvas); stage.appendChild(group);
  const legend = document.createElement('pre');
  legend.style.cssText = 'position:absolute;top:120px;left:16px;z-index:9;max-width:calc(100% - 32px);padding:12px;border-radius:12px;background:#171c20e6;color:#fff;font:12px/1.5 monospace;pointer-events:none;white-space:pre-wrap;display:none';
  stage.appendChild(legend);
  const toggle = document.createElement('button');
  toggle.type = 'button'; toggle.textContent = 'Axes'; toggle.setAttribute('aria-label', 'Axes du sol'); toggle.title = 'Axes du sol'; toggle.setAttribute('aria-pressed', 'false');
  document.getElementById('tools').appendChild(toggle);
  let shown = false;
  const draw = () => {
    const d = c.adapter.geometryDiagnostics();
    if (!d) return null;
    canvas.width = d.width; canvas.height = d.height;
    const ctx = canvas.getContext('2d');
    const line = (a, b, color, dash = []) => {
      if (![a.x,a.y,b.x,b.y].every(Number.isFinite)) return;
      ctx.strokeStyle = color; ctx.lineWidth = Math.max(2, d.width / 600); ctx.setLineDash(dash);
      ctx.beginPath(); ctx.moveTo(a.x,a.y); ctx.lineTo(b.x,b.y); ctx.stroke();
    };
    const text = [`${d.scene} · lame ${(d.plankM*1000).toFixed(0)} mm`];
    for (const z of d.zones) {
      if (!z.valid) { text.push(`${z.id}: pas de sol mesurable`); continue; }
      for (let i=0;i<z.contour.length;i++) line(z.contour[i],z.contour[(i+1)%z.contour.length],'#ff8e87');
      for (const a of z.axes) {
        const dx=a.b.x-a.a.x, dy=a.b.y-a.a.y;
        line({x:a.a.x-dx*10,y:a.a.y-dy*10},{x:a.b.x+dx*10,y:a.b.y+dy*10},a.color,[10,8]);
      }
      for (const s of z.samples) if (s.valid) line(s.a,s.b,'#fff');
      text.push(`${z.id}: `+z.samples.map(s=>`${s.position} ${s.valid?s.plankWidthPx.toFixed(1)+' px':'—'}`).join(' · '));
    }
    legend.textContent=text.join('\n');
    c.applyTransform();
    return d;
  };
  const show = (value = true) => {
    shown = value; toggle.setAttribute('aria-pressed', String(value));
    group.style.display = legend.style.display = value ? '' : 'none';
    return value ? draw() : null;
  };
  toggle.addEventListener('click', () => show(!shown));
  window.__geometryReview = { show, draw };
  const refresh = () => { if (shown) draw(); };
  stage.addEventListener('pointerup', refresh);
  document.addEventListener('click', () => setTimeout(refresh, 300));
}
