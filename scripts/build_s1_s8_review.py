"""Build a private S1-S8 review from the EXISTING diagnostic packs."""
from pathlib import Path
from PIL import Image,ImageDraw
import json,copy,html
import numpy as np
ROOT=Path('review/visual-quality-s1-s8')
CRITERIA=['S'+str(i) for i in range(1,9)]
def project(cam,point):
 r=np.array(cam['rotation']).reshape(3,3);q=r@(np.array(point)-np.array(cam['center']))
 if q[2]<=0:return None
 return [(cam['fx']*q[0]/q[2]+cam['skew']*q[1]/q[2]+cam['cx'])/cam['imageWidth'],(cam['fy']*q[1]/q[2]+cam['cy'])/cam['imageHeight']]
def main():
 rows=[]
 for dest in sorted(ROOT.iterdir()):
  if not (dest/'visual-report-before.json').is_file():continue
  scene=dest.name;a=Path('review/defects')/('s1s8-before-'+scene);b=Path('review/defects')/('s1s8-after-'+scene);mobile=Path('review/defects')/('s1s8-mobile-'+scene)
  before=json.loads((a/'metadata.json').read_text());after=json.loads((b/'metadata.json').read_text());mob=json.loads((mobile/'metadata.json').read_text())
  assert before['cameras']==after['cameras'],scene+' camera changed'
  for key in ['productId','floorAngle','pattern','boardWidthMeters','boardLengthMeters']:assert before.get(key)==after.get(key),(scene,key)
  max_projection=0.
  for full,small in zip(after['cameras'],mob['cameras']):
   assert full['floorPlane']==small['floorPlane'],scene+' mobile plane changed'
   floor=full['floorPlane']
   for u,v in [(0,0),(.5,1),(1,2),(2,4)]:
    point=np.array(floor['origin'])+u*np.array(floor['axisU'])+v*np.array(floor['axisV'])
    p=project(full['camera'],point);q=project(small['camera'],point)
    if p is not None and q is not None:max_projection=max(max_projection,float(np.linalg.norm(np.array(p)-q)*after['imageSize']['width']))
  assert max_projection<.5,(scene,max_projection)
  report=json.loads((dest/'visual-report-before.json').read_text());report['phase']='after';report['debugMetadata']=after
  report['humanReviewPending']=True;report['viewport']=after['viewportSize']
  report['responsive']={'mobileViewport':mob['viewportSize'],'mobileImageSize':mob['imageSize'],'normalizedProjectionMaxSourcePixels':max_projection,'samePlane':True,'sourceSampling':'Raster resolution may differ; no scene-space offset added'}
  report['changes']={'criteria':['S3','S4','S8'],'causes':['pixel-centre-contour-loss','binary-edge-alpha'],'stage1Pack':'s1s8-stage1-'+scene}
  for key in ['S3','S4','S8']:
   if report['criteria'][key]['status']=='PARTIAL':
    report['criteria'][key]['observation']+=' Cell coverage now preserved and mixed edge alpha retained; improvement is local, residual source segmentation remains visible.'
  report['observations']=['Assistant visual review, not independent human validation.','No paired Roomvo reference available; no pixel/algorithm comparison with Roomvo.']
  report['recommendedDecision']='MANUAL_REQUIRED' if after['renderBlocked'] else 'APPROXIMATE' if after.get('geometryStatus')=='APPROXIMATE' or any(report['criteria'][k]['status']!='PASS' for k in ['S1','S2','S4']) or any(report['scores'].get(k) is not None and report['scores'][k]<4 for k in ['perspective','scale','occlusion']) else 'HUMAN_REVIEW_REQUIRED'
  for key in report['confirmedCorrect']:assert report['criteria'][key]['status']=='PASS',(scene,key)
  (dest/'visual-report.json').write_text(json.dumps(report,indent=2))
  (dest/'visual-report-mobile.json').write_text(json.dumps(dict(report,viewport=mob['viewportSize'],debugMetadata=mob,phase='after-mobile'),indent=2))
  sources={'01-original.jpg':a/'01-original.png','02-current.jpg':a/'02-render.png','03-grid.jpg':b/'03-debug-grid.png','04-masks.jpg':b/'04-debug-masks.png','05-neutral.jpg':b/'14-neutral.png','06-no-lighting.jpg':b/'09-unlit.png','07-final.jpg':b/'02-render.png','08-pattern.jpg':b/'08-debug-pattern.png','09-pattern-flat.jpg':b/'13-pattern-floor-space.png'}
  available={}
  for name,path in sources.items():
   if path.exists():Image.open(path).convert('RGB').save(dest/name,quality=97,subsampling=0);available[name]=True
   else:available[name]=False
  # A rejected render has no neutral/unlit/wood material. No invented fallback.
  report['availableImages']=available
  (dest/'visual-report.json').write_text(json.dumps(report,indent=2))
  im=Image.open(b/'02-render.png').convert('RGB');w,h=im.size
  floor=np.array(Image.open(b/'10-floor-mask-raw.png').convert('L'));occ=np.array(Image.open(b/'11-occluder-mask-raw.png').convert('L'))
  ys,xs=np.nonzero(floor>127);y0=int(ys.min()) if len(ys) else int(h*.6);y1=int(ys.max()) if len(ys) else h-1
  farrange=max(24,round((y1-y0)*.22));middle=round((y0+y1)*.5)
  overlap=(floor>127)&(occ>127);oy,ox=np.nonzero(overlap)
  objectbox=(max(0,int(ox.min())-12),max(0,int(oy.min())-12),min(w,int(ox.max())+13),min(h,int(oy.max())+13)) if len(ox) else (0,y0,w,min(h,y0+farrange))
  boxes={'near':(0,round(h*.7),w,h),'mid':(0,max(0,middle-farrange//2),w,min(h,middle+farrange//2)),'far':(0,y0,w,min(h,y0+farrange)),'objects':objectbox,'boundary':(0,max(0,y0-20),w,min(h,y0+farrange))}
  crops=dest/'crops';crops.mkdir(exist_ok=True)
  for name,box in boxes.items():im.crop(box).save(crops/(name+'.jpg'),quality=98,subsampling=0)
  report['cropRegions']={k:list(v) for k,v in boxes.items()};report['objectCropHasFloorOcclusion']=bool(len(ox))
  # True before/after crops at exactly the same source coordinates.
  for name in ['objects','boundary']:
   box=boxes[name];ims=[Image.open(path).convert('RGB').crop(box) for path in [a/'02-render.png',b/'02-render.png']]
   height=min(600,max(100,round(600*ims[0].height/max(1,ims[0].width))))
   sheet=Image.new('RGB',(1200,height+28),'white');draw=ImageDraw.Draw(sheet)
   for i,img in enumerate(ims):sheet.paste(img.resize((600,height)),(i*600,28));draw.text((i*600+8,7),['Before','After'][i],fill='black')
   sheet.save(crops/(name+'-before-after.jpg'),quality=98,subsampling=0)
  (dest/'visual-report.json').write_text(json.dumps(report,indent=2));rows.append(report)
 table='<table><thead><tr><th>Scène</th>'+''.join('<th>'+k+'</th>' for k in CRITERIA)+'<th>Priorité</th></tr></thead><tbody>'
 for r in rows:table+='<tr><td><a href="#'+html.escape(r['sceneId'])+'">'+html.escape(r['sceneId'])+'</a></td>'+''.join('<td class="'+r['criteria'][k]['status']+'">'+r['criteria'][k]['status'].replace('NOT_EVALUABLE','N/E')+'</td>' for k in CRITERIA)+'<td>'+html.escape(r['recommendedDecision'])+'</td></tr>'
 table+='</tbody></table>'
 page='<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Revue S1–S8</title><style>body{font:15px system-ui;margin:24px;background:#f6f4ee;color:#282720}nav{position:sticky;top:0;background:#f6f4eef5;padding:12px 0;z-index:2}a{color:#725039}table{border-collapse:collapse;font-size:12px}td,th{padding:7px;border:1px solid #ccc}th{background:#eee}.matrix{overflow:auto}.PASS{background:#e1eddf}.PARTIAL{background:#fff1d1}.FAIL{background:#f9d6d4}.NOT_EVALUABLE{background:#eaeaea}.images{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}img{max-width:100%;height:auto}figure{margin:0}section{margin:42px 0;padding-top:40px}button,select{min-height:44px;padding:8px}p{max-width:1000px}.crops{display:flex;gap:12px;flex-wrap:wrap}.crops a{max-width:48%}@media(max-width:600px){body{margin:12px}.images{grid-template-columns:1fr}.crops a{max-width:100%}}</style><nav><b>Revue S1–S8</b> · <a href="#matrix">Matrice</a> · Assistant : pré-revue visuelle, validation humaine en attente.</nav><h1>Le parquet semble-t-il présent avant la photo ?</h1><p>Aucune validation esthétique déduite des tests. N/E : données insuffisantes. Pas de référence Roomvo appariée fournie. Les images restent privées.</p><div id="matrix" class="matrix">'+table+'</div>'
 for r in rows:
  scene=r['sceneId'];page+='<section id="'+scene+'"><h2>'+scene+'</h2><p>'+r['recommendedDecision']+' · '+r['criteria']['S8']['observation']+'</p><div class="images">'
  for file,title in [('01-original.jpg','Original'),('02-current.jpg','Avant'),('07-final.jpg','Après')]:page+='<figure><a href="'+scene+'/'+file+'"><img loading="lazy" src="'+scene+'/'+file+'"></a><figcaption>'+title+'</figcaption></figure>'
  page+='</div><p><label>Diagnostic <select data-scene="'+scene+'">'
  for file,title in [('03-grid.jpg','Grille'),('04-masks.jpg','Masques'),('05-neutral.jpg','Sol neutre'),('06-no-lighting.jpg','Sans lumière'),('08-pattern.jpg','Cellules / joints'),('09-pattern-flat.jpg','Motif à plat')]:
   if r['availableImages'][file]:page+='<option value="'+file+'">'+title+'</option>'
  page+='</select></label></p><img loading="lazy" id="diagnostic-'+scene+'" src="'+scene+'/03-grid.jpg"><div class="crops">'
  for name in ['near','mid','far','objects-before-after','boundary-before-after']:page+='<a href="'+scene+'/crops/'+name+'.jpg"><img loading="lazy" src="'+scene+'/crops/'+name+'.jpg" alt="'+name+'"></a>'
  page+='</div><p><a href="'+scene+'/visual-report.json">Rapport JSON</a> · <a href="'+scene+'/visual-report.txt">Rapport texte</a> · <a href="'+scene+'/visual-report-mobile.json">390 mobile</a></p></section>'
 page+='<script>document.querySelectorAll("select[data-scene]").forEach(s=>s.addEventListener("change",()=>{document.getElementById("diagnostic-"+s.dataset.scene).src=s.dataset.scene+"/"+s.value}));</script></html>'
 (ROOT/'index.html').write_text(page,encoding='utf8');(ROOT/'matrix-after.json').write_text(json.dumps(rows,indent=2))
 print('Review built:',len(rows),'scenes; max normalized mobile projection error',max(r['responsive']['normalizedProjectionMaxSourcePixels'] for r in rows))
if __name__=='__main__':main()
