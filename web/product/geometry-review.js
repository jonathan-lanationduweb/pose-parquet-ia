/** DEV-only overlay: horizon, vanishing points, floor contour, projected axes,
 *  plank guides every 50 cm and actual plank width. Never shown without ?dev=1. */
import { zoneTransform } from '../scene/geometry.js';
import { apply } from '../scene/perspective.js';

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
    const text = [`${d.scene} · lame ${((d.nominalPlankM || d.plankM)*1000).toFixed(0)} mm · échelle ${d.scale || 1}`];
    /* Horizon and the vanishing points measured on the walls (yellow), then
       the plane's own vanishing points (cyan rings): they must coincide. */
    const snap = c.adapter.visitSnapshot && c.adapter.visitSnapshot();
    const cam = snap && snap.scene && snap.scene.camera;
    if (cam && Number.isFinite(cam.horizon)) {
      const hy = cam.horizon * d.height;
      line({ x: 0, y: hy }, { x: d.width, y: hy }, '#ffd400', [14, 8]);
      text.push(`horizon ${cam.horizon.toFixed(4)}`);
      for (const v of cam.vanishingPoints || []) {
        ctx.fillStyle = '#ffd400'; ctx.beginPath();
        ctx.arc(Math.min(Math.max(v.x * d.width, 8), d.width - 8), v.y * d.height, Math.max(5, d.width / 250), 0, Math.PI * 2); ctx.fill();
      }
    }
    if (snap && snap.scene) {
      for (const zone of snap.scene.floorZones) {
        const t = zoneTransform(zone, d.width, d.height);
        if (!t) continue;
        const mw = zone.plane.meters.width; const md = zone.plane.meters.depth;
        const proj = (u, v) => apply(t.H, u / mw, v / md);
        const w = (u, v) => t.H[6] * (u / mw) + t.H[7] * (v / md) + t.H[8];
        const signe = Math.sign(w(mw / 2, md / 2));
        ctx.save();
        const contour = snap.masks.getPolygon(zone.id);
        ctx.beginPath(); contour.forEach((p, i) => (i ? ctx.lineTo(p.x * d.width, p.y * d.height) : ctx.moveTo(p.x * d.width, p.y * d.height)));
        ctx.closePath(); ctx.clip();
        for (let k = -12; k <= 12; k += 0.5) {
          for (let q = -12; q < 12; q += 0.1) {
            if (Math.sign(w(k, q)) === signe && Math.sign(w(k, q + 0.1)) === signe) line(proj(k, q), proj(k, q + 0.1), 'rgba(101,227,211,0.85)');
            if (Math.sign(w(q, k)) === signe && Math.sign(w(q + 0.1, k)) === signe) line(proj(q, k), proj(q + 0.1, k), 'rgba(255,255,255,0.5)');
          }
        }
        ctx.restore();
        for (const i of [0, 1]) {
          if (Math.abs(t.H[6 + i]) < 1e-12) continue;
          const f = { x: t.H[i] / t.H[6 + i], y: t.H[3 + i] / t.H[6 + i] };
          ctx.strokeStyle = '#65e3d3'; ctx.setLineDash([]); ctx.lineWidth = Math.max(2, d.width / 600);
          ctx.beginPath(); ctx.arc(Math.min(Math.max(f.x, 10), d.width - 10), Math.min(Math.max(f.y, 10), d.height - 10), Math.max(8, d.width / 160), 0, Math.PI * 2); ctx.stroke();
        }
      }
    }
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
