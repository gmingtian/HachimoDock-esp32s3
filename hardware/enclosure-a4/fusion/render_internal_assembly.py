"""Render the real enclosure/PCB with explicitly illustrative module exteriors."""
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import trimesh
import vtk
import manifold3d as mf
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from build_enclosure import board,mesh,D,P
from explore_geometry import load

OUT=ROOT/'output/r4-original-copy/assembly-render'
OUT.mkdir(exist_ok=True)
W=json.loads((ROOT/'fusion/working-r4.json').read_text(encoding='utf-8'))
O=np.array(W['screen_origin_mm']);q=math.sqrt(.5)
ROT=np.array([[1,0,0],[0,q,-q],[0,q,q]])
FONT=Path('C:/Windows/Fonts/msyh.ttc')
COLORS={'shell':(.89,.91,.92),'board':(.025,.24,.16),'gold':(.75,.53,.18),
        'black':(.025,.032,.042),'silver':(.65,.69,.73),'purple':(.26,.075,.38)}
OBJECTS=[]


def font(size):return ImageFont.truetype(str(FONT),size)


def world(u,v,n):return O+ROT@np.array([u,v,n])


def add(m,color,group,name='',metal=0,opacity=1):
    OBJECTS.append(dict(mesh=m,color=color,group=group,name=name,metal=metal,opacity=opacity))


def box(a,b,color,group,name='',metal=0):
    m=trimesh.creation.box(np.array(b)-a);m.apply_translation((np.array(a)+b)/2)
    add(m,color,group,name,metal)


def pcbbox(e,z0,z1,color,group='pcb',name='',metal=0):
    x0,y0,x1,y1=e;box([x0,-y1,z0],[x1,-y0,z1],color,group,name,metal)


def cylinder(a,b,r,color,group,metal=0):
    add(trimesh.creation.cylinder(radius=r,segment=[a,b],sections=32),color,group,metal=metal)


def ring(x,y,r,dr,z0,z1,color,group='pcb'):
    s=mf.Manifold.cylinder(z1-z0,r,circular_segments=32)
    if dr:s=s-mf.Manifold.cylinder(z1-z0+.2,dr,circular_segments=32).translate([0,0,-.1])
    add(mesh(s.translate([x,-y,z0])),color,group,metal=.6)


def screen_box(a,b,color,group='lcd',name='',metal=0):
    m=trimesh.creation.box(np.array(b)-a);m.apply_translation((np.array(a)+b)/2)
    T=np.eye(4);T[:3,:3]=ROT;T[:3,3]=O;m.apply_transform(T);add(m,color,group,name,metal)


