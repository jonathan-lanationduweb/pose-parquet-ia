"""Refresh only foreground proposals from existing semantic labels.
No camera, floor, material or lighting updates. No inference/download.
"""
from pathlib import Path
import argparse,json,copy
import cv2,numpy as np
from app.services.foreground import build_foreground

def refresh(scene, labels, image):
    h,w=image.shape[:2]
    if (scene['image']['width'],scene['image']['height'])!=(w,h):
        raise ValueError('Original image must match SceneData dimensions')
    floor=np.zeros((h,w),np.uint8)
    for z in scene['floorZones']:
        points=np.array([[round(p['x']*(w-1)),round(p['y']*(h-1))] for p in z['mask']['polygon']],np.int32)
        cv2.fillPoly(floor,[points],1)
    foreground=build_foreground(labels,floor.astype(bool),image)
    out=copy.deepcopy(scene)
    out['occluders']=[o for o in scene.get('occluders',[]) if not o['id'].startswith('semantic-v3-')]
    out['occluders'] += [dict(o.model_dump(by_alias=True,exclude_none=True),id='semantic-v3-'+o.id)
                        for o in foreground.objects if o.kind!='mask-opening']
    for key in ['camera','planes','floorZones','light']:
        assert scene.get(key)==out.get(key),key
    return out

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--scene-file',type=Path,required=True);p.add_argument('--image',type=Path,required=True)
    p.add_argument('--labels-file',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    image=cv2.imread(str(a.image))
    if image is None:raise ValueError('Image unavailable')
    out=refresh(json.loads(a.scene_file.read_text(encoding='utf8')),np.load(a.labels_file),cv2.cvtColor(image,cv2.COLOR_BGR2RGB))
    a.output.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
if __name__=='__main__':main()
