"""Sphere-cap motion envelope study; pivot and travel assumptions are explicit.

Uses a true analytical sphere against signed distance to closed triangle meshes.
The original cap is ~14 mm; allow a 7.05 mm radius. Pivot uncertainty is scanned
as neutral pivot-to-cap-center lengths of 12, 15.1 and 18 mm, not claimed measured.
"""
import json
import math
import sys
import numpy as np
import trimesh
import vtk
from explore_geometry import ROOT,OUT,load
from build_enclosure import OUT

def locator(m):
    points=vtk.vtkPoints();points.SetDataTypeToDouble()
    for p in m.vertices:points.InsertNextPoint(*p)
    cells=vtk.vtkCellArray()
    for f in m.faces:
        cells.InsertNextCell(3)
        for i in f:cells.InsertCellPoint(int(i))
    data=vtk.vtkPolyData();data.SetPoints(points);data.SetPolys(cells)
    d=vtk.vtkImplicitPolyDataDistance();d.SetInput(data)
    return d

def positions(extension,step=8):
    c=np.array([65.62495,-59.44864,26.6])
    for arm in [12,15.1,18]:
        for press in [0,1]:
            for theta in np.arange(0,32.001,step):
                a=math.radians(float(theta))
                for phi in np.arange(0,360,step):
                    p=math.radians(float(phi));r=(arm+extension)*math.sin(a)
                    center=c+np.array([r*math.cos(p),r*math.sin(p),-arm+(arm+extension)*math.cos(a)-press])
                    yield center,{'arm':arm,'press':press,'theta':float(theta),'phi':float(phi)}

def evaluate(locators,extension,step=8):
    result={name:{'gap_mm':1e9} for name in locators}
    for center,pose in positions(extension,step):
        for name,distance in locators.items():
            gap=distance.EvaluateFunction(center.tolist())-7.05
            if gap<result[name]['gap_mm']:result[name]={'gap_mm':round(float(gap),4),'pose':pose,'center':np.round(center,4).tolist()}
    return result

def main():
    upperfile=sys.argv[1] if len(sys.argv)>1 else 'a4-upper-r1-assembly.stl'
    locators={'case':locator(trimesh.load_mesh(OUT/upperfile)),**{f'SW{i-1}':locator(load(i)) for i in [2,3,4]}}
    results={}
    for extension in [0,4,8,10,12,14,16,20,24,32]:
        result=evaluate(locators,extension)
        results[extension]=result
        print(extension,{k:r['gap_mm'] for k,r in result.items()},flush=True)
    report={'capRadiusMm':7.05,'maxAngleDeg':32,'clickTravelAssumedMm':1,'neutralArmLengthsScannedMm':[12,15.1,18],'angleStepDeg':8,'pivotMeasured':False,'results':results}
    (OUT/'joystick-motion-study.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':main()
