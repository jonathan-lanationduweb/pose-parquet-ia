import numpy as np
from app.services.photo_mask_refiner import refine_photo_mask
from scripts.refine_catalogue_foreground import refine_scene
from scripts.apply_scene_mask_review import raster

def test_local_foreground_colours_do_not_keep_brown_floor_halo():
    im=np.full((100,160,3),[170,115,70],np.uint8)
    im[25:75,20:70]=[225,225,220];im[25:75,100:140]=[85,45,25]
    objects=np.zeros((100,160),bool);objects[21:79,16:74]=True;objects[25:75,100:140]=True
    result=refine_photo_mask(im,np.ones_like(objects),objects)
    assert not result.visible_floor[50,45]
    assert result.visible_floor[50,17]
    assert not result.visible_floor[50,115]
    assert np.array_equal(result.visible_floor,refine_photo_mask(im,np.ones_like(objects),objects).visible_floor)

def test_fixture_and_slender_support_survive():
    im=np.full((70,100,3),[180,140,90],np.uint8);im[15:50,40:43]=[30,30,35];im[55:58,10:30]=[110,70,30]
    objects=np.zeros((70,100),bool);objects[15:50,40:43]=True;objects[55:58,10:30]=True
    fixture=np.zeros_like(objects);fixture[55:58,10:30]=True
    result=refine_photo_mask(im,np.ones_like(objects),objects,immutable=fixture)
    assert not result.visible_floor[30,41]
    assert not result.visible_floor[56,20]

def test_reconstructed_support_preserves_geometry_and_foreground():
    scene={'image':{'width':100,'height':80},'camera':{'heightM':1.5},'planes':{'sol':{'sentinel':42}},'light':{'strength':.7},'surfaces':[{'id':'sol'}],
      'floorZones':[{'id':'zone','surfaceId':'sol','planeRef':'sol','mask':{'polygon':[{'x':.1,'y':.3},{'x':.9,'y':.3},{'x':.9,'y':1},{'x':.6,'y':1},{'x':.6,'y':.6},{'x':.4,'y':.6},{'x':.4,'y':1},{'x':.1,'y':1}],'holes':[]}}],
      'occluders':[{'id':'object','kind':'furniture','polygon':[{'x':.4,'y':.5},{'x':.6,'y':.5},{'x':.6,'y':1},{'x':.4,'y':1}]}]}
    im=np.full((80,100,3),[180,120,70],np.uint8);im[40:,40:60]=[240,240,235]
    labels=np.full((80,100),3,np.int32);labels[40:,40:60]=10
    out,stats=refine_scene(scene,im,labels)
    for key in ['camera','planes','image','light','surfaces']:assert out[key]==scene[key]
    assert len(out['floorZones'])==1
    support=raster((80,100),out['floorZones'][0]['mask']['polygon']);blocked=np.zeros_like(support)
    for o in out['occluders']:blocked|=raster((80,100),o['polygon'],o.get('holes',[]))
    assert support[60,50] and blocked[60,50]
    assert not support[10,50] and not support[60,5]
    assert stats['recoveredSupportPixels']>0