def populate():
    gold,black,silver=COLORS['gold'],COLORS['black'],COLORS['silver']
    for part in ['upper','lower']:
        add(trimesh.load_mesh(OUT.parent/f'a4-{part}-r4-assembly.stl'),COLORS['shell'],part,'Case '+part)
    add(mesh(board()),COLORS['board'],'pcb','Actual carrier PCB')
    top=P['pcb_bottom_z']+1.6
    for c in D['components']:
        for p in c['pads']:
            ring(p['x'],p['y'],p['width']/2,p.get('drill',0)/2,top,top+.055,gold)
    for h in D['mountingHoles']:
        ring(h['x'],h['y'],2.2,h['diameter']/2,top,top+.055,gold)
    # U1 keeps its normal sockets. Audio modules have no female sockets.
    for y in [2.294,27.694]:
        pcbbox([5.66,y-1.27,59,y+1.27],top,top+8.5,black)
    for ref in ['U1','U2','U3']:
        c=next(c for c in D['components'] if c['ref']==ref)
        z=P['pcb_bottom_z']+P['module_board_bottom_by_ref'][ref]
        if ref=='U3':
            s=mf.Manifold.cylinder(1.6,7,circular_segments=64)-mf.Manifold.cylinder(1.8,.8,circular_segments=32).translate([0,0,-.1])
            add(mesh(s.translate([46,-42.1,z])),black,'pcb','INMP441 low mount')
            ring(46,42.1,6.7,6.4,z+1.6,z+1.64,gold)
            pcbbox([44.5,40.6,47.5,43.6],z-1.5,z,silver,metal=.75)
        else:
            pcbbox(c['envelope'],z,z+1.6,black if ref=='U1' else COLORS['purple'],name=ref)
        for p in c['pads']:
            pcbbox([p['x']-.31,p['y']-.31,p['x']+.31,p['y']+.31],top-.25,z+1.68,gold,metal=.7)
            base=z-2.5
            pcbbox([p['x']-.95,p['y']-.95,p['x']+.95,p['y']+.95],base,z,black)
    z=P['pcb_bottom_z']+12.6+1.6
    pcbbox([37,6.1,61.5,23.7],z,z+3.5,silver,name='ESP32-S3 shield',metal=.8)
    for y in [8.3,21.1]:
        pcbbox([-.7,y-3.5,7,y+3.5],z,z+3.2,silver,name='Type-C',metal=.8)
        pcbbox([-.81,y-2.8,-.72,y+2.8],z+.45,z+2.7,black)
        pcbbox([-.83,y-1.9,-.71,y+1.9],z+1.4,z+1.8,(.30,.30,.29))
    for x,y,dx,dy in [(17,12,5,5),(24,19,4,3),(12,19,3,4)]:
        pcbbox([x,y,x+dx,y+dy],z,z+1.5,black)
    for y in [7,10,13,16,19,22]:pcbbox([62,y,65.8,y+.32],z,z+.08,gold,metal=.6)
    ampz=P['pcb_bottom_z']+4.1+1.6
    pcbbox([10,37,15,42],ampz,ampz+1.3,black)
    for x,y in [(8,34),(17,34),(18,41)]:pcbbox([x,y,x+2.7,y+1.3],ampz,ampz+1,(.67,.56,.38))
    for x in [17,21]:ring(x,32.7,.95,.5,ampz,ampz+.05,gold)
    for c in D['components']:
        if not c['ref'].startswith('SW'):continue
        e=c['envelope'];cx=(e[0]+e[2])/2;cy=(e[1]+e[3])/2
        pcbbox(e,top,top+8.2,black)
        pcbbox([cx-6.8,cy-6.8,cx+6.8,cy+6.8],top+8.2,top+11.6,(.69,.73,.74))
        pcbbox([cx-2,cy-.7,cx+2,cy+.7],top+11.6,top+15,(.53,.36,.19))
        pcbbox([cx-.7,cy-2,cx+.7,cy+2],top+11.6,top+15,(.53,.36,.19))
    x,y=D['joystickMotionReservation']['center']
    pcbbox([x-6.5,y-6.5,x+6.5,y+6.5],top,top+11,silver,metal=.7)
    pcbbox([x-9.3,y-4.75,x-6.5,y+4.75],top+1.5,top+8.9,(.04,.30,.18))
    pcbbox([x-4.75,y+6.5,x+4.75,y+9.3],top+1.5,top+8.9,(.04,.30,.18))
    pcbbox([x-4.75,y-13.3,x+4.75,y-6.5],top,top+6,black)
    for i in range(2,8):
        col=(.96,.50,.075) if i==5 else silver if i==6 else (.91,.92,.91)
        add(load(i),col,'caps',f'Original control {i}',metal=.65 if i==6 else 0)
    # Current two machine screws and heat-set inserts, not the old H1 screw.
    for h in D['mountingHoles']:
        if h['ref'] not in ['H3','H4']:continue
        x,y=h['x'],-h['y']
        cylinder([x,y,-1.8],[x,y,.705],2.6,silver,'pcb',.75)
        cylinder([x,y,.705],[x,y,8.705],1.2,silver,'pcb',.75)
        ring(x,-y,1.75,1.25,4.305,8.305,(.78,.51,.16),'upper')
    j=next(c for c in D['components'] if c['ref']=='J1')['envelope']
    pcbbox(j,top,top+2.5,black)
    pcbbox([24.89,29.5,46.89,32.5],top+2.5,top+11,black,name='J1 DuPont')
    pcbbox([26.5,37.7,29.5,45.4],top,top+2.5,black)
    pcbbox([26.1,37.5,30,43.1],top+2.5,top+7,(.08,.23,.51))
    # LCD PCB and its four actual mounting holes, in the current screen datum.
    pcb=mf.Manifold.cube([81.2,51,1.6]).translate([0,0,-6.4])
    for u in [3,78.2]:
        for v in [3,48]:pcb-=mf.Manifold.cylinder(2,1.5,circular_segments=48).translate([u,v,-6.6])
    sm=mesh(pcb);T=np.eye(4);T[:3,:3]=ROT;T[:3,3]=O;sm.apply_transform(T)
    add(sm,(.035,.19,.25),'lcd','Actual LCD board 81.2 x 51')
    screen_box([6.0002,.5,-4.8],[75.1982,50.5,-.6],(.015,.025,.035),'glass','LCD glass')
    for u in [3,78.2]:
        for v in [3,48]:
            cylinder(world(u,v,-8),world(u,v,-6.4),1.9,silver,'lcd',.75)
            cylinder(world(u,v,-6.4),world(u,v,-1.4),.9,silver,'lcd',.75)
    for i,v in enumerate(np.linspace(16.61,34.39,8)):
        screen_box([.73,v-1.27,-9.4],[3.27,v+1.27,-6.4],black,'lcd','3 mm pin base')
        screen_box([.73,v-1.24,-23.4],[3.27,v+1.24,-9.4],black,'lcd','14 mm DuPont housing')
    # A restrained test-screen artwork is illustrative, not a firmware claim.
    im=Image.new('RGB',(1200,900),'#071c27');dr=ImageDraw.Draw(im)
    dr.rounded_rectangle((38,38,1162,862),radius=46,outline='#2a5261',width=4)
    dr.text((82,65),'HACHIMODOCK',font=font(58),fill='#8ee6d4')
    dr.text((84,145),'READY',font=font(30),fill='#6b96a2')
    dr.ellipse((410,260,790,640),fill='#193b4b',outline='#69cab6',width=7)
    dr.ellipse((500,380,524,412),fill='#ddf4e9');dr.ellipse((675,380,699,412),fill='#ddf4e9')
    dr.arc((540,400,660,510),10,170,fill='#ddf4e9',width=8)
    dr.rounded_rectangle((360,720,840,800),radius=25,fill='#77d2bb')
    dr.text((432,730),'SPI CONNECTED',font=font(35),fill='#102b35')
    im.save(OUT/'display-artwork.png')


