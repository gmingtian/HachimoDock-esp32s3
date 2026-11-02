"""Coordinate-based assembly illustration; unmeasured heights are explicit.

Uses the actual PCB XY geometry and the upstream printed cap/keycap solids.
Module electronics/USB appearance and the Z stack are schematic. It is not a
collision simulation or a manufacturing model.
"""
import hashlib
import argparse
import json
import math
from pathlib import Path
import sys

import numpy as np
from PIL import Image,ImageDraw,ImageFont
from shapely import constrained_delaunay_triangles
from shapely.geometry import Point,Polygon,box
import vtk

from build_design import ROOT,REVISION
from route_board import outline_polygon

OUT=ROOT.parents[1]/'artifacts/pcb'/f'{REVISION}-assembly'
FONT='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
SOURCE_STEP=Path.home()/'下载/桌搭-整机外壳3d打印版.STEP'
R=vtk.vtkRenderer()
ACTORS=[]


def actor(data,color,metal=0,rough=.5):
    mapper=vtk.vtkPolyDataMapper();mapper.SetInputData(data)
    a=vtk.vtkActor();a.SetMapper(mapper);p=a.GetProperty()
    p.SetColor(*color);p.SetInterpolationToPBR();p.SetMetallic(metal);p.SetRoughness(rough)
    R.AddActor(a);ACTORS.append(a);return a


def mesh(vertices,faces,color,metal=0,rough=.5):
    pts=vtk.vtkPoints()
    for v in vertices:pts.InsertNextPoint(*v)
    cells=vtk.vtkCellArray()
    for f in faces:
        cells.InsertNextCell(len(f))
        for i in f:cells.InsertCellPoint(i)
    d=vtk.vtkPolyData();d.SetPoints(pts);d.SetPolys(cells)
    normals=vtk.vtkPolyDataNormals();normals.SetInputData(d);normals.AutoOrientNormalsOn()
    normals.SetFeatureAngle(45);normals.Update()
    return actor(normals.GetOutput(),color,metal,rough)


def solid(poly,z0,z1,color,metal=0,rough=.5):
    vv=[];ff=[]
    def face(coords):
        i=len(vv);vv.extend(coords);ff.append(tuple(range(i,len(vv))))
    for t in constrained_delaunay_triangles(poly).geoms:
        xy=list(t.exterior.coords)[:3]
        face([(x,-y,z1) for x,y in xy]);face([(x,-y,z0) for x,y in xy[::-1]])
    for ring in [poly.exterior,*poly.interiors]:
        q=list(ring.coords)
        for (x,y),(u,v) in zip(q,q[1:]):face([(x,-y,z0),(u,-v,z0),(u,-v,z1),(x,-y,z1)])
    return mesh(vv,ff,color,metal,rough)


def cube(x0,y0,x1,y1,z0,z1,color,metal=0,rough=.5):
    s=vtk.vtkCubeSource();s.SetCenter((x0+x1)/2,-(y0+y1)/2,(z0+z1)/2)
    s.SetXLength(x1-x0);s.SetYLength(y1-y0);s.SetZLength(z1-z0);s.Update()
    return actor(s.GetOutput(),color,metal,rough)


def cylinder(x,y,r,z0,z1,color,metal=0,rough=.5):
    s=vtk.vtkCylinderSource();s.SetRadius(r);s.SetHeight(z1-z0);s.SetResolution(48);s.Update()
    a=actor(s.GetOutput(),color,metal,rough);a.RotateX(90);a.SetPosition(x,-y,(z0+z1)/2);return a


def text(label,x,y,z,size=.8,color=(.92,.94,.91)):
    t=vtk.vtkVectorText();t.SetText(label);t.Update();b=t.GetOutput().GetBounds()
    a=actor(t.GetOutput(),color,0,.9);a.SetScale(size,size,size)
    a.SetPosition(x-(b[0]+b[1])/2*size,-y-(b[2]+b[3])/2*size,z)


