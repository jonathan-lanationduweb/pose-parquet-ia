import fs from'node:fs';import assert from'node:assert/strict';import{visualQualityReport,qualityReportText}from'../web/product/visual-quality-report.js';
const root='review/visual-quality-s1-s8';let scenes=0;
for(const dir of fs.readdirSync(root,{withFileTypes:true}).filter(e=>e.isDirectory())){
 const file=root+'/'+dir.name+'/visual-report.json';if(!fs.existsSync(file))continue;
 const r=visualQualityReport(JSON.parse(fs.readFileSync(file))),before=JSON.parse(fs.readFileSync(root+'/'+dir.name+'/visual-report-before.json'));
 assert.equal(r.recommendedDecision,r.reviewDecision,dir.name+' review gate mismatch');
 for(const key of before.confirmedCorrect)assert.equal(r.criteria[key].status,'PASS',dir.name+' regressed '+key);
 assert.ok(r.responsive.normalizedProjectionMaxSourcePixels<.5);assert.equal(r.criteria.S6.status,'NOT_EVALUABLE');
 fs.writeFileSync(file,JSON.stringify(r,null,2));fs.writeFileSync(root+'/'+dir.name+'/visual-report.txt',qualityReportText(r));
 for(const f of ['01-original.jpg','02-current.jpg','03-grid.jpg','04-masks.jpg','07-final.jpg','crops/near.jpg','crops/mid.jpg','crops/far.jpg','crops/objects.jpg','crops/boundary.jpg'])assert.ok(fs.existsSync(root+'/'+dir.name+'/'+f),f);
 if(!r.debugMetadata.renderBlocked)for(const f of ['05-neutral.jpg','06-no-lighting.jpg'])assert.ok(fs.existsSync(root+'/'+dir.name+'/'+f),f);
 scenes++;
}
assert.equal(scenes,11);console.log('PASS 11 complete private S1-S8 packs, crops, preserved confirmed criteria and mobile projection');
