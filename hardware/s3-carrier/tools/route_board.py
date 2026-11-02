"""Bounded two-layer routing of this carrier. Native KiCad DRC is mandatory.

Raster search only proposes tracks: it never approves fabrication or suppresses
DRC errors. The exported design remains an engineering draft after routing.
"""
import argparse
import heapq
import itertools
import json
import math
from pathlib import Path

import numpy as np
from shapely.geometry import Polygon
from shapely import contains_xy

from build_design import ROOT, STEM, arc_mid, kicad

GRID=.20
MAX_VISITS=350000


def outline_polygon(edges):
    todo=list(edges);edge=todo.pop(0);points=[];current=edge['start']
    while True:
        a,b=edge['start'],edge['end'];angle=edge['angle']
        if math.dist(current,a)>.002:a,b=b,a;angle=-angle
        points.append(a)
        if angle:
            t=math.radians(angle);sx,sy=a;ex,ey=b
            cx=(sx+ex)/2-(ey-sy)/(2*math.tan(t/2))
            cy=(sy+ey)/2+(ex-sx)/(2*math.tan(t/2))
            for f in np.linspace(0,1,32)[1:]:
                points.append((cx+(sx-cx)*math.cos(t*f)-(sy-cy)*math.sin(t*f),
                               cy+(sx-cx)*math.sin(t*f)+(sy-cy)*math.cos(t*f)))
        current=b
        if not todo:break
        match=next(i for i,e in enumerate(todo)
                   if min(math.dist(current,e['start']),math.dist(current,e['end']))<.002)
        edge=todo.pop(match)
    # The export has sub-micron endpoint rounding differences. Snap only the
    # routing raster boundary; the native board keeps the exact source arcs.
    clean=[]
    for point in points:
        point=tuple(round(value,4) for value in point)
        if not clean or clean[-1]!=point:clean.append(point)
    result=Polygon(clean)
    if not result.is_valid:raise ValueError('Invalid imported outline')
    return result


