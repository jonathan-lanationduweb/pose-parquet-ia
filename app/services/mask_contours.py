"""Trace binary pixel CELL edges, rather than OpenCV pixel-centre contours."""
from __future__ import annotations
import cv2
import numpy as np
from app.schemas.scene_data import Point

def cell_polygons(mask: np.ndarray) -> list[tuple[list[Point],list[list[Point]],float]]:
    m=np.asarray(mask,bool)
    if not m.any():return []
    h,w=m.shape;stride=w+1;p=np.pad(m,1)
    edge_sets=[]
    for exposed,dx0,dy0,dx1,dy1 in [
        (m & ~p[:-2,1:-1],0,0,1,0),
        (m & ~p[1:-1,2:],1,0,1,1),
        (m & ~p[2:,1:-1],1,1,0,1),
        (m & ~p[1:-1,:-2],0,1,0,0)]:
        yy,xx=np.nonzero(exposed)
        edge_sets.append(((yy+dy0)*stride+xx+dx0,(yy+dy1)*stride+xx+dx1))
    edges:dict[int,list[int]]={}
    for starts,ends in edge_sets:
        for a,b in zip(starts.tolist(),ends.tolist()):edges.setdefault(a,[]).append(b)
    direction=lambda a,b: 0 if b-a==1 else 1 if b-a==stride else 2 if b-a==-1 else 3
    loops=[]
    while edges:
        start=next(iter(edges));a=start;previous=None;loop=[]
        while True:
            loop.append((a%stride,a//stride))
            choices=edges[a]
            # At a diagonal contact turn right: keep each pixel island and hole.
            b=choices[0] if previous is None or len(choices)==1 else min(choices,key=lambda q:{1:0,0:1,3:2,2:3}[(direction(a,q)-previous)%4])
            choices.remove(b)
            if not choices:del edges[a]
            previous=direction(a,b);a=b
            if a==start:break
        pts=np.asarray(loop,np.int32)
        prev=np.roll(pts,1,axis=0);nxt=np.roll(pts,-1,axis=0)
        v=pts-prev;u=nxt-pts
        keep=(v[:,0]*u[:,1]-v[:,1]*u[:,0])!=0
        pts=pts[keep]
        if len(pts)<3:continue
        area=float(np.sum(pts[:,0]*np.roll(pts[:,1],-1)-pts[:,1]*np.roll(pts[:,0],-1))/2)
        loops.append((pts,area))
    outers=sorted([(pts,[],area) for pts,area in loops if area>0],key=lambda x:-x[2])
    for hole,area in loops:
        if area>=0:continue
        point=tuple(float(x) for x in hole[0])
        parents=[entry for entry in outers if cv2.pointPolygonTest(entry[0],point,False)>=0]
        if not parents:raise ValueError('Uncontained mask opening')
        min(parents,key=lambda x:x[2])[1].append(hole)
    def points(pts):
        return [Point(x=float(x)/w,y=float(y)/h) for x,y in pts]
    return [(points(outer),[points(hole) for hole in holes],area) for outer,holes,area in outers]
