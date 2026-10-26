import assert from'node:assert/strict';import{physicalPattern,patternUV,physicalHerringbone}from'../web/scene/world-pattern.js';
const material={boardWidth:.15,boardLength:1.8};
for(const width of[.09,.092,.15])for(const length of[.45,.5,.6]){
 const p=physicalPattern(material,{pattern:'baton-rompu',width,plankLength:length});
 for(const a of[.1,.5,.9])for(const b of[.1,.5,.9]){
  const u=.5+(a*p.l-b*p.w)/Math.SQRT2,v=.5+(a*p.l+b*p.w)/Math.SQRT2;
  const mapped=patternUV(u,v,p),s=Math.SQRT2*(mapped[1]-.5),d=Math.SQRT2*(mapped[0]-.5);
  assert.ok(Math.abs((s+d)/2/p.sourceL-a)<1e-8);assert.ok(Math.abs((s-d)/2/p.sourceW-b)<1e-8);
 }
 const straight=physicalPattern(material,{pattern:'lames',width,plankLength:length});
 const uv=patternUV(straight.l*.3,straight.w*.7,straight);assert.ok(Math.abs(uv[0]/straight.sourceL-.3)<1e-10);assert.ok(Math.abs(uv[1]/straight.sourceW-.7)<1e-10);
 const chevron=physicalPattern(material,{pattern:'point-de-hongrie',width,plankLength:length});
 const step=chevron.w/Math.sin(chevron.angle),a=patternUV(.132,.345,chevron),b=patternUV(.132,.345+step,chevron);
 assert.ok(Math.abs(b[1]-a[1]-chevron.period.pas)<1e-9);
 assert.ok(Math.abs(chevron.w*4.8-width)<1e-12);assert.ok(Math.abs(chevron.l*4.8-length)<1e-12);
}
console.log('PASS physical plank mapping: 90/92/150mm; 450/500/600mm; exact length/width without tile quantization');

for(const [width,length]of[[.09,.5],[.092,.5],[.15,.5],[.09,.45]]){
 for(let i=0;i<10000;i++){
  const u=((i*.754877)%1)*4-2,v=((i*.5698402)%1)*4-2;
  assert.ok(physicalHerringbone(u,v,width/4.8,length/4.8),'physical herringbone leaves a hole');
 }
}
console.log('PASS 40,000 non-integer length/width herringbone coverage probes');
