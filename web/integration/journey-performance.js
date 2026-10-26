const STEPS=['photoSelected','photoDisplayed','analysisStarted','sceneReady','firstFloorRender','interactiveReady'];
export class JourneyPerformance{
 constructor({enabled=true,performance:perf=globalThis.performance}={}){this.enabled=enabled;this.perf=perf;this.id=0;this.seen=new Set();this.rows=[];this.names=[];}
 start(){for(const n of this.names){this.perf.clearMarks?.(n);this.perf.clearMeasures?.(n);}this.names=[];this.id++;this.seen.clear();this.rows=[];this.mark('photoSelected');}
 mark(step){
  if(!this.enabled||!STEPS.includes(step)||this.seen.has(step))return;
  const name='pp.journey.'+this.id+'.'+step;this.perf.mark(name);this.names.push(name);this.seen.add(step);
  const at=STEPS.indexOf(step),previous=STEPS[at-1];
  if(previous&&this.seen.has(previous)){const measure='pp.journey.'+this.id+'.'+previous+'→'+step;this.perf.measure(measure,'pp.journey.'+this.id+'.'+previous,name);this.names.push(measure);const entry=this.perf.getEntriesByName(measure).at(-1);this.rows.push({from:previous,to:step,ms:entry.duration});}
 }
 snapshot(){return this.rows.map(x=>({...x}));}
}