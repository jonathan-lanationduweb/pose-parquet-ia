import copy,json,hashlib
from pathlib import Path
import numpy as np
import pytest
from scripts.apply_scene_mask_review import apply_review,raster

ROOT=Path(__file__).resolve().parents[1]

def effective(scene):
    shape=(scene['image']['height'],scene['image']['width'])
    floor=np.zeros(shape,bool);blocked=floor.copy()
    for z in scene['floorZones']:floor|=raster(shape,z['mask']['polygon'],z['mask'].get('holes',[]))
    for o in scene.get('occluders',[]):blocked|=raster(shape,o['polygon'],o.get('holes',[]))
    return floor & ~blocked


def test_review_rejects_rescaled_photo():
    with pytest.raises(ValueError,match='original image size'):
        apply_review({'image':{'width':10,'height':10}}, {'imageSize':[20,10]})


def test_catalogue_geometry_digest_is_preserved():
    reviews=json.loads((ROOT/'web/data/scene-mask-reviews.json').read_text(encoding='utf8'))
    for id,review in reviews.items():
        rel='web/data/scenes/'+id+'.json'
        before=json.loads((ROOT/rel).read_text(encoding='utf8'))
        keys=('camera','planes','light','surfaces','image')
        digest=hashlib.sha256(json.dumps({k:before.get(k)for k in keys},sort_keys=True).encode()).hexdigest()
        assert digest==review['geometryDigest'],id
        # Photo-guided foreground refinement supersedes the coarse matte.
        # The frozen geometry digest and real-photo probes remain binding.



def test_real_photo_floor_and_foreground_probes():
    # Pixel coordinates are inspected on the original photographs, not derived
    # from the edited polygons. Include protected feet, plinths and the real rug.
    cases={
      'cuisine-ilot':([(800,476)],[(785,450),(650,530)]),
      'cuisine-blanche':([(1042,532)],[(1042,500)]),
      'couloir-enfilade':([(905,739)],[(905,710)]),
      'premibel-entree':([(210,513)],[(205,500),(220,555)]),
      'salle-a-manger-meublee':([(530,510)],[(590,550),(638,600),(480,550)]),
      'bureau-meuble':([(900,610)],[(861,605),(295,715)]),
      'premibel-chambre':([(225,295)],[(225,277),(160,370),(300,440)])}
    for id,(floor,protected)in cases.items():
        m=effective(json.loads((ROOT/('web/data/scenes/'+id+'.json')).read_text(encoding='utf8')))
        for x,y in floor:assert m[y,x],(id,'missing floor',x,y)
        for x,y in protected:assert not m[y,x],(id,'painted foreground',x,y)
