"""Geometric acceptance checks for the actual exported upper and lower solids."""
import json
import sys
from pathlib import Path
import numpy as np
import trimesh
import manifold3d as mf

ROOT=Path(__file__).resolve().parents[1]
D=json.loads((ROOT/'../s3-carrier/output/design.json').read_text(encoding='utf-8'))
HOLES={h['ref']:h for h in D['mountingHoles']}
def solid(path):
    m=trimesh.load_mesh(path)
    return mf.Manifold(mf.Mesh(np.asarray(m.vertices,dtype=np.float32),np.asarray(m.faces,dtype=np.uint32)))
def cylinder(h,r,z0,z1):
    return mf.Manifold.cylinder(z1-z0,r,circular_segments=96).translate([h['x'],-h['y'],z0])
def checks(upper,lower):
    result={}
    for ref in ['H3','H4']:
        h=HOLES[ref]
        # A complete ring must exist on the FRONT, not just behind the PCB.
        bearing=cylinder(h,3.05,4.35,5.50)-cylinder(h,1.95,4.34,5.51)
        shaft=cylinder(h,1.55,4.40,8.65)
        through=cylinder(h,1.20,-2.40,4.40)
        head=cylinder(h,2.7,-2.25,.65)
        seat=cylinder(h,2.65,.75,1.10)-cylinder(h,1.45,.74,1.11)
        result[ref]={'front_bearing_fraction':(upper^bearing).volume()/bearing.volume(),
                     'front_pilot_obstruction_mm3':(upper^shaft).volume(),
                     'rear_screw_route_obstruction_mm3':(lower^through).volume(),
                     'rear_head_route_obstruction_mm3':(lower^head).volume(),
                     'rear_head_seat_fraction':(lower^seat).volume()/seat.volume()}
    h=HOLES['H1']
    locator=cylinder(h,1.20,2.80,3.40)
    result['H1_locator_fraction']=(lower^locator).volume()/locator.volume()
    for ref in ['H3','H4']:
        row=result[ref]
        assert row['front_bearing_fraction']>.985,(ref,'missing front round support',row)
        assert row['front_pilot_obstruction_mm3']<.02,(ref,'blocked front pilot',row)
        assert row['rear_screw_route_obstruction_mm3']<.02,(ref,'blocked rear screw route',row)
        assert row['rear_head_route_obstruction_mm3']<.02,(ref,'blocked head recess',row)
        assert row['rear_head_seat_fraction']>.985,(ref,'missing screw head seat',row)
    assert result['H1_locator_fraction']>.985,result
    return result
if __name__=='__main__':
    folder=Path(sys.argv[1])
    upper=solid(next(folder.glob('a4-upper-*-assembly.stl')))
    lower=solid(next(folder.glob('a4-lower-*-assembly.stl')))
    print(json.dumps(checks(upper,lower),indent=2))
