"""Refine reviewed catalogue foreground without replacing floor geometry.

Reads existing labels only. Does not download or invoke a semantic model.
Produces a candidate SceneData for visual review before publication.
"""
import argparse,copy,json
from pathlib import Path
import cv2,numpy as np
from scripts.apply_scene_mask_review import raster
from app.services.photo_mask_refiner import refine_photo_mask
from app.services.foreground import polygons, OBJECT_CLASSES


def refine_scene(scene,image_rgb,labels):
    h,w=image_rgb.shape[:2]
    if (scene['image']['width'],scene['image']['height'])!=(w,h):raise ValueError('Original photo dimensions required')
    domain=np.zeros((h,w),bool);occlusion=domain.copy();rug=domain.copy();fixture=domain.copy()
    for zone in scene['floorZones']:
        domain|=raster((h,w),zone['mask']['polygon'],zone['mask'].get('holes',[]))
    for obj in scene.get('occluders',[]):
        mask=raster((h,w),obj['polygon'],obj.get('holes',[]));occlusion|=mask
        if obj.get('kind')=='rug':rug|=mask
        if obj.get('kind')=='fixture':fixture|=mask
    original_domain=domain.copy()
    semantic_objects=np.isin(labels,[*OBJECT_CLASSES,28])
    # Silhouettes baked into floorZones and repeated in occluders prevent any
    # foreground refinement from recovering their old-floor halo. Reconstruct
    # support behind foreground, bounded by each existing plane's floor hull.
    # This is mask support, not a new homography or a camera measurement.
    occlusion |= semantic_objects
    groups={}
    for zone in scene['floorZones']:
        groups.setdefault(zone['planeRef'],[]).append(zone)
    group_masks={}
    group_hulls={}
    for ref,zones in groups.items():
        base=np.zeros((h,w),bool)
        for z in zones:base|=raster((h,w),z['mask']['polygon'],z['mask'].get('holes',[]))
        vertices=np.array([[p['x']*w,p['y']*h]for z in zones for p in z['mask']['polygon']],np.float32)
        hull_points=cv2.convexHull(vertices).reshape(-1,2)
        hull_polygon=[{'x':float(x/w),'y':float(y/h)}for x,y in hull_points]
        hull=raster((h,w),hull_polygon)
        group_hulls[ref]=hull_polygon
        support=base | (occlusion & hull.astype(bool))
        group_masks[ref]=support
    domain=np.logical_or.reduce(list(group_masks.values()))
    result=refine_photo_mask(image_rgb,domain,occlusion,immutable=fixture)
    # Replace the old union: adding the new masks to the old masks would retain
    # exactly the false foreground patches and old-floor halos being corrected.
    # The non-floor matte must continue OUTSIDE the plane envelope too.
    # Clipping both to the same binary hull leaves a half-pixel AA seam through
    # a foreground object when the geometric hull crosses its silhouette.
    blocked=~result.visible_floor
    out=copy.deepcopy(scene)
    # A single physical plane must not be validated once per disconnected
    # few-pixel mask fragment. Keep its geometric envelope as one zone; the
    # foreground/boundary matte carries all the precise visible cut-outs.
    out['floorZones']=[]
    for ref,zones in groups.items():
        z=copy.deepcopy(zones[0])
        z['mask']={'polygon':group_hulls[ref],'holes':[]}
        out['floorZones'].append(z)
    out['occluders']=[o.model_dump(by_alias=True,exclude_none=True) for o in (
        polygons(blocked & fixture,kind='fixture',prefix='fixture-photo')+
        polygons(blocked & rug & ~fixture,kind='rug',prefix='rug-photo')+
        polygons(blocked & ~rug & ~fixture,kind='furniture',prefix='foreground-photo'))]
    for key in ('camera','planes','image','surfaces','light'):
        assert out.get(key)==scene.get(key),key
    return out,{'radiusPx':result.radius_px,'changedPixels':result.changed_pixels,'instancesRefined':result.instances_refined,'recoveredSupportPixels':int(np.count_nonzero(domain & ~original_domain))}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--scene',type=Path,required=True);p.add_argument('--image',type=Path,required=True)
    p.add_argument('--labels',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();im=cv2.imread(str(a.image))
    if im is None:raise ValueError('Photo unavailable')
    out,stats=refine_scene(json.loads(a.scene.read_text(encoding='utf8')),cv2.cvtColor(im,cv2.COLOR_BGR2RGB),np.load(a.labels))
    a.output.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(stats))
if __name__=='__main__':main()
