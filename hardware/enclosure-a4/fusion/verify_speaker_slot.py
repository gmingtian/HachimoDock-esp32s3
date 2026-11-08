"""Read back the real speaker-slot STL and check speaker/port/vent clearances."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import trimesh
import manifold3d as mf

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from build_enclosure import solid,pcb_box,cyl,D,P
from verify_fixings import checks as fixing_checks

OUT=ROOT/'output/r4-original-copy/speaker-slot'


def box(a,b):return mf.Manifold.cube((np.array(b)-a).tolist()).translate(a)


def main():
    w=json.loads((OUT/'working-speaker.json').read_text());s=w['speaker_mount']
    path=OUT/w.get('export',{}).get('file','a4-lower-speaker-slot.stl')
    assert path.exists(),'Speaker slot STL has not been generated yet'
    baseline=solid(trimesh.load_mesh(w.get('speaker_baseline_lower_assembly',OUT/'baseline-lower-assembly.stl')))
    m=trimesh.load_mesh(path)
    assert m.is_watertight and m.is_winding_consistent and len(m.split())==1
    m.apply_translation(w['export']['assembly_minimum_mm']);lower=solid(m)
    upper=solid(trimesh.load_mesh(OUT/'upper-assembly.stl'))
    cx,cz=s['center_xz_mm'];y=s['rear_inner_y_mm'];front=y-4.6
    speaker=box([cx-10,y-4.35,cz-5.5],[cx+10,y,cz+5.5])
    cavity=box([cx-10.15,front+.04,cz-5.65],[cx+10.15,y-.04,cz+5.65])
    port=box([cx+10.25,front+.05,cz+.05],[cx+11.65,y-.05,cz+3.95])
    overlap={'speaker_to_lower':(speaker^lower).volume(),'speaker_to_upper':(speaker^upper).volume(),
             'cavity_obstruction':(cavity^lower).volume(),'wire_port_obstruction':(port^lower).volume(),
             'added_case_interference':((lower^upper)-(baseline^upper)).volume()}
    assert all(v<.025 for v in overlap.values()),overlap
    # Check actual solid strips, including both borders of the right-side port.
    wall_specs={
        'left':([cx-11.65,front+.2,cz-5.6],[cx-10.25,y-.2,cz+5.6]),
        'right_bottom':([cx+10.25,front+.2,cz-5.6],[cx+11.65,y-.2,cz-.1]),
        'right_top':([cx+10.25,front+.2,cz+4.1],[cx+11.65,y-.2,cz+5.6]),
        'bottom':([cx-10.1,front+.2,cz-7.15],[cx+10.1,y-.2,cz-5.75]),
        'top':([cx-10.1,front+.2,cz+5.75],[cx+10.1,y-.2,cz+7.15])}
    walls={}
    for name,(a,b) in wall_specs.items():
        p=box(a,b);walls[name]=(p^lower).volume()/p.volume();assert walls[name]>.995,(name,walls[name])
    # Adjacent air checks establish the 1.5 mm wall boundaries at the open face.
    outside=box([cx-12,front+.1,cz-4],[cx-11.75,front+1.1,cz+4])
    assert (outside^lower).volume()<.02
    vents=[]
    for x,z,r in w['rear_vent_bores_mm']:
        bore=mf.Manifold.cylinder(7.5,.54,circular_segments=32).rotate([90,0,0]).translate([x,y+2.6,z])
        vents.append((bore^lower).volume())
    assert len(vents)==54 and max(vents)<.025,vents
    O=np.array(w['screen_origin_mm'])
    def screen(a):return a.rotate([45,0,0]).translate(O.tolist())
    lcd=screen(mf.Manifold.cube([81.2,51,1.6]).translate([0,0,-6.4]))
    spi=screen(mf.Manifold.cube([3.6,22.4,17.1]).translate([.2,14.3,-23.4]))
    region=box([cx-11.8,front-.1,cz-7.3],[cx+11.8,y+.3,cz+7.3])
    added=lower-baseline;removed=baseline-lower
    assert (added-region).volume()<.25 and (removed-region).volume()<.25
    gaps={'speaker_to_lcd':speaker.min_gap(lcd,30),'mount_to_lcd':(added^region).min_gap(lcd,30),
          'speaker_to_spi':speaker.min_gap(spi,100)}
    assert min(gaps.values())>1,gaps
    report={'units':'mm','status':'speaker-slot-engineering-trial','physical_fit_verified':False,
        'wall_mm':1.5,'speaker_mm':[20,11,4.35],'cavity_mm':[20.4,11.4,4.605],
        'right_upper_wire_port_mm':4,'center_xz_mm':[cx,cz],
        'grid_right_shift_mm':s['grid_right_shift_mm'],'overlaps_mm3':overlap,'wall_filled_fractions':walls,
        'vent_count':54,'max_vent_obstruction_mm3':max(vents),'gaps_mm':gaps,
        'pcb_fixings':fixing_checks(upper,lower),'added_volume_mm3':added.volume(),
        'removed_volume_mm3':removed.volume(),'file':path.name,'bytes':path.stat().st_size,
        'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'closed_single_solid':True}
    (OUT/'speaker-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