class Router:
    def __init__(self,design):
        self.design=design
        self.poly=outline_polygon(design['outline'])
        self.nx=math.ceil(self.poly.bounds[2]/GRID)+2
        self.ny=math.ceil(self.poly.bounds[3]/GRID)+2
        self.yy,self.xx=np.mgrid[:self.ny,:self.nx]*GRID
        inside=contains_xy(self.poly.buffer(-.65),self.xx,self.yy)
        self.base=np.where(inside,0,-1).astype(np.int16)
        x1,y1,x2,y2=design['antennaKeepout']
        self.base[(self.xx>=x1)&(self.xx<=x2)&(self.yy>=y1)&(self.yy<=y2)]=-1
        self.pads=[dict(p,ref=c['ref'],mount=c.get('mount','through_hole')) for c in design['components'] for p in c['pads']]
        self.nets={name:i+1 for i,name in enumerate(sorted({p['net'] for p in self.pads if p['net']}))}
        self.pad_masks=[];self.via_pad_masks=[]
        for p in self.pads:
            radius=max(p['width'],p['height'])/2
            if p['shape']=='rect':radius*=math.sqrt(2)
            distance=(self.xx-p['x'])**2+(self.yy-p['y'])**2
            self.pad_masks.append((distance<(radius+.34)**2,self.nets.get(p['net'],-1),p['mount']))
            self.via_pad_masks.append((distance<(radius+.56)**2,self.nets.get(p['net'],-1),p['mount']))
        for h in design['mountingHoles']+[h for c in design['components'] for h in c['holes']]:
            # 0.25mm hole clearance + 0.25mm half-width of a power trace,
            # plus raster margin. Copper clearance alone is insufficient.
            self.base[(self.xx-h['x'])**2+(self.yy-h['y'])**2 < (h['diameter']/2+.60)**2]=-1
        for h in design.get('fastenerEnvelopes',[]):
            self.base[(self.xx-h['x'])**2+(self.yy-h['y'])**2 < (h['copperKeepoutRadiusMm']+.40)**2]=-1
        self.dynamic=np.zeros((2,self.ny,self.nx),dtype=np.int16)
        self.via_dynamic=np.zeros_like(self.dynamic)

    def node(self,p):return int(round(p['x']/GRID)),int(round(p['y']/GRID))

    def mask(self,net,via=False,wide=False):
        mask=np.broadcast_to(self.base<0,(2,self.ny,self.nx)).copy()
        for region,owner,mount in self.via_pad_masks if (via or wide) else self.pad_masks:
            if owner!=net or (via and mount=='smd'):
                mask[0,region]=True
                if via or mount!='smd':mask[1,region]=True
        occupied=self.via_dynamic if (via or wide) else self.dynamic
        mask|=(occupied!=0)&(occupied!=net)
        return mask

    def paint(self,a,b,owner,layer,radius=.46,via_radius=.69):
        ax,ay=a;bx,by=b;dx=bx-ax;dy=by-ay
        scale=dx*dx+dy*dy
        t=np.clip(((self.xx-ax)*dx+(self.yy-ay)*dy)/scale,0,1) if scale else 0
        dist=(self.xx-(ax+t*dx))**2+(self.yy-(ay+t*dy))**2
        for target,r in [(self.dynamic,radius),(self.via_dynamic,via_radius)]:
            region=dist<r*r
            # Never erase another net's exclusion region.
            target[layer,region&(target[layer]==0)]=owner

    def search(self,start,end,net,companion=None):
        sx,sy=self.node(start);gx,gy=self.node(end)
        power=start['net'] in ['GND','+3V3','+5V'] and start['mount']!='smd' and end['mount']!='smd'
        blocked=self.mask(net,wide=power);via_blocked=self.mask(net,True)
        if companion:
            # Parallel LCD CLK/MOSI escapes occupy opposite fixed layers.
            # Plan them together so routing either first cannot block the
            # other's connector approach. Neither path uses a via.
            mate,offset=companion;other=self.mask(mate)
            blocked[:,:,:-offset] |= other[::-1,:,offset:]
            blocked[:,:,-offset:]=True
            via_blocked[:]=True
        if start['mount']=='smd':blocked[1,sy,sx]=True
        for x,y in [(sx,sy),(gx,gy)]:
            if blocked[:,y,x].all():raise ValueError(f'Pad endpoint obstructed: {start} -> {end}')
        goals={(gx,gy,0)} if end['mount']=='smd' else {(gx,gy,0),(gx,gy,1)}
        heap=[];best={};previous={};count=itertools.count()
        for layer in [0,1]:
            state=(sx,sy,layer)
            if blocked[layer,sy,sx]:continue
            best[state]=0;heapq.heappush(heap,(math.hypot(gx-sx,gy-sy),next(count),state))
        steps=[(1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,-1),(1,-1),(-1,1)]
        visited=0
        while heap:
            _,_,here=heapq.heappop(heap);x,y,layer=here;score=best[here]
            if here in goals:
                path=[here]
                while here in previous:here=previous[here];path.append(here)
                return path[::-1]
            visited+=1
            if visited>MAX_VISITS:break
            for dx,dy in steps:
                nx,ny=x+dx,y+dy
                if not (0<=nx<self.nx and 0<=ny<self.ny) or blocked[layer,ny,nx]:continue
                # Avoid corner cutting across a hole or another track.
                if dx and dy and (blocked[layer,y,nx] or blocked[layer,ny,x]):continue
                weight=math.hypot(dx,dy)+(.08 if (layer==0 and dy) or (layer==1 and dx) else 0)
                nxt=(nx,ny,layer);new=score+weight
                if new<best.get(nxt,float('inf')):
                    best[nxt]=new;previous[nxt]=here
                    heapq.heappush(heap,(new+math.hypot(gx-nx,gy-ny),next(count),nxt))
            if not via_blocked[:,y,x].any():
                nxt=(x,y,1-layer);new=score+16
                if new<best.get(nxt,float('inf')):
                    best[nxt]=new;previous[nxt]=here
                    heapq.heappush(heap,(new+math.hypot(gx-x,gy-y),next(count),nxt))
        raise RuntimeError(f'Unable to route net {start["net"]} from {start["x"],start["y"]} to {end["x"],end["y"]}')

    def add_path(self,path,start,end,name):
        owner=self.nets[name];layer=path[0][2];points=[(start['x'],start['y'])]
        width=.5 if name in ['GND','+3V3','+5V'] and start['mount']!='smd' and end['mount']!='smd' else .25
        def flush():
            if len(points)<2:return
            simplified=[points[0]]
            for i,p in enumerate(points[1:-1],1):
                a=simplified[-1];b=points[i+1]
                if abs((p[0]-a[0])*(b[1]-p[1])-(p[1]-a[1])*(b[0]-p[0]))>1e-7:simplified.append(p)
            simplified.append(points[-1])
            for a,b in zip(simplified,simplified[1:]):
                self.paint(a,b,owner,layer,.59 if width==.5 else .46,.82 if width==.5 else .69)
            self.design['traces'].append({'net':name,'layer':['F.Cu','B.Cu'][layer],'points':simplified,'width':width})
        for x,y,z in path:
            point=(round(x*GRID,6),round(y*GRID,6))
            if z!=layer:
                points.append(point);flush()
                self.design['vias'].append({'net':name,'x':point[0],'y':point[1]})
                for side in [0,1]:self.paint(point,point,owner,side,.70,.92)
                layer=z;points=[point]
            else:points.append(point)
        points.append((end['x'],end['y']));flush()

    def run(self):
        # Reserve the dense small-device ground escapes before signal tracks
        # can enclose them; long routes can use the other copper layer.
        lcd_order={'GPIO21':0,'GPIO47':1,'GPIO45':2,'GPIO40':3,'GPIO41':4,'GPIO42':5}
        # Reserve the paired, via-free LCD escape before wider supply routes
        # occupy the short corridor between devkit sockets and LCD header.
        names=sorted(self.nets,key=lambda n:(0 if n in ['GPIO21','GPIO47'] else
                                            1 if n=='GND' else 2 if n=='+3V3' else
                                            3 if n in lcd_order else 4,lcd_order.get(n,0),n))
        for name in names:
            if name=='GPIO47':continue  # Planned with CLK below.
            pads=[p for p in self.pads if p['net']==name]
            if len(pads)<2:continue
            if name=='GPIO21':
                start=next(p for p in pads if p['ref']=='U1');end=next(p for p in pads if p['ref']=='J1')
                mates=[p for p in self.pads if p['net']=='GPIO47']
                a=next(p for p in mates if p['ref']=='U1');b=next(p for p in mates if p['ref']=='J1')
                offset=round((a['x']-start['x'])/GRID)
                path=self.search(start,end,self.nets[name],(self.nets['GPIO47'],offset))
                self.add_path(path,start,end,name)
                self.add_path([(x+offset,y,1-z) for x,y,z in path],a,b,'GPIO47')
                print('Routed GPIO21 / GPIO47 as opposite-layer LCD pair',flush=True)
                continue
            # Give the amplifier its own feed/return directly to a devkit
            # supply pad instead of daisy-chaining through LCD/microphone.
            amplifier=next((p for p in pads if p['ref']=='U2' and
                            p['number']==('2' if name=='GND' else '1')),None) if name in ['GND','+3V3'] else None
            if amplifier:
                roots=[p for p in pads if p['ref']=='U1']
                root=min(roots,key=lambda p:math.dist((p['x'],p['y']),(amplifier['x'],amplifier['y'])))
                self.add_path(self.search(root,amplifier,self.nets[name]),root,amplifier,name)
                pads.remove(amplifier)
                if name=='+3V3':
                    enable=next(p for p in pads if p['ref']=='U2' and p['number']=='3')
                    self.add_path(self.search(amplifier,enable,self.nets[name]),amplifier,enable,name)
                    pads.remove(enable)
                pads.remove(root);connected=[root]
            else:connected=[pads.pop(0)]
            while pads:
                a,b=min(((a,b) for a in connected for b in pads),
                        key=lambda pair:math.dist((pair[0]['x'],pair[0]['y']),(pair[1]['x'],pair[1]['y'])))
                path=self.search(a,b,self.nets[name]);self.add_path(path,a,b,name)
                connected.append(b);pads.remove(b)
            print(f'Routed {name}: {len(connected)} pads',flush=True)
        return self.design


