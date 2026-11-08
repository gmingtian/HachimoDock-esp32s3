"""Ray-test every active-area edge through the exported flared window."""
import json,math
from pathlib import Path
import numpy as np
import trimesh
import vtk
from check_side_holes import locator

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'output/r3-original'
w=json.loads((ROOT/'fusion/working-r3.json').read_text(encoding='utf-8'))
a=math.radians(w['screen_angle_deg']);c,s=math.cos(a),math.sin(a)
rotation=np.array([[1,0,0],[0,c,-s],[0,s,c]]);origin=np.array(w['screen_origin_mm'])
mesh=trimesh.load_mesh(OUT/'a4-upper-r3-assembly.stl');loc=locator(mesh)
points=[]
for u in np.linspace(8.6,66.2,117):points.extend([(u,3.9),(u,47.1)])
for v in np.linspace(3.9,47.1,89):points.extend([(8.6,v),(66.2,v)])
bad=[];rays=0
for u,v in points:
    start=origin+rotation@np.array([u,v,-.599])
    for tilt in [0,15,30,45]:
        for az in range(0,360,30):
            t,p=math.radians(tilt),math.radians(az)
            direction=rotation@np.array([math.sin(t)*math.cos(p),math.sin(t)*math.sin(p),math.cos(t)])
            end=start+5*direction
            hit_t=vtk.reference(0.);sub=vtk.reference(0);cell=vtk.reference(0);hit=[0.,0.,0.];coords=[0.,0.,0.]
            blocked=loc.IntersectWithLine(start.tolist(),end.tolist(),1e-7,hit_t,hit,coords,sub,cell)
            rays+=1
            if blocked:bad.append(dict(u=float(u),v=float(v),tilt_deg=tilt,azimuth_deg=az,hit=hit))
result={'active_area_mm':[57.6,43.2],'glass_recess_mm':.6,'edge_points':len(points),'rays':rays,'view_half_angle_deg':45,'blocked_rays':len(bad),'samples':bad[:20],'physical_view_verified':False}
(OUT/'screen-view-verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2));assert not bad
