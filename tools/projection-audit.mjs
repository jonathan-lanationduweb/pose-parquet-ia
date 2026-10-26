import fs from'node:fs';import{normalizeScene}from'../web/scene/schema.js';import{metricFloor}from'../web/scene/floor-projection.js';
const rows=[];
for(const file of [...fs.readdirSync('web/data/scenes').filter(x=>x.endsWith('.json')).map(x=>'web/data/scenes/'+x),'review/room-occlusion-v2-2/owner-photo/scene-after.json']){
 const raw=JSON.parse(fs.readFileSync(file,'utf8').replace(/^\uFEFF/,''));const scene=normalizeScene(raw);const p=scene.floorZones[0].plane.projection;
 const start=performance.now();for(let n=0;n<100;n++)metricFloor(scene.floorZones[0].plane,scene.camera,scene.image);const projectionMs=(performance.now()-start)/100;
 const {project,atPixel,widthAt,...data}=p;rows.push({file,projectionMs,...data});console.log(file.split('/').slice(-2).join('/'),p.status,p.reason||'',p.legacyAxisScale?.map(x=>x.toFixed(3)));
}
fs.mkdirSync('review/floor-projection-v3',{recursive:true});fs.writeFileSync('review/floor-projection-v3/audit.json',JSON.stringify({rows},null,2));
