import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import trimesh
import vtk
from explore_geometry import ROOT,load
from interface_seams import is_driver_cover_seam

def locator(mesh):
    points=vtk.vtkPoints();points.SetDataTypeToDouble()
    for p in mesh.vertices:points.InsertNextPoint(*p)
    cells=vtk.vtkCellArray()
    for f in mesh.faces:
        cells.InsertNextCell(3)
        for i in f:cells.InsertCellPoint(int(i))
    data=vtk.vtkPolyData();data.SetPoints(points);data.SetPolys(cells)
    loc=vtk.vtkStaticCellLocator();loc.SetDataSet(data);loc.BuildLocator();return loc
def first(loc,y,z,side):
    t=vtk.reference(0.);sub=vtk.reference(0);cell=vtk.reference(0);point=[0.,0.,0.];coords=[0.,0.,0.]
    hit=loc.IntersectWithLine([side*100,float(y),float(z)],[-side*100,float(y),float(z)],1e-7,t,point,coords,sub,cell)
    return point[0] if hit else None
def check(folder,step=.5):
    working=json.loads((folder.parent.parent/'fusion/working-r4.json').read_text(encoding='utf-8'))
    old=[locator(trimesh.load_mesh(folder/f'exterior-reference-{label}.stl')) for label in ['upper','lower']]
    new=[locator(trimesh.load_mesh(folder/f'a4-{name}-r4-assembly.stl')) for name in ['upper','lower']]
    result={}
    for side,label in [(-1,'left'),(1,'right')]:
        bad=[];tested=0
        for y in np.arange(-75,11.01,step):
            for z in np.arange(-2,72.01,step):
                source=[v for loc in old if (v:=first(loc,y,z,side)) is not None]
                if not source:continue
                before=(min if side==-1 else max)(source)
                if is_driver_cover_seam(before,y,z,working):continue
                if side==-1 and -30.1<y<-.9 and 14.4<z<24.6:continue
                current=[v for loc in new if (v:=first(loc,y,z,side)) is not None]
                after=(min if side==-1 else max)(current) if current else None
                tested+=1
                if after is None or (before-after)*side>.15:bad.append({'y':float(y),'z':float(z),'before_x':before,'after_x':after})
        result[label]={'checked_rays':tested,'unexpected_opening_samples':len(bad),'samples':bad[:100]}
    return result
if __name__=='__main__':
    folder=Path(sys.argv[1]);result=check(folder);print(json.dumps(result,indent=2))
    (folder/'side-surface-check.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    assert all(v['unexpected_opening_samples']==0 for v in result.values()),{k:v['unexpected_opening_samples'] for k,v in result.items()}