def main():
    p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,default=ROOT/'output');args=p.parse_args()
    path=args.directory/'design.json';design=json.loads(path.read_text())
    design['traces']=[];design['vias']=[]
    Router(design).run()
    unique=[]
    for via in design['vias']:
        match=next((v for v in unique if v['net']==via['net'] and
                    math.dist((v['x'],v['y']),(via['x'],via['y']))<.65),None)
        if match:
            if (via['x'],via['y'])!=(match['x'],match['y']):
                for layer in ['F.Cu','B.Cu']:
                    design['traces'].append({'net':via['net'],'layer':layer,'width':.25,
                        'points':[(via['x'],via['y']),(match['x'],match['y'])]})
        else:unique.append(via)
    design['vias']=unique
    add_ground_stitches(design)
    path.write_text(json.dumps(design,indent=2)+'\n')
    kicad(design,args.directory/f'{STEM}.kicad_pcb')


def add_ground_stitches(design):
    for via in design.get('groundStitches',[]):
        design['vias'].append({'x':via['x'],'y':via['y'],'net':'GND'})
        pad=next(p for c in design['components'] if c['ref']==via['padRef']
                 for p in c['pads'] if p['number']==via['padNumber'])
        design['traces'].append({'net':'GND','layer':'B.Cu','width':.5,
            'points':[(pad['x'],pad['y']),(via['x'],via['y'])]})


if __name__=='__main__':main()