def polydata(m):
    points=vtk.vtkPoints()
    for p in m.vertices:points.InsertNextPoint(*p)
    cells=vtk.vtkCellArray()
    for f in m.faces:
        cells.InsertNextCell(3)
        for i in f:cells.InsertCellPoint(int(i))
    data=vtk.vtkPolyData();data.SetPoints(points);data.SetPolys(cells)
    normals=vtk.vtkPolyDataNormals();normals.SetInputData(data);normals.AutoOrientNormalsOn();normals.SetFeatureAngle(55);normals.Update()
    return normals.GetOutput()


def tube(renderer,points,color,radius=.6,opacity=1):
    v=vtk.vtkPoints()
    for p in points:v.InsertNextPoint(*p)
    line=vtk.vtkPolyLine();line.GetPointIds().SetNumberOfIds(len(points))
    for i in range(len(points)):line.GetPointIds().SetId(i,i)
    cells=vtk.vtkCellArray();cells.InsertNextCell(line)
    data=vtk.vtkPolyData();data.SetPoints(v);data.SetLines(cells)
    filt=vtk.vtkTubeFilter();filt.SetInputData(data);filt.SetRadius(radius);filt.SetNumberOfSides(14);filt.CappingOn();filt.Update()
    mapper=vtk.vtkPolyDataMapper();mapper.SetInputData(filt.GetOutput());a=vtk.vtkActor();a.SetMapper(mapper)
    a.GetProperty().SetColor(*color);a.GetProperty().SetOpacity(opacity);a.GetProperty().SetSpecular(.25)
    renderer.AddActor(a)


