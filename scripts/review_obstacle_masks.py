"""Private cached-label replay. Never invokes inference or changes room geometry."""
from pathlib import Path
import json, time, copy
import cv2
import numpy as np
from app.services.foreground import build_foreground
from app.services.floor_scene import refine_mask, mask_zones

def main():
    cv2.setNumThreads(1)
    root=Path('review/occlusion-obstacles')
    rows=[]
    for name,source in [('owner-photo','owner'),('petite-piece','petite-piece'),('bureau-vide','bureau-vide')]:
        cache=Path('review/room-occlusion-v2-2')/name
        labels=np.load(cache/'labels.npy');floor=np.load(cache/'floor.npy')
        image=cv2.cvtColor(cv2.imread(str(Path('review/room-understanding-v2')/source/'original.png')),cv2.COLOR_BGR2RGB)
        support=refine_mask(floor,image_rgb=image)
        holes=[hole for _,hs in mask_zones(support) for hole in hs]
        timings=[]
        for _ in range(12):
            fg=build_foreground(labels,support,image,opening_polygons=holes)
            timings.append(fg.timings_ms)
        before=json.loads((cache/'scene-after.json').read_text())
        after=copy.deepcopy(before);after['occluders']=[o.model_dump(by_alias=True,exclude_none=True) for o in fg.objects]
        assert before['camera']==after['camera'] and before['planes']==after['planes'] and before['floorZones']==after['floorZones']
        dest=root/name;dest.mkdir(parents=True,exist_ok=True)
        (dest/'scene-after.json').write_text(json.dumps(after))
        (dest/'scene-before.json').write_text(json.dumps(before))
        cv2.imwrite(str(dest/'semantic-coarse.png'),fg.coarse.astype(np.uint8)*255)
        cv2.imwrite(str(dest/'semantic-refined.png'),fg.refined.astype(np.uint8)*255)
        stats={key:dict(zip(['median','p95','max'],[float(np.median([t[key] for t in timings])),float(np.percentile([t[key] for t in timings],95)),float(max(t[key] for t in timings))])) for key in timings[0]}
        added={int(label):int((labels==label).sum()) for label in [39,41,57,69,97,115,125,135] if (labels==label).any()}
        rows.append({'scene':name,'runs':len(timings),'timingsMs':stats,'reusedClasses':added,'cameraPlaneFloorIdentical':True,'noInference':True,'sourceSize':[image.shape[1],image.shape[0]]})
    (root/'backend-replay.json').write_text(json.dumps(rows,indent=2))
    print(json.dumps(rows,indent=2))
if __name__=='__main__':main()
