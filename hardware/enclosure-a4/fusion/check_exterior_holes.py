"""Compare front-most ray intersections with the ORIGINAL external surface.

Internal pockets must not cut that surface outside explicitly required ports.
"""
import json,sys,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import trimesh
import vtk
from explore_geometry import ROOT,load
working=json.loads((ROOT/'fusion/working-r3.json').read_text(encoding='utf-8'))
angle=math.radians(working.get('screen_angle_deg',45));c,sn=math.cos(angle),math.sin(angle)
O=np.array(working['screen_origin_mm'])
M=np.eye(4);M[:3,:3]=[[1,0,0],[0,c,sn],[0,-sn,c]];M[:3,3]=-M[:3,:3]@O

def reference_surface():
    return trimesh.load_mesh(ROOT/'output/r3-original/exterior-reference-upper.stl')

def tree(mesh):
    m=mesh.copy();m.apply_transform(M)
    points=vtk.vtkPoints();points.SetDataTypeToDouble()
    for p in m.vertices:points.InsertNextPoint(*p)
    faces=vtk.vtkCellArray()
    for f in m.faces:
        faces.InsertNextCell(3)
        for i in f:faces.InsertCellPoint(int(i))
    data=vtk.vtkPolyData();data.SetPoints(points);data.SetPolys(faces)
    obb=vtk.vtkStaticCellLocator();obb.SetDataSet(data);obb.BuildLocator();return obb
def first(obb,u,v):
    t=vtk.reference(0.);sub=vtk.reference(0);cell=vtk.reference(0);point=[0.,0.,0.];coords=[0.,0.,0.]
    hit=obb.IntersectWithLine([float(u),float(v),100],[float(u),float(v),-100],1e-7,t,point,coords,sub,cell)
    return point[2] if hit else None
def check(path,step=.5):
    old=tree(reference_surface());new=tree(trimesh.load_mesh(path));bad=[];tested=0
    for u in np.arange(-7.0,87.01,step):
        for v in np.arange(-15,65.01,step):
            before=first(old,u,v)
            if before is None or before<-8:continue
            world=O+np.array([u,c*v-sn*before,sn*v+c*before])
            x,y,z=world
            if 7.55<u<67.25 and 2.85<v<48.15:continue # new active display window
            if y<-48:continue # inherited key/joystick openings and travel relief
            if (x-46)**2+(y+42.1)**2<1.45**2:continue # requested upper mic inlet
            if x<7.1 and -30.1<y<-.9 and 14.4<z<24.6:continue # requested two USB ports
            after=first(new,u,v);tested+=1
            if after is None or before-after>.15:bad.append({'u':float(u),'v':float(v),'before_n':before,'after_n':after,'world':world.tolist()})
    return {'grid_step_mm':step,'checked_rays':tested,'unexpected_surface_opening_samples':len(bad),'samples':bad[:80]}
if __name__=='__main__':
    path=Path(sys.argv[1]);result=check(path);print(json.dumps(result,indent=2))
    (path.parent/(path.stem+'-exterior-check.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
    assert not result['unexpected_surface_opening_samples'],result['samples'][:5]
