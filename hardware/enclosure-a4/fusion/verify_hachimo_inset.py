"""Verify the actual engraved mesh, its floor thickness and bounded changes."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import trimesh
import manifold3d as mf

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from build_enclosure import solid,mesh,D,P,pcb_box,cyl,board
from verify_fixings import checks as fixing_checks

OUT=ROOT/'output/r4-original-copy/hachimo-inset'


def main():
    path=OUT/'a4-upper-hachimo-inset.stl'
    assert path.exists(),'Engraved upper STL has not been generated yet'
    w=json.loads((OUT/'working-hachimo.json').read_text(encoding='utf-8'))
    spec=w['lettering'];origin=np.array(w['screen_origin_mm']);q=2**-.5
    def place(s):return s.rotate([45,0,0]).translate(origin.tolist())
    m=trimesh.load_mesh(path)
    assert m.is_watertight and m.is_winding_consistent and len(m.split())==1
    m.apply_translation(w['export']['assembly_minimum_mm'])
    new=solid(m);baseline=solid(trimesh.load_mesh(OUT/'baseline-upper-assembly.stl'))
    data=json.loads((ROOT/'output/r4-original-copy/lettering-preview/lettering-options.json').read_text())['joystick']
    sections=[mf.CrossSection(c,mf.FillRule.NonZero) for c in data['components']]
    word=mf.CrossSection.batch_boolean(sections,mf.OpType.Add).translate(spec['offset_uv_mm'])
    empty=place(mf.Manifold.extrude(word,.3).translate([0,0,-.4]))
    floor=place(mf.Manifold.extrude(word,1.25).translate([0,0,-1.78]))
    face_before=(empty^baseline).volume()/empty.volume()
    face_after=(empty^new).volume()
    floor_after=(floor^new).volume()/floor.volume()
    assert face_before>.995,face_before
    assert face_after<.025,face_after
    assert floor_after>.995,floor_after
    region=place(mf.Manifold.cube([37.8,10.35,2.05]).translate([18.5,-10.75,-1.95]))
    extra_outside=((new-baseline)-region).volume()
    removed_outside=((baseline-new)-region).volume()
    assert extra_outside<.25 and removed_outside<.25,(extra_outside,removed_outside)
    assert np.max(np.abs(np.array(w['bodies'][0]['bounds_mm'])-m.bounds))<.02
    assert abs((np.mean(word.bounds()[::2])+origin[0])-36.12495)<1e-5
    lower_path=ROOT/'output/r4-original-copy/a4-lower-r4-spi17-fixed.stl'
    assert hashlib.sha256(lower_path.read_bytes()).hexdigest()==w['lower_sha256']
    lm=trimesh.load_mesh(lower_path);lm.apply_translation(w['lower_assembly_minimum_mm'])
    lower=solid(lm);fixings=fixing_checks(new,lower)
    added_joint_overlap=((new^lower)-(baseline^lower)).volume()
    assert added_joint_overlap<.025,added_joint_overlap
    overlaps={}
    hardware={'carrier':board(),
        'lcd_pcb':place(mf.Manifold.cube([81.2,51,1.6]).translate([0,0,-6.4]))}
    for ref in ['U1','U2','U3']:
        part=next(c for c in D['components'] if c['ref']==ref)
        z=P['pcb_bottom_z']+P['module_board_bottom_by_ref'][ref]
        hardware[ref]=cyl(46,42.1,7,z,z+5.1) if ref=='U3' else pcb_box(part['envelope'],z,z+5.1)
    j=next(c for c in D['connectorMatingEnvelopes'] if c['ref']=='J1')['envelope']
    hardware['J1']=pcb_box(j,P['pcb_bottom_z']+1.6,P['pcb_bottom_z']+12.6)
    for name,part in hardware.items():
        overlaps[name]=(part^new).volume();assert overlaps[name]<.025,(name,overlaps[name])
    report={'status':'engraved-engineering-trial','text':'Hachimo','style':'C joystick wordmark',
        'units':'mm','watertight':True,'connected_solids':1,'recess_depth_mm':spec['recess_depth_mm'],
        'word_bounds_uv_mm':list(word.bounds()),'center_world_x_mm':36.12495,
        'original_face_occupancy_fraction':face_before,'groove_obstruction_mm3':face_after,
        'remaining_floor_1p25mm_fraction':floor_after,'target_floor_thickness_mm':1.3,
        'extra_material_outside_lettering_region_mm3':extra_outside,
        'removed_material_outside_lettering_region_mm3':removed_outside,
        'pcb_fixings':fixings,'hardware_overlaps_mm3':overlaps,
        'added_upper_lower_interference_mm3':added_joint_overlap,'file':path.name,'bytes':path.stat().st_size,
        'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'physical_fit_verified':False}
    (OUT/'engraving-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