def screen_actor(renderer,offset,opacity):
    points=vtk.vtkPoints()
    for a in [(8.6,3.9,-.585),(66.2,3.9,-.585),(66.2,47.1,-.585),(8.6,47.1,-.585)]:points.InsertNextPoint(*(world(*a)+offset))
    quad=vtk.vtkQuad()
    for i in range(4):quad.GetPointIds().SetId(i,i)
    cells=vtk.vtkCellArray();cells.InsertNextCell(quad)
    data=vtk.vtkPolyData();data.SetPoints(points);data.SetPolys(cells)
    uv=vtk.vtkFloatArray();uv.SetNumberOfComponents(2)
    for p in [(0,0),(1,0),(1,1),(0,1)]:uv.InsertNextTuple(p)
    data.GetPointData().SetTCoords(uv);mapper=vtk.vtkPolyDataMapper();mapper.SetInputData(data)
    reader=vtk.vtkPNGReader();reader.SetFileName(str(OUT/'display-artwork.png'));reader.Update()
    tex=vtk.vtkTexture();tex.SetInputConnection(reader.GetOutputPort());tex.InterpolateOn()
    a=vtk.vtkActor();a.SetMapper(mapper);a.SetTexture(tex);a.GetProperty().SetOpacity(opacity);a.GetProperty().LightingOff();renderer.AddActor(a)


def cables(renderer,offsets):
    colors=[(.045,.045,.055),(.76,.12,.10),(.92,.47,.09),(.88,.73,.12),(.11,.45,.23),(.08,.39,.62),(.39,.21,.62),(.61,.65,.65)]
    for i,(v,color) in enumerate(zip(np.linspace(16.61,34.39,8),colors)):
        screen_offset=offsets['lcd'];base_offset=offsets['pcb'];end=world(8,v,-26.4)+screen_offset
        x=27+2.54*i;start=np.array([x,-31,P['pcb_bottom_z']+1.6+11])+base_offset
        control=[start,start+[0,0,6],np.array([14+.3*i,-20,24+.1*i])+base_offset,
                 end+np.array([2,-7,-2]),end]
        # Dense piecewise cubic Bezier keeps the bundle smooth; the final bend
        # uses the actual R3 screen-exit path checked by verify_spi_r4.py.
        points=[]
        for j in range(len(control)-1):
            p0=control[max(0,j-1)];p1=control[j];p2=control[j+1];p3=control[min(len(control)-1,j+2)]
            for t in np.linspace(0,1,12,endpoint=False):
                points.append(.5*((2*p1)+(-p0+p2)*t+(2*p0-5*p1+4*p2-p3)*t*t+(-p0+3*p1-3*p2+p3)*t*t*t))
        points.append(end)
        points.append(world(5,v,-26.4)+screen_offset)
        for t in np.linspace(math.pi/2,0,25):points.append(world(5-3*math.cos(t),v,-23.4-3*math.sin(t))+screen_offset)
        tube(renderer,points,color)


def projected(renderer,p,width,height):
    renderer.SetWorldPoint(*p,1);renderer.WorldToDisplay();x,y,_=renderer.GetDisplayPoint();return x,height-y