def line(points,color,r=.12):
    pts=vtk.vtkPoints();poly=vtk.vtkPolyLine();poly.GetPointIds().SetNumberOfIds(len(points))
    for i,(x,y,z) in enumerate(points):pts.InsertNextPoint(x,-y,z);poly.GetPointIds().SetId(i,i)
    cells=vtk.vtkCellArray();cells.InsertNextCell(poly)
    d=vtk.vtkPolyData();d.SetPoints(pts);d.SetLines(cells)
    tube=vtk.vtkTubeFilter();tube.SetInputData(d);tube.SetRadius(r);tube.SetNumberOfSides(10);tube.Update()
    return actor(tube.GetOutput(),color,0,.8)


def import_caps(d,source):
    from OCP.STEPControl import STEPControl_Reader
    from OCP.TopAbs import TopAbs_SOLID
    from OCP.TopExp import TopExp_Explorer
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.StlAPI import StlAPI_Writer
    reader=STEPControl_Reader();assert reader.ReadFile(str(source))==1;reader.TransferRoots()
    ex=TopExp_Explorer(reader.OneShape(),TopAbs_SOLID);index=0
    while ex.More():
        shape=ex.Current()
        if index in range(2,8):
            p=OUT/f'original-solid-{index}.stl'
            BRepMesh_IncrementalMesh(shape,.06,False,.15,True);StlAPI_Writer().Write(shape,str(p))
            read=vtk.vtkSTLReader();read.SetFileName(str(p));read.Update()
            bounds=Bnd_Box();BRepBndLib.Add_s(shape,bounds);lo=bounds.CornerMin();hi=bounds.CornerMax()
            if index<5:
                c=next(c for c in d['components'] if c['ref']==f'SW{index-1}')
                e=c['envelope'];cx=(e[0]+e[2])/2;cy=(e[1]+e[3])/2
                dx=cx-(lo.X()+hi.X())/2;dy=-cy+(lo.Z()+hi.Z())/2
                dz=15.2-lo.Y();color=(.91,.88,.79)
            else:
                dx=65.62495-29.5;dy=-59.44864+15.75
                dz=26.6-10.144747468305837;color=(.98,.34,.055)
            matrix=vtk.vtkMatrix4x4();matrix.Identity()
            for i,row in enumerate([[1,0,0,dx],[0,0,-1,dy],[0,1,0,dz],[0,0,0,1]]):
                for j,value in enumerate(row):matrix.SetElement(i,j,value)
            a=actor(read.GetOutput(),color,0,.48);a.SetUserMatrix(matrix)
        ex.Next();index+=1


