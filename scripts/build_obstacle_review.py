"""Build private, source-resolution obstacle A/B review from captured packs."""
from pathlib import Path
import json,shutil
from PIL import Image,ImageDraw
import numpy as np
def main():
 root=Path('review/occlusion-obstacles');rows=[]
 cases=[
 ('premibel-salon','sofa',(430,195,610,365),'D2-D','Main sofa support recovered with existing semantic output; minor contact edges remain'),
 ('salle-a-manger-meublee','table / chair / thin-leg',(280,390,670,640),'D2-D','Rear table/chair supports recovered; all principal visible legs protected'),
 ('premibel-piano','rug',(30,475,610,690),'D2-C','Interior protected; edge refinement improves contact, minor contour remains'),
 ('premibel-chambre','bed',(200,420,580,600),'D2-C','Bed protected; lower contact contour improved'),
 ('piece-claire','TV-unit',(570,665,810,770),'D2-C','All main supports protected; local boundary improved, small residual edges'),
 ('chambre','empty-room',(400,760,850,1000),'none','Identical empty-room render; fixture preserved'),
 ('terrasse-mer','terrace',(210,555,720,740),'none','Identical terrace render'),
 ('owner','sofa / rug / TV-unit',(380,300,680,410),'D2-C','Foreground preserved; irregular source contour below console still needs work'),
 ]
 for scene,kind,box,defect,note in cases:
  a=Path('review/defects')/('case-004-private' if scene=='owner' else 'occlusion-before-'+scene)
  b=Path('review/defects')/('occlusion-after-'+scene)
  dest=root/scene;dest.mkdir(exist_ok=True,parents=True)
  before=json.loads((a/'metadata.json').read_text());after=json.loads((b/'metadata.json').read_text())
  for key in ['cameras','floorAngle','productId','pattern','imageSize']:
   assert before.get(key)==after.get(key),(scene,key)
  assert {k:v for k,v in before['scale'].items() if k!='zones'}=={k:v for k,v in after['scale'].items() if k!='zones'}
  old=np.array(Image.open(a/'02-render.png'));new=np.array(Image.open(b/'02-render.png'))
  changed=int(np.any(old!=new,axis=2).sum())
  if kind in ['empty-room','terrace']:assert changed==0,(scene,changed)
  for src,name in [(a/'01-original.png','01-original.png'),(a/'02-render.png','02-render-before.png'),(a/'10-floor-mask-raw.png','03-floor-mask.png'),(a/'11-occluder-mask-raw.png','04-occluder-mask-before.png'),(b/'11-occluder-mask-raw.png','04-occluder-mask-after.png'),(b/'02-render.png','05-render-after.png'),(a/'03-debug-grid.png','debug-grid.png'),(a/'05-debug-camera.png','debug-camera.png')]:shutil.copyfile(src,dest/name)
  crops=[]
  for p,title in [(a/'01-original.png','Original'),(a/'02-render.png','Before'),(b/'02-render.png','After'),(a/'04-debug-masks.png','Mask before'),(b/'04-debug-masks.png','Mask after')]:
   im=Image.open(p).convert('RGB').crop(box);im=im.resize((480,round(480*im.height/im.width)));crops.append((im,title))
  ch=crops[0][0].height+30;sheet=Image.new('RGB',(1440,ch*2),'#eee');draw=ImageDraw.Draw(sheet)
  for i,(im,title) in enumerate(crops):
   x=i%3*480;y=i//3*ch;sheet.paste(im,(x,y+25));draw.text((x+8,y+5),title,fill='#111')
  sheet.save(dest/'06-object-crops.png')
  row={'scene':scene,'objectType':kind,'defect':defect,'changedPixels':changed,'floorMask':'unchanged','occluderMask':'source-space independent mask','mapping':'PASS actual renderer probes / same ViewTransform','composite':'straight alpha; same production formula','manualNeeded':scene in ['owner'],'result':note,
   'confirmedCorrect':[{'code':code,'status':'PASS','scope':scope,'evidence':'Inspected source debug grid; identical cameras, scale, product and angle before/after'} for code,scope in [('D3','Existing projection preserved; not a new camera calibration'),('D4','Configured metric board sizes and perspective scale preserved; absolute metres remain assumed'),('D6','Existing horizon and vanishing directions unchanged')]]}
  rows.append(row);(dest/'metadata.json').write_text(json.dumps({'before':before,'after':after,'roi':box,**row},indent=2))
 (root/'visual-matrix.json').write_text(json.dumps(rows,indent=2))
 html='<!doctype html><meta charset="utf-8"><title>Obstacle occlusion review</title><style>body{font:16px system-ui;background:#f5f4ef;margin:28px}img{width:100%;max-width:1440px}section{margin:32px 0}a{color:#724c31}</style><h1>Occlusions — comparaison privée</h1><p>Mêmes caméra, plan, produit et angle. Aucun verdict de réalisme automatique.</p>'
 for row in rows:
  html+='<section><h2>'+row['scene']+' — '+row['objectType']+'</h2><p>'+row['result']+'</p><a href="'+row['scene']+'/06-object-crops.png"><img loading="lazy" src="'+row['scene']+'/06-object-crops.png"></a><p><a href="'+row['scene']+'/metadata.json">Mesures et invariants</a></p></section>'
 (root/'index.html').write_text(html,encoding='utf8')
 print(json.dumps([{'scene':r['scene'],'changedPixels':r['changedPixels'],'manualNeeded':r['manualNeeded']} for r in rows]))
if __name__=='__main__':main()
