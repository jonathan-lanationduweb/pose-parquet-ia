import copy
import numpy as np
from scripts.refresh_scene_occlusion import refresh
from app.services.floor_scene import build_experimental_scene
from tests.test_floor_scene import _sol_trapeze, W, H

def test_refresh_only_foreground_and_is_idempotent():
    p=lambda x,y: {'x':x,'y':y}
    scene={'image':{'width':100,'height':80},'camera':{'horizon':.2},
           'planes':{'sol':{'quad':[p(0,.4),p(1,.4),p(1,1),p(0,1)]}},
           'floorZones':[{'mask':{'polygon':[p(0,.4),p(1,.4),p(1,1),p(0,1)],'holes':[]}}],
           'light':{'strength':1},'occluders':[{'id':'manual-grate','polygon':[p(.1,.8),p(.2,.8),p(.2,.9)]}]}
    original=copy.deepcopy(scene);labels=np.full((80,100),3,np.uint8);labels[40:70,45:49]=19
    image=np.full((80,100,3),150,np.uint8);image[40:70,45:49]=30
    out=refresh(scene,labels,image)
    assert scene==original
    for key in ['camera','planes','floorZones','light']:assert out[key]==scene[key]
    assert out['occluders'][0]==scene['occluders'][0]
    assert len(out['occluders'])>len(scene['occluders'])
    assert refresh(out,labels,image)==out

def test_scene_reports_uncalibrated_occlusion_instead_of_floor_confidence():
    floor=_sol_trapeze();labels=np.where(floor,3,0).astype(np.uint8)
    labels[300:420,230:420]=23
    result=build_experimental_scene(floor,W,H,labels=labels)
    quality=result.provenance['decision']['quality']
    assert quality['occlusionQuality'] is None
    assert quality['occlusionAreaRatio']>.05
    assert result.status!='auto_render'
    assert 'occlusion_confidence_unmeasured' in result.provenance['decision']['reasons']