def populate(d,source):
    green=(.035,.24,.18);gold=(.76,.54,.18);black=(.035,.043,.052);silver=(.67,.71,.74)
    outline=outline_polygon(d['outline'])
    holes=[Point(h['x'],h['y']).buffer(h['diameter']/2,quad_segs=12) for h in d['mountingHoles']]
    for c in d['components']:
        holes += [Point(h['x'],h['y']).buffer(h['diameter']/2,quad_segs=12) for h in c['holes']]
        holes += [Point(p['x'],p['y']).buffer(p['drill']/2,quad_segs=8) for p in c['pads'] if p['drill']]
    for h in holes:outline=outline.difference(h)
    solid(outline,0,1.6,green)
    for c in d['components']:
        for p in c['pads']:
            outer=Point(p['x'],p['y']).buffer(p['width']/2,quad_segs=10)
            if p['shape']=='rect':outer=box(p['x']-p['width']/2,p['y']-p['height']/2,p['x']+p['width']/2,p['y']+p['height']/2)
            inner=Point(p['x'],p['y']).buffer(p['drill']/2,quad_segs=10)
            solid(outer.difference(inner),1.6,1.65,gold,.6,.3)
    for h in d['fastenerEnvelopes']:
        # The original case uses two screws; H3 is a locating/support hole.
        # Keep all five conservative CAD keepouts, but do not depict five screws.
        if h['ref'] not in ('H1','H4'):continue
        x,y=h['x'],h['y'];color=(.84,.84,.78) if h['material']=='nylon' else silver
        cylinder(x,y,1.35,-1,1.9,color,.4)
        cylinder(x,y,3,1.65,4.65,color,.4,.35)
        cavity=Polygon([(x+1.3*math.cos(t*math.pi/3),y+1.3*math.sin(t*math.pi/3)) for t in range(6)])
        solid(cavity,4.65,4.67,(.14,.16,.16))
    # Female socket body 8.5mm + male header shoulder 2.5mm: assumed stack.
    for s in d['mountingSockets']:
        x0,y0,x1,y1=s['bodyEnvelope'];cube(x0,y0,x1,y1,1.7,10.2,black)
    for ref in ['U1','U2','U3']:
        c=next(c for c in d['components'] if c['ref']==ref)
        for p in c['pads']:
            cube(p['x']-.31,p['y']-.31,p['x']+.31,p['y']+.31,1.3,13.5,gold,.7,.25)
            cube(p['x']-1.1,p['y']-1.1,p['x']+1.1,p['y']+1.1,10.2,12.6,black)
        e=c['envelope']
        if ref=='U3':
            poly=Point(46,42.1).buffer(7,quad_segs=32).difference(Point(46,42.1).buffer(1,quad_segs=16))
            solid(poly,12.6,14.2,(.06,.065,.07));cube(44.5,40.6,47.5,43.6,11,12.6,silver,.65)
            text('INMP441',46,42.1,14.24,.68)
        else:
            solid(box(*e),12.6,14.2,(.035,.15,.21) if ref=='U1' else (.27,.09,.4))
    # Devkit exterior is illustrative; only its carrier footprint/envelope is sourced.
    cube(36,5.5,67,24.3,14.2,14.9,(.045,.055,.06))
    cube(37,6.1,61.5,23.7,14.9,17.7,silver,.78,.33)
    text('ESP32-S3',49.2,13,17.74,1.6,(.16,.18,.18));text('N16R8',49.2,17,17.74,1.0,(.2,.22,.22))
    for y in [8.3,21.1]:
        cube(-.7,y-3.5,7,y+3.5,14.2,17.4,silver,.85,.27)
        cube(-.81,y-2.9,-.73,y+2.9,14.55,16.9,black)
        cube(-.84,y-2,-.72,y+2,15.25,15.65,(.22,.23,.24))
    for x,y,w,h in [(17,12,5,5),(24,19,4,3),(12,19,3,4)]:cube(x,y,x+w,y+h,14.2,15.8,black)
    text('GOOUUU',22,6,14.25,1.2)
    for y in [7,10,13,16,19,22]:line([(62,y,14.95),(65.8,y,14.95)],gold,.15)
    cube(10,37,15,42,14.2,15.5,black);text('MAX98357A',15,46,14.23,.65)
    for x,y in [(8,34),(17,34),(18,41)]:cube(x,y,x+2.7,y+1.3,14.2,15.2,(.72,.62,.43))
    # Speaker connection remains on amplifier module, never the carrier.
    for x in [17,21]:
        cylinder(x,32.7,.95,14.2,14.28,gold,.65);cylinder(x,32.7,.5,14.28,14.31,black)
    for c in d['components']:
        if not c['ref'].startswith('SW'):continue
        e=c['envelope'];cx=(e[0]+e[2])/2;cy=(e[1]+e[3])/2
        cube(*e,1.6,9.8,black);cube(cx-6.8,cy-6.8,cx+6.8,cy+6.8,9.8,13.2,(.36,.29,.22))
        cube(cx-2,cy-.7,cx+2,cy+.7,13.2,17,(.45,.25,.11));cube(cx-.7,cy-2,cx+.7,cy+2,13.2,17,(.45,.25,.11))
    x,y=d['joystickMotionReservation']['center']
    cube(x-6.5,y-6.5,x+6.5,y+6.5,1.6,12.6,silver,.7,.38)
    cube(x-9.3,y-4.75,x-6.5,y+4.75,3.2,10.5,(.055,.32,.19))
    cube(x-4.75,y+6.5,x+4.75,y+9.3,3.2,10.5,(.055,.32,.19))
    cube(x-4.75,y-13.3,x+4.75,y-6.5,1.6,7.6,black)
    cylinder(x,y,1.75,9,21,silver,.7)
    import_caps(d,source)
    # Actual J1 XY; housing height is an assumed plugged assembly.
    jp=next(c for c in d['components'] if c['ref']=='JP1')
    x0,y0,x1,y1=jp['envelope'];cube(x0,y0,x1,y1,1.65,4.2,black)
    for p in jp['pads']:cube(p['x']-.32,p['y']-.32,p['x']+.32,p['y']+.32,1.5,10.2,gold,.7)
    # Shunt is shown in the quieter 1-2 position. Body/height are allowances.
    cube(26,37.52,30,43.02,4.3,10.3,(.12,.29,.62))
    text('JP1',28,35.7,1.7,.8)
    x0,y0,x1,y1=next(c for c in d['components'] if c['ref']=='J1')['envelope']
    cube(x0,y0,x1,y1,1.65,4.15,black)
    for i in range(8):cube(26.7+2.54*i,30.7,27.3+2.54*i,31.3,4.1,10.1,gold,.7)
    cube(24.89,29.5,46.89,32.5,4.3,18.3,(.045,.05,.055))
    wirecolors=[(.06,.06,.06),(.7,.13,.08),(.8,.46,.1),(.74,.67,.14),(.17,.43,.23),(.1,.4,.55),(.3,.24,.55),(.5,.5,.53)]
    for i,col in enumerate(wirecolors):
        x=27+2.54*i
        line([(x,31,18.2),(x,31,21),(x,29,24),(x,24,26),(x,17,26)],col,.33)
    text(f'HACHIMODOCK S3 / {REVISION}',34,69,1.67,.9)