def render(name,exploded=False):
    width,height=2100,1800
    ren=vtk.vtkRenderer();ren.SetBackground(.947,.961,.972);ren.SetUseDepthPeeling(True);ren.SetMaximumNumberOfPeels(100);ren.SetOcclusionRatio(.05)
    win=vtk.vtkRenderWindow();win.SetOffScreenRendering(1);win.SetSize(width,height);win.SetMultiSamples(0);win.SetAlphaBitPlanes(1);win.AddRenderer(ren)
    ren.SetViewport(0,100/height,1,1-180/height)
    offsets={g:np.zeros(3) for g in ['upper','lower','pcb','caps','lcd','glass']}
    if exploded:
        offsets.update(upper=np.array([105,15,100]),lower=np.array([0,0,-35]),pcb=np.array([0,0,5]),caps=np.array([0,0,25]),lcd=np.array([-10,5,38]),glass=np.array([-10,5,38]))
    for obj in OBJECTS:
        mapper=vtk.vtkPolyDataMapper();mapper.SetInputData(polydata(obj['mesh']));a=vtk.vtkActor();a.SetMapper(mapper);a.SetPosition(*offsets[obj['group']])
        p=a.GetProperty();p.SetColor(*obj['color']);p.SetInterpolationToPBR();p.SetMetallic(obj['metal']);p.SetRoughness(.33 if obj['metal'] else .48)
        if not exploded:
            if obj['group']=='upper':p.SetOpacity(.105)
            if obj['group']=='lower':p.SetOpacity(.28)
            if obj['group']=='glass':p.SetOpacity(.16)
            if obj['group']=='lcd':p.SetOpacity(.70)
        ren.AddActor(a)
    screen_actor(ren,offsets['lcd'],1 if exploded else .24)
    cables(ren,offsets)
    if exploded:
        for u in [3,78.2]:
            for v in [3,48]:tube(ren,[world(u,v,-4.8)+offsets['lcd'],world(u,v,-4.8)+offsets['upper']],(.45,.55,.62),.07,.7)
    for position,intensity in [((-120,-150,190),1.3),((140,-40,130),1.1),((30,150,190),1.1)]:
        light=vtk.vtkLight();light.SetPosition(*position);light.SetFocalPoint(35,-20,45 if exploded else 20);light.SetIntensity(intensity);ren.AddLight(light)
    cam=ren.GetActiveCamera();cam.ParallelProjectionOn();cam.SetViewUp(0,0,1)
    if exploded:
        cam.SetPosition(-140,-210,240);cam.SetFocalPoint(35,-21,74)
    else:
        cam.SetPosition(-125,-180,210);cam.SetFocalPoint(35,-24,27)
    ren.ResetCamera();cam.SetParallelScale(cam.GetParallelScale()*1.035)
    ren.ResetCameraClippingRange();win.Render()
    capture=vtk.vtkWindowToImageFilter();capture.SetInput(win);capture.ReadFrontBufferOff();capture.Update()
    path=OUT/name;writer=vtk.vtkPNGWriter();writer.SetFileName(str(path));writer.SetInputConnection(capture.GetOutputPort());writer.Write()
    im=Image.open(path).convert('RGB');dr=ImageDraw.Draw(im)
    dr.rectangle((0,0,width,185),fill='#f1f5f8')
    title='零部件爆炸装配' if exploded else '外壳半透明 · 内部装配'
    dr.text((65,32),title,font=font(48),fill='#223742')
    dr.text((67,102),'原版操作区 / 四孔内装屏幕 / 双 Type-C / SPI 杜邦接头17 mm',font=font(24),fill='#637986')
    labels=(
        [('01 上盖 · 屏幕从内侧固定',np.array([24,-8,59])+offsets['upper'],(70,230)),
         ('02 屏幕总成 · PCB 81.2 × 51 mm',world(42,25,-4.8)+offsets['lcd'],(70,470)),
         ('8P 杜邦线 · 线束走向示意',world(2,25,-18)+offsets['lcd'],(70,750)),
         ('03 原版三键 + 14 mm 球帽',np.array([42,-59,23])+offsets['caps'],(1110,890)),
         ('04 主 PCB / ESP32-S3 / 低位音频',np.array([36,-22,16])+offsets['pcb'],(70,1220)),
         ('05 下盖 · 圆柱定位与螺丝固定',np.array([37,-53,-1])+offsets['lower'],(1120,1460))]
        if exploded else
        [('屏幕：有效区57.6 × 43.2 mm',world(40,25,-.6),(70,250)),
         ('17 mm 插接总高 / 左侧 SPI',world(2,25,-16),(70,515)),
         ('开发板：保留双 Type-C',np.array([4,-14,18]),(70,1160)),
         ('功放 MAX98357A：低位安装',np.array([14,-42,9]),(1110,1120)),
         ('麦克风 INMP441：低位安装',np.array([46,-42.1,8.4]),(1110,1280)),
         ('主 PCB：实际布局和孔位',np.array([34,-55,4.3]),(1110,1450))]
    )
    for text,anchor,position in labels:
        px,py=projected(ren,anchor,width,height);tx,ty=position
        bounds=dr.textbbox((tx,ty),text,font=font(25));boxy=(bounds[1]+bounds[3])/2
        endx=bounds[2]+14 if tx<width/2 else tx-14
        dr.line([(px,py),(endx,boxy)],fill='#748e9a',width=2)
        dr.ellipse((px-5,py-5,px+5,py+5),fill='#188c8b')
        dr.rounded_rectangle((bounds[0]-12,bounds[1]-8,bounds[2]+12,bounds[3]+8),radius=8,fill='#f1f5f8')
        dr.text((tx,ty),text,font=font(25),fill='#25434f')
    dr.rectangle((0,height-105,width,height),fill='#f1f5f8')
    dr.text((65,height-72),'基于实际外壳与PCB坐标渲染；模块外观、焊后高度及线束走向为示意，需实物试装。',font=font(23),fill='#657d88')
    im.save(path);win.Finalize();print(path,flush=True)


