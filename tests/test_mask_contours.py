import numpy as np
from app.services.mask_contours import cell_polygons

def signed_area(points):
    a=np.array([(p.x,p.y) for p in points])
    return .5*float(np.sum(a[:,0]*np.roll(a[:,1],-1)-a[:,1]*np.roll(a[:,0],-1)))

def test_cell_contours_preserve_area_topology_and_bounds():
    rng=np.random.default_rng(184)
    for shape in [(1,1),(7,9),(40,60)]:
        for _ in range(8):
            mask=rng.random(shape)<.4
            regions=cell_polygons(mask)
            area=sum(signed_area(outer)+sum(signed_area(hole) for hole in holes) for outer,holes,_ in regions)
            assert abs(area*mask.size-int(mask.sum()))<1e-8
            assert all(0<=p.x<=1 and 0<=p.y<=1 for outer,holes,_ in regions for ring in [outer,*holes] for p in ring)

def test_nested_island_and_hole_are_retained():
    mask=np.zeros((40,60),bool);mask[2:38,2:58]=True;mask[10:30,12:48]=False;mask[18:22,25:30]=True
    regions=cell_polygons(mask)
    assert len(regions)==2
    assert sum(len(holes) for _,holes,_ in regions)==1
    assert abs(sum(signed_area(a)+sum(signed_area(b) for b in hs) for a,hs,_ in regions)*mask.size-mask.sum())<1e-8
