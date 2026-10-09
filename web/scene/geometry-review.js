/** Development diagnostics. Projection is shared with the actual renderer. */
import { zoneTransform } from './geometry.js';
import { apply } from './perspective.js';

export function reviewGeometry(scene, masks, size, config) {
  if (!scene || !masks || !size) return null;
  const { width, height } = size;
  const theta = (Number(config.angle) || 0) * Math.PI / 180;
  const plankM = Number(config.width) || 0.15;
  return {
    scene: scene.id, width, height, plankM,
    zones: scene.floorZones.map((zone, index) => {
      const t = zoneTransform(zone, width, height);
      const box = masks.box(zone.id);
      if (!t || !box) return { id: zone.id, valid: false };
      const project = (u, v) => apply(t.H, u / zone.plane.meters.width, v / zone.plane.meters.depth);
      const rows = [['far', .12], ['middle', .5], ['near', .88]];
      const samples = rows.map(([position, k]) => {
        const y = Math.round(box.y0 + (box.y1 - box.y0 - 1) * k);
        const xs = [];
        for (let x = box.x0; x < box.x1; x += 1) {
          if (masks.labels[y * width + x] === index + 1 && masks.coverage[y * width + x] > 192) xs.push(x);
        }
        if (!xs.length) return { position, valid: false };
        const x = xs[Math.floor(xs.length / 2)];
        const q = apply(t.M, x, y);
        const u = q.x * zone.plane.meters.width;
        const v = q.y * zone.plane.meters.depth;
        // Width is across the plank; an angle of zero puts the plank along u.
        const a = project(u - Math.sin(theta) * plankM / 2, v - Math.cos(theta) * plankM / 2);
        const b = project(u + Math.sin(theta) * plankM / 2, v + Math.cos(theta) * plankM / 2);
        return { position, valid: true, at: { x, y }, a, b, plankWidthPx: Math.hypot(b.x - a.x, b.y - a.y) };
      });
      const center = samples.find(s => s.position === 'middle' && s.valid) || samples.find(s => s.valid);
      const axes = [];
      if (center) {
        const q = apply(t.M, center.at.x, center.at.y);
        const u = q.x * zone.plane.meters.width;
        const v = q.y * zone.plane.meters.depth;
        axes.push({ color: '#65e3d3', a: project(u - 1, v), b: project(u + 1, v) });
        axes.push({ color: '#ffcb6b', a: project(u, v - 1), b: project(u, v + 1) });
      }
      return { id: zone.id, valid: true, samples, axes,
        contour: masks.getPolygon(zone.id).map(p => ({ x: p.x * width, y: p.y * height })),
        vanishing: [0, 1].map(i => Math.abs(t.H[6+i]) > 1e-9
          ? { x: t.H[i] / t.H[6+i], y: t.H[3+i] / t.H[6+i] } : null) };
    }),
  };
}
