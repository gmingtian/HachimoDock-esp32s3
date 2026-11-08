from pathlib import Path
import json
import numpy as np
import trimesh
import vtk
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'output'
OUT.mkdir(exist_ok=True)
SHIFT=[36.12495,43.69864,16.45525253169416]
T=np.array([[1,0,0,SHIFT[0]],[0,0,-1,-SHIFT[1]],[0,1,0,SHIFT[2]],[0,0,0,1]],float)

def load(i):
    m=trimesh.load_mesh(ROOT/f'reference/step-solids/solid-{i}.stl')
    # Proper rotation: physical Y = -PCB drawing Y. Never mirror the original.
    m.apply_transform(T)
    m.merge_vertices(digits_vertex=4)
    return m

def heights(m,x,y):
    y=-y
    v=m.triangles
    a=v[:,0,:2];b=v[:,1,:2]-a;c=v[:,2,:2]-a;p=np.array([x,y])-a
    den=b[:,0]*c[:,1]-b[:,1]*c[:,0]
    ok=np.abs(den)>1e-9
    u=np.zeros(len(v));w=u.copy()
    u[ok]=(p[ok,0]*c[ok,1]-p[ok,1]*c[ok,0])/den[ok]
    w[ok]=(b[ok,0]*p[ok,1]-b[ok,1]*p[ok,0])/den[ok]
    ok&=(u>=-1e-5)&(w>=-1e-5)&(u+w<=1.00001)
    z=v[:,0,2]+u*(v[:,1,2]-v[:,0,2])+w*(v[:,2,2]-v[:,0,2])
    return sorted(set(round(float(t),3) for t in z[ok]))

def actor(mesh,color):
    pts=vtk.vtkPoints()
    for p in mesh.vertices:pts.InsertNextPoint(*p)
    polys=vtk.vtkCellArray()
    for f in mesh.faces:
        polys.InsertNextCell(3)
        for k in f:polys.InsertCellPoint(int(k))
    data=vtk.vtkPolyData();data.SetPoints(pts);data.SetPolys(polys)
    normals=vtk.vtkPolyDataNormals();normals.SetInputData(data);normals.AutoOrientNormalsOn();normals.Update()
    mapper=vtk.vtkPolyDataMapper();mapper.SetInputData(normals.GetOutput())
    a=vtk.vtkActor();a.SetMapper(mapper);a.GetProperty().SetColor(*color)
    return a

def render(meshes,path,camera=(150,-190,145)):
    r=vtk.vtkRenderer();r.SetBackground(.94,.95,.97)
    for m,col in meshes:r.AddActor(actor(m,col))
    c=r.GetActiveCamera();c.SetPosition(*camera);c.SetFocalPoint(36,-28,24);c.SetViewUp(0,0,1);c.ParallelProjectionOn()
    r.ResetCamera();c.Zoom(1.12)
    w=vtk.vtkRenderWindow();w.SetOffScreenRendering(1);w.AddRenderer(r);w.SetSize(1100,850);w.SetMultiSamples(4);w.Render()
    capture=vtk.vtkWindowToImageFilter();capture.SetInput(w);capture.Update()
    writer=vtk.vtkPNGWriter();writer.SetFileName(str(path));writer.SetInputConnection(capture.GetOutputPort());writer.Write();w.Finalize()

if __name__=='__main__':
    meshes=[load(i) for i in range(8)]
    report={}
    for i in [0,1]:
        m=meshes[i]
        report[i]={'bounds':m.bounds.tolist(),'volume':m.volume,'watertight':m.is_watertight,'heights':{f'{x},{y}':heights(m,x,y) for x,y in [(11.04067642,36.00313348),(36.04367442,36.05953418),(61.05627489,36.0265345),(36,0),(36,10),(36,20),(36,30),(36,40),(36,50),(36,65)]}}
        render([(m,(.15,.18,.21))],OUT/f'original-solid-{i}.png')
    render([(meshes[0],(.16,.18,.21)),(meshes[1],(.3,.32,.36))]+[(m,(.88,.85,.76)) for m in meshes[2:5]]+[(m,(.94,.36,.1)) for m in meshes[5:]],OUT/'original-assembled.png')
    (OUT/'original-geometry.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