def render(name,camera,target,scale,title,subtitle,detail=False):
    w=vtk.vtkEGLRenderWindow();w.SetOffScreenRendering(1);w.SetSize(1800,1400 if not detail else 1100)
    w.SetMultiSamples(0);w.AddRenderer(R);R.SetBackground(.945,.956,.964);R.SetUseFXAA(False)
    cam=R.GetActiveCamera();cam.SetPosition(*camera);cam.SetFocalPoint(*target);cam.SetViewUp(0,0,1)
    cam.ParallelProjectionOn();cam.SetParallelScale(scale);R.ResetCameraClippingRange()
    w.Render();capture=vtk.vtkWindowToImageFilter();capture.SetInput(w);capture.ReadFrontBufferOff();capture.SetScale(1);capture.Update()
    path=OUT/name;writer=vtk.vtkPNGWriter();writer.SetFileName(str(path));writer.SetInputConnection(capture.GetOutputPort());writer.Write()
    w.Finalize()
    im=Image.open(path).convert('RGB');dr=ImageDraw.Draw(im)
    dr.rectangle((0,0,im.width,153),fill='#f1f4f6')
    dr.rectangle((0,im.height-73,im.width,im.height),fill='#f1f4f6')
    dr.text((65,40),title,font=ImageFont.truetype(FONT,43),fill='#26333e')
    dr.text((65,103),subtitle,font=ImageFont.truetype(FONT,24),fill='#64717c')
    note=f'PCB XY按{REVISION}；模块外观、排母及装配高度为示意，非三维无干涉验证。'
    dr.text((65,im.height-57),note,font=ImageFont.truetype(FONT,23),fill='#687580')
    if detail:
        dr.rounded_rectangle((55,im.height-220,850,im.height-83),radius=12,fill='#f7f9fa')
        f=ImageFont.truetype(FONT,29)
        dr.text((78,im.height-207),'与ESP32排母的平面间隙：约0.54 mm',font=f,fill='#2c5d5c')
        dr.text((78,im.height-156),'H3定位孔不装螺丝；定位柱尺寸仍待核准',font=f,fill='#2c5d5c')
    im.save(path);print(path,flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source-step',type=Path,default=SOURCE_STEP)
    args=parser.parse_args()
    if not args.source_step.is_file():raise SystemExit('Provide the original case/keycap STEP with --source-step.')
    OUT.mkdir(parents=True,exist_ok=True);d=json.loads((ROOT/'output/design.json').read_text())
    populate(d,args.source_step)
    for pos,intensity in [((10,-100,180),1.5),((-90,20,100),1.1),((130,80,100),1.4)]:
        light=vtk.vtkLight();light.SetPosition(*pos);light.SetFocalPoint(35,-35,0);light.SetIntensity(intensity);R.AddLight(light)
    render('assembly-isometric.png',(135,-155,135),(35,-35,10),56,
        'HachimoDock S3 · 装配示意', '新增JP1增益跳线；原版三键、摇杆与模块位置不变')
    render('connector-fastener-clearance.png',(48,-65,80),(35,-31.7,8),15,
        '屏幕接口与定位孔 · 局部', 'H1/H4两处固定；H3保留定位/支撑孔，不安装螺丝',True)
    views=[('front-right.png',(135,-155,135),'右前视角'),
           ('front-left.png',(-100,-150,120),'左前视角'),
           ('rear.png',(110,100,115),'背面视角'),
           ('top.png',(35,-35.1,200),'俯视图')]
    for name,camera,title in views:
        render(name,camera,(35,-35,10),56,'HachimoDock S3 · '+title,
               'A4底板装配示意；H1/H4两处固定，H3不装螺丝')
    sheet=Image.new('RGB',(2400,2006),'#f1f4f6');draw=ImageDraw.Draw(sheet)
    draw.text((48,24),'HachimoDock S3 · A4 多视角装配示意',
              font=ImageFont.truetype(FONT,46),fill='#26333e')
    draw.text((48,88),'未放置屏幕和外壳；模块外观与高度为示意，非实物照片或碰撞验证。',
              font=ImageFont.truetype(FONT,25),fill='#64717c')
    for i,(name,_,_) in enumerate(views):
        with Image.open(OUT/name) as view:
            sheet.paste(view.resize((1200,933),Image.Resampling.LANCZOS),((i%2)*1200,140+(i//2)*933))
    sheet.save(OUT/'assembly-four-views.png')
    report={'revision':REVISION,'designSha256':hashlib.sha256((ROOT/'output/design.json').read_bytes()).hexdigest(),
        'renderMethod':'VTK/EGL from PCB coordinates and imported original STEP cap/keycap solids',
        'printedCapAndKeycapSourceSha256':hashlib.sha256(args.source_step.read_bytes()).hexdigest(),
        'assumedHeightsMm':{'carrier':1.6,'femaleSocket':8.5,'maleShoulder':2.4,'modulePcbBottom':12.6,
            'modulePcbThickness':1.6,'screwHeadMaximum':3.0,'keycapBottom':15.2,'printedSphereCenter':26.6,'screenPlugHeight':14.0},
        'gainSelector':{'shuntShown':'1-2 / 6dB','assumedShuntHeightMm':10.3,'actualHeightVerified':False},
        'screwHeadDiameterPlanningMm':6,'connectorBodyMaximumXYmm':[22,3],
        'shownFasteners':['H1','H4'],'locatingSupportHole':'H3; no screw installed',
        'moduleElectronicsAndUsbExterior':'schematic; not a measured vendor STEP',
        'screenBodyShown':False,'screenBodyReason':'actual Unvision board dimensions/mounting remain unconfirmed',
        'collisionSimulation':False,'fabricationApproved':False}
    (OUT/'render-assumptions.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':main()