def main():
    populate();render('internal-assembly.png');render('exploded-assembly.png',True)
    a=Image.open(OUT/'internal-assembly.png');b=Image.open(OUT/'exploded-assembly.png')
    sheet=Image.new('RGB',(3000,1410),'#f1f5f8');dr=ImageDraw.Draw(sheet)
    dr.text((55,24),'HachimoDock · 修正版零部件装配效果',font=font(44),fill='#223742')
    dr.text((58,88),'包含屏幕、17 mm 杜邦接头与排线、主 PCB、开发板、功放和麦克风',font=font(25),fill='#637986')
    sheet.paste(a.resize((1500,1286),Image.Resampling.LANCZOS),(0,124))
    sheet.paste(b.resize((1500,1286),Image.Resampling.LANCZOS),(1500,124))
    sheet.save(OUT/'assembly-overview.png')
    assumptions={'method':'VTK rendering of actual enclosure STL and carrier outline/holes/pads',
        'source_enclosure_hashes':{n:hashlib.sha256((OUT.parent/f'a4-{n}-r4-assembly.stl').read_bytes()).hexdigest() for n in ['upper','lower']},
        'pcb_design_sha256':hashlib.sha256((ROOT/'../s3-carrier/output/design.json').read_bytes()).hexdigest(),
        'screen_pcb_mm':[81.2,51,1.6],'screen_active_mm':[57.6,43.2],
        'dupont_housing_length_mm':14,'dupont_installed_height_mm':17,
        'schematic':['module electronics and USB exterior','wire routing and wire lengths in exploded view','display artwork','module Z stack remains a design assumption'],
        'does_not_establish_physical_fit':True}
    (OUT/'render-assumptions.json').write_text(json.dumps(assumptions,indent=2),encoding='utf-8')


if __name__=='__main__':main()
