"""Fit study keeping the original external surface, not a new outer bezel."""
import sys,json,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import trimesh
import manifold3d as mf
from build_enclosure import solid,mesh,pcb_box,cyl,D,P
from explore_geometry import load,heights,ROOT
q=math.sqrt(.5)
O=np.array([-4.47505,-39,21.153])
def box(a,b):return mf.Manifold.cube(np.subtract(b,a).tolist()).translate(a)
def at_screen(s,shift):return s.rotate([45,0,0]).translate((O+[0,q*shift,q*shift]).tolist())
modules={}
for ref in ['U1','U2','U3']:
    c=next(v for v in D['components'] if v['ref']==ref)
    z=P['pcb_bottom_z']+P['module_board_bottom_by_ref'][ref]
    modules[ref]=cyl(46,42.1,7,z,z+5.1) if ref=='U3' else pcb_box(c['envelope'],z,z+5.1)
j=next(v for v in D['connectorMatingEnvelopes'] if v['ref']=='J1')['envelope']
connector=pcb_box(j,P['pcb_bottom_z']+1.6,P['pcb_bottom_z']+1.6+11)
rows=[]
for shift in [0,1,2,3]:
    lcd=at_screen(box([0,0,-6.6],[81.2,51,-5]),shift)
    spi=at_screen(box([.2,14.3,-22.6],[3.8,36.7,-6.5]),shift)
    inv=np.eye(4);inv[:3,:3]=[[1,0,0],[0,q,q],[0,-q,q]];inv[:3,3]=-inv[:3,:3]@(O+[0,q*shift,q*shift])
    original=load(0);original.apply_transform(inv)
    row={'shift_mm':shift,'lcd_module_gap':{r:lcd.min_gap(v,20) for r,v in modules.items()},'lcd_j1_gap':lcd.min_gap(connector,20),'spi_u1_gap':spi.min_gap(modules['U1'],20),'spi_u1_overlap':(spi^modules['U1']).volume(),'hole_wall_intersections_N':{f'{u},{v}':heights(original,u,-v) for u in [3,78.2] for v in [3,48]}}
    rows.append(row)
(ROOT/'fusion/original-fit-study.json').write_text(json.dumps(rows,indent=2))
print(json.dumps(rows,indent=2))
